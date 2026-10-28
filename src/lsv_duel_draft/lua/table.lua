-- Table adapter: wires DraftCore to Tabletop Simulator objects, hands and UI.
-- The builder concatenates draft_core.lua + this file into the save's Global script.

COLORS = { "White", "Red" }
CUBE_GUID = "c00001"
HAND_GUIDS = { White = "a00001", Red = "a00002" }
FOG_GUIDS = { White = "b00001", Red = "b00002" }

PICK_COLS = 12
PICK_ROWS = 4
DISCARD_X = 6
CUBE_X = -6
LOCK_DELAY = 1.2

local draft = nil       -- DraftCore instance
local cube = nil        -- the face-down cube deck
local discardGuid = nil -- face-up discard pile (a deck once 2+ cards land)
local L = nil           -- computed layout

-- ---------------------------------------------------------------- helpers

local function say(color, msg)
  if Player[color] and Player[color].seated then
    broadcastToColor(msg, color, { 1, 0.6, 0.4 })
  else
    printToAll("[" .. color .. "] " .. msg, { 1, 0.6, 0.4 })
  end
end

local function handTransform(color)
  return Player[color].getHandTransform()
end

-- Yaw that makes a face-up card read upright for a seat.
local function seatYaw(color)
  local t = handTransform(color)
  if t and t.rotation then return (t.rotation.y + 180) % 360 end
  if color == COLORS[1] then return 180 end
  return 0
end

local function sideSign(color)
  if color == COLORS[1] then return -1 end
  return 1
end

local function inList(list, value)
  for _, v in ipairs(list) do
    if v == value then return true end
  end
  return false
end

local function isInHand(color, obj)
  for _, o in ipairs(Player[color].getHandObjects()) do
    if o == obj then return true end
  end
  return false
end

-- ---------------------------------------------------------------- layout

local function boundsSize(obj)
  if obj == nil then return nil end
  local ok, b = pcall(function() return obj.getBounds() end)
  if ok and b and b.size then return b.size end
  return nil
end

-- Sizes everything from the real card and table dimensions so the layout
-- fits whatever table this save ends up on.
function computeLayout()
  local w, h = 2.2, 3.1
  local size = boundsSize(cube)
  if size and size.x > 0.5 and size.z > 0.5 then w, h = size.x, size.z end

  local tableHalfW, tableHalfD = 40, 26
  local ok, tbl = pcall(function() return Tables.getTableObject() end)
  local tsize = ok and boundsSize(tbl) or nil
  if tsize then tableHalfW, tableHalfD = tsize.x / 2 - 0.5, tsize.z / 2 - 0.5 end

  local tableY = 1
  if cube then tableY = cube.getPosition().y end

  local s, rowStart, outer, halfW = 1, 0, 0, 0
  while true do
    rowStart = h / 2 + 0.8 + s * h / 2
    outer = rowStart + (PICK_ROWS - 1) * h * 1.06 * s + s * h / 2
    halfW = PICK_COLS * w * 1.08 * s / 2
    if (outer <= tableHalfD and halfW <= tableHalfW) or s <= 0.5 then break end
    s = s - 0.05
  end

  L = {
    s = s, w = w, h = h, tableY = tableY,
    dx = w * 1.08 * s, dz = h * 1.06 * s,
    rowStart = rowStart, outer = outer, halfW = halfW,
    handZ = outer + 2.5,
  }
end

-- Moves hand zones and hidden zones to match the computed layout.
function placeZones()
  for _, color in ipairs(COLORS) do
    local sign = sideSign(color)
    local hand = getObjectFromGUID(HAND_GUIDS[color])
    if hand then
      local p = hand.getPosition()
      hand.setPosition({ x = 0, y = p.y, z = sign * L.handZ })
    end
    local fog = getObjectFromGUID(FOG_GUIDS[color])
    if fog then
      local inner = L.h / 2 + 0.4
      local outerEdge = L.handZ - 1.5
      fog.setPosition({ x = 0, y = L.tableY + 3, z = sign * (inner + outerEdge) / 2 })
      fog.setScale({ x = L.halfW * 2 + 2, y = 8, z = outerEdge - inner })
    end
  end
end

function slotPosition(color, slot)
  local i = slot - 1
  local col = i % PICK_COLS
  local row = math.floor(i / PICK_COLS)
  local sign = sideSign(color)
  local x = (col - (PICK_COLS - 1) / 2) * L.dx * -sign
  local z = sign * (L.rowStart + row * L.dz)
  return { x = x, y = L.tableY + 0.6, z = z }
end

function inPickArea(color, pos)
  local sign = sideSign(color)
  local z = pos.z * sign
  return z >= L.h / 2 + 0.4 and z <= L.handZ and math.abs(pos.x) <= L.halfW + 1
end

-- ---------------------------------------------------------------- UI

function updateUI()
  local text = "Loading..."
  if draft then text = draft:status() end
  UI.setValue("statusText", text)
  local started = draft and draft.started
  UI.setAttribute("startButton", "active", started and "false" or "true")
  local picker = draft and draft:picker() or nil
  for _, color in ipairs(COLORS) do
    UI.setAttribute("prompt_" .. color, "active", (picker == color) and "true" or "false")
  end
end

-- ---------------------------------------------------------------- actions

local function attachMenu(card)
  card.clearContextMenu()
  card.addContextMenuItem("Draft this card", function(playerColor)
    tryPick(playerColor, card)
  end)
end

-- Cards go straight into the hand face-up (no flight across the table): a hand
-- shows its cards' faces only to its owner, but keeps a face-down card face-down.
local function dealTo(color, count)
  local t = handTransform(color)
  local yaw = seatYaw(color)
  for i = 1, count do
    local card = cube.takeObject({
      position = { x = t.position.x, y = t.position.y + 0.5 + i * 0.2, z = t.position.z },
      rotation = { x = 0, y = yaw, z = 0 },
      smooth = false,
    })
    if card then
      draft:addToPack(card.getGUID())
      attachMenu(card)
    end
  end
end

local function passPack(to, ids)
  local t = handTransform(to)
  local yaw = seatYaw(to)
  for i, id in ipairs(ids) do
    local card = getObjectFromGUID(id)
    if card then
      card.setRotation({ x = 0, y = yaw, z = 0 })
      card.setPosition({ x = t.position.x, y = t.position.y + 0.5 + i * 0.2, z = t.position.z })
    end
  end
end

local function placePick(color, id, slot)
  local card = getObjectFromGUID(id)
  if card == nil then return end
  card.clearContextMenu()
  card.setLock(false)
  card.setScale({ x = L.s, y = 1, z = L.s })
  card.setRotation({ x = 0, y = seatYaw(color), z = 0 })
  card.setPosition(slotPosition(color, slot))
  Wait.time(function()
    if card ~= nil then card.setLock(true) end
  end, LOCK_DELAY)
end

local function discardCards(ids)
  local toGroup = {}
  local existing = discardGuid and getObjectFromGUID(discardGuid) or nil
  if existing then table.insert(toGroup, existing) end
  for i, id in ipairs(ids) do
    local card = getObjectFromGUID(id)
    if card then
      card.clearContextMenu()
      card.setRotation({ x = 0, y = 180, z = 0 })
      card.setPosition({ x = DISCARD_X, y = L.tableY + 1 + i * 0.3, z = 0 })
      table.insert(toGroup, card)
    end
  end
  Wait.time(function()
    local alive = {}
    for _, o in ipairs(toGroup) do
      if o ~= nil then table.insert(alive, o) end
    end
    if #alive >= 2 then
      local groups = group(alive)
      if groups and groups[1] then discardGuid = groups[1].getGUID() end
    elseif alive[1] then
      discardGuid = alive[1].getGUID()
    end
  end, 1)
end

function runActions(actions)
  for _, a in ipairs(actions) do
    if a.type == "deal" then
      dealTo(a.to, a.count)
    elseif a.type == "pass" then
      passPack(a.to, a.cards)
    elseif a.type == "pick" then
      placePick(a.color, a.card, a.slot)
    elseif a.type == "discard" then
      discardCards(a.cards)
    elseif a.type == "finished" then
      broadcastToAll("Draft complete! Your 48 picks are laid out in front of you (hidden from your opponent).", { 0.5, 1, 0.5 })
    end
  end
  updateUI()
  local picker = draft:picker()
  if picker then say(picker, "Your pick! Right-click a card in your hand > Draft this card.") end
end

function tryPick(color, card)
  if draft == nil or card == nil then return end
  local actions, err = draft:pick(color, card.getGUID())
  if not actions then
    say(color, err)
    return
  end
  runActions(actions)
end

-- Points a seat's camera from behind its hand toward the middle of the table,
-- far enough out that the hand, the pick grid and the cube are all on screen.
function frameCamera(color)
  if L == nil or not inList(COLORS, color) or not Player[color].seated then return end
  local t = handTransform(color)
  Player[color].lookAt({
    position = { x = 0, y = L.tableY, z = sideSign(color) * L.handZ * 0.45 },
    pitch = 55,
    yaw = t and t.rotation and t.rotation.y or 0,
    distance = L.handZ * 1.9,
  })
end

-- ---------------------------------------------------------------- events

function onResetView(player)
  frameCamera(player.color)
end

function onPlayerChangeColor(color)
  Wait.frames(function() frameCamera(color) end, 5)
end

function onStartClicked(player)
  if draft == nil then return end
  if draft.started then return end
  if cube == nil then
    broadcastToAll("Cube deck not found; reload the save.", { 1, 0.3, 0.3 })
    return
  end
  if not inList(COLORS, player.color) and not player.host then
    say(player.color, "Sit at White or Red to start the draft.")
    return
  end
  for _, color in ipairs(COLORS) do
    if not Player[color].seated then
      broadcastToAll(color .. " seat is empty; its packs will be dealt anyway (solo testing).", { 1, 0.8, 0.3 })
    end
  end
  local first = COLORS[math.random(1, 2)]
  draft = DraftCore.new({ colors = COLORS, picksPerPlayer = 48, firstStarter = first })
  cube.shuffle()
  broadcastToAll(first .. " starts pack 1. Starting player alternates every pack.", { 0.6, 0.85, 1 })
  for _, color in ipairs(COLORS) do frameCamera(color) end
  runActions(draft:start())
end

function onObjectDrop(color, obj)
  if draft == nil or obj == nil then return end
  local id = obj.getGUID()
  if not draft:inPack(id) then return end
  local picker = draft:picker()
  if picker and color == picker and inPickArea(picker, obj.getPosition()) then
    tryPick(color, obj)
    return
  end
  -- Dropped anywhere else: send it back to the picker's hand.
  Wait.time(function()
    if obj ~= nil and draft:inPack(id) and picker and not isInHand(picker, obj) then
      passPack(picker, { id })
    end
  end, 0.4)
end

function onSave()
  if draft == nil then return "" end
  return JSON.encode({ draft = draft:serialize(), discard = discardGuid })
end

function onLoad(saved)
  math.randomseed(os.time())
  cube = getObjectFromGUID(CUBE_GUID)
  if cube then cube.interactable = false end

  local data = nil
  if saved and saved ~= "" then
    local ok, decoded = pcall(function() return JSON.decode(saved) end)
    if ok then data = decoded end
  end
  if data and data.draft then
    draft = DraftCore.restore(data.draft)
    discardGuid = data.discard
  else
    draft = DraftCore.new({ colors = COLORS, picksPerPlayer = 48 })
  end

  Wait.frames(function()
    computeLayout()
    if not draft.started then placeZones() end
    for _, id in ipairs(draft.pack) do
      local card = getObjectFromGUID(id)
      if card then attachMenu(card) end
    end
    updateUI()
    for _, color in ipairs(COLORS) do frameCamera(color) end
  end, 10)
end

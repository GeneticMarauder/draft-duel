-- Table adapter: wires DraftCore to Tabletop Simulator objects and UI.
-- The builder concatenates draft_core.lua + this file into the save's Global script.
--
-- Each player's half of the table, from the middle outward:
--   middle strip  : cube deck and face-up discard pile (z = 0)
--   pack row      : the current pack, 4 large cards side by side, with Draft buttons
--   pick grid     : the player's picks, 12 x 4 smaller cards
-- Privacy is per card: the pack is hidden from the opponent (they see card
-- backs), picks are invisible to everyone but their owner.

COLORS = { "White", "Red" }
CUBE_GUID = "c00001"
HAND_GUIDS = { White = "a00001", Red = "a00002" }

-- Every seat color, so a card can be hidden from all but its owner.
ALL_COLORS = { "White", "Brown", "Red", "Orange", "Yellow", "Green", "Teal", "Blue",
               "Purple", "Pink", "Grey", "Black" }

PACK_SCALE = 1.5     -- pack cards are drawn larger than normal
PACK_GAP = 0.5       -- space between pack cards
PACK_ROW_Z = 5.2     -- distance of the pack row's centre from the middle line
PICK_SCALE = 0.65
PICK_COLS = 12
PICK_ROWS = 4
PICK_GRID_Z = 9.8    -- distance of the first pick row's centre from the middle line
HAND_Z = 20          -- hand zones (unused during the draft) sit past the table edge
DISCARD_X = 6
LOCK_DELAY = 1.2
BOT_DELAY = 1.0
CAMERA_PITCH = 60
CAMERA_DISTANCE = 23

local draft = nil       -- DraftCore instance
local cube = nil        -- the face-down cube deck
local discardGuid = nil -- face-up discard pile (a deck once 2+ cards land)
local L = nil           -- measured sizes
local bots = {}         -- color -> true for seats that were empty at Start Draft

-- ---------------------------------------------------------------- helpers

local function say(color, msg)
  if Player[color] and Player[color].seated then
    broadcastToColor(msg, color, { 1, 0.6, 0.4 })
  else
    printToAll("[" .. color .. "] " .. msg, { 1, 0.6, 0.4 })
  end
end

-- Yaw that makes a face-up card read upright for a seat.
local function seatYaw(color)
  local t = Player[color].getHandTransform()
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

local function othersThan(owner)
  local others = {}
  for _, c in ipairs(ALL_COLORS) do
    if c ~= owner then table.insert(others, c) end
  end
  return others
end

local function boundsSize(obj)
  if obj == nil then return nil end
  local ok, b = pcall(function() return obj.getBounds() end)
  if ok and b and b.size then return b.size end
  return nil
end

-- ---------------------------------------------------------------- layout

-- Measures the card size and felt height from the cube deck.
function computeLayout()
  local w, h = 2.2, 3.06
  local size = boundsSize(cube)
  if size and size.x > 0.5 and size.z > 0.5 then w, h = size.x, size.z end
  -- Felt height: bottom of the cube deck (measured 0.96 on Table_RPG).
  local tableY, feltY = 2, 0.96
  if cube then
    tableY = cube.getPosition().y
    if size then feltY = tableY - size.y / 2 end
  end
  L = { w = w, h = h, tableY = tableY, feltY = feltY }
end

-- Moves the (unused) hand zones past the table edges.
function placeZones()
  for _, color in ipairs(COLORS) do
    local hand = getObjectFromGUID(HAND_GUIDS[color])
    if hand then
      local p = hand.getPosition()
      hand.setPosition({ x = 0, y = p.y, z = sideSign(color) * HAND_Z })
    end
  end
end

-- Pack card i of n, centred left-to-right on the player's pack row.
function packPosition(color, i, n)
  local sign = sideSign(color)
  local step = L.w * PACK_SCALE + PACK_GAP
  local x = (i - (n + 1) / 2) * step * -sign
  return { x = x, y = L.feltY + 0.25, z = sign * PACK_ROW_Z }
end

function slotPosition(color, slot)
  local i = slot - 1
  local col = i % PICK_COLS
  local row = math.floor(i / PICK_COLS)
  local sign = sideSign(color)
  local dx = L.w * PICK_SCALE * 1.05
  local dz = L.h * PICK_SCALE * 1.05
  local x = (col - (PICK_COLS - 1) / 2) * dx * -sign
  local z = sign * (PICK_GRID_Z + row * dz)
  return { x = x, y = L.feltY + 0.25, z = z }
end

-- ---------------------------------------------------------------- debug

local function fmt(v)
  if v == nil then return "nil" end
  return string.format("(%.1f, %.1f, %.1f)", v.x, v.y, v.z)
end

-- Chat "!draftdebug": prints the numbers needed to diagnose layout problems.
function printDebug()
  local ok, tbl = pcall(function() return Tables.getTableObject() end)
  local tsize = ok and boundsSize(tbl) or nil
  printToAll("table=" .. tostring(ok and tbl ~= nil) .. " size=" .. fmt(tsize), { 0.8, 0.8, 0.8 })
  if L then
    printToAll(string.format("card=%.2fx%.2f tableY=%.2f feltY=%.2f", L.w, L.h, L.tableY, L.feltY),
      { 0.8, 0.8, 0.8 })
  end
  for _, color in ipairs(COLORS) do
    local o = getObjectFromGUID(HAND_GUIDS[color])
    if o then
      printToAll(color .. " hand: pos=" .. fmt(o.getPosition()), { 0.8, 0.8, 0.8 })
    else
      printToAll(color .. " hand: MISSING (" .. HAND_GUIDS[color] .. ")", { 1, 0.4, 0.4 })
    end
  end
end

-- Testing aid: make up to n random picks for human seats (bots keep picking on their own).
function autoPick(n)
  if n <= 0 or draft == nil or not draft.started or draft.finished then return end
  local picker = draft:picker()
  if picker and not bots[picker] and #draft.pack == DraftCore.PACK_SIZE then
    local actions = draft:pick(picker, draft.pack[math.random(1, #draft.pack)])
    if actions then
      runActions(actions)
      n = n - 1
    end
  end
  Wait.time(function() autoPick(n) end, 0.4)
end

function onChat(message, player)
  if message == "!draftdebug" then
    printDebug()
    return false
  end
  local n = message:match("^!draftauto%s*(%d*)$")
  if n then
    autoPick(tonumber(n) or 48)
    return false
  end
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

-- ---------------------------------------------------------------- pack cards

-- Draft button under each pack card, plus a right-click menu entry.
local function makePickable(card)
  card.clearButtons()
  card.createButton({
    click_function = "onDraftButton",
    function_owner = Global,
    label = "Draft",
    position = { x = 0, y = 0.3, z = 1.75 },
    width = 600, height = 220, font_size = 150,
    color = { 0.72, 0.53, 0.04 }, font_color = { 1, 1, 1 },
    tooltip = "Draft this card",
  })
  card.clearContextMenu()
  card.addContextMenuItem("Draft this card", function(playerColor)
    tryPick(playerColor, card)
  end)
end

local function makeUnpickable(card)
  card.clearButtons()
  card.clearContextMenu()
end

function onDraftButton(card, playerColor)
  tryPick(playerColor, card)
end

-- Lays the current pack out on its holder's pack row: face-up, large, locked,
-- hidden from everyone else (they see card backs).
function layoutPack()
  if draft == nil or not draft.started or draft.finished then return end
  local holder = draft:picker()
  if holder == nil then return end
  local n = #draft.pack
  for i, id in ipairs(draft.pack) do
    local card = getObjectFromGUID(id)
    if card then
      card.setHiddenFrom(othersThan(holder))
      card.setInvisibleTo({})
      card.setLock(true)
      card.setScale({ x = PACK_SCALE, y = 1, z = PACK_SCALE })
      card.setRotation({ x = 0, y = seatYaw(holder), z = 0 })
      card.setPosition(packPosition(holder, i, n))
    end
  end
end

local function dealTo(color, count)
  for i = 1, count do
    local card = cube.takeObject({
      position = { x = 0, y = L.tableY + 2 + i * 0.2, z = sideSign(color) * PACK_ROW_Z },
      rotation = { x = 0, y = seatYaw(color), z = 180 },
      smooth = false,
    })
    if card then
      card.setHiddenFrom(othersThan(color))
      draft:addToPack(card.getGUID())
      makePickable(card)
    end
  end
end

local function placePick(color, id, slot)
  local card = getObjectFromGUID(id)
  if card == nil then return end
  makeUnpickable(card)
  card.setInvisibleTo(othersThan(color)) -- before it moves, so it is never seen
  card.setHiddenFrom({})
  card.setLock(false)
  card.setScale({ x = PICK_SCALE, y = 1, z = PICK_SCALE })
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
      makeUnpickable(card)
      card.setHiddenFrom({})
      card.setInvisibleTo({})
      card.setLock(false)
      card.setScale({ x = 1, y = 1, z = 1 })
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

-- ---------------------------------------------------------------- flow

function runActions(actions)
  for _, a in ipairs(actions) do
    if a.type == "deal" then
      dealTo(a.to, a.count)
    elseif a.type == "pick" then
      placePick(a.color, a.card, a.slot)
    elseif a.type == "discard" then
      discardCards(a.cards)
    elseif a.type == "finished" then
      broadcastToAll("Draft complete! Your 48 picks are laid out in front of you (hidden from your opponent).", { 0.5, 1, 0.5 })
    end
    -- "pass" needs no work of its own: layoutPack moves the pack to its new holder.
  end
  layoutPack()
  updateUI()
  promptPicker()
end

-- Schedules the bot's pick when it is a bot's turn. (Human pickers are
-- prompted by the on-screen "Your pick!" panel that updateUI shows.)
function promptPicker()
  local picker = draft:picker()
  if picker and bots[picker] then scheduleBotPick(picker) end
end

-- Bot: takes a random card from its pack after a short pause.
function scheduleBotPick(color)
  local turn = draft.packNumber * 10 + draft.step
  Wait.time(function()
    if draft:picker() ~= color or draft.packNumber * 10 + draft.step ~= turn then return end
    local id = draft.pack[math.random(1, #draft.pack)]
    local actions = draft:pick(color, id)
    if actions then runActions(actions) end
  end, BOT_DELAY)
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

-- Looks down at the seat's pack row, so the pack sits mid-screen with the
-- pick grid below it and the cube, discard pile and opponent beyond.
function frameCamera(color)
  if L == nil or not inList(COLORS, color) or not Player[color].seated then return end
  local t = Player[color].getHandTransform()
  Player[color].lookAt({
    position = { x = 0, y = L.feltY, z = sideSign(color) * (PACK_ROW_Z + 1) },
    pitch = CAMERA_PITCH,
    yaw = t and t.rotation and t.rotation.y or 0,
    distance = CAMERA_DISTANCE,
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
  bots = {}
  for _, color in ipairs(COLORS) do
    if not Player[color].seated then
      bots[color] = true
      broadcastToAll(color .. " seat is empty, so a bot will draft random cards for it.", { 1, 0.8, 0.3 })
    end
  end
  local first = COLORS[math.random(1, 2)]
  draft = DraftCore.new({ colors = COLORS, picksPerPlayer = 48, firstStarter = first })
  cube.shuffle()
  broadcastToAll(first .. " starts pack 1. Starting player alternates every pack.", { 0.6, 0.85, 1 })
  for _, color in ipairs(COLORS) do frameCamera(color) end
  runActions(draft:start())
end

function onSave()
  if draft == nil then return "" end
  local botList = {}
  for color in pairs(bots) do table.insert(botList, color) end
  return JSON.encode({ draft = draft:serialize(), discard = discardGuid, bots = botList })
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
    bots = {}
    for _, color in ipairs(data.bots or {}) do bots[color] = true end
  else
    draft = DraftCore.new({ colors = COLORS, picksPerPlayer = 48 })
  end

  Wait.frames(function()
    computeLayout()
    placeZones()
    -- Buttons, menus and visibility are not kept across a reload: reapply them.
    for _, id in ipairs(draft.pack) do
      local card = getObjectFromGUID(id)
      if card then makePickable(card) end
    end
    layoutPack()
    for _, color in ipairs(COLORS) do
      for _, id in ipairs(draft.picks[color]) do
        local card = getObjectFromGUID(id)
        if card then card.setInvisibleTo(othersThan(color)) end
      end
    end
    updateUI()
    for _, color in ipairs(COLORS) do frameCamera(color) end
    if draft.started and not draft.finished then promptPicker() end
  end, 10)
end

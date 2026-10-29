-- Table adapter: wires DraftCore to Tabletop Simulator objects and UI.
-- The builder concatenates draft_core.lua + this file into the save's Global script.
--
-- Each player's half of the table, from the middle outward:
--   middle strip  : cube deck and face-up discard pile (z = 0)
--   pack row      : the current pack, 5 large cards side by side, with Draft buttons
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
BOT_DELAY = 1.0
CAMERA_PITCH = 60
CAMERA_DISTANCE = 23

local draft = nil       -- DraftCore instance
local cube = nil        -- the face-down cube deck
local discardGuid = nil -- face-up discard pile (a deck once 2+ cards land)
local L = nil           -- measured sizes
local bots = {}         -- color -> true for seats that were empty at Start Draft
local building = false  -- deck editor mode (after the draft)
local deckCounts = {}   -- color -> { main, side, lands }
local ready = {}        -- color -> true once their library and sideboard are gathered
local piles = {}        -- color -> { library = guid, sideboard = guid }
local playing = false   -- board set up for the game
local firstPlayer = nil
local booster = nil      -- { color = opener, cards = { guid, ... } } while Booster Tutor's pack is open
local owned = {}         -- color -> { main = { guid, ... }, side = { guid, ... } } as of their last Ready
local tutored = {}       -- guids of cards taken with Booster Tutor this game (they leave after it)
local gameNumber = 1
local mats = {}          -- color -> { name = ..., guid = ... } for each seat's chosen playmat

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
  if message == "!hide" then
    rehideAll()
    broadcastToAll("Private cards re-hidden.", { 0.6, 0.85, 1 })
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
  if building then text = "Deck building: your deck is on your left, your sideboard on your right." end
  if building and gameNumber > 1 then
    text = "Sideboarding for game " .. gameNumber .. ": your deck is on your left, your sideboard on your right."
  end
  if playing then text = "Game on! " .. (firstPlayer or "?") .. " goes first. Good luck!" end
  UI.setValue("statusText", text)
  -- Once the game starts the bar would only sit over the opponent's side;
  -- who goes first is announced in a broadcast (and the chat log) instead.
  UI.setAttribute("statusPanel", "active", playing and "false" or "true")
  UI.setAttribute("nextGameButton", "active", playing and "true" or "false")
  local started = draft and draft.started
  UI.setAttribute("startButton", "active", started and "false" or "true")
  local picker = draft and draft:picker() or nil
  for _, color in ipairs(COLORS) do
    UI.setAttribute("prompt_" .. color, "active", (picker == color and not building) and "true" or "false")
    UI.setAttribute("deck_" .. color, "active", building and "true" or "false")
    UI.setAttribute("ready_" .. color, "active", (building and not ready[color]) and "true" or "false")
    local c = deckCounts[color]
    if ready[color] then
      UI.setValue("deckText_" .. color, "Ready! Waiting for your opponent...")
    elseif c then
      UI.setValue("deckText_" .. color, "Deck " .. c.main .. "  (" .. (c.main - c.lands) .. " spells + "
        .. c.lands .. " lands)      Sideboard " .. c.side)
    end
    for _, name in ipairs(BASIC_ORDER) do
      local n = c and c.basics and c.basics[name] or 0
      UI.setValue("land_" .. color .. "_" .. name, name .. "  " .. n)
    end
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
  card.setPosition(slotPosition(color, slot)) -- left unlocked: picks are yours to move
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
      broadcastToAll("Draft complete! Build your deck: drag cards between your deck (left) and sideboard (right).",
        { 0.5, 1, 0.5 })
      startDeckBuilding(true)
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
  -- While deck building, pull back to show both the deck and sideboard columns.
  local z, distance = PACK_ROW_Z + 1, CAMERA_DISTANCE
  if building then z, distance = DECK_TOP_Z + 6, BUILD_CAMERA_DISTANCE end
  if playing then
    -- Just in front of the hand zone (so only TTS's own hand display shows),
    -- looking across your battlefield toward your opponent's.
    z = PLAY_CAMERA_Z
    distance = (HAND_Z - 2.5 - PLAY_CAMERA_Z) / math.cos(math.rad(CAMERA_PITCH))
  end
  Player[color].lookAt({
    position = { x = 0, y = L.feltY, z = sideSign(color) * z },
    pitch = CAMERA_PITCH,
    yaw = t and t.rotation and t.rotation.y or 0,
    distance = distance,
  })
end

-- ---------------------------------------------------------------- deck editor
-- After the draft each player's picks are laid out in columns by mana value
-- (0 .. 7+, then lands). The deck sits in the middle of the table; the
-- sideboard is a smaller area to the owner's right. Dropping a card re-sorts
-- that player's side. Basic lands are added and removed with the land buttons
-- in the bottom panel; a basic dropped in the sideboard is removed.

DECK_SCALE = 0.8
DECK_COLS = 9          -- mana value 0..7+, then a lands column
DECK_COL_STEP = 1.95
DECK_CASCADE = 0.55    -- how much of each card shows above the next one
DECK_LAYER = 0.06      -- height step between cascaded cards (more than a card is thick)
DECK_TOP_Z = 3.6       -- first card's centre, measured from the middle line
SIDE_SPLIT_U = 9.4     -- owner-relative x: left of this is the deck, right is the sideboard
-- Per-area column layout, in owner-relative x (negative = owner's left).
AREAS = {
  main = { u0 = -(DECK_COLS - 1) * DECK_COL_STEP / 2, step = DECK_COL_STEP, scale = DECK_SCALE, cascade = DECK_CASCADE },
  side = { u0 = 10.8, step = 1.55, scale = 0.65, cascade = 0.45 },
}
BASIC_ORDER = { "Plains", "Island", "Swamp", "Mountain", "Forest" }
BUILD_CAMERA_DISTANCE = 38

function cardInfo(obj)
  local ok, t = pcall(function() return JSON.decode(obj.getGMNotes()) end)
  if ok and type(t) == "table" then return t end
  return {}
end

-- A drafted card or basic land (not the cube deck or discard pile).
function isDeckCard(obj)
  return obj ~= nil and obj.type == "Card" and cardInfo(obj).id ~= nil
end

local function ownerU(color, x) return x * -sideSign(color) end
local function worldX(color, u) return u * -sideSign(color) end

local function areaOf(color, obj)
  if ownerU(color, obj.getPosition().x) < SIDE_SPLIT_U then return "main" end
  return "side"
end

-- Re-sorts everything on a player's side into deck and sideboard columns.
-- forceMain puts every card in the deck (used when the draft ends).
function layoutDeck(color, forceMain)
  if L == nil or ready[color] then return end
  local sign = sideSign(color)
  local cols = { main = {}, side = {} }
  for _, area in ipairs({ "main", "side" }) do
    for c = 0, DECK_COLS - 1 do cols[area][c] = {} end
  end
  local counts = { main = 0, side = 0, lands = 0, basics = {} }
  for _, o in ipairs(getObjects()) do
    if isDeckCard(o) and o.getPosition().z * sign > 1 then
      local info = cardInfo(o)
      local area = "side"
      if forceMain or areaOf(color, o) == "main" then area = "main" end
      if info.basic and area == "side" then
        o.destruct()
      else
        local col = math.min(math.floor(info.cmc or 0), DECK_COLS - 2)
        if info.land then col = DECK_COLS - 1 end
        table.insert(cols[area][col], o)
        counts[area] = counts[area] + 1
        if area == "main" and info.land then counts.lands = counts.lands + 1 end
        if area == "main" and info.basic then
          counts.basics[o.getName()] = (counts.basics[o.getName()] or 0) + 1
        end
      end
    end
  end
  for area, byCol in pairs(cols) do
    local a = AREAS[area]
    for c = 0, DECK_COLS - 1 do
      local list = byCol[c]
      table.sort(list, function(x, y) return x.getName() < y.getName() end)
      for k, o in ipairs(list) do
        o.setInvisibleTo(othersThan(color))
        o.setHiddenFrom({})
        makeUnpickable(o)
        -- Gravity off: a cascaded card would otherwise rest half on the card
        -- before it and half on the felt, tilting or sliding underneath it.
        -- Each card floats flat, a step above the one before, and stays draggable.
        o.setLock(false)
        o.use_gravity = false
        -- Not sticky: lifting a card must not carry the cards cascaded on top of it.
        o.sticky = false
        o.setScale({ x = a.scale, y = 1, z = a.scale })
        o.setRotation({ x = 0, y = seatYaw(color), z = 0 })
        o.setPosition({
          x = worldX(color, a.u0 + c * a.step),
          y = L.feltY + 0.1 + k * DECK_LAYER,
          z = sign * (DECK_TOP_Z + (k - 1) * a.cascade),
        })
        o.setVelocity({ x = 0, y = 0, z = 0 })
        o.setAngularVelocity({ x = 0, y = 0, z = 0 })
      end
    end
  end
  deckCounts[color] = counts
  updateUI()
end

local function basicLandData(name)
  for _, land in ipairs(BASIC_LANDS) do
    if land.Nickname == name then return land end
  end
  return nil
end

-- Adds one basic land straight into the player's Lands column.
function addBasic(color, name)
  local land = basicLandData(name)
  if land == nil or not building or ready[color] or L == nil then return end
  local a = AREAS.main
  spawnObjectData({
    data = land,
    position = { x = worldX(color, a.u0 + (DECK_COLS - 1) * a.step), y = L.feltY + 2,
                 z = sideSign(color) * DECK_TOP_Z },
    rotation = { x = 0, y = seatYaw(color), z = 0 },
    callback_function = function() layoutDeck(color, false) end,
  })
end

-- Removes one basic land of that name from the player's deck.
function removeBasic(color, name)
  if not building or ready[color] then return end
  local sign = sideSign(color)
  for _, o in ipairs(getObjects()) do
    if isDeckCard(o) and cardInfo(o).basic and o.getName() == name
        and o.getPosition().z * sign > 1 and areaOf(color, o) == "main" then
      o.destruct()
      Wait.frames(function() layoutDeck(color, false) end, 1)
      return
    end
  end
end

-- Land buttons in the bottom panel: left-click adds one, right-click removes one.
function onLandClicked(player, mouseButton, id)
  local color, name = id:match("^land_(%a+)_(%a+)$")
  if color == nil or player.color ~= color then return end
  if mouseButton == "-2" then removeBasic(color, name) else addBasic(color, name) end
end

-- forceMain: true when the draft has just ended (every pick starts in the
-- deck); false when resuming after a reload (keep the player's choices).
function startDeckBuilding(forceMain)
  building = true
  for _, color in ipairs(COLORS) do
    layoutDeck(color, forceMain)
    frameCamera(color)
  end
  updateUI()
end

-- ---------------------------------------------------------------- ready & play

MIN_DECK = 40
LIBRARY_U = 14         -- owner-relative x of the library (owner's right)
SIDEBOARD_U = 18.5
LIFE_U = -14           -- life counter on the owner's left
PILE_Z = 13
PLAY_CAMERA_Z = 5

-- The cards a player currently has in their deck (left) and sideboard (right).
function sideCards(color)
  local sign = sideSign(color)
  local main, side = {}, {}
  for _, o in ipairs(getObjects()) do
    if isDeckCard(o) and o.getPosition().z * sign > 1 then
      if areaOf(color, o) == "main" then table.insert(main, o) else table.insert(side, o) end
    end
  end
  return main, side
end

-- Stacks cards face-down at a spot on the owner's side and groups them into one
-- pile; the sideboard stays invisible to the opponent, the library shows its backs.
local function gatherPile(color, cards, u, kind)
  local sign = sideSign(color)
  local pos = { x = worldX(color, u), y = L.feltY + 0.5, z = sign * PILE_Z }
  piles[color] = piles[color] or {}
  for k, o in ipairs(cards) do
    makeUnpickable(o)
    o.use_gravity = true
    o.setScale({ x = 1, y = 1, z = 1 })
    o.setRotation({ x = 0, y = seatYaw(color), z = 180 })
    if kind == "library" then o.setInvisibleTo({}) else o.setInvisibleTo(othersThan(color)) end
    o.setPosition({ x = pos.x, y = pos.y + k * 0.05, z = pos.z })
  end
  Wait.time(function()
    local alive = {}
    for _, o in ipairs(cards) do
      if o ~= nil then table.insert(alive, o) end
    end
    local pile = alive[1]
    if #alive >= 2 then
      local groups = group(alive)
      pile = groups and groups[1] or nil
    end
    if pile then
      pile.setName(color .. " " .. kind)
      if kind == "sideboard" then pile.setInvisibleTo(othersThan(color)) end
      piles[color][kind] = pile.getGUID()
    end
  end, 0.6)
end

function readyUp(color)
  if not building or ready[color] or L == nil then return end
  layoutDeck(color, false)
  local main, side = sideCards(color)
  if #main < MIN_DECK and not bots[color] then
    say(color, "Your deck has " .. #main .. " cards; a limited deck needs at least " .. MIN_DECK .. ".")
    return
  end
  ready[color] = true
  -- Who owns what, so Next game can bring every card back to the right player.
  owned[color] = { main = {}, side = {} }
  for _, o in ipairs(main) do table.insert(owned[color].main, o.getGUID()) end
  for _, o in ipairs(side) do table.insert(owned[color].side, o.getGUID()) end
  gatherPile(color, main, LIBRARY_U, "library")
  if #side > 0 then gatherPile(color, side, SIDEBOARD_U, "sideboard") end
  broadcastToAll(color .. " is ready to play.", { 0.6, 0.85, 1 })
  -- Bot seats ready up with whatever is in their deck.
  for _, c in ipairs(COLORS) do
    if bots[c] and not ready[c] then readyUp(c) end
  end
  updateUI()
  local all = true
  for _, c in ipairs(COLORS) do
    if not ready[c] then all = false end
  end
  if all then Wait.time(startGame, 1.5) end
end

function onReadyClicked(player)
  if not inList(COLORS, player.color) then return end
  readyUp(player.color)
end

-- Clears the middle of the table, shuffles both libraries, deals opening hands
-- and sets life counters.
function startGame()
  if playing then return end
  building = false
  playing = true
  for _, o in ipairs(getObjects()) do
    local note = o.getGMNotes()
    if note and note:find("^basic%-bag") then o.destruct() end
  end
  if cube then
    cube.setPosition({ x = -28, y = L.tableY + 1, z = 0 })
    cube.setLock(true)
  end
  -- The discard pile: whatever cards or piles are left in the middle strip.
  -- (Found by position, not GUID: merging cards into a pile can give it a new GUID.)
  local n = 0
  for _, o in ipairs(getObjects()) do
    if o ~= cube and (o.type == "Deck" or o.type == "Card") then
      local p = o.getPosition()
      if math.abs(p.z) < 2.5 and math.abs(p.x) < 12 then
        o.setPosition({ x = 28, y = L.tableY + 1 + n * 0.5, z = 0 })
        o.setLock(true)
        n = n + 1
      end
    end
  end
  firstPlayer = COLORS[math.random(1, 2)]
  for _, color in ipairs(COLORS) do
    local lib = piles[color] and piles[color].library and getObjectFromGUID(piles[color].library) or nil
    if lib then
      lib.shuffle()
      lib.deal(7, color)
    end
    local sign = sideSign(color)
    spawnObject({
      type = "Counter",
      position = { x = worldX(color, LIFE_U), y = L.feltY + 0.5, z = sign * PILE_Z },
      rotation = { x = 0, y = seatYaw(color), z = 0 },
      callback_function = function(counter)
        counter.Counter.setValue(20)
        counter.setName(color .. " life")
      end,
    })
    frameCamera(color)
  end
  broadcastToAll("Game on! " .. firstPlayer .. " goes first. Libraries are shuffled and you have drawn 7.",
    { 0.5, 1, 0.5 })
  addPlayMenus()
  updateUI()
end

-- ---------------------------------------------------------------- tokens
-- During the game, right-clicking a card that makes tokens offers
-- "Create <token>": the token appears beside that card (or, for a card in
-- hand, on your side of the table). Which cards make which tokens comes from
-- the TOKENS_JSON script header, keyed by the card id in GMNotes. Menus are
-- lost when a card goes into a deck or the game reloads, so they are re-added
-- whenever a card appears.

TOKEN_GAP = 0.3        -- space kept between a new token and the cards around it
TOKEN_HOME_U = -8      -- where tokens from a card in hand go (owner-relative)
TOKEN_HOME_Z = 8
TOKEN_Z_MIN = 1.8      -- a token lands on its owner's battlefield: this far from the middle line...
TOKEN_Z_MAX = 16       -- ...and no further (the hand zone starts beyond)
TOKEN_X_MAX = 29       -- and inside the table's edges
-- One of a kind: creating it again moves the existing card to you.
UNIQUE_TOKENS = { ["The Monarch"] = true, ["Day // Night"] = true }

local tokenData = { tokens = {}, makers = {} }

function loadTokens()
  if TOKENS_JSON then tokenData = JSON.decode(TOKENS_JSON) or tokenData end
end

-- Token labels this card makes, or nil.
function tokensFor(obj)
  if obj == nil or obj.type ~= "Card" then return nil end
  local id = cardInfo(obj).id
  if id == nil then return nil end
  return tokenData.makers[id]
end

-- Adds a card's game-time menu: "Create <token>" for each token it makes and
-- "Open a booster" on Booster Tutor (calling it again replaces them).
function addPlayMenu(obj)
  if obj == nil or obj.type ~= "Card" or inBooster(obj) then return end
  local labels = tokensFor(obj)
  local tutor = obj.getName() == BOOSTER_TUTOR
  if labels == nil and not tutor then return end
  obj.clearContextMenu()
  for _, label in ipairs(labels or {}) do
    obj.addContextMenuItem("Create " .. label, function(color) createToken(color, label, obj) end)
  end
  if tutor then
    obj.addContextMenuItem("Open a booster", function(color) openBooster(color) end)
  end
end

function addPlayMenus()
  for _, o in ipairs(getObjects()) do addPlayMenu(o) end
end

local function inSomeHand(obj)
  local guid = obj.getGUID()
  for _, color in ipairs(COLORS) do
    for _, h in ipairs(Player[color].getHandObjects() or {}) do
      if h.getGUID() == guid then return true end
    end
  end
  return false
end

-- True when a card-sized spot at (x, z) touches no card, pile or counter
-- (other than `ignore`). Bounds follow rotation, so tapped cards count as wide.
local function spotIsFree(x, z, ignore)
  for _, o in ipairs(getObjects()) do
    if o ~= ignore and (o.type == "Card" or o.type == "Deck" or o.type == "Counter") then
      local p = o.getPosition()
      local b = boundsSize(o) or { x = L.w, z = L.h }
      if math.abs(p.x - x) < (b.x + L.w) / 2 + TOKEN_GAP - 0.01
          and math.abs(p.z - z) < (b.z + L.h) / 2 + TOKEN_GAP - 0.01 then
        return false
      end
    end
  end
  return true
end

-- Candidate offsets around the anchor, in card steps (du to the owner's right,
-- dv toward the owner's hand), nearest first: along the row to the right, then
-- the left, then the next row.
local TOKEN_OFFSETS = {}
for dv = 0, 3 do
  for du = -6, 6 do
    if du ~= 0 or dv ~= 0 then
      local cost = (du > 0 and du or -du + 1.5) + dv * 3
      table.insert(TOKEN_OFFSETS, { du = du, dv = dv, cost = cost })
    end
  end
end
table.sort(TOKEN_OFFSETS, function(a, b) return a.cost < b.cost end)

-- The nearest free spot on the owner's battlefield beside the source card (or
-- beside their "home" spot when the card is in hand).
local function tokenSpot(color, source, ignore)
  local sign = sideSign(color)
  local ax, az
  if source ~= nil and not inSomeHand(source) then
    local p = source.getPosition()
    ax, az = p.x, p.z
  else
    ax, az = worldX(color, TOKEN_HOME_U), sign * TOKEN_HOME_Z
  end
  local su, sv = L.w + TOKEN_GAP, L.h + TOKEN_GAP
  for _, off in ipairs(TOKEN_OFFSETS) do
    local x = ax + worldX(color, off.du * su)
    local z = az + sign * off.dv * sv
    if math.abs(x) <= TOKEN_X_MAX and z * sign >= TOKEN_Z_MIN and z * sign <= TOKEN_Z_MAX
        and spotIsFree(x, z, ignore) then
      return { x = x, y = L.feltY + 0.3, z = z }
    end
  end
  -- Battlefield full: put it on top of the spot to the card's right.
  return { x = ax + worldX(color, su), y = L.feltY + 1, z = az }
end

local function findToken(label)
  for _, o in ipairs(getObjects()) do
    if o.type == "Card" and cardInfo(o).token == label then return o end
  end
  return nil
end

function createToken(color, label, source)
  local data = tokenData.tokens[label]
  if data == nil or L == nil then return end
  if not inList(COLORS, color) then
    say(color, "Sit at White or Red to create tokens.")
    return
  end
  local rot = { x = 0, y = seatYaw(color), z = 0 }
  if UNIQUE_TOKENS[label] then
    local existing = findToken(label)
    if existing then
      existing.setPosition(tokenSpot(color, source, existing))
      existing.setRotation(rot)
      broadcastToAll(color .. " takes " .. label .. ".", { 0.6, 0.85, 1 })
      return
    end
  end
  spawnObjectData({ data = data, position = tokenSpot(color, source), rotation = rot })
end

-- Drawn, dealt and searched-for cards are new objects with no menu yet.
function onObjectSpawn(obj)
  if not playing then return end
  Wait.frames(function()
    if obj ~= nil then addPlayMenu(obj) end
  end, 1)
end

function onObjectLeaveContainer(container, obj)
  onObjectSpawn(obj)
end

-- ---------------------------------------------------------------- booster tutor
-- Booster Tutor (right-click > "Open a booster") reveals 15 cards from the
-- undrafted rest of the cube in a row across the middle of the table. The
-- player who opened it clicks Take on one: it goes to their hand and the
-- other cards are shuffled back into the cube.

BOOSTER_TUTOR = "Booster Tutor"
BOOSTER_SIZE = 15
BOOSTER_SCALE = 0.9
BOOSTER_GAP = 0.2

function inBooster(obj)
  if booster == nil or obj == nil then return false end
  return inList(booster.cards, obj.getGUID())
end

-- Card i of n, in a row across the middle, reading left to right for the opener.
function boosterPosition(color, i, n)
  local step = L.w * BOOSTER_SCALE + BOOSTER_GAP
  return { x = (i - (n + 1) / 2) * step * -sideSign(color), y = L.feltY + 1.5, z = 0 }
end

-- Lays the open booster out face-up for everyone, locked, each card with a Take button.
function layoutBooster()
  if booster == nil or L == nil then return end
  local n = #booster.cards
  for i, id in ipairs(booster.cards) do
    local card = getObjectFromGUID(id)
    if card then
      card.setHiddenFrom({})
      card.setInvisibleTo({})
      card.setLock(true)
      card.setScale({ x = BOOSTER_SCALE, y = 1, z = BOOSTER_SCALE })
      card.setRotation({ x = 0, y = seatYaw(booster.color), z = 0 })
      card.setPosition(boosterPosition(booster.color, i, n))
      card.clearButtons()
      card.createButton({
        click_function = "onBoosterTake",
        function_owner = Global,
        label = "Take",
        position = { x = 0, y = 0.3, z = 1.75 },
        width = 600, height = 220, font_size = 150,
        color = { 0.35, 0.2, 0.55 }, font_color = { 1, 1, 1 },
        tooltip = "Put this card into your hand",
      })
      card.clearContextMenu()
      card.addContextMenuItem("Take this card", function(color) takeFromBooster(color, card) end)
    end
  end
end

function openBooster(color)
  if not inList(COLORS, color) then
    say(color, "Sit at White or Red to open a booster.")
    return
  end
  if booster then
    say(color, booster.color .. " already has a booster open.")
    return
  end
  if cube == nil or L == nil then return end
  local n = math.min(BOOSTER_SIZE, cube.getQuantity())
  if n < 1 then
    say(color, "The cube has no cards left to open.")
    return
  end
  cube.shuffle()
  booster = { color = color, cards = {} }
  for i = 1, n do
    local card = cube.takeObject({ position = boosterPosition(color, i, n), smooth = false })
    if card then table.insert(booster.cards, card.getGUID()) end
  end
  layoutBooster()
  broadcastToAll(color .. " opens a booster with Booster Tutor.", { 0.6, 0.85, 1 })
end

function onBoosterTake(card, color)
  takeFromBooster(color, card)
end

-- Puts cards back face-down into the cube and reshuffles it. The cube is
-- locked during the game, and a locked deck refuses putObject.
function returnToCube(cards)
  if cube == nil or #cards == 0 then return end
  cube.setLock(false)
  for _, o in ipairs(cards) do
    o.clearButtons()
    o.clearContextMenu()
    o.setLock(false)
    o.setScale({ x = 1, y = 1, z = 1 })
    o.setHiddenFrom({})
    o.setInvisibleTo({})
    o.setRotation(cube.getRotation()) -- face-down like the cube, so it stays hidden there
    cube.putObject(o)
  end
  Wait.time(function()
    if cube then
      cube.shuffle()
      cube.setLock(true)
    end
  end, 1)
end

-- The opener takes one card into their hand; the rest go back into the cube.
-- The taken card is only theirs for this game (see nextGame).
function takeFromBooster(color, card)
  if card == nil or not inBooster(card) then return end
  if color ~= booster.color then
    say(color, "Only " .. booster.color .. " can take a card from this booster.")
    return
  end
  local taken = card.getGUID()
  local rest = {}
  for _, id in ipairs(booster.cards) do
    local o = getObjectFromGUID(id)
    if o and id ~= taken then table.insert(rest, o) end
  end
  booster = nil
  returnToCube(rest)
  table.insert(tutored, taken)
  card.clearButtons()
  card.clearContextMenu()
  card.setLock(false)
  card.setScale({ x = 1, y = 1, z = 1 })
  card.setRotation({ x = 0, y = seatYaw(color), z = 0 })
  card.setPosition(Player[color].getHandTransform().position)
  addPlayMenu(card)
  broadcastToAll(color .. " takes " .. card.getName() .. " from the booster (it goes back to the cube after this game).",
    { 0.6, 0.85, 1 })
end

-- ---------------------------------------------------------------- next game
-- "Next game" (click twice to confirm) ends the current game and starts a
-- sideboarding phase: every card a player owns comes back from their library,
-- hand, battlefield and piles into the deck editor, deck and sideboard as they
-- were at Ready. Tokens and life counters are removed and Booster Tutor picks
-- go back into the cube. Ready to play then starts the next game.

local nextGameArmed = nil  -- color that clicked Next game once and must confirm

function onNextGameClicked(player)
  local color = player.color
  if not playing or not inList(COLORS, color) then return end
  if nextGameArmed ~= color then
    nextGameArmed = color
    UI.setAttribute("nextGameButton", "text", "Click again to confirm")
    Wait.time(function()
      if nextGameArmed == color then
        nextGameArmed = nil
        UI.setAttribute("nextGameButton", "text", "Next game")
      end
    end, 4)
    return
  end
  nextGameArmed = nil
  UI.setAttribute("nextGameButton", "text", "Next game") -- (UI.setValue does not relabel a Button)
  nextGame()
end

-- Where a card goes between games: "cube", or its owner and "main"/"side".
local function routeOf(guid)
  if inList(tutored, guid) then return "cube" end
  for _, color in ipairs(COLORS) do
    local o = owned[color]
    if o and inList(o.main, guid) then return color, "main" end
    if o and inList(o.side, guid) then return color, "side" end
  end
  return nil
end

-- Moves a card to its owner's deck or sideboard area (layoutDeck tidies it up).
-- k spreads the cards over the columns; they float, so they never land on each other.
local function sendToEditor(card, color, area, k)
  local a = AREAS[area]
  card.setInvisibleTo(othersThan(color)) -- before it moves, so it is never seen
  card.setHiddenFrom({})
  card.clearButtons()
  card.clearContextMenu()
  card.setLock(false)
  card.setScale({ x = a.scale, y = 1, z = a.scale })
  card.use_gravity = false
  card.setRotation({ x = 0, y = seatYaw(color), z = 0 })
  card.setPosition({
    x = worldX(color, a.u0 + (k % DECK_COLS) * a.step),
    y = L.feltY + 0.5 + k * DECK_LAYER,
    z = sideSign(color) * (DECK_TOP_Z + math.floor(k / DECK_COLS) * a.cascade),
  })
end

function nextGame()
  if not playing or L == nil then return end
  -- Deck-building rules from here on: tryObjectEnterContainer stops the cards
  -- coming back from merging into piles again as they are moved.
  playing = false
  building = true
  ready = {}
  piles = {}
  firstPlayer = nil
  gameNumber = gameNumber + 1
  if booster then
    local open = {}
    for _, id in ipairs(booster.cards) do
      local o = getObjectFromGUID(id)
      if o then table.insert(open, o) end
    end
    booster = nil
    returnToCube(open)
  end
  -- Empty every pile holding someone's cards (library, sideboard, graveyard...).
  -- All but the last card are taken out; the last is left as a plain card.
  for _, d in ipairs(getObjects()) do
    if d.type == "Deck" and d.getGUID() ~= CUBE_GUID then
      local entries = d.getObjects()
      local ours = false
      for _, e in ipairs(entries) do
        if routeOf(e.guid) then ours = true end
      end
      if ours then
        for i = 1, #entries - 1 do
          local p = d.getPosition()
          d.takeObject({ guid = entries[i].guid, position = { x = p.x, y = p.y + 2 + i * 0.05, z = p.z },
                         smooth = false })
        end
      end
    end
  end
  Wait.time(function()
    local toCube = {}
    local count = {}  -- "<color><area>" -> cards sent there so far
    for _, o in ipairs(getObjects()) do
      if o.type == "Card" then
        local info = cardInfo(o)
        local color, area = routeOf(o.getGUID())
        if info.token then
          o.destruct()
        elseif color == "cube" then
          table.insert(toCube, o)
        elseif color then
          local key = color .. area
          count[key] = (count[key] or 0) + 1
          sendToEditor(o, color, area, count[key] - 1)
        end
      elseif o.type == "Counter" and o.getName():find(" life$") then
        o.destruct()
      end
    end
    returnToCube(toCube)
    tutored = {}
    broadcastToAll("Game over. Sideboard for game " .. gameNumber
      .. ": drag cards between your deck (left) and sideboard (right), then press Ready to play.", { 0.5, 1, 0.5 })
    Wait.time(function() startDeckBuilding(false) end, 0.5)
  end, 0.5)
end

-- ---------------------------------------------------------------- playmats
-- Each seated player picks a playmat from the dropdown at the bottom right
-- (visible only to them). The mat is a locked, non-interactable tile under
-- their half of the table; cards and tokens rest on it. The artwork is drawn
-- by the builder (playmats.py) and listed in the MATS_JSON script header.

MAT_D = 16             -- playmat depth in table units (it covers the owner's battlefield...)
MAT_Z = 9.5            -- ...centred this far from the middle line); the width (44) follows
MAT_THICKNESS = 0.1    -- the image's 2048 x 744 shape
-- Measured in TTS: a custom tile at scale 1 is 2 units deep. (Its bounds are not
-- known until the image has loaded, so the scale is set up front.)
MAT_SCALE = MAT_D / 2
MATS = {}              -- { { name = ..., url = ... }, ... }

local function matUrl(name)
  for _, m in ipairs(MATS) do
    if m.name == name then return m.url end
  end
  return nil
end

-- Locks the mat in place over the owner's battlefield.
local function fitPlaymat(tile, color)
  if tile == nil or L == nil then return end
  tile.setScale({ x = MAT_SCALE, y = 1, z = MAT_SCALE })
  tile.setPosition({ x = 0, y = L.feltY + MAT_THICKNESS / 2, z = sideSign(color) * MAT_Z })
  tile.setLock(true)
  tile.interactable = false
end

-- Replaces a seat's playmat (name nil or unknown: no playmat).
function setPlaymat(color, name)
  local old = mats[color] and getObjectFromGUID(mats[color].guid) or nil
  if old then old.destruct() end
  mats[color] = nil
  local url = matUrl(name)
  if url == nil or L == nil then return end
  -- spawnObject + setCustomObject in the same frame is TTS's way to make a
  -- custom tile (raw spawnObjectData without every field fails to load).
  local tile = spawnObject({
    type = "Custom_Tile",
    position = { x = 0, y = L.feltY + MAT_THICKNESS / 2, z = sideSign(color) * MAT_Z },
    rotation = { x = 0, y = seatYaw(color), z = 0 },
    scale = { x = MAT_SCALE, y = 1, z = MAT_SCALE },
    sound = false,
    callback_function = function(o)
      o.setName(color .. " playmat: " .. name)
      Wait.frames(function() fitPlaymat(o, color) end, 2)
    end,
  })
  if tile == nil then return end
  tile.setCustomObject({ image = url, type = 0, thickness = MAT_THICKNESS, stackable = false, stretch = true })
  tile.setLock(true)
  mats[color] = { name = name, guid = tile.getGUID() }
end

-- Dropdown handler; each seat's dropdown is only shown to that seat.
function onMatChosen(player, value, id)
  local color = id:match("^mat_(%a+)$")
  if color == nil or player.color ~= color then return end
  setPlaymat(color, value)
end

-- ---------------------------------------------------------------- privacy
-- TTS can lose a card's "invisible to" list when a player picks it up, moves
-- or flips it, so private cards are re-hidden on every pickup, drop and flip
-- (and again a few frames later, after TTS has finished its own handling).

-- Seat a card is private to, or nil if it is public.
function privateOwner(obj)
  if obj == nil or draft == nil then return nil end
  local id = obj.getGUID()
  for _, color in ipairs(COLORS) do
    if inList(draft.picks[color], id) and not playing then return color end
    if piles[color] and piles[color].sideboard == id then return color end
  end
  if building and isDeckCard(obj) then
    local z = obj.getPosition().z
    if z < -1 then return COLORS[1] end
    if z > 1 then return COLORS[2] end
  end
  return nil
end

function rehide(obj, owner)
  owner = owner or privateOwner(obj)
  if owner == nil then return end
  obj.setInvisibleTo(othersThan(owner))
  Wait.frames(function()
    if obj ~= nil then obj.setInvisibleTo(othersThan(owner)) end
  end, 3)
end

-- Re-applies privacy to every card on the table (chat command "!hide").
function rehideAll()
  for _, o in ipairs(getObjects()) do
    local owner = privateOwner(o)
    if owner then o.setInvisibleTo(othersThan(owner)) end
  end
  layoutPack()
end

function onObjectPickUp(color, obj)
  rehide(obj)
end

-- A double-faced card flipped to its other face becomes a new object.
function onObjectStateChange(obj, oldGuid)
  if draft then
    for _, color in ipairs(COLORS) do
      for i, id in ipairs(draft.picks[color]) do
        if id == oldGuid then draft.picks[color][i] = obj.getGUID() end
      end
    end
  end
  local lists = { tutored }
  for _, color in ipairs(COLORS) do
    if owned[color] then
      table.insert(lists, owned[color].main)
      table.insert(lists, owned[color].side)
    end
  end
  for _, list in ipairs(lists) do
    for i, id in ipairs(list) do
      if id == oldGuid then list[i] = obj.getGUID() end
    end
  end
  rehide(obj)
  if playing then addPlayMenu(obj) end
end

function onObjectDrop(color, obj)
  rehide(obj)
  if not building or ready[color] or not inList(COLORS, color) or not isDeckCard(obj) then return end
  local sign = sideSign(color)
  local p = obj.getPosition()
  -- Dropped in the middle or on the opponent's side: bring it back to your deck.
  if p.z * sign <= 1 then obj.setPosition({ x = worldX(color, -1), y = p.y, z = sign * DECK_TOP_Z }) end
  Wait.frames(function() layoutDeck(color, false) end, 2)
end

-- Cards dropped on each other must not merge into a pile while deck building
-- (the discard pile in the middle still stacks normally).
function tryObjectEnterContainer(container, obj)
  if not building or not isDeckCard(obj) then return true end
  -- Booster Tutor picks go back into the cube when Next game starts the deck editor.
  if container.getGUID() == CUBE_GUID then return true end
  local z = obj.getPosition().z
  if math.abs(z) <= 1 then return true end
  local owner = COLORS[2]
  if z < 0 then owner = COLORS[1] end
  return ready[owner] == true -- ready players' piles are grouped on purpose
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
  return JSON.encode({ draft = draft:serialize(), discard = discardGuid, bots = botList,
                       ready = ready, piles = piles, playing = playing, firstPlayer = firstPlayer,
                       booster = booster, owned = owned, tutored = tutored, gameNumber = gameNumber,
                       mats = mats })
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
    ready = data.ready or {}
    piles = data.piles or {}
    playing = data.playing == true
    firstPlayer = data.firstPlayer
    booster = data.booster
    owned = data.owned or {}
    tutored = data.tutored or {}
    gameNumber = data.gameNumber or 1
    mats = data.mats or {}
  else
    draft = DraftCore.new({ colors = COLORS, picksPerPlayer = 48 })
  end

  BASIC_LANDS = {}
  if BASIC_LANDS_JSON then BASIC_LANDS = JSON.decode(BASIC_LANDS_JSON) or {} end
  loadTokens()
  if MATS_JSON then MATS = JSON.decode(MATS_JSON) or {} end

  Wait.frames(function()
    computeLayout()
    placeZones()
    -- Playmats are saved with the table; interactable is not, so reapply it.
    for color, m in pairs(mats) do
      local tile = getObjectFromGUID(m.guid)
      if tile then fitPlaymat(tile, color) else mats[color] = nil end
    end
    -- Buttons, menus and visibility are not kept across a reload: reapply them.
    for _, id in ipairs(draft.pack) do
      local card = getObjectFromGUID(id)
      if card then makePickable(card) end
    end
    layoutPack()
    for _, color in ipairs(COLORS) do
      for _, id in ipairs(draft.picks[color]) do
        local card = getObjectFromGUID(id)
        if card then
          card.setInvisibleTo(othersThan(color))
          card.setLock(false)
        end
      end
    end
    if playing then
      layoutBooster()
      addPlayMenus()
      updateUI()
      for _, color in ipairs(COLORS) do frameCamera(color) end
    elseif draft.finished then
      startDeckBuilding(false)
    else
      updateUI()
      for _, color in ipairs(COLORS) do frameCamera(color) end
      if draft.started then promptPicker() end
    end
  end, 10)
end

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
  if building then text = "Deck building: your deck is on your left, your sideboard on your right." end
  if playing then text = "Game on! " .. (firstPlayer or "?") .. " goes first. Good luck!" end
  UI.setValue("statusText", text)
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
-- (0 .. 7+, then lands). Owner's left half = deck, right half = sideboard.
-- Dropping a card re-sorts that player's side. Bottomless bags of basic lands
-- sit along the player's edge; a basic dropped in the sideboard is removed.

DECK_SCALE = 0.8
DECK_COLS = 9          -- mana value 0..7+, then a lands column
DECK_COL_STEP = 1.95
DECK_CASCADE = 0.55    -- how much of each card shows above the next one
DECK_LAYER = 0.06      -- height step between cascaded cards (more than a card is thick)
DECK_TOP_Z = 3.6       -- first card's centre, measured from the middle line
MAIN_U0 = -19.6        -- deck column 0, in owner-relative x (negative = owner's left)
SIDE_U0 = 4.0          -- sideboard column 0
BAG_Z = 19
BAG_U = { -8, -4, 0, 4, 8 }
BUILD_CAMERA_DISTANCE = 38

function cardInfo(obj)
  local ok, t = pcall(function() return JSON.decode(obj.getGMNotes()) end)
  if ok and type(t) == "table" then return t end
  return {}
end

-- A drafted card or basic land (not the cube deck, discard pile or bags).
function isDeckCard(obj)
  return obj ~= nil and obj.type == "Card" and cardInfo(obj).id ~= nil
end

local function ownerU(color, x) return x * -sideSign(color) end
local function worldX(color, u) return u * -sideSign(color) end

-- Re-sorts everything on a player's side into deck and sideboard columns.
-- forceMain puts every card in the deck (used when the draft ends).
function layoutDeck(color, forceMain)
  if L == nil or ready[color] then return end
  local sign = sideSign(color)
  local cols = { main = {}, side = {} }
  for _, area in ipairs({ "main", "side" }) do
    for c = 0, DECK_COLS - 1 do cols[area][c] = {} end
  end
  local counts = { main = 0, side = 0, lands = 0 }
  for _, o in ipairs(getObjects()) do
    if isDeckCard(o) and o.getPosition().z * sign > 1 then
      local info = cardInfo(o)
      local area = "side"
      if forceMain or ownerU(color, o.getPosition().x) < 0 then area = "main" end
      if info.basic and area == "side" then
        o.destruct()
      else
        local col = math.min(math.floor(info.cmc or 0), DECK_COLS - 2)
        if info.land then col = DECK_COLS - 1 end
        table.insert(cols[area][col], o)
        counts[area] = counts[area] + 1
        if area == "main" and info.land then counts.lands = counts.lands + 1 end
      end
    end
  end
  for area, byCol in pairs(cols) do
    local u0 = SIDE_U0
    if area == "main" then u0 = MAIN_U0 end
    for c = 0, DECK_COLS - 1 do
      local list = byCol[c]
      table.sort(list, function(a, b) return a.getName() < b.getName() end)
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
        o.setScale({ x = DECK_SCALE, y = 1, z = DECK_SCALE })
        o.setRotation({ x = 0, y = seatYaw(color), z = 0 })
        o.setPosition({
          x = worldX(color, u0 + c * DECK_COL_STEP),
          y = L.feltY + 0.1 + k * DECK_LAYER,
          z = sign * (DECK_TOP_Z + (k - 1) * DECK_CASCADE),
        })
        o.setVelocity({ x = 0, y = 0, z = 0 })
        o.setAngularVelocity({ x = 0, y = 0, z = 0 })
      end
    end
  end
  deckCounts[color] = counts
  updateUI()
end

-- Bottomless bags of each basic land along the player's edge (spawned once).
function spawnBasicBags(color)
  local marker = "basic-bag:" .. color
  for _, o in ipairs(getObjects()) do
    if o.getGMNotes() == marker then return end
  end
  local sign = sideSign(color)
  for i, land in ipairs(BASIC_LANDS) do
    spawnObjectData({
      data = {
        Name = "Infinite_Bag",
        Nickname = land.Nickname,
        Description = "Drag a " .. land.Nickname .. " onto your deck.",
        GMNotes = marker,
        Transform = { posX = 0, posY = 0, posZ = 0, rotX = 0, rotY = 0, rotZ = 0,
                      scaleX = 0.7, scaleY = 0.7, scaleZ = 0.7 },
        ContainedObjects = { land },
      },
      position = { x = worldX(color, BAG_U[i] or (i * 4 - 12)), y = L.feltY + 1, z = sign * BAG_Z },
      rotation = { x = 0, y = seatYaw(color), z = 0 },
    })
  end
end

-- forceMain: true when the draft has just ended (every pick starts in the
-- deck); false when resuming after a reload (keep the player's choices).
function startDeckBuilding(forceMain)
  building = true
  for _, color in ipairs(COLORS) do
    spawnBasicBags(color)
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
      if ownerU(color, o.getPosition().x) < 0 then table.insert(main, o) else table.insert(side, o) end
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
  local discard = discardGuid and getObjectFromGUID(discardGuid) or nil
  if discard then
    discard.setPosition({ x = 28, y = L.tableY + 1, z = 0 })
    discard.setLock(true)
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
  updateUI()
end

function onObjectDrop(color, obj)
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
                       ready = ready, piles = piles, playing = playing, firstPlayer = firstPlayer })
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
  else
    draft = DraftCore.new({ colors = COLORS, picksPerPlayer = 48 })
  end

  BASIC_LANDS = {}
  if BASIC_LANDS_JSON then BASIC_LANDS = JSON.decode(BASIC_LANDS_JSON) or {} end

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
        if card then
          card.setInvisibleTo(othersThan(color))
          card.setLock(false)
        end
      end
    end
    if playing then
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

-- Minimal stand-in for the Tabletop Simulator scripting API, enough to run
-- table.lua end to end. Hand membership is decided by position, like TTS.

Mock = { objects = {}, waits = {}, messages = {}, ui = {}, nextCard = 0 }

local function vec(p)
  return { x = p.x or p[1] or 0, y = p.y or p[2] or 0, z = p.z or p[3] or 0 }
end

function Mock.newObject(guid, kind)
  local o = { guid = guid, kind = kind, type = kind, notes = "", name = guid,
              pos = { x = 0, y = 1, z = 0 }, rot = { x = 0, y = 0, z = 0 },
              scale = { x = 1, y = 1, z = 1 }, menu = {}, locked = false, interactable = true }
  o.getGMNotes = function() return o.notes end
  o.getName = function() return o.name end
  o.setName = function(n) o.name = n end
  o.destruct = function() Mock.objects[o.guid] = nil end
  o.getGUID = function() return o.guid end
  o.getPosition = function() return vec(o.pos) end
  o.setPosition = function(p) o.pos = vec(p) end
  o.setRotation = function(r) o.rot = vec(r) end
  o.setScale = function(s) o.scale = vec(s) end
  o.getScale = function() return vec(o.scale) end
  o.getValue = function() return o.value end
  o.setValue = function(v) o.value = v end
  o.setInvisibleTo = function(colors) o.invisibleTo = colors end
  o.setHiddenFrom = function(colors) o.hiddenFrom = colors end
  o.buttons = {}
  o.createButton = function(params) table.insert(o.buttons, params) end
  o.clearButtons = function() o.buttons = {} end
  o.setLock = function(b) o.locked = b end
  o.setVelocity = function(v) o.velocity = vec(v) end
  o.setAngularVelocity = function(v) o.angularVelocity = vec(v) end
  o.getBounds = function() return { size = { x = 2.2, y = 0.2, z = 3.1 } } end
  o.addContextMenuItem = function(label, fn) table.insert(o.menu, { label = label, fn = fn }) end
  o.clearContextMenu = function() o.menu = {} end
  Mock.objects[guid] = o
  return o
end

function Mock.newDeck(guid, count)
  local d = Mock.newObject(guid, "Deck")
  d.cards = {}
  for i = 1, count do table.insert(d.cards, string.format("d%05x", i)) end
  d.shuffle = function() end
  d.takeObject = function(params)
    local id = table.remove(d.cards, 1)
    local c = Mock.newObject(id, "Card")
    -- Mana values 0..7 and every sixth card a land, like the real GMNotes payload.
    local n = tonumber(id:sub(2), 16)
    c.notes = string.format('{"id":"%s","cmc":%d,"land":%s,"basic":false}', id, n % 8, tostring(n % 6 == 0))
    c.name = "Card " .. id
    c.setPosition(params.position)
    if params.rotation then c.setRotation(params.rotation) end
    Mock.nextCard = Mock.nextCard + 1
    return c
  end
  return d
end

function Mock.newHand(guid, color, z, yaw)
  local h = Mock.newObject(guid, "Hand")
  h.pos = { x = 0, y = 4, z = z }
  h.rot = { x = 0, y = yaw, z = 0 }
  h.color = color
  return h
end

local hands = {}

local function makePlayer(color, handGuid)
  local p = { color = color, seated = true, host = color == "White", camera = nil }
  p.lookAt = function(params) p.camera = params end
  p.getHandTransform = function()
    local h = Mock.objects[handGuid]
    return { position = vec(h.pos), rotation = vec(h.rot) }
  end
  p.getHandObjects = function()
    local h = Mock.objects[handGuid]
    local out = {}
    for _, o in pairs(Mock.objects) do
      if o.kind == "Card" and math.abs(o.pos.z - h.pos.z) < 2.5 and math.abs(o.pos.x - h.pos.x) < 12 then
        table.insert(out, o)
      end
    end
    return out
  end
  return p
end

function Mock.setup(cubeSize)
  Mock.objects, Mock.waits, Mock.messages, Mock.ui = {}, {}, {}, {}
  -- Measured in game on Table_RPG: deck centre y=2.01, 2.1 thick (felt at 0.96).
  local cube = Mock.newDeck("c00001", cubeSize)
  cube.pos = { x = -6, y = 2.01, z = 0 }
  cube.getBounds = function() return { size = { x = 2.2, y = 2.1, z = 3.06 } } end
  Mock.newHand("a00001", "White", -19, 0)
  Mock.newHand("a00002", "Red", 19, 180)
  Player = { White = makePlayer("White", "a00001"), Red = makePlayer("Red", "a00002") }
end

function Mock.flush()
  local guard = 0
  while #Mock.waits > 0 do
    local fn = table.remove(Mock.waits, 1)
    fn()
    guard = guard + 1
    if guard > 100000 then error("Wait queue never drained") end
  end
end

-- The pack is on the table: the pickable cards (those with a Draft button)
-- on one side. White's side is z < 0.
local function sideOf(o)
  if o.pos.z < 0 then return "White" end
  return "Red"
end

function Mock.packHolder()
  for _, o in pairs(Mock.objects) do
    if o.kind == "Card" and #o.buttons > 0 then return sideOf(o) end
  end
  return nil
end

function Mock.packCards(color)
  local out = {}
  for _, o in pairs(Mock.objects) do
    if o.kind == "Card" and #o.buttons > 0 and sideOf(o) == color then table.insert(out, o) end
  end
  table.sort(out, function(a, b) return a.pos.x < b.pos.x end)
  return out
end

-- TTS globals ---------------------------------------------------------------

getObjectFromGUID = function(guid) return Mock.objects[guid] end
Wait = {
  time = function(fn) table.insert(Mock.waits, fn) end,
  frames = function(fn) table.insert(Mock.waits, fn) end,
}
UI = {
  setValue = function(id, v) Mock.ui[id] = v end,
  setAttribute = function(id, k, v) Mock.ui[id .. "." .. k] = v end,
}
Tables = { getTableObject = function()
  local t = { getBounds = function() return { size = { x = Mock.tableW or 60, y = 1, z = Mock.tableD or 40 } } end }
  return t
end }
-- Grouping cards makes one Deck object holding them (like the G key).
group = function(objs)
  Mock.spawned = (Mock.spawned or 0) + 1
  local d = Mock.newObject(string.format("9%05x", Mock.spawned), "Deck")
  d.pos = objs[1].pos
  d.rot = objs[1].rot
  d.cards = {}
  for _, o in ipairs(objs) do
    table.insert(d.cards, o.guid)
    Mock.objects[o.guid] = nil
  end
  d.shuffled = 0
  d.shuffle = function() d.shuffled = d.shuffled + 1 end
  d.deal = function(n, color)
    Mock.dealt = Mock.dealt or {}
    Mock.dealt[color] = (Mock.dealt[color] or 0) + n
    for _ = 1, n do table.remove(d.cards, 1) end
  end
  return { d }
end
broadcastToAll = function(msg) table.insert(Mock.messages, msg) end
broadcastToColor = function(msg, color) table.insert(Mock.messages, color .. ": " .. msg) end
printToAll = function(msg) table.insert(Mock.messages, msg) end
getObjects = function()
  local out = {}
  for _, o in pairs(Mock.objects) do table.insert(out, o) end
  return out
end
spawnObjectData = function(params)
  Mock.spawned = (Mock.spawned or 0) + 1
  local o = Mock.newObject(string.format("b%05x", Mock.spawned), params.data.Name)
  o.notes = params.data.GMNotes or ""
  o.name = params.data.Nickname or o.guid
  o.data = params.data
  o.setPosition(params.position)
  if params.rotation then o.setRotation(params.rotation) end
  if params.callback_function then params.callback_function(o) end
  return o
end
-- A player pulling a card out of a bottomless bag and dropping it at pos.
function Mock.takeFromBag(bag, pos)
  Mock.spawned = (Mock.spawned or 0) + 1
  local land = bag.data.ContainedObjects[1]
  local c = Mock.newObject(string.format("e%05x", Mock.spawned), "Card")
  c.notes = land.GMNotes
  c.name = land.Nickname
  c.setPosition(pos)
  return c
end
spawnObject = function(params)
  Mock.spawned = (Mock.spawned or 0) + 1
  local o = Mock.newObject(string.format("f%05x", Mock.spawned), params.type)
  o.setPosition(params.position)
  if params.scale then o.setScale(params.scale) end
  if params.type == "Counter" then
    o.Counter = { setValue = function(v) o.counterValue = v end }
  end
  if params.callback_function then params.callback_function(o) end
  return o
end

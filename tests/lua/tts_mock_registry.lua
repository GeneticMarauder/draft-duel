-- Extra TTS API for the registry samples (core/**/scripts, shared/**/scripts).
-- Load after tts_mock.lua and before Mock.setup(); it only adds to the mock,
-- so the mod's own tests are unaffected.

Global = Global or { getGUID = function() return "-1" end }

-- Waits get ids so Wait.stop can cancel them before Mock.flush runs them.
Mock.cancelled = {}
local nextWaitId = 0

local function queue(fn)
  nextWaitId = nextWaitId + 1
  local id = nextWaitId
  table.insert(Mock.waits, function()
    if not Mock.cancelled[id] then fn() end
  end)
  return id
end

Wait.frames = function(fn) return queue(fn) end
Wait.time = function(fn) return queue(fn) end
-- Time isn't simulated: the condition is checked once, when the queue drains.
Wait.condition = function(fn, condition, timeout, onTimeout)
  return queue(function()
    if condition() then fn() elseif onTimeout then onTimeout() end
  end)
end
Wait.stop = function(id) Mock.cancelled[id] = true end

-- Coroutines run to completion immediately.
startLuaCoroutine = function(owner, name)
  local co = coroutine.create(_G[name])
  while coroutine.status(co) ~= "dead" do
    local ok, err = coroutine.resume(co)
    if not ok then error(err) end
  end
end

-- Objects: tags, button editing, lock state, loading flags.
local baseNewObject = Mock.newObject
function Mock.newObject(guid, kind)
  local o = baseNewObject(guid, kind)
  o.tags = {}
  o.spawning = false
  o.resting = true
  o.addTag = function(t) o.tags[t] = true end
  o.removeTag = function(t) o.tags[t] = nil end
  o.hasTag = function(t) return o.tags[t] == true end
  o.getLock = function() return o.locked end
  o.getButtons = function() return o.buttons end
  o.editButton = function(p)
    local b = o.buttons[(p.index or 0) + 1]
    if b then
      for k, v in pairs(p) do
        if k ~= "index" then b[k] = v end
      end
    end
  end
  return o
end

-- Decks made by Mock.newDeck can be searched like TTS's deck.getObjects().
local baseNewDeck = Mock.newDeck
function Mock.newDeck(guid, count)
  local d = baseNewDeck(guid, count)
  d.getObjects = function()
    local out = {}
    for i, id in ipairs(d.cards) do
      out[i] = { guid = id, index = i - 1, name = "Card " .. id, gm_notes = "" }
    end
    return out
  end
  return d
end

getObjectsWithTag = function(tag)
  local out = {}
  for _, o in pairs(Mock.objects) do
    if o.tags and o.tags[tag] then table.insert(out, o) end
  end
  return out
end

getSeatedPlayers = function()
  local out = {}
  for color, p in pairs(Player) do
    if type(p) == "table" and p.seated then table.insert(out, color) end
  end
  return out
end

printToColor = function(msg, color) table.insert(Mock.messages, color .. ": " .. msg) end
log = function(value) table.insert(Mock.messages, "log: " .. tostring(value)) end

-- spawnObject with counters that can be read back and the rotation kept.
local spawnCount = 0
spawnObject = function(params)
  spawnCount = spawnCount + 1
  local o = Mock.newObject(string.format("7%05x", spawnCount), params.type)
  o.setPosition(params.position)
  if params.rotation then o.setRotation(params.rotation) end
  if params.scale then o.setScale(params.scale) end
  if params.type == "Counter" then
    o.counterValue = 0
    o.Counter = {
      setValue = function(v) o.counterValue = v end,
      getValue = function() return o.counterValue end,
    }
  end
  if params.callback_function then params.callback_function(o) end
  return o
end

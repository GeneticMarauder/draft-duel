--[[ shared.counters-and-tokens :: life_counters.lua
Purpose  : Spawn one named, tagged life counter per seat, read and adjust them from script,
           and remove them at the end of a game.
Attach   : Global
API      : spawnObject (type "Counter"), obj.Counter.setValue / getValue, setName, addTag,
           getObjectsWithTag, destruct
Verified : in-game (draft-duel startGame spawns "<color> life" counters at 20; nextGame removes them)
Use      :
  1. spawnLifeCounters({ White = {x=-14, y=1.5, z=-13}, Red = {x=14, y=1.5, z=13} }, 20)
  2. adjustLife("Red", -3); lifeOf("Red")
  3. removeLifeCounters() between games.
Gotchas  :
  - Counter methods live on obj.Counter, not obj (obj.Counter.setValue(20)).
  - The counter exists in the spawn callback; set its value there, not right after spawnObject.
  - Players can type numbers into counters; read the value, don't cache it.
]]

LIFE_TAG = "life-counter"

local function counterFor(color)
  for _, o in ipairs(getObjectsWithTag(LIFE_TAG)) do
    if o.getName() == color .. " life" then return o end
  end
  return nil
end

-- positions: color -> {x, y, z}; yaw per seat optional (color -> degrees).
function spawnLifeCounters(positions, startValue, yaws)
  for color, pos in pairs(positions) do
    local old = counterFor(color)
    if old then old.destruct() end
    spawnObject({
      type = "Counter",
      position = pos,
      rotation = { x = 0, y = yaws and yaws[color] or 0, z = 0 },
      callback_function = function(counter)
        counter.setName(color .. " life")
        counter.addTag(LIFE_TAG)
        counter.Counter.setValue(startValue or 20)
      end,
    })
  end
end

function lifeOf(color)
  local c = counterFor(color)
  return c and c.Counter.getValue() or nil
end

function adjustLife(color, delta)
  local c = counterFor(color)
  if c == nil then return nil end
  local v = c.Counter.getValue() + delta
  c.Counter.setValue(v)
  return v
end

function removeLifeCounters()
  for _, o in ipairs(getObjectsWithTag(LIFE_TAG)) do o.destruct() end
end

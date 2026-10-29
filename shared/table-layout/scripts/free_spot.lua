--[[ shared.table-layout :: free_spot.lua
Purpose  : Find the nearest empty card-sized spot near an anchor, so spawned or returned cards
           (tokens, revealed cards, counters) never land on top of others.
Attach   : Global
API      : getObjects, getBounds, getPosition, obj.type
Verified : in-game (generalised from draft-duel's tokenSpot; the old fixed fan-out piled
           tokens onto neighbouring cards, this search fixed it)
Use      :
  1. local pos = freeSpotNear({ x = ax, z = az }, { w = 2.2, h = 3.06, toward = 1, rightSign = -1 })
     toward    : +1 or -1, the z direction rows grow in (toward the owner's hand)
     rightSign : +1 or -1, the world x direction of the owner's right
  2. Optionally bound the search with zMin/zMax (absolute z, measured toward `toward`) and xMax.
  3. Spawn or move your object to pos.
Gotchas  :
  - Checks loose Cards, Decks and Counters only; add types (Tile, Bag) to BLOCKING if needed.
  - Bounds follow rotation, so tapped cards count as wide.
  - Objects still flying (just spawned) report their current position; space spawns a frame apart.
]]

BLOCKING = { Card = true, Deck = true, Counter = true }
SPOT_GAP = 0.3     -- clear space kept around the new card
FELT_Y = 0.96

-- Candidate offsets, in card steps: along the row to the right, then the
-- left, then the next row out. Cheaper = tried first.
local OFFSETS = {}
for dv = 0, 3 do
  for du = -6, 6 do
    if du ~= 0 or dv ~= 0 then
      local cost = (du > 0 and du or -du + 1.5) + dv * 3
      table.insert(OFFSETS, { du = du, dv = dv, cost = cost })
    end
  end
end
table.sort(OFFSETS, function(a, b) return a.cost < b.cost end)

local function boundsSize(obj)
  local ok, b = pcall(function() return obj.getBounds() end)
  if ok and b and b.size then return b.size end
  return nil
end

-- True when a w x h spot centred at (x, z) touches no blocking object but `ignore`.
function spotIsFree(x, z, w, h, ignore)
  for _, o in ipairs(getObjects()) do
    if o ~= ignore and BLOCKING[o.type] then
      local p = o.getPosition()
      local b = boundsSize(o) or { x = w, z = h }
      if math.abs(p.x - x) < (b.x + w) / 2 + SPOT_GAP - 0.01
          and math.abs(p.z - z) < (b.z + h) / 2 + SPOT_GAP - 0.01 then
        return false
      end
    end
  end
  return true
end

-- opts: w, h (card size), toward (+1/-1), rightSign (+1/-1), zMin, zMax (distances
-- from the middle line measured toward `toward`), xMax (|x| limit), ignore (object).
-- Returns {x, y, z}; if everything is full, the spot just right of the anchor.
function freeSpotNear(anchor, opts)
  local w, h = opts.w or 2.2, opts.h or 3.06
  local toward, right = opts.toward or 1, opts.rightSign or 1
  local su, sv = w + SPOT_GAP, h + SPOT_GAP
  for _, off in ipairs(OFFSETS) do
    local x = anchor.x + right * off.du * su
    local z = anchor.z + toward * off.dv * sv
    local depth = z * toward
    local inside = (opts.xMax == nil or math.abs(x) <= opts.xMax)
      and (opts.zMin == nil or depth >= opts.zMin)
      and (opts.zMax == nil or depth <= opts.zMax)
    if inside and spotIsFree(x, z, w, h, opts.ignore) then
      return { x = x, y = FELT_Y + 0.3, z = z }
    end
  end
  return { x = anchor.x + right * su, y = FELT_Y + 1, z = anchor.z }
end

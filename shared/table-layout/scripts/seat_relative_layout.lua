--[[ shared.table-layout :: seat_relative_layout.lua
Purpose  : Lay things out once, in seat-relative coordinates, and have them mirror correctly
           for the opposite seat: measure card size and felt height, then place rows and grids.
Attach   : Global
API      : getObjectFromGUID, getBounds, getPosition, Tables.getTableObject, setPosition, setRotation
Verified : in-game (draft-duel computeLayout / packPosition / slotPosition / ownerU / worldX)
Use      :
  1. measureLayout(REFERENCE_GUID) once objects exist (e.g. a few frames after onLoad).
  2. Think in (u, v) per seat: u = to the seat's right, v = away from the middle toward the seat.
     toWorld("White", u, v) gives world {x, y, z}; rowPosition / gridPosition build on it.
  3. Rotate cards with seatYaw(color) so they read upright for their owner.
Gotchas  :
  - Two-seat mirror: the first seat sits at -z and faces +z, so its right is world +x; for
    the other seat both flip. Never hard-code world x/z per seat; go through toWorld.
  - Table_RPG felt top is y ~ 0.96, bounds 64 x 43 (verified); other tables differ: measure.
  - Place cards slightly above the felt (+0.2) or physics pushes them through/away.
  - getBounds follows rotation: a tapped card is wider than tall.
]]

SEATS = { "White", "Red" }
DEFAULT_CARD = { w = 2.2, h = 3.06 }   -- a standard card at scale 1, in table units
DEFAULT_FELT_Y = 0.96                  -- Table_RPG

L = nil  -- { w, h, feltY, tableW, tableD } after measureLayout

local function boundsSize(obj)
  if obj == nil then return nil end
  local ok, b = pcall(function() return obj.getBounds() end)
  if ok and b and b.size then return b.size end
  return nil
end

-- Card size and felt height from a reference deck/card lying on the felt;
-- table size from the table object. Falls back to Table_RPG numbers.
function measureLayout(referenceGuid)
  local ref = referenceGuid and getObjectFromGUID(referenceGuid) or nil
  local size = boundsSize(ref)
  local w, h, feltY = DEFAULT_CARD.w, DEFAULT_CARD.h, DEFAULT_FELT_Y
  if size and size.x > 0.5 and size.z > 0.5 then w, h = size.x, size.z end
  if ref and size then feltY = ref.getPosition().y - size.y / 2 end
  local tw, td = 64, 43
  local t = Tables and Tables.getTableObject and Tables.getTableObject() or nil
  local tb = boundsSize(t)
  if tb then tw, td = tb.x, tb.z end
  L = { w = w, h = h, feltY = feltY, tableW = tw, tableD = td }
  return L
end

-- -1 for the first seat (z < 0), +1 for the second.
function sideSign(color)
  if color == SEATS[1] then return -1 end
  return 1
end

-- Seat-relative (u to the seat's right, v from the middle line toward the seat) -> world.
function toWorld(color, u, v, lift)
  local s = sideSign(color)
  return { x = -s * u, y = (L and L.feltY or DEFAULT_FELT_Y) + (lift or 0.2), z = s * v }
end

-- World -> seat-relative u (how far to the seat's right a world x is).
function ownerU(color, x)
  return -sideSign(color) * x
end

-- Item i of n in a row centred on the seat's axis, `v` from the middle.
function rowPosition(color, i, n, v, scale, gap)
  local step = (L.w * (scale or 1)) + (gap or 0.3)
  return toWorld(color, (i - (n + 1) / 2) * step, v)
end

-- Slot `slot` (1-based) of a cols-wide grid starting `v0` from the middle,
-- filling left-to-right then away from the middle.
function gridPosition(color, slot, cols, v0, scale)
  local i = slot - 1
  local col = i % cols
  local row = math.floor(i / cols)
  local dx = L.w * (scale or 1) * 1.05
  local dz = L.h * (scale or 1) * 1.05
  local u = (col - (cols - 1) / 2) * dx
  return toWorld(color, u, v0 + row * dz)
end

-- Yaw that makes a face-up card read upright for its seat.
function seatYaw(color)
  if sideSign(color) < 0 then return 180 end
  return 0
end

-- Moves and rotates an object onto a seat-relative spot, face up.
function placeFor(obj, color, pos, scale)
  if obj == nil then return end
  if scale then obj.setScale({ x = scale, y = 1, z = scale }) end
  obj.setRotation({ x = 0, y = seatYaw(color), z = 0 })
  obj.setPosition(pos)
end

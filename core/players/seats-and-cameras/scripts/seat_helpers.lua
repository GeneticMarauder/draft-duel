--[[ core.players.seats-and-cameras :: seat_helpers.lua
Purpose  : Seat-aware basics: who is seated, everyone-but-me lists for privacy, messages to one
           seat, which way a seat faces, what's in a hand, and pointing a player's camera.
Attach   : Global
API      : Player[color], player.seated, player.host, getHandTransform, getHandObjects, lookAt,
           broadcastToColor, printToAll, getSeatedPlayers, onPlayerChangeColor
Verified : in-game (same helpers as draft-duel's say / othersThan / seatYaw / frameCamera)
Use      :
  1. Set SEATS to the colors your game uses (each needs a hand zone in the save).
  2. say(color, "Your turn"), othersThan(color) for setInvisibleTo, seatYaw(color) for card rotation,
     frameCamera(color, {x=0,y=1,z=-8}) to point their camera.
Gotchas  :
  - Player[color] exists for every color, seated or not: check .seated before messaging.
  - Hidden/invisible lists must include *every* other color, spectators ("Grey") and
    unused seats too, or someone who switches seat can see the card.
  - getHandTransform() is nil when the color has no hand zone.
  - lookAt is ignored by players who are moving their camera at that moment.
]]

SEATS = { "White", "Red" }
ALL_COLORS = { "White", "Brown", "Red", "Orange", "Yellow", "Green", "Teal", "Blue",
               "Purple", "Pink", "Grey", "Black" }
CAMERA_PITCH = 60
CAMERA_DISTANCE = 23

local function inList(list, value)
  for _, v in ipairs(list) do
    if v == value then return true end
  end
  return false
end

-- True for a player color sitting in one of our seats.
function isSeat(color)
  return inList(SEATS, color)
end

function seatedSeats()
  local out = {}
  for _, c in ipairs(SEATS) do
    if Player[c] and Player[c].seated then table.insert(out, c) end
  end
  return out
end

-- Every color except `owner` (pass to setInvisibleTo / setHiddenFrom).
function othersThan(owner)
  local out = {}
  for _, c in ipairs(ALL_COLORS) do
    if c ~= owner then table.insert(out, c) end
  end
  return out
end

-- A private message to one seat, or a labelled public one if nobody sits there.
function say(color, msg, tint)
  tint = tint or { 1, 0.6, 0.4 }
  if Player[color] and Player[color].seated then
    broadcastToColor(msg, color, tint)
  else
    printToAll("[" .. color .. "] " .. msg, tint)
  end
end

-- Yaw that makes a face-up card read upright for a seat (from its hand zone).
function seatYaw(color)
  local t = Player[color] and Player[color].getHandTransform() or nil
  if t and t.rotation then return (t.rotation.y + 180) % 360 end
  return 0
end

-- -1 for the first seat's half of the table (z < 0), +1 for the second's.
function sideSign(color)
  if color == SEATS[1] then return -1 end
  return 1
end

function handCards(color)
  local out = {}
  for _, o in ipairs(Player[color].getHandObjects() or {}) do
    if o.type == "Card" then table.insert(out, o) end
  end
  return out
end

-- Points a seated player's camera at `target`, from behind their own seat.
function frameCamera(color, target, distance)
  if not isSeat(color) or not Player[color].seated then return end
  local t = Player[color].getHandTransform()
  Player[color].lookAt({
    position = target,
    pitch = CAMERA_PITCH,
    yaw = t and t.rotation and t.rotation.y or 0,
    distance = distance or CAMERA_DISTANCE,
  })
end

-- Reframe whoever just sat down (after TTS finishes moving them).
function onPlayerChangeColor(color)
  if not isSeat(color) then return end
  Wait.frames(function()
    frameCamera(color, { x = 0, y = 1, z = sideSign(color) * 6 })
  end, 5)
end

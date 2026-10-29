--[[ shared.card-privacy :: private_cards.lua
Purpose  : Keep cards private to one player on the open table — opponents see either the card
           back (hidden) or nothing at all (invisible) — and keep them private as they are
           picked up, moved, flipped and reloaded.
Attach   : Global
API      : setHiddenFrom, setInvisibleTo, onObjectPickUp, onObjectDrop, onObjectStateChange,
           onLoad, getObjectFromGUID, Wait.frames
Verified : in-game (draft-duel: pack cards hidden, picks and sideboards invisible)
Use      :
  1. Paste into Global (merge handlers with existing ones).
  2. makePrivate(card, "White", "invisible") or makePrivate(card, "White", "hidden").
     makePublic(card) to reveal.
  3. Privacy is tracked by GUID in PRIVATE and saved, so it comes back after a reload.
Gotchas  :
  - hidden: others see the card's back (as with a hand). invisible: others see nothing.
  - TTS can drop an object's lists when it is picked up, moved or flipped: re-apply on
    every pickup/drop/state change, and again a few frames later.
  - Hidden zones look like solid colored blocks and ignore their tint; per-card privacy is nicer.
  - Lists must contain every other color, spectators included (see othersThan).
  - Merge PRIVATE into your own onSave if your script already has one.
]]

ALL_COLORS = { "White", "Brown", "Red", "Orange", "Yellow", "Green", "Teal", "Blue",
               "Purple", "Pink", "Grey", "Black" }
REAPPLY_FRAMES = 3

PRIVATE = {}  -- guid -> { owner = color, mode = "hidden" | "invisible" }

local function othersThan(owner)
  local out = {}
  for _, c in ipairs(ALL_COLORS) do
    if c ~= owner then table.insert(out, c) end
  end
  return out
end

local function apply(obj, rule)
  if obj == nil then return end
  if rule == nil then
    obj.setHiddenFrom({})
    obj.setInvisibleTo({})
  elseif rule.mode == "hidden" then
    obj.setInvisibleTo({})
    obj.setHiddenFrom(othersThan(rule.owner))
  else
    obj.setHiddenFrom({})
    obj.setInvisibleTo(othersThan(rule.owner))
  end
end

-- Apply now and again after TTS has finished handling the pickup/drop/flip.
function rehide(obj)
  if obj == nil then return end
  local rule = PRIVATE[obj.getGUID()]
  if rule == nil then return end
  apply(obj, rule)
  Wait.frames(function() if obj ~= nil then apply(obj, PRIVATE[obj.getGUID()]) end end, REAPPLY_FRAMES)
end

function makePrivate(obj, owner, mode)
  PRIVATE[obj.getGUID()] = { owner = owner, mode = mode or "invisible" }
  rehide(obj)
end

function makePublic(obj)
  PRIVATE[obj.getGUID()] = nil
  apply(obj, nil)
end

function rehideAll()
  for guid, rule in pairs(PRIVATE) do
    local obj = getObjectFromGUID(guid)
    if obj ~= nil then apply(obj, rule) else PRIVATE[guid] = nil end
  end
end

function onObjectPickUp(color, obj) rehide(obj) end
function onObjectDrop(color, obj) rehide(obj) end

-- A flipped multi-state card is a new object with a new GUID: carry the rule over.
function onObjectStateChange(obj, oldGuid)
  if PRIVATE[oldGuid] then
    PRIVATE[obj.getGUID()] = PRIVATE[oldGuid]
    PRIVATE[oldGuid] = nil
  end
  rehide(obj)
end

function onSave()
  return JSON.encode({ private = PRIVATE })
end

function onLoad(savedState)
  if savedState and savedState ~= "" then
    local ok, data = pcall(function() return JSON.decode(savedState) end)
    if ok and type(data) == "table" and type(data.private) == "table" then PRIVATE = data.private end
  end
  -- Visibility isn't saved by TTS; restore it once objects exist.
  Wait.frames(rehideAll, 10)
end

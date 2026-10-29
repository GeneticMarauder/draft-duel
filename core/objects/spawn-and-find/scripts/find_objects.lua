--[[ core.objects.spawn-and-find :: find_objects.lua
Purpose  : Find objects on the table by GUID, type, name, tag or a GMNotes field, and find
           cards inside a deck without taking them out.
Attach   : Global
API      : getObjectFromGUID, getObjects, getObjectsWithTag, obj.type, getName, getGMNotes,
           hasTag, addTag, deck.getObjects
Verified : docs-only (GUID / type / GMNotes lookups are verified in draft-duel)
Use      :
  1. Paste and call the finder you need, e.g. findAll({ type = "Card", notes = { token = "Treasure" } }).
  2. Prefer tags for objects you create: obj.addTag("mymod:life") then byTag("mymod:life").
Gotchas  :
  - getObjects() returns only loose objects; cards inside a deck are not objects until taken out.
  - getObjectFromGUID returns nil for destroyed objects and for cards inside containers.
  - Names aren't unique and players can rename things; GUIDs and tags are the stable keys.
  - obj.type is "Card", "Deck", "Bag", "Counter", "Tile", "Hand", "Scripting", ...
    (obj.tag is the deprecated name for the same thing).
]]

local function notesOf(obj)
  local raw = obj.getGMNotes and obj.getGMNotes() or ""
  if raw == "" then return {} end
  local ok, t = pcall(function() return JSON.decode(raw) end)
  if ok and type(t) == "table" then return t end
  return {}
end

-- An object by GUID, or nil if it is gone (never errors on a nil GUID).
function byGuid(guid)
  if guid == nil then return nil end
  return getObjectFromGUID(guid)
end

-- Every loose object with this tag. Tags are saved with the object.
function byTag(tag)
  if getObjectsWithTag then return getObjectsWithTag(tag) end
  local out = {}
  for _, o in ipairs(getObjects()) do
    if o.hasTag and o.hasTag(tag) then table.insert(out, o) end
  end
  return out
end

-- Loose objects matching every given filter:
--   type = "Card", name = "Treasure", notes = { token = "Treasure" }, where = function(o) ... end
function findAll(filter)
  local out = {}
  for _, o in ipairs(getObjects()) do
    local ok = true
    if filter.type and o.type ~= filter.type then ok = false end
    if ok and filter.name and o.getName() ~= filter.name then ok = false end
    if ok and filter.notes then
      local n = notesOf(o)
      for k, v in pairs(filter.notes) do
        if n[k] ~= v then ok = false end
      end
    end
    if ok and filter.where and not filter.where(o) then ok = false end
    if ok then table.insert(out, o) end
  end
  return out
end

function findFirst(filter)
  return findAll(filter)[1]
end

-- Entries for cards inside a deck/bag whose name matches. Each entry has
-- guid, name, index, gm_notes, description; take one out with
-- deck.takeObject({ guid = entry.guid, position = ... }).
function findInContainer(container, name)
  local out = {}
  for _, entry in ipairs(container.getObjects() or {}) do
    if entry.name == name then table.insert(out, entry) end
  end
  return out
end

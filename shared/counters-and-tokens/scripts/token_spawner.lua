--[[ shared.counters-and-tokens :: token_spawner.lua
Purpose  : Let cards create tokens from their right-click menu: a maker-id -> token-labels table,
           spawnable token data, unique tokens that move instead of duplicating, and placement
           beside the source card.
Attach   : Global
API      : addContextMenuItem, clearContextMenu, spawnObjectData, getGMNotes, getObjects,
           setPosition, setRotation, onObjectSpawn, onObjectLeaveContainer, onLoad, JSON
Verified : in-game (condensed from draft-duel's TOKENS_JSON / addPlayMenu / createToken)
Use      :
  1. Fill TOKENS.tokens (label -> spawnObjectData data) and TOKENS.makers (card id -> labels).
     In a built mod, generate both in Python and embed them as a JSON string.
  2. Card GMNotes must hold {"id": "..."} matching TOKENS.makers keys.
  3. Replace placeBeside with free_spot.lua's freeSpotNear for crowded tables.
Gotchas  :
  - Token GMNotes should not carry an "id", so card-only logic (deck building) ignores tokens.
  - Menus vanish when a card enters a deck and on reload: they're re-added from the events below.
  - Unique tokens (a monarch marker, day/night) must be found and moved, not spawned twice.
]]

TOKENS = {
  tokens = {
    -- label -> save-format object data (see core.objects.spawn-and-find spawn_card_from_data.lua)
    ["Treasure"] = { Name = "Card", Nickname = "Treasure", GMNotes = '{"token":"Treasure"}' },
  },
  makers = {
    -- card id (from GMNotes) -> list of token labels it makes
    ["example-card-id"] = { "Treasure" },
  },
}
UNIQUE_TOKENS = {}         -- e.g. { ["The Monarch"] = true }
TOKEN_OFFSET_X = 2.6       -- beside the source card

local function notesOf(obj)
  local ok, t = pcall(function() return JSON.decode(obj.getGMNotes() or "") end)
  if ok and type(t) == "table" then return t end
  return {}
end

local function findToken(label)
  for _, o in ipairs(getObjects()) do
    if o.type == "Card" and notesOf(o).token == label then return o end
  end
  return nil
end

-- Simple placement: just right of the source card. Use freeSpotNear for real tables.
function placeBeside(source)
  local p = source.getPosition()
  return { x = p.x + TOKEN_OFFSET_X, y = p.y + 0.5, z = p.z }
end

function createToken(color, label, source)
  local data = TOKENS.tokens[label]
  if data == nil then return nil end
  local pos = placeBeside(source)
  local rot = source.getRotation()
  if UNIQUE_TOKENS[label] then
    local existing = findToken(label)
    if existing then
      existing.setPosition(pos)
      existing.setRotation({ x = 0, y = rot.y, z = 0 })
      broadcastToAll(color .. " takes " .. label .. ".", { 0.6, 0.85, 1 })
      return existing
    end
  end
  return spawnObjectData({ data = data, position = pos, rotation = { x = 0, y = rot.y, z = 0 } })
end

function addTokenMenu(obj)
  if obj == nil or obj.type ~= "Card" then return end
  local labels = TOKENS.makers[notesOf(obj).id or ""]
  if labels == nil then return end
  obj.clearContextMenu()
  for _, label in ipairs(labels) do
    obj.addContextMenuItem("Create " .. label, function(color) createToken(color, label, obj) end)
  end
end

function onObjectSpawn(obj)
  Wait.frames(function() addTokenMenu(obj) end, 1)
end

function onObjectLeaveContainer(container, obj)
  onObjectSpawn(obj)
end

function onLoad(savedState)
  Wait.frames(function()
    for _, o in ipairs(getObjects()) do addTokenMenu(o) end
  end, 5)
end

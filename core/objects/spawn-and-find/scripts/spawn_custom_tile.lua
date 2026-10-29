--[[ core.objects.spawn-and-find :: spawn_custom_tile.lua
Purpose  : Spawn an image as a flat, locked, non-interactable tile (playmat, board, banner).
Attach   : Global
API      : spawnObject, setCustomObject, setLock, interactable, setName, getObjectFromGUID, destruct
Verified : in-game (draft-duel playmats)
Use      :
  1. Host the image somewhere TTS can download it (see shared.custom-assets).
  2. local tile = spawnImageTile({ url = URL, position = {x=0, y=1, z=-9.5}, depth = 16 })
  3. Keep tile.getGUID() in your saved state; call fitTile again in onLoad.
Gotchas  :
  - Call setCustomObject in the *same frame* as spawnObject. Later, it needs obj.reload().
  - spawnObjectData with hand-written Custom_Tile data failed to load in TTS; use this instead.
  - A tile is 2 units deep at scale 1; its width follows the image's aspect ratio.
  - interactable isn't saved: set it again after every load.
]]

TILE_THICKNESS = 0.1

-- Locks the tile and makes it ignore clicks so cards can be played on top.
local function fitTile(tile, position, scale)
  if tile == nil then return end
  tile.setScale({ x = scale, y = 1, z = scale })
  tile.setPosition(position)
  tile.setLock(true)
  tile.interactable = false
end

-- opts: url, position, depth (table units front-to-back), yaw (degrees), name.
-- Returns the tile object (still loading its image).
function spawnImageTile(opts)
  local scale = (opts.depth or 2) / 2
  local pos = opts.position
  local tile = spawnObject({
    type = "Custom_Tile",
    position = pos,
    rotation = { x = 0, y = opts.yaw or 0, z = 0 },
    scale = { x = scale, y = 1, z = scale },
    sound = false,
    callback_function = function(o)
      if opts.name then o.setName(opts.name) end
      -- The callback runs once the object exists; physics may still nudge it.
      Wait.frames(function() fitTile(o, pos, scale) end, 2)
    end,
  })
  if tile == nil then return nil end
  tile.setCustomObject({
    image = opts.url,
    type = 0,            -- 0 box, 1 hex, 2 circle, 3 rounded
    thickness = TILE_THICKNESS,
    stackable = false,
    stretch = true,      -- fill the tile instead of keeping square pixels
  })
  tile.setLock(true)
  return tile
end

-- Replaces whatever tile `oldGuid` points at; returns the new tile's GUID.
function replaceImageTile(oldGuid, opts)
  local old = oldGuid and getObjectFromGUID(oldGuid) or nil
  if old ~= nil then old.destruct() end
  local tile = spawnImageTile(opts)
  return tile and tile.getGUID() or nil
end

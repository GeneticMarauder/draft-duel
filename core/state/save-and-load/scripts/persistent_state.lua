--[[ core.state.save-and-load :: persistent_state.lua
Purpose  : Keep script state across save, load, rewind and "Save & Play" with versioned JSON,
           safe defaults for keys older saves don't have, and a hook to rebuild what TTS forgets.
Attach   : Global (works unchanged on an object script: onSave/onLoad are per script)
API      : onSave, onLoad, JSON.encode, JSON.decode, getObjectFromGUID, Wait.frames
Verified : in-game (same shape as draft-duel's table.lua onSave/onLoad)
Use      :
  1. Paste into your script. Put every persistent field in DEFAULT_STATE.
  2. Read and write state.<field> anywhere; TTS calls onSave on save/autosave/rewind points.
  3. Rebuild buttons, menus, visibility and interactable in rebuildTransient().
  4. Store objects by GUID (strings), never object references.
Gotchas  :
  - TTS does not save buttons, context menus, setInvisibleTo/setHiddenFrom or interactable.
  - onLoad runs before objects are fully ready: rebuild after a few frames.
  - JSON turns sparse arrays into objects and empty tables into []; keep tables simple.
  - A rename of a field breaks old saves unless you migrate it in migrate().
]]

STATE_VERSION = 2

-- Every persistent field with its default. A save made before a field existed
-- gets the default instead of nil.
DEFAULT_STATE = {
  version = STATE_VERSION,
  round = 1,
  scores = {},       -- color -> number
  markerGuid = nil,  -- GUID of an object this script owns
}

state = nil

local function copy(t)
  if type(t) ~= "table" then return t end
  local out = {}
  for k, v in pairs(t) do out[k] = copy(v) end
  return out
end

-- Fill keys missing from `loaded` with defaults (one level deep is enough for
-- most state; nested tables are taken whole from whichever side has them).
local function withDefaults(loaded)
  local out = copy(DEFAULT_STATE)
  for k, v in pairs(loaded or {}) do out[k] = v end
  return out
end

-- Upgrade older saves. Each step moves one version forward.
local function migrate(s)
  if (s.version or 1) < 2 then
    -- v1 called it "turn"; v2 calls it "round".
    s.round = s.turn or s.round
    s.turn = nil
    s.version = 2
  end
  return s
end

local function decode(saved)
  if saved == nil or saved == "" then return nil end
  local ok, data = pcall(function() return JSON.decode(saved) end)
  if ok and type(data) == "table" then return data end
  print("Saved state could not be read; starting fresh.")
  return nil
end

-- Everything TTS forgets across a reload goes here.
function rebuildTransient()
  local marker = state.markerGuid and getObjectFromGUID(state.markerGuid) or nil
  if state.markerGuid and marker == nil then
    state.markerGuid = nil -- the object was deleted while the save was closed
  end
  if marker ~= nil then
    marker.interactable = false
    marker.clearButtons()
    marker.createButton({
      click_function = "onMarkerClicked", function_owner = Global,
      label = "Round " .. state.round, position = { x = 0, y = 0.3, z = 0 },
      width = 900, height = 300, font_size = 160,
    })
  end
end

function onMarkerClicked(obj, playerColor, altClick)
  state.round = state.round + (altClick and -1 or 1)
  rebuildTransient()
end

function onSave()
  return JSON.encode(state)
end

function onLoad(savedState)
  state = withDefaults(migrate(decode(savedState) or copy(DEFAULT_STATE)))
  -- Give TTS a few frames to finish spawning saved objects before touching them.
  Wait.frames(rebuildTransient, 5)
end

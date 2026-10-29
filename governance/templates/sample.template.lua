--[[ core.area.skill-name :: sample_name.lua
Purpose  : One line: what this gives you.
Attach   : Global | any object (say what to change for an object script)
API      : the TTS functions and events this uses
Verified : docs-only
Use      :
  1. Paste into the Global script.
  2. Adjust the constants below.
Gotchas  :
  - The trap someone will hit first.
]]

-- Configuration ------------------------------------------------------------

EXAMPLE_SETTING = 1

-- Helpers (local, so pasting several samples into one script can't collide) --

local function helper()
  return EXAMPLE_SETTING
end

-- TTS entry points (global, so TTS can find them) ---------------------------

function onLoad(savedState)
  helper()
end

--[[ core.events.event-hooks :: event_logger.lua
Purpose  : Log which TTS events fire, in what order, with what arguments, so you can see what
           the game actually does when a player draws, drops, flips or merges something.
Attach   : Global of a *scratch* save (it defines handlers that would replace your mod's)
API      : onObjectSpawn, onObjectDestroy, onObjectPickUp, onObjectDrop, onObjectRotate,
           onObjectStateChange, onObjectEnterContainer, onObjectLeaveContainer,
           tryObjectEnterContainer, onPlayerChangeColor, onChat, log, printToAll
Verified : docs-only
Use      :
  1. Paste into the Global script of a test save (not your mod).
  2. Type !events on / !events off in chat; output goes to chat and the log.
  3. Do the thing you're unsure about and read the sequence.
Gotchas  :
  - Defining a handler replaces any other with the same name in the script.
  - onObjectHover is left out on purpose: it fires constantly.
]]

EVENT_LOG_ON = true

local function describe(obj)
  if obj == nil then return "nil" end
  return string.format("%s[%s] '%s'", obj.type or "?", obj.getGUID(), obj.getName() or "")
end

local function report(name, ...)
  if not EVENT_LOG_ON then return end
  local parts = {}
  for _, v in ipairs({ ... }) do
    if type(v) == "table" or type(v) == "userdata" then
      local ok, s = pcall(describe, v)
      table.insert(parts, ok and s or tostring(v))
    else
      table.insert(parts, tostring(v))
    end
  end
  local line = name .. "(" .. table.concat(parts, ", ") .. ")"
  log(line)
  printToAll(line, { 0.7, 0.7, 0.7 })
end

function onObjectSpawn(obj) report("onObjectSpawn", obj) end
function onObjectDestroy(obj) report("onObjectDestroy", obj) end
function onObjectPickUp(color, obj) report("onObjectPickUp", color, obj) end
function onObjectDrop(color, obj) report("onObjectDrop", color, obj) end
function onObjectRotate(obj, spin, flip, color, oldSpin, oldFlip)
  report("onObjectRotate", obj, spin, flip, color, oldSpin, oldFlip)
end
function onObjectStateChange(obj, oldGuid) report("onObjectStateChange", obj, oldGuid) end
function onObjectEnterContainer(container, obj) report("onObjectEnterContainer", container, obj) end
function onObjectLeaveContainer(container, obj) report("onObjectLeaveContainer", container, obj) end
function tryObjectEnterContainer(container, obj)
  report("tryObjectEnterContainer", container, obj)
  return true
end
function onPlayerChangeColor(color) report("onPlayerChangeColor", color) end

function onChat(message, player)
  local mode = message:match("^!events%s+(%a+)$")
  if mode == "on" or mode == "off" then
    EVENT_LOG_ON = mode == "on"
    printToAll("Event log " .. mode)
    return false
  end
end

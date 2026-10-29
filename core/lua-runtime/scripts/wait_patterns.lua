--[[ core.lua-runtime :: wait_patterns.lua
Purpose  : Run code later without freezing the game: after N frames, after N seconds,
           repeatedly, when a condition becomes true, or as a step-by-step coroutine.
Attach   : Global (on an object script, pass self instead of Global to startLuaCoroutine)
API      : Wait.frames, Wait.time, Wait.condition, Wait.stop, startLuaCoroutine, coroutine.yield
Verified : docs-only (Wait.frames / Wait.time are verified in draft-duel)
Use      :
  1. Paste the helpers you need into your script.
  2. afterFrames(fn, 2)   -- let TTS finish its own handling of a spawn/drop first
     every(fn, 1, 5)      -- five times, a second apart; returns an id for Wait.stop
     whenReady(obj, fn)   -- once a spawned object has finished loading
     runSteps({fn1, fn2}) -- one step per frame, for long loops that would stall a frame
Gotchas  :
  - Anything captured in a callback may be destroyed by the time it runs: nil-check it.
  - Wait.time's third argument is the repeat count; -1 repeats forever (keep the id!).
  - A coroutine started by startLuaCoroutine must be a *global* function and return 1.
  - Nothing here survives a save/load: re-schedule from onLoad if it matters.
]]

-- Run fn after `frames` frames (default 1). TTS often needs a frame or two
-- before a freshly spawned/dropped object reports its final state.
local function afterFrames(fn, frames)
  return Wait.frames(fn, frames or 1)
end

-- Run fn every `seconds`, `times` times (-1 = forever). Returns the Wait id.
local function every(fn, seconds, times)
  return Wait.time(fn, seconds, times or -1)
end

-- Run fn(obj) once obj has finished spawning/loading, or onTimeout() after
-- `timeout` seconds. obj.spawning stays true until TTS has finished loading
-- the object; use obj.resting instead to wait for physics to settle.
local function whenReady(obj, fn, timeout, onTimeout)
  return Wait.condition(
    function() if obj ~= nil then fn(obj) end end,
    function() return obj == nil or not obj.spawning end,
    timeout or 10,
    onTimeout or function() end
  )
end

-- Cancel a pending Wait (safe to call with nil).
local function cancel(id)
  if id ~= nil then Wait.stop(id) end
end

-- Coroutines: run a list of functions, one per frame, so a long job (laying
-- out 100 cards, say) doesn't stall a single frame. TTS resumes the coroutine
-- every frame until the function returns.
STEP_QUEUE = {}

function runStepQueue()
  while #STEP_QUEUE > 0 do
    local step = table.remove(STEP_QUEUE, 1)
    step()
    coroutine.yield(0)
  end
  return 1 -- TTS requires coroutine functions to return 1
end

local function runSteps(steps)
  for _, s in ipairs(steps) do table.insert(STEP_QUEUE, s) end
  startLuaCoroutine(Global, "runStepQueue")
end

-- Example: a countdown broadcast that can be cancelled.
local countdownId = nil

function startCountdown(seconds)
  cancel(countdownId)
  local left = seconds
  countdownId = every(function()
    left = left - 1
    if left > 0 then
      broadcastToAll(left .. "...")
    else
      broadcastToAll("Go!")
      countdownId = nil
    end
  end, 1, seconds)
end

function onLoad(savedState)
  afterFrames(function() print("Script loaded; objects have had a frame to settle.") end, 2)
end

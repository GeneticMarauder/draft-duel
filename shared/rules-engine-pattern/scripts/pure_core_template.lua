--[[ shared.rules-engine-pattern :: pure_core_template.lua
Purpose  : Template for splitting a game into a pure rules engine (no TTS calls, fully testable,
           serializable) and a thin TTS adapter that executes the engine's actions.
Attach   : Global (both halves in one script, or engine first + adapter after, as the builder does)
API      : engine: none. adapter: getObjectFromGUID, broadcastToAll, JSON, onSave, onLoad
Verified : in-game (the shape of draft-duel's draft_core.lua + table.lua)
Use      :
  1. Rename TurnCore, fill in the rules in :act(); keep it free of TTS calls.
  2. Every engine method returns a list of *actions* (plain tables) or nil, err.
  3. The adapter's runActions() turns actions into TTS calls; onSave stores core:serialize().
  4. Test the engine directly from Python (no mock needed), the adapter with the mock.
Gotchas  :
  - Store GUIDs/ids in the engine, never TTS objects: it must serialize to JSON.
  - Keep randomness injectable (pass a random function) so tests are deterministic.
  - Rejected moves return nil, reason: the adapter tells the player why.
]]

-- ======================================================== engine (pure Lua)

TurnCore = {}
TurnCore.__index = TurnCore

-- opts.players: list of colors; opts.rounds: how many rounds; opts.first: starting color.
function TurnCore.new(opts)
  local self = setmetatable({}, TurnCore)
  self.players = opts.players
  self.rounds = opts.rounds or 3
  self.round = 1
  self.turn = 1                       -- index into players
  self.scores = {}
  for _, p in ipairs(self.players) do self.scores[p] = 0 end
  if opts.first then
    for i, p in ipairs(self.players) do
      if p == opts.first then self.turn = i end
    end
  end
  self.finished = false
  return self
end

function TurnCore:current()
  return self.players[self.turn]
end

-- The one move in this toy game: the current player scores `points`.
-- Returns actions, or nil + reason when the move is illegal.
function TurnCore:act(color, points)
  if self.finished then return nil, "the game is over" end
  if color ~= self:current() then return nil, "it is " .. self:current() .. "'s turn" end
  if type(points) ~= "number" or points < 0 then return nil, "invalid points" end
  self.scores[color] = self.scores[color] + points
  local actions = { { type = "scored", color = color, points = points, total = self.scores[color] } }
  self.turn = self.turn % #self.players + 1
  if self.turn == 1 then
    self.round = self.round + 1
    if self.round > self.rounds then
      self.finished = true
      table.insert(actions, { type = "finished", scores = self.scores })
      return actions
    end
    table.insert(actions, { type = "round", round = self.round })
  end
  table.insert(actions, { type = "prompt", color = self:current() })
  return actions
end

function TurnCore:serialize()
  return { players = self.players, rounds = self.rounds, round = self.round, turn = self.turn,
           scores = self.scores, finished = self.finished }
end

function TurnCore.restore(t)
  local self = setmetatable({}, TurnCore)
  for k, v in pairs(t) do self[k] = v end
  return self
end

-- ======================================================== adapter (TTS)

core = nil

function runActions(actions)
  for _, a in ipairs(actions or {}) do
    if a.type == "scored" then
      broadcastToAll(a.color .. " scores " .. a.points .. " (total " .. a.total .. ")")
    elseif a.type == "round" then
      broadcastToAll("Round " .. a.round)
    elseif a.type == "prompt" then
      broadcastToColor("Your turn", a.color, { 1, 0.8, 0.3 })
    elseif a.type == "finished" then
      broadcastToAll("Game over")
    end
  end
end

-- Entry point from a button / UI / chat: ask the engine, run what it says.
function tryAct(color, points)
  local actions, err = core:act(color, points)
  if actions == nil then
    broadcastToColor("Not now: " .. err, color, { 1, 0.5, 0.4 })
    return false
  end
  runActions(actions)
  return true
end

function onSave()
  return JSON.encode({ core = core:serialize() })
end

function onLoad(savedState)
  local data = nil
  if savedState and savedState ~= "" then
    local ok, decoded = pcall(function() return JSON.decode(savedState) end)
    if ok then data = decoded end
  end
  if data and data.core then
    core = TurnCore.restore(data.core)
  else
    core = TurnCore.new({ players = { "White", "Red" }, rounds = 3 })
  end
end

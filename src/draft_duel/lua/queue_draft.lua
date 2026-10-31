-- QueueDraft: pure rules engine for the four-player queue draft.
-- No Tabletop Simulator API in here, so it can be unit tested outside the game.
--
-- Every player opens a pack of PACK_SIZE (16) cards, takes PICKS_PER_TURN (2)
-- and passes the rest on: the pack joins the back of the next player's queue.
-- A player always picks from the pack at the front of their own queue, so fast
-- drafters can work through several packs and queue them up for a slower
-- neighbour instead of waiting. A pack goes round until it is empty (16 cards
-- = 8 turns: two laps of four seats), so nothing is discarded.
--
-- Rounds: each player opens ROUNDS (3) packs, one per round; round 1 and 3
-- pass left (to the next color in `colors`), round 2 passes right. A player
-- opens their next pack as soon as they have taken their last turn of the
-- round, without waiting for the rest of the table (they then simply join the
-- next round early; the new pack goes to the back of their queue).
-- 3 rounds x 16 cards = 48 picks each.
--
-- The engine returns "actions" for the table adapter to perform:
--   {type="deal",  to=color, count=n, pack=id}   open a pack: deal n cards (addToPack(card, id))
--   {type="pick",  color=color, card=id, slot=n, turnOver=bool}
--   {type="pass",  from=color, to=color, pack=id}
--   {type="finished"}

QueueDraft = {}
QueueDraft.__index = QueueDraft

QueueDraft.PACK_SIZE = 16
QueueDraft.PICKS_PER_TURN = 2
QueueDraft.ROUNDS = 3

-- opts.colors: seats in passing order (each passes left to the next);
-- opts.rounds / packSize / picksPerTurn override the defaults (tests).
function QueueDraft.new(opts)
  local self = setmetatable({}, QueueDraft)
  self.kind = "queue"
  self.colors = {}
  for i, c in ipairs(opts.colors) do self.colors[i] = c end
  self.rounds = opts.rounds or QueueDraft.ROUNDS
  self.packSize = opts.packSize or QueueDraft.PACK_SIZE
  self.picksPerTurn = opts.picksPerTurn or QueueDraft.PICKS_PER_TURN
  local turnsPerPack = self.packSize / self.picksPerTurn
  if turnsPerPack % #self.colors ~= 0 then
    error("QueueDraft: a pack's turns must share out evenly between the seats")
  end
  -- Each player's turns per round: every pack visits them turnsPerPack / #colors times.
  self.turnsPerRound = turnsPerPack
  self.picksPerPlayer = self.rounds * self.packSize
  self.started = false
  self.finished = false
  self.nextId = 0
  self.packs = {}   -- id -> { id, opener, round, dir, cards = { cardId, ... }, filled, taken }
  self.queues = {}  -- color -> { packId, ... }; the first is the pack being picked from
  self.picks = {}   -- color -> { cardId, ... }
  self.opened = {}  -- color -> packs opened so far (= the round they are in)
  self.turns = {}   -- color -> { [round] = turns taken in that round }
  for _, c in ipairs(self.colors) do
    self.queues[c] = {}
    self.picks[c] = {}
    self.opened[c] = 0
    self.turns[c] = {}
    for r = 1, self.rounds do self.turns[c][r] = 0 end
  end
  return self
end

local function indexOf(list, value)
  for i, v in ipairs(list) do
    if v == value then return i end
  end
  return nil
end

-- The seat dir steps from color: +1 = left (the next color), -1 = right.
function QueueDraft:neighbour(color, dir)
  local n = #self.colors
  local i = indexOf(self.colors, color)
  return self.colors[(i - 1 + dir) % n + 1]
end

function QueueDraft:_open(color, actions)
  self.opened[color] = self.opened[color] + 1
  self.nextId = self.nextId + 1
  local round = self.opened[color]
  local id = "p" .. string.format("%d", self.nextId)
  self.packs[id] = { id = id, opener = color, round = round, dir = (round % 2 == 1) and 1 or -1,
                     cards = {}, filled = 0, taken = 0 }
  table.insert(self.queues[color], id)
  table.insert(actions, { type = "deal", to = color, count = self.packSize, pack = id })
end

function QueueDraft:start()
  if self.started then return nil, "The draft has already started." end
  self.started = true
  local actions = {}
  for _, c in ipairs(self.colors) do self:_open(c, actions) end
  return actions
end

-- The table adapter calls this for every card it deals into a pack.
function QueueDraft:addToPack(id, packId)
  local pack = self.packs[packId]
  if pack == nil then return end
  table.insert(pack.cards, id)
  pack.filled = pack.filled + 1
end

function QueueDraft:_head(color)
  local q = self.queues[color]
  if q == nil or q[1] == nil then return nil end
  return self.packs[q[1]]
end

-- Cards of the pack the color is picking from, or nil.
function QueueDraft:currentPack(color)
  local pack = self:_head(color)
  return pack and pack.cards or nil
end

-- Packs waiting behind the current one, in the order they will be picked.
function QueueDraft:queuedPacks(color)
  local out = {}
  for i, id in ipairs(self.queues[color] or {}) do
    if i > 1 and self.packs[id] then table.insert(out, self.packs[id]) end
  end
  return out
end

-- Changes whenever a new turn starts at this seat (the adapter lays a pack out
-- once per turn, so cards don't shuffle under the mouse between two picks).
function QueueDraft:turnKey(color)
  local pack = self:_head(color)
  if pack == nil then return nil end
  return pack.id .. ":" .. string.format("%d", #pack.cards + pack.taken)
end

function QueueDraft:canPick(color)
  if not self.started or self.finished then return false end
  local pack = self:_head(color)
  return pack ~= nil and pack.filled >= self.packSize
end

-- Every seat with a pick to make right now.
function QueueDraft:pickers()
  local out = {}
  for _, c in ipairs(self.colors) do
    if self:canPick(c) then table.insert(out, c) end
  end
  return out
end

function QueueDraft:pickCount(color)
  return #self.picks[color]
end

function QueueDraft:_totalPicks()
  local n = 0
  for _, c in ipairs(self.colors) do n = n + #self.picks[c] end
  return n
end

-- Returns actions on success, or nil plus a message explaining the refusal.
function QueueDraft:pick(color, id)
  if not self.started then return nil, "The draft has not started yet." end
  if self.finished then return nil, "The draft is over." end
  if self.queues[color] == nil then return nil, "Only seated players draft." end
  local pack = self:_head(color)
  if pack == nil then return nil, "No pack for you yet: wait for one to be passed to you." end
  local at = indexOf(pack.cards, id)
  if at == nil then return nil, "That card is not in the pack in front of you, not yours to take." end
  if pack.filled < self.packSize then return nil, "Wait for the pack to be dealt." end

  table.remove(pack.cards, at)
  table.insert(self.picks[color], id)
  pack.taken = pack.taken + 1
  local pickAction = { type = "pick", color = color, card = id, slot = #self.picks[color], turnOver = false }
  local actions = { pickAction }
  if pack.taken < self.picksPerTurn and #pack.cards > 0 then return actions end

  -- Turn over: the pack moves on (or is used up) and the next one in the queue comes up.
  pickAction.turnOver = true
  pack.taken = 0
  table.remove(self.queues[color], 1)
  self.turns[color][pack.round] = self.turns[color][pack.round] + 1
  if #pack.cards > 0 then
    local to = self:neighbour(color, pack.dir)
    table.insert(self.queues[to], pack.id)
    table.insert(actions, { type = "pass", from = color, to = to, pack = pack.id })
  else
    self.packs[pack.id] = nil
  end
  local round = self.opened[color]
  if round < self.rounds and self.turns[color][round] >= self.turnsPerRound then
    self:_open(color, actions)
  end
  if self:_totalPicks() >= #self.colors * self.picksPerPlayer then
    self.finished = true
    table.insert(actions, { type = "finished" })
  end
  return actions
end

-- Human-readable one-line status.
function QueueDraft:status()
  if not self.started then
    local n = #self.colors
    return "Waiting to start. Sit at " .. table.concat(self.colors, ", ", 1, n - 1) .. " or " .. self.colors[n]
      .. ", then press Start Draft."
  end
  local parts = {}
  local lowest = self.rounds
  for _, c in ipairs(self.colors) do
    local waiting = #self.queues[c]
    local text = c .. " " .. #self.picks[c] .. "/" .. self.picksPerPlayer
    if not self.finished then
      text = text .. " (" .. waiting .. (waiting == 1 and " pack)" or " packs)")
      if self.opened[c] < lowest then lowest = self.opened[c] end
    end
    table.insert(parts, text)
  end
  if self.finished then return "Draft complete!   " .. table.concat(parts, "   ") end
  return "Round " .. lowest .. "/" .. self.rounds .. "   " .. table.concat(parts, "   ")
end

function QueueDraft:serialize()
  local packs = {}
  for _, p in pairs(self.packs) do table.insert(packs, p) end
  return {
    kind = "queue",
    colors = self.colors,
    rounds = self.rounds,
    packSize = self.packSize,
    picksPerTurn = self.picksPerTurn,
    started = self.started,
    finished = self.finished,
    nextId = self.nextId,
    packs = packs,
    queues = self.queues,
    picks = self.picks,
    opened = self.opened,
    turns = self.turns,
  }
end

function QueueDraft.restore(t)
  local self = QueueDraft.new({
    colors = t.colors, rounds = t.rounds, packSize = t.packSize, picksPerTurn = t.picksPerTurn,
  })
  self.started = t.started
  self.finished = t.finished
  self.nextId = t.nextId or 0
  for _, p in ipairs(t.packs or {}) do
    p.cards = p.cards or {}
    self.packs[p.id] = p
  end
  for _, c in ipairs(self.colors) do
    self.queues[c] = (t.queues and t.queues[c]) or {}
    self.picks[c] = (t.picks and t.picks[c]) or {}
    self.opened[c] = (t.opened and t.opened[c]) or 0
    local turns = (t.turns and t.turns[c]) or {}
    for r = 1, self.rounds do self.turns[c][r] = turns[r] or 0 end
  end
  return self
end

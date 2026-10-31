-- DraftCore: pure rules engine for the 1v1 pick-from-5 draft.
-- No Tabletop Simulator API in here, so it can be unit tested outside the game.
--
-- One pack, started by S (the other player is O):
--   step 1: S draws 5, takes 1          -> pack passes to O
--   step 2: O tops the pack up to 5, takes 1
--   step 3: O tops the pack up to 5, takes 1 -> pack passes back to S
--   step 4: S tops the pack up to 5, takes 1 -> the 4 leftovers are discarded (the table destroys them)
-- The starting player alternates every pack.
--
-- The engine returns "actions" for the table adapter to perform:
--   {type="deal",    to=color, count=n}
--   {type="pass",    from=color, to=color, cards={id,...}}
--   {type="pick",    color=color, card=id, slot=n}
--   {type="discard", cards={id,...}}
--   {type="finished"}

DraftCore = {}
DraftCore.__index = DraftCore

DraftCore.PACK_SIZE = 5

-- opts.colors: {colorA, colorB}; opts.picksPerPlayer: defaults to 48;
-- opts.firstStarter: color that starts pack 1 (defaults to colors[1]).
function DraftCore.new(opts)
  local self = setmetatable({}, DraftCore)
  self.colors = { opts.colors[1], opts.colors[2] }
  self.picksPerPlayer = opts.picksPerPlayer or 48
  self.totalPacks = math.floor(self.picksPerPlayer / 2)
  self.firstStarter = opts.firstStarter or self.colors[1]
  self.started = false
  self.finished = false
  self.packNumber = 0
  self.step = 0
  self.pack = {}
  self.picks = { [self.colors[1]] = {}, [self.colors[2]] = {} }
  self.discards = {}
  return self
end

function DraftCore:other(color)
  if color == self.colors[1] then return self.colors[2] end
  return self.colors[1]
end

function DraftCore:starter()
  if self.packNumber % 2 == 1 then return self.firstStarter end
  return self:other(self.firstStarter)
end

-- Color whose turn it is to pick, or nil when no pick is pending.
function DraftCore:picker()
  if not self.started or self.finished then return nil end
  if self.step == 1 or self.step == 4 then return self:starter() end
  return self:other(self:starter())
end

function DraftCore:inPack(id)
  for _, c in ipairs(self.pack) do
    if c == id then return true end
  end
  return false
end

function DraftCore:pickCount(color)
  return #self.picks[color]
end

-- The table adapter calls this for every card it deals into the pack.
function DraftCore:addToPack(id)
  table.insert(self.pack, id)
end

function DraftCore:_startPack(actions)
  self.packNumber = self.packNumber + 1
  self.step = 1
  self.pack = {}
  table.insert(actions, { type = "deal", to = self:starter(), count = DraftCore.PACK_SIZE })
end

function DraftCore:start()
  if self.started then return nil, "The draft has already started." end
  self.started = true
  local actions = {}
  self:_startPack(actions)
  return actions
end

-- Returns actions on success, or nil plus a message explaining the refusal.
function DraftCore:pick(color, id)
  if not self.started then return nil, "The draft has not started yet." end
  if self.finished then return nil, "The draft is over." end
  local picker = self:picker()
  if color ~= picker then return nil, "It is " .. picker .. "'s pick, not yours." end
  if not self:inPack(id) then return nil, "That card is not in the current pack." end
  if #self.pack < DraftCore.PACK_SIZE then
    return nil, "Wait for the pack to fill back up to " .. DraftCore.PACK_SIZE .. " cards."
  end

  for i, c in ipairs(self.pack) do
    if c == id then table.remove(self.pack, i) break end
  end
  table.insert(self.picks[color], id)

  local actions = {
    { type = "pick", color = color, card = id, slot = #self.picks[color] },
  }
  local S = self:starter()
  local O = self:other(S)

  if self.step == 1 then
    self.step = 2
    table.insert(actions, { type = "pass", from = S, to = O, cards = self:_packCopy() })
    table.insert(actions, { type = "deal", to = O, count = 1 })
  elseif self.step == 2 then
    self.step = 3
    table.insert(actions, { type = "deal", to = O, count = 1 })
  elseif self.step == 3 then
    self.step = 4
    table.insert(actions, { type = "pass", from = O, to = S, cards = self:_packCopy() })
    table.insert(actions, { type = "deal", to = S, count = 1 })
  else
    local leftovers = self:_packCopy()
    for _, c in ipairs(leftovers) do table.insert(self.discards, c) end
    self.pack = {}
    table.insert(actions, { type = "discard", cards = leftovers })
    if self.packNumber >= self.totalPacks then
      self.finished = true
      self.step = 0
      table.insert(actions, { type = "finished" })
    else
      self:_startPack(actions)
    end
  end
  return actions
end

function DraftCore:_packCopy()
  local t = {}
  for i, c in ipairs(self.pack) do t[i] = c end
  return t
end

-- Human-readable one-line status.
function DraftCore:status()
  if not self.started then return "Waiting to start. Sit at White or Red, then press Start Draft." end
  local a, b = self.colors[1], self.colors[2]
  local counts = a .. " " .. #self.picks[a] .. "/" .. self.picksPerPlayer
    .. "   " .. b .. " " .. #self.picks[b] .. "/" .. self.picksPerPlayer
  if self.finished then return "Draft complete!   " .. counts end
  return "Pack " .. self.packNumber .. "/" .. self.totalPacks
    .. "   " .. self:picker() .. " to pick (pick " .. self.step .. " of 4)   " .. counts
end

function DraftCore:serialize()
  return {
    colors = self.colors,
    picksPerPlayer = self.picksPerPlayer,
    firstStarter = self.firstStarter,
    started = self.started,
    finished = self.finished,
    packNumber = self.packNumber,
    step = self.step,
    pack = self.pack,
    picksA = self.picks[self.colors[1]],
    picksB = self.picks[self.colors[2]],
    discards = self.discards,
  }
end

function DraftCore.restore(t)
  local self = DraftCore.new({
    colors = t.colors, picksPerPlayer = t.picksPerPlayer, firstStarter = t.firstStarter,
  })
  self.started = t.started
  self.finished = t.finished
  self.packNumber = t.packNumber
  self.step = t.step
  self.pack = t.pack or {}
  self.picks[self.colors[1]] = t.picksA or {}
  self.picks[self.colors[2]] = t.picksB or {}
  self.discards = t.discards or {}
  return self
end

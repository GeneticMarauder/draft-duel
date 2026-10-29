--[[ core.objects.decks-and-containers :: deck_operations.lua
Purpose  : Deal, draw to positions, take a named card, put cards back (even into a locked deck),
           and group loose cards into a deck — handling the deck-becomes-a-card edge case.
Attach   : Global
API      : takeObject, putObject, deal, shuffle, getQuantity, getObjects, group, setLock,
           setRotation, getRotation, Wait.time
Verified : in-game (patterns from draft-duel: dealing packs, returnToCube, readyUp's group)
Use      :
  1. local deck = getObjectFromGUID(DECK_GUID)
  2. drawRow(deck, 5, rowStart, step, faceUp)  -- lay out cards
     returnCards(deck, cards)                    -- put them back, shuffle, re-lock
     local pile = groupInto(cards)               -- G-key equivalent; nil if <2 cards
Gotchas  :
  - A locked deck refuses putObject: unlock, put, re-lock (returnCards does this).
  - A deck left with one card turns into that card and the deck GUID disappears.
  - takeObject returns the card immediately; its final position settles a frame later.
  - Cards dropped on each other merge into a deck; see prevent_merging.lua.
]]

-- Takes `n` cards from the top and lays them in a row. Returns the cards.
-- start/step are positions {x,y,z}; faceUp flips them as they come out.
function drawRow(deck, n, start, step, faceUp)
  local cards = {}
  for i = 1, n do
    if deck == nil or deck.getQuantity() == 0 then break end
    local pos = { x = start.x + step.x * (i - 1), y = start.y, z = start.z + step.z * (i - 1) }
    local card = deck.takeObject({
      position = pos,
      rotation = { x = 0, y = 0, z = faceUp and 0 or 180 },
      smooth = false,  -- teleport; true animates, but lands later
    })
    table.insert(cards, card)
  end
  return cards
end

-- The card named `name` from inside `container`, moved to `position` (or nil).
function takeNamed(container, name, position)
  for _, entry in ipairs(container.getObjects() or {}) do
    if entry.name == name then
      return container.takeObject({ guid = entry.guid, position = position, smooth = false })
    end
  end
  return nil
end

-- Deals `n` cards from the top to each listed seat's hand.
function dealToSeats(deck, n, colors)
  for _, color in ipairs(colors) do
    deck.deal(n, color)
  end
end

-- Puts loose cards back into `deck` face-down, then shuffles and re-locks it.
function returnCards(deck, cards)
  if deck == nil or #cards == 0 then return end
  local wasLocked = deck.getLock and deck.getLock() or false
  deck.setLock(false)
  for _, card in ipairs(cards) do
    if card ~= nil then
      card.clearButtons()
      card.setLock(false)
      card.setRotation(deck.getRotation()) -- match the deck, so it goes in face-down
      deck.putObject(card)
    end
  end
  -- putObject animates; give it a moment before shuffling and locking again.
  Wait.time(function()
    if deck ~= nil then
      deck.shuffle()
      deck.setLock(wasLocked)
    end
  end, 1)
end

-- Groups loose cards into one deck (like selecting them and pressing G).
-- Returns the deck, or the single card when only one is given.
function groupInto(cards)
  if #cards == 0 then return nil end
  if #cards == 1 then return cards[1] end
  local result = group(cards)
  return result and result[1] or nil
end

-- True when `guid` still refers to a deck (it may have collapsed into one card).
function isStillDeck(guid)
  local o = getObjectFromGUID(guid)
  return o ~= nil and o.type == "Deck"
end

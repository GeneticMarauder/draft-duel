--[[ core.objects.decks-and-containers :: prevent_merging.lua
Purpose  : Stop cards merging into piles when dropped on each other, except where you want piles.
Attach   : Global (tryObjectEnterContainer is a Global event)
API      : tryObjectEnterContainer, onObjectEnterContainer, getGUID, getPosition, type
Verified : in-game (draft-duel deck editor: cards stay separate, the cube still accepts cards)
Use      :
  1. Paste into Global.
  2. Set MERGE_ALLOWED to the GUIDs of decks/bags that may receive cards (draw pile, discard).
  3. Toggle `freePlacement` from your game flow (true while laying cards out).
Gotchas  :
  - Returning false also blocks your own putObject calls into that container,
    so always allow the containers your script feeds.
  - Called for every container entry (bags too), so check obj.type before refusing.
  - Only one tryObjectEnterContainer can exist in a script; merge rules with any existing one.
]]

MERGE_ALLOWED = {
  -- ["c00001"] = true, -- e.g. the draw deck
}
MIDDLE_STRIP = 1      -- |z| below this counts as the shared middle, where piles are fine

freePlacement = true  -- your game flow switches this

function tryObjectEnterContainer(container, obj)
  if not freePlacement then return true end
  if obj.type ~= "Card" then return true end
  if MERGE_ALLOWED[container.getGUID()] then return true end
  -- Shared piles in the middle of the table still stack normally.
  if math.abs(obj.getPosition().z) <= MIDDLE_STRIP then return true end
  return false
end

-- Useful while debugging: see what TTS tried to merge.
function onObjectEnterContainer(container, obj)
  log("entered " .. container.getGUID() .. ": " .. obj.getGUID())
end

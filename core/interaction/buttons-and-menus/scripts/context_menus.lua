--[[ core.interaction.buttons-and-menus :: context_menus.lua
Purpose  : Add right-click menu items to objects and keep them attached as cards are drawn,
           searched out of decks, flipped and reloaded.
Attach   : Global
API      : addContextMenuItem, clearContextMenu, onObjectSpawn, onObjectLeaveContainer,
           onObjectStateChange, onLoad, getObjects, Wait.frames
Verified : in-game (draft-duel "Create <token>" / "Open a booster" / "Draft this card")
Use      :
  1. Fill menuItemsFor(obj) with the items each object should have.
  2. Paste the event handlers (merge them into existing ones if your script has them).
  3. Call refreshAllMenus() whenever the rules for who gets which item change.
Gotchas  :
  - Menu items are lost when a card goes into a deck (it's data there) and on reload.
  - Items can't be removed one at a time: clearContextMenu() then add back what's left.
  - The callback gets (playerColor, position, obj); check the seat yourself.
  - A card fresh out of a deck needs a frame before items stick.
]]

-- Which items an object gets: { { label = "...", fn = function(color, obj) end }, ... }
-- Return nil to leave the object's menu alone.
function menuItemsFor(obj)
  if obj == nil or obj.type ~= "Card" then return nil end
  return {
    { label = "Announce", fn = function(color, o)
        broadcastToAll(color .. " points at " .. o.getName(), { 0.6, 0.85, 1 })
      end },
  }
end

function applyMenu(obj)
  local items = menuItemsFor(obj)
  if items == nil then return end
  obj.clearContextMenu()
  for _, item in ipairs(items) do
    obj.addContextMenuItem(item.label, function(color, position, o)
      item.fn(color, o or obj)
    end)
  end
end

function refreshAllMenus()
  for _, o in ipairs(getObjects()) do applyMenu(o) end
end

-- New objects: drawn, dealt, searched out of a deck, spawned by scripts.
function onObjectSpawn(obj)
  Wait.frames(function() if obj ~= nil then applyMenu(obj) end end, 1)
end

function onObjectLeaveContainer(container, obj)
  onObjectSpawn(obj)
end

-- Flipping a multi-state card (DFC) replaces the object.
function onObjectStateChange(obj, oldGuid)
  onObjectSpawn(obj)
end

function onLoad(savedState)
  Wait.frames(refreshAllMenus, 5)
end

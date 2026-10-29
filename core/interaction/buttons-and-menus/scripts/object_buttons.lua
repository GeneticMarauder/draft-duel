--[[ core.interaction.buttons-and-menus :: object_buttons.lua
Purpose  : Put clickable buttons on objects (a "Draft" button under a card, a +/- counter),
           relabel them, and keep them after a reload.
Attach   : Global (buttons owned by Global; on an object script use function_owner = self)
API      : createButton, editButton, clearButtons, getButtons, click function (obj, color, altClick)
Verified : in-game (draft-duel "Draft" / "Take" buttons on cards)
Use      :
  1. addActionButton(card, "Draft", "onDraftClicked", { tooltip = "Draft this card" })
  2. Define function onDraftClicked(obj, playerColor, altClick) ... end as a global.
  3. Rebuild buttons in onLoad: TTS doesn't save them.
Gotchas  :
  - click_function is a *string* naming a global function on function_owner.
  - Button position is in the object's local space, scaled by the object's scale;
    y must clear the surface (0.2-0.3 on a card) or the button hides inside it.
  - altClick is true for a right-click. Seat checks are yours to do (spectators can click).
  - Card buttons flip with the card: a face-down card shows them upside down underneath.
]]

BUTTON_COLOR = { 0.72, 0.53, 0.04 }
BUTTON_TEXT = { 1, 1, 1 }

-- One wide button at the bottom edge of a card (in card-local units).
function addActionButton(obj, label, clickFunction, opts)
  opts = opts or {}
  obj.createButton({
    click_function = clickFunction,
    function_owner = Global,
    label = label,
    position = opts.position or { x = 0, y = 0.3, z = 1.75 },
    rotation = { x = 0, y = 0, z = 0 },
    width = opts.width or 600, height = opts.height or 220,
    font_size = opts.font_size or 150,
    color = opts.color or BUTTON_COLOR, font_color = opts.font_color or BUTTON_TEXT,
    tooltip = opts.tooltip or "",
  })
end

-- Changes the label of the button at `index` (0-based, creation order).
function relabelButton(obj, index, label)
  obj.editButton({ index = index, label = label })
end

-- A label-only button (no click) works as floating text on an object.
function addLabel(obj, text)
  obj.createButton({
    click_function = "noop", function_owner = Global, label = text,
    position = { x = 0, y = 0.3, z = -1.9 }, width = 0, height = 0,
    font_size = 120, font_color = { 1, 1, 1 },
  })
end

function noop() end

-- Example click handler: only seated players, left-click +1, right-click -1.
counterValue = 0

function onCounterClicked(obj, playerColor, altClick)
  if Player[playerColor] == nil or not Player[playerColor].seated then return end
  counterValue = counterValue + (altClick and -1 or 1)
  relabelButton(obj, 0, tostring(counterValue))
end

function addCounterButton(obj)
  obj.clearButtons()
  addActionButton(obj, tostring(counterValue), "onCounterClicked",
    { position = { x = 0, y = 0.3, z = 0 }, tooltip = "Left +1, right -1" })
end

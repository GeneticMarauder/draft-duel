--[[ core.ui.xml-ui :: seat_panel.lua
Purpose  : Drive per-seat XML UI panels from Lua: show/hide, relabel buttons and text,
           parse the seat out of element ids, and a two-click confirm for risky buttons.
Attach   : Global (pairs with seat_panel.xml in the Global UI)
API      : UI.setAttribute, UI.getAttribute, UI.setValue, UI callbacks (player, value, id),
           player.color, Wait.time
Verified : in-game (draft-duel: per-seat prompts, Ready, Next game confirm, playmat buttons)
Use      :
  1. Paste seat_panel.xml into the Global UI and this file into the Global script.
  2. showSeatPanel("White", true); setSeatText("White", "Your turn")
  3. Replace the bodies of onReadyClicked / doReset with your game logic.
Gotchas  :
  - UI.setValue does not relabel a Button: use UI.setAttribute(id, "text", label).
  - Changes made with setAttribute aren't saved: re-apply UI state in onLoad.
  - visibility="White" hides an element from everyone else, but anyone can call a handler
    by id in theory: check player.color against the id's seat.
  - Elements in the top-right corner (under the player list) don't receive clicks.
  - XML entities (&amp; etc.) show literally in some places; keep labels plain.
]]

SEATS = { "White", "Red" }
CONFIRM_SECONDS = 4

local ready = {}
local confirmUntil = {}  -- color -> os.clock() deadline for the second click

-- "ready_White" -> "ready", "White"
local function splitId(id)
  return id:match("^(%a+)_(%a+)$")
end

function showSeatPanel(color, show)
  UI.setAttribute("seat_" .. color, "active", show and "true" or "false")
end

function setSeatText(color, text)
  UI.setValue("seatText_" .. color, text)  -- setValue is right for <Text>
end

function setButtonLabel(id, label)
  UI.setAttribute(id, "text", label)       -- ...but Buttons need setAttribute
end

function onReadyClicked(player, value, id)
  local _, color = splitId(id)
  if player.color ~= color then return end  -- only the seat's owner
  ready[color] = not ready[color]
  setButtonLabel(id, ready[color] and "Not ready" or "Ready")
  setSeatText(color, ready[color] and "Ready - waiting for the others" or "Waiting...")
end

-- First click arms the button; a second click within CONFIRM_SECONDS acts.
function onConfirmClicked(player, value, id)
  local _, color = splitId(id)
  if player.color ~= color then return end
  local now = os.clock()
  if confirmUntil[color] and now <= confirmUntil[color] then
    confirmUntil[color] = nil
    setButtonLabel(id, "Reset round")
    doReset(color)
    return
  end
  confirmUntil[color] = now + CONFIRM_SECONDS
  setButtonLabel(id, "Click again to confirm")
  Wait.time(function()
    if confirmUntil[color] and os.clock() >= confirmUntil[color] then
      confirmUntil[color] = nil
      setButtonLabel(id, "Reset round")
    end
  end, CONFIRM_SECONDS)
end

function doReset(color)
  broadcastToAll(color .. " reset the round.", { 1, 0.8, 0.3 })
  for _, c in ipairs(SEATS) do ready[c] = false end
  for _, c in ipairs(SEATS) do
    setButtonLabel("ready_" .. c, "Ready")
    setSeatText(c, "Waiting...")
  end
end

function onLoad(savedState)
  for _, c in ipairs(SEATS) do showSeatPanel(c, true) end
end

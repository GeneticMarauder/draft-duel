--[[ core.debug.chat-commands :: chat_commands.lua
Purpose  : A small `!command args` dispatcher for testing and debugging in game: register
           commands with help text, optionally host-only, and keep them out of the chat log.
Attach   : Global
API      : onChat (return false hides the message), player.host, player.color, printToColor,
           broadcastToColor, getObjects, log
Verified : docs-only (draft-duel's !draftdebug / !draftauto / !hide use the same onChat shape)
Use      :
  1. Paste into Global (merge with an existing onChat).
  2. command("name", "help text", function(player, args) ... end, { hostOnly = true })
  3. In game type !help to list commands.
Gotchas  :
  - Return false from onChat or the command also shows up in chat for everyone.
  - Only one onChat per script: put your commands into this dispatcher.
  - /execute <lua> (host only) runs code in Global directly; lines over ~240 characters get cut.
]]

local COMMANDS = {}
local ORDER = {}

-- Register `!name`. fn(player, args) where args is a list of words.
function command(name, help, fn, opts)
  if COMMANDS[name] == nil then table.insert(ORDER, name) end
  COMMANDS[name] = { help = help, fn = fn, hostOnly = opts and opts.hostOnly or false }
end

local function reply(player, msg)
  if player and player.color and player.color ~= "Grey" then
    broadcastToColor(msg, player.color, { 0.7, 0.9, 1 })
  else
    printToAll(msg, { 0.7, 0.9, 1 })
  end
end

local function words(s)
  local out = {}
  for w in s:gmatch("%S+") do table.insert(out, w) end
  return out
end

function onChat(message, player)
  local name, rest = message:match("^!(%w+)%s*(.*)$")
  if name == nil then return true end
  local cmd = COMMANDS[name:lower()]
  if cmd == nil then return true end  -- not ours: let it through
  if cmd.hostOnly and not player.host then
    reply(player, "!" .. name .. " is host-only.")
    return false
  end
  local ok, err = pcall(cmd.fn, player, words(rest))
  if not ok then reply(player, "!" .. name .. " failed: " .. tostring(err)) end
  return false
end

-- Built-in commands ---------------------------------------------------------

command("help", "List commands", function(player)
  for _, n in ipairs(ORDER) do reply(player, "!" .. n .. " - " .. COMMANDS[n].help) end
end)

command("count", "Count loose objects by type", function(player)
  local counts = {}
  for _, o in ipairs(getObjects()) do counts[o.type] = (counts[o.type] or 0) + 1 end
  for t, n in pairs(counts) do reply(player, t .. ": " .. n) end
end)

command("where", "Print position of the object with a GUID: !where <guid>", function(player, args)
  local o = args[1] and getObjectFromGUID(args[1]) or nil
  if o == nil then reply(player, "No object " .. tostring(args[1])); return end
  local p = o.getPosition()
  reply(player, string.format("%s at x=%.2f y=%.2f z=%.2f", o.getName(), p.x, p.y, p.z))
end)

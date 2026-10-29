--[[ core.objects.spawn-and-find :: spawn_card_from_data.lua
Purpose  : Spawn a card from data: one cell of a hosted deck sheet, or a single-image card,
           with a name, description and JSON GMNotes the script can read back.
Attach   : Global
API      : spawnObjectData, JSON.encode, JSON.decode, getGMNotes
Verified : docs-only (draft-duel spawns cards from builder-made data, which is verified)
Use      :
  1. sheetCardData{ sheetId=1, index=0, face=SHEET_URL, back=BACK_URL, cols=10, rows=7,
                    name="Goblin", notes={ token="Goblin" } }
     or singleCardData{ face=URL, back=URL, name="Promo" }
  2. spawnObjectData({ data = thatData, position = {...}, rotation = {...} })
  3. Read notes back with readNotes(obj).
Gotchas  :
  - CardID = sheetId * 100 + index (0-based, left-to-right, top-to-bottom).
  - The same sheetId must always mean the same images within a save, or cards swap faces.
  - A face-up card has rotation z = 0; face-down is z = 180.
  - Cheapest path for many cards: build the data in Python (tts_save.py) and embed it as JSON.
]]

local function transform()
  return { posX = 0, posY = 1, posZ = 0, rotX = 0, rotY = 0, rotZ = 0,
           scaleX = 1, scaleY = 1, scaleZ = 1 }
end

-- One card cut from a grid sheet (up to 10 x 7; the last cell is TTS's hidden-card slot).
function sheetCardData(c)
  return {
    Name = "Card",
    Nickname = c.name or "",
    Description = c.description or "",
    GMNotes = c.notes and JSON.encode(c.notes) or "",
    CardID = c.sheetId * 100 + c.index,
    CustomDeck = {
      [c.sheetId] = {
        FaceURL = c.face, BackURL = c.back,
        NumWidth = c.cols or 10, NumHeight = c.rows or 7,
        BackIsHidden = true,  -- face-down cards show the back, not the hidden slot
        UniqueBack = false,
        Type = 0,             -- 0 = rectangle card
      },
    },
    Transform = transform(),
    Hands = true,             -- may be held in a hand
    Sticky = false,           -- lifting it doesn't drag cards resting on it
  }
end

-- A card whose face is one whole image.
function singleCardData(c)
  local id = c.sheetId or 9000
  return {
    Name = "CardCustom",
    Nickname = c.name or "",
    Description = c.description or "",
    GMNotes = c.notes and JSON.encode(c.notes) or "",
    CardID = id * 100,
    CustomDeck = {
      [id] = { FaceURL = c.face, BackURL = c.back, NumWidth = 1, NumHeight = 1,
               BackIsHidden = true, UniqueBack = false, Type = 0 },
    },
    Transform = transform(),
    Hands = true,
  }
end

-- GMNotes as a table ({} when empty or not JSON).
function readNotes(obj)
  local raw = obj and obj.getGMNotes() or ""
  if raw == "" then return {} end
  local ok, t = pcall(function() return JSON.decode(raw) end)
  if ok and type(t) == "table" then return t end
  return {}
end

-- Spawn face-up at a position; returns the new object.
function spawnCard(data, position, yaw, onReady)
  return spawnObjectData({
    data = data,
    position = position,
    rotation = { x = 0, y = yaw or 0, z = 0 },
    callback_function = onReady,
  })
end

# TTS Event Catalog (the ones mods actually use)

Define these as **global functions** in the Global script (or an object script,
where most fire too). Return values matter only where noted.
Signatures follow the [official event docs](https://api.tabletopsimulator.com/events/);
check there for the full list.

## Lifecycle

| Event | Signature | Notes |
| --- | --- | --- |
| `onLoad` | `(savedState)` | `""` for a fresh save. Objects may not be ready yet: defer work. |
| `onSave` | `() -> string` | Return your JSON state. Called on saves, autosaves and rewind points. |
| `onUpdate` | `()` | Every frame. Avoid. |
| `onFixedUpdate` | `()` | Every physics tick. Avoid. |

## Objects

| Event | Signature | Notes |
| --- | --- | --- |
| `onObjectSpawn` | `(obj)` | Any new object, including cards taken out of decks. |
| `onObjectDestroy` | `(obj)` | Still readable during the call. |
| `onObjectPickUp` | `(playerColor, obj)` | Player grabbed it. |
| `onObjectDrop` | `(playerColor, obj)` | Player released it; position settles a frame later. |
| `onObjectRotate` | `(obj, spin, flip, playerColor, oldSpin, oldFlip)` | Rotation keys / flip by a player. |
| `onObjectStateChange` | `(obj, oldGuid)` | Multi-state object changed state; **new GUID**. |
| `onObjectEnterContainer` | `(container, obj)` | After a merge. |
| `onObjectLeaveContainer` | `(container, obj)` | Card taken/drawn/searched out. |
| `tryObjectEnterContainer` | `(container, obj) -> bool` | Return `false` to refuse a merge (also blocks script `putObject`). |
| `onObjectEnterZone` / `onObjectLeaveZone` | `(zone, obj)` | Scripting/hand zones. |
| `onObjectNumberTyped` | `(obj, playerColor, number) -> bool` | Return `true` to stop TTS's default (e.g. drawing N). |
| `onObjectHover` | `(playerColor, obj)` | `obj` is nil when hovering nothing. Fires a lot. |

## Players

| Event | Signature | Notes |
| --- | --- | --- |
| `onPlayerChangeColor` | `(color)` | Someone sat down / stood up / switched. |
| `onPlayerConnect` / `onPlayerDisconnect` | `(player)` | |
| `onPlayerTurn` | `(player, previousPlayer)` | With TTS's Turns enabled. |
| `onChat` | `(message, player) -> bool` | Return `false` to hide the message (use for `!commands`). |
| `onPlayerAction` | `(player, action, targets) -> bool` | Newer API: intercept pick up/flip/delete etc. Return `false` to block. |

## UI

UI callbacks are not events: they are the functions named in XML `onClick`,
called as `fn(player, value, id)`. Object button callbacks are
`fn(obj, playerColor, altClick)`. Context menu callbacks are
`fn(playerColor, position, obj)`.

## In this repo

`table.lua` handles: `onLoad`, `onSave`, `onChat`, `onObjectSpawn`,
`onObjectLeaveContainer`, `onObjectPickUp`, `onObjectDrop`, `onObjectStateChange`,
`tryObjectEnterContainer`, `onPlayerChangeColor`. Adding another handler with the
same name anywhere in the Global script **replaces** it — extend the existing one.

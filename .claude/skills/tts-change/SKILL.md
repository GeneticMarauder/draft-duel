---
name: tts-change
description: Start any Tabletop Simulator change in this repo (feature, in-game bug, token, playmat, card swap, new Lua sample, new mod, review) by routing it through the skills registry. Use when the user asks to change, fix or extend the TTS mod, or invokes /tts-change.
---

# TTS change

Follow [`router/tts-change-router/SKILL.md`](../../../router/tts-change-router/SKILL.md):
classify the request, open the mod map in `mods/`, read the selected `shared/` and
`core/` skills (start from their `scripts/` samples), work test-first, and finish
with the router's definition of done and an in-game test plan.

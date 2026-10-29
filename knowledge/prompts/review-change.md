# Prompt: Review a change

**Use when:** before handing a change to the user for in-game testing, or reviewing someone else's.
**Routes to:** `governance/review-checklist.md`.

```text
Review the current diff of this repo against governance/review-checklist.md.

Focus on what the mock can't catch:
- MoonSharp syntax (//, goto, bitwise operators, <const>) in src/**/*.lua
- state added to onSave without a default in onLoad (old saves)
- buttons / menus / visibility / interactable not rebuilt after reload
- privacy lost after pickup, drop or flip
- objects captured in Wait callbacks without nil checks
- handlers defined twice (the second silently replaces the first)
- UI placed in the top-right dead zone; Button labels set with UI.setValue
Report findings with file:line and a concrete failure scenario; then run uv run pytest.
```

# Resume: Google Calendar Refresh with preview

- Worktree: `/home/hasone/code/mydiary-gcal-refresh` (stack on http://localhost:8087, `--db snapshot`)
- Branch: `gcal-refresh`
- Plan: `~/.claude/plans/gcal-refresh.md`

Delete this file in the final commit before merging.

## Steps

- [x] 1. Glossary + resume notes
- [x] 2. Backend core (renderer, preview, apply, tests)
- [x] 3. Routes, API tests, regenerate client
- [ ] 4. Frontend button and dialog
- [ ] 5. Docs

## Next action

Step 4: a \"Refresh calendar\" button next to `g-cal-auth` in `MyDiaryDay.vue` (only when `diaryNoteExists`) and a `GcalRefreshDialog` component over `joplinGcalRefreshPreview` / `joplinGcalRefresh` in `src/api.ts`. Lint and build inside the container, then browser-check at http://localhost:8087 (never click Confirm without asking).

## Notes

- `.mcp.json` and `.claude/` (settings, local settings, skills) were copied from the primary checkout so a session started here has the Playwright MCP server. Both are gitignored.
- Confirming a Refresh writes the real Diary Note, since Joplin is shared with the primary stack. Ask before confirming in the browser.
- `black --check` already flags lines on `main` in `mydiary_day.py`; only new files are black-formatted, to keep the diff to this feature.
- Added during step 2 review (not in the plan): `SectionUnreadable`, raised by preview and apply when the note has the calendar heading twice or an unclosed ``` fence. Agreed status: 422, with its message shown in the dialog.
- Route errors, each with a `detail` message for the dialog: 404 no note, 409 calendar or note changed (`detail` names which), 422 section unreadable, 502 Google unavailable (from `get_gcal` or the fetch).
- `backend/api.json` is a stale tracked file nothing regenerates; codegen writes the gitignored `mydiary-vuetify/api.json`.
- A failed event save after the note is written is logged, not raised, so apply never reports a failure for a note it wrote. Any other unexpected 500 from apply: the dialog should suggest previewing again rather than claim nothing was written.
- Left as is: `get_gcal` builds `MyDiaryGCal` (may refresh the token file) before the note lookup, so a day with no note and an expired token gets 502 rather than 404. The button only shows on days with a note.

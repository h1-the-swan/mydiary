# Resume: Google Calendar Refresh with preview

- Worktree: `/home/hasone/code/mydiary-gcal-refresh` (stack on http://localhost:8087, `--db snapshot`)
- Branch: `gcal-refresh`
- Plan: `~/.claude/plans/gcal-refresh.md`

Delete this file in the final commit before merging.

## Steps

- [x] 1. Glossary + resume notes
- [x] 2. Backend core (renderer, preview, apply, tests)
- [ ] 3. Routes, API tests, regenerate client
- [ ] 4. Frontend button and dialog
- [ ] 5. Docs

## Next action

Step 3: routes `GET /joplin/gcal_refresh_preview/{dt}` and `POST /joplin/gcal_refresh/{dt}` over `preview_gcal_refresh` / `apply_gcal_refresh` in `backend/mydiary/gcal_refresh.py`, API tests, then regenerate the client.

## Notes

- `.mcp.json` and `.claude/` (settings, local settings, skills) were copied from the primary checkout so a session started here has the Playwright MCP server. Both are gitignored.
- Confirming a Refresh writes the real Diary Note, since Joplin is shared with the primary stack. Ask before confirming in the browser.
- `black --check` already flags lines on `main` in `mydiary_day.py`; only new files are black-formatted, to keep the diff to this feature.
- Added during step 2 review (not in the plan): `SectionUnreadable`, raised by preview and apply when the note has the calendar heading twice or an unclosed ``` fence. Step 3 needs a status for it (proposed 422, message shown in the dialog).

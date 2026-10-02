# Resume: Google Calendar Refresh with preview

- Worktree: `/home/hasone/code/mydiary-gcal-refresh` (stack on http://localhost:8087, `--db snapshot`)
- Branch: `gcal-refresh`
- Plan: `~/.claude/plans/gcal-refresh.md`

Delete this file in the final commit before merging.

## Steps

- [x] 1. Glossary + resume notes
- [ ] 2. Backend core (renderer, preview, apply, tests)
- [ ] 3. Routes, API tests, regenerate client
- [ ] 4. Frontend button and dialog
- [ ] 5. Docs

## Next action

`docker compose up -d` in the worktree and start step 2 (backend core).

## Notes

- `.mcp.json` and `.claude/` (settings, local settings, skills) were copied from the primary checkout so a session started here has the Playwright MCP server. Both are gitignored.
- Confirming a Refresh writes the real Diary Note, since Joplin is shared with the primary stack. Ask before confirming in the browser.

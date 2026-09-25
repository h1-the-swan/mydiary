# Playwright MCP

To see a UI change rendered, drive the running app with the Playwright MCP tools (`mcp__playwright__*`) — don't write a standalone Playwright script against the backend venv, the MCP tools already cover navigate/resize/scroll/screenshot with no script to maintain. Resize to 1440×900 and 390×844, and scroll the page before capturing: `v-img` lazy-loads via IntersectionObserver, so an unscrolled full-page screenshot shows blank gaps where photos should be. Pass `browser_take_screenshot` a `filename` under `.playwright-mcp/` (e.g. `.playwright-mcp/foo.png`) — a bare relative name saves to the repo root instead of that gitignored output directory.

## Setup

The Playwright MCP server must run **Firefox** in an **isolated** context (`--browser firefox --isolated`), not the `@playwright/mcp` default of Chromium. This is set in `.mcp.json` at the repo root, which is gitignored (local machine setup, not shared) — if that file is missing or a session is defaulting to Chromium, add this entry under its `mcpServers` key (alongside the existing `mydiary` entry) and make sure `"playwright"` is listed in `.claude/settings.local.json`'s `enabledMcpjsonServers`:

```json
"playwright": {
  "command": "npx",
  "args": ["@playwright/mcp@latest", "--browser", "firefox", "--isolated"]
}
```

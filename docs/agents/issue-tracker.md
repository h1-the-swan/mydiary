# Issue tracker: Local Markdown

The backlog, specs and issues for this repo live as markdown files in `.scratch/`. It's gitignored, since the repo is public and these files talk about the diary's contents. There is one copy, in the primary checkout. `scripts/bootstrap-worktree.sh` symlinks every worktree's `.scratch` to it, so anything written from a worktree lands in the primary.

## Backlog

Ideas and todos that nobody is working on yet live in `.scratch/backlog/`, one file per item:

- The file is `.scratch/backlog/<slug>.md`. The slug is the item's permanent name. Once assigned it is never reused or changed, even if the item is renamed, finished or dropped, so `[slug]` references anywhere keep resolving.
- The body is free-form: the problem, what's known, rough shape, open questions. It doesn't need to be a spec.
- There's no `Status:` line. An item that is waiting on something gets a `Revisit when: <trigger>` line under its title instead, e.g. `Revisit when: diary-note-module merges`. An item without one is live.
- Link to other items with relative paths: `[other-slug](other-slug.md)` for backlog items, `[slug](../slug/spec.md)` for features, `../../` for repo files.
- To start work, move the file to `.scratch/<slug>/spec.md` and turn it into a real spec. Keep the same slug for the feature directory. Issue files come after that, as below.
- To drop an item, delete the file. Record why in the commit or conversation that decided it, if anywhere.
- A new idea from a skill or conversation that isn't being worked on now goes here, not into a feature directory.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`, never a single combined tickets file
- Each issue file has these lines near the top:
  - `Status: open | claimed | resolved`
  - `Type: task | research | prototype | grilling`
  - `Blocked by: none` or `Blocked by: NN, NN`, optionally followed by a note in parentheses
- A finished feature keeps its directory. The spec plus its resolved issues are the record of what was built and why; don't move it anywhere.
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## Archive

`.scratch/_archive/` holds things that are no longer live and aren't a finished feature: superseded plans, one-off reports, and `done-log.md` (the finished items from the old pre-2026-09-25 todo list, so their `[slug]`s still resolve). Nothing in it is worked on. Link into it when a live item needs the history.

## When a skill says "publish to the issue tracker"

If it's a feature being worked on now, create a new file under `.scratch/<feature-slug>/` (creating the directory if needed). If it's an idea for later, create `.scratch/backlog/<slug>.md`.

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` (the Notes / Decisions-so-far / Fog body).
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.

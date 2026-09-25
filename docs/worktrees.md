# Git worktrees

A second checkout can run its own stack alongside the primary one, so a feature
can be developed on its own branch without stopping the main app:

```sh
git worktree add ../mydiary-<feature> -b <feature>
cd ../mydiary-<feature>
scripts/bootstrap-worktree.sh --db snapshot   # or --db empty
docker compose up -d
```

The script picks free host ports and writes the worktree's root `.env`. Compose
derives its project name from the directory, so containers, networks and
volumes are separate automatically.

Sharing the credentials takes two mechanisms, and it's worth knowing why. The
script leaves host symlinks (`backend/.env`, `mydiary-vuetify/.env`, the three
`token_cache/` files) for anything run outside Docker, but **a symlink to an
absolute host path is dangling inside the containers** — only `./backend` and
`./mydiary-vuetify` are mounted in, so nothing above them resolves. The overlay
therefore bind-mounts the primary's `token_cache/` and `mydiary-vuetify/.env`
as well. `backend/.env` needs no mount, since Compose reads it host-side as
`env_file`. The bootstrap script checks a token file is readable *inside* the
container before declaring success, because a dangling symlink otherwise shows
up much later as an unexplained `FileNotFoundError` or, for the frontend, a
silently watermarked map.

The script also symlinks the worktree's `.scratch` to the primary's. That
directory is the issue tracker (backlog, specs, issues; see
[agents/issue-tracker.md](agents/issue-tracker.md)), and it's gitignored, so
without the link a worktree would start with none of it, and specs written
there would vanish at teardown. If the worktree already has a real `.scratch`,
the script leaves it and prints the commands to merge and link it by hand.
Teardown removes only the link.

## Choosing `--db`

The flag is required and has no default, because the right answer depends on the
feature. `MYDIARY_ROOTDIR` ([db.py:7](../backend/mydiary/db.py#L7)) remains the
escape hatch for pointing a stack at a database outside the tree, but neither
mode needs it — the `./backend` bind mount already gives each worktree its own
`database.db`.

| | `--db snapshot` | `--db empty` |
|---|---|---|
| Setup | instant, copies the primary's database | `create_all()` + `alembic stamp head` |
| Data | the real diary, forked at copy time | schema only, no rows |
| Use for | UI work, anything needing realistic volume or real edge cases | schema and migration work, connector work, routes you'll populate yourself |
| Watch for | it diverges as soon as either side writes — throwaway, never copy it back | every view is blank until you sync, and Joplin-backed views stay blank |

The snapshot is taken through sqlite's online backup API, so it's consistent
even if the primary stack is mid-write, and a `database.db.snapshot-info` file
is written beside it recording where it came from.

`--db empty` runs `backend/scripts/init_db.py` (`create_all()` off the SQLModel
metadata) and then stamps alembic at head. It deliberately does **not** run
`alembic upgrade head`: the migration history can't build a schema from
nothing, because its root revision (`1e4c09f9bc6e`, "fresh start") has an empty
`upgrade()` — alembic was adopted after the database already existed. Replaying
from zero fails on an `ALTER TABLE pocketarticle` for a table nothing ever
created. The stamp is what lets later migrations apply normally.

## What a worktree stack turns off, and what it still shares

[docker-compose.worktree.yaml](../docker-compose.worktree.yaml) patches a handful
of keys into the base compose file.

| Turned off | Why |
|---|---|
| the `tailscale` sidecar (gated behind an unused profile) | `TS_HOSTNAME` is hardcoded to `mydiary` and the authkey is reusable, so a second node would race the real one and force a fresh Let's Encrypt fetch, against a limit of 5 failed validations per hour. A worktree stack is localhost-only. |
| the APScheduler jobs (`MYDIARY_ENABLE_SCHEDULER=0`) | Both stacks would poll Spotify hourly against one shared `token_cache/spotify.json`, and a refresh by one invalidates the other's token. This also stops the OwnTracks and Joplin-note-sync jobs; see [env-vars.md](env-vars.md). |

One more thing two stacks would otherwise collide over: Vite's HMR websocket
can't upgrade through nginx, so the client falls back to the dev server's own
port. With a single stack that's invisible; with two, the worktree's browser
connects to whichever stack published 3001 — the primary. `VITE_HMR_CLIENT_PORT`
(set from `MYDIARY_VITE_PORT` in the base compose file, defaulting to 3001)
pins it to the right one.

Still shared, and not solved: Joplin and the OwnTracks recorder are single
instances on the host, and every stack talks to the same ones. Reading from
either is harmless. **Joplin writes are not** — anything reaching
`init_or_update_joplin_note` (the "Init note" button, or
`POST /joplin/init_note/{dt}`) edits the real diary notes, and it will do that
with whatever the worktree's database happens to contain. Point
`JOPLIN_NOTEBOOK_ID` at a scratch notebook if a feature needs to exercise those
paths.

## Tearing one down

```sh
cd ../mydiary-<feature>
docker compose down -v
cd -
git worktree remove ../mydiary-<feature> && git branch -d <feature>
```

`git worktree remove` will fail with `Permission denied`. The containers run as
root and leave root-owned `__pycache__` and `.pytest_cache` directories behind
in the bind-mounted `backend/`. Clear them with a container before removing:

```sh
docker run --rm -v /abs/path/to/mydiary-<feature>:/wt alpine \
  sh -c 'rm -rf /wt/* /wt/.[!.]*'
rmdir ../mydiary-<feature> && git worktree prune
```

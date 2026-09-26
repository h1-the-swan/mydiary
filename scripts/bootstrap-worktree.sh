#!/usr/bin/env bash
#
# Make a fresh git worktree runnable: link the primary checkout's credentials,
# pick host ports that don't collide with the primary stack, and set up a
# database. See the "Git worktrees" section of CLAUDE.md.
#
# Run it from inside the worktree, after `git worktree add`.

set -euo pipefail

DB_MODE=""
HTTP_PORT=""
VITE_PORT=""
FORCE=0

readonly DEFAULT_HTTP_PORT=8087
readonly DEFAULT_VITE_PORT=3002

# The three files the compose env overrides point at, by exact name. Anything
# else under token_cache/ (notably the tracked README.md) is left alone.
readonly TOKEN_FILES=(
  spotify.json
  googlecalendar_token.json
  googlecalendar_credentials.json
)

usage() {
  cat <<'EOF'
Usage: scripts/bootstrap-worktree.sh --db <snapshot|empty> [options]

Run from inside a git worktree. Symlinks backend/.env, the token cache files,
mydiary-vuetify/.env and the .scratch issue tracker from the primary checkout,
writes a root .env with
free host ports and the worktree compose overlay, and sets up a database.

Required:
  --db snapshot     Copy the primary checkout's database into this worktree.
  --db empty        Create the schema only, with no rows in it.

                    Which to choose depends on the feature:

                      snapshot  Instant (~50 MB copy), and every view has
                                realistic data with real edge cases in it.
                                Best for UI work. It forks the moment either
                                side writes, so treat it as throwaway and
                                never copy it back.

                      empty     No data at all -- every view is blank until
                                you run a sync, and Joplin-backed views stay
                                blank. Best for schema and migration work,
                                connector work, or routes you'll populate
                                yourself.

Options:
  --http-port N     Host port for the app. Default: first free from 8087.
  --vite-port N     Host port for the Vite dev server. Default: from 3002.
  --force           Overwrite an existing root .env or database.db.
  -h, --help        Show this message.
EOF
}

die() { printf '\nerror: %s\n' "$*" >&2; exit 1; }
note() { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db)         DB_MODE="${2:-}"; shift 2 ;;
    --db=*)       DB_MODE="${1#*=}"; shift ;;
    --http-port)  HTTP_PORT="${2:-}"; shift 2 ;;
    --vite-port)  VITE_PORT="${2:-}"; shift 2 ;;
    --force)      FORCE=1; shift ;;
    -h|--help)    usage; exit 0 ;;
    *)            usage >&2; die "unknown argument: $1" ;;
  esac
done

case "$DB_MODE" in
  snapshot|empty) ;;
  "") usage >&2; die "--db is required (snapshot or empty), and is deliberately not defaulted" ;;
  *)  die "--db must be 'snapshot' or 'empty', got: $DB_MODE" ;;
esac

# --- Locate this worktree and the primary checkout -----------------------

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git repository"

WORKTREE_ROOT="$(git rev-parse --show-toplevel)"
# --git-common-dir points at the primary checkout's .git from any worktree.
PRIMARY_ROOT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"

if [[ "$WORKTREE_ROOT" == "$PRIMARY_ROOT" ]]; then
  die "this is the primary checkout, not a worktree.
       Create one first:  git worktree add ../mydiary-<feature> -b <feature>
       then run this script from inside it."
fi

cd "$WORKTREE_ROOT"

step "Worktree $WORKTREE_ROOT"
note "primary checkout: $PRIMARY_ROOT"
note "branch:           $(git rev-parse --abbrev-ref HEAD)"

# --- Symlink credentials from the primary --------------------------------
#
# Symlink rather than copy, so credentials live in exactly one place. The
# Google token file is refreshed in place, and writing through a symlink
# updates the primary's copy, which is what we want.

link_from_primary() {
  local rel="$1"
  local src="$PRIMARY_ROOT/$rel"
  local dst="$WORKTREE_ROOT/$rel"

  if [[ -L "$dst" ]]; then
    note "$rel -> already linked"
    return
  fi
  if [[ -e "$dst" ]]; then
    note "$rel -> exists as a real file, left alone"
    return
  fi
  if [[ ! -e "$src" ]]; then
    note "$rel -> SKIPPED, the primary checkout doesn't have it"
    return
  fi
  mkdir -p "$(dirname "$dst")"
  ln -s "$src" "$dst"
  note "$rel -> $src"
}

step "Linking credentials from the primary checkout"
link_from_primary backend/.env
link_from_primary mydiary-vuetify/.env
for f in "${TOKEN_FILES[@]}"; do
  link_from_primary "backend/token_cache/$f"
done

[[ -e "$WORKTREE_ROOT/backend/.env" ]] || die "backend/.env is missing in both checkouts.
       Copy backend/.env.example to $PRIMARY_ROOT/backend/.env and fill it in."

# Those symlinks serve anything run on the host. They are dangling *inside* the
# containers, because they point at absolute host paths and only ./backend and
# ./mydiary-vuetify are mounted in -- nothing resolves above them. The overlay
# bind-mounts the primary's token_cache and mydiary-vuetify/.env to cover the
# container side, and docker would helpfully create a *directory* where it
# expects that file, so check it exists first.
if [[ ! -f "$PRIMARY_ROOT/mydiary-vuetify/.env" ]]; then
  die "the primary checkout has no mydiary-vuetify/.env, and the worktree
       overlay bind-mounts it. Create it first (copy
       mydiary-vuetify/.env.example), even if you leave the key blank."
fi
[[ -d "$PRIMARY_ROOT/backend/token_cache" ]] || die "the primary checkout has no backend/token_cache directory"

# --- Share the issue tracker ---------------------------------------------
#
# .scratch/ holds the backlog, specs and issues (docs/agents/issue-tracker.md).
# It's gitignored, so a worktree would otherwise start with none of it, and
# anything written there would be lost with the worktree. One copy, in the
# primary, seen from every checkout.

step "Linking the issue tracker (.scratch) from the primary checkout"
mkdir -p "$PRIMARY_ROOT/.scratch"
link_from_primary .scratch
if [[ ! -L "$WORKTREE_ROOT/.scratch" ]]; then
  note "WARNING: this worktree has its own .scratch, so it can't see the"
  note "primary's backlog. Move its contents into $PRIMARY_ROOT/.scratch,"
  note "remove it, then:  ln -s $PRIMARY_ROOT/.scratch $WORKTREE_ROOT/.scratch"
fi

# --- Pick host ports -----------------------------------------------------

port_in_use() {
  ss -ltnH 2>/dev/null | awk '{print $4}' | sed 's/.*://' | grep -qx "$1"
}

find_free_port() {
  local port="$1" limit=$(( $1 + 50 ))
  while (( port < limit )); do
    port_in_use "$port" || { printf '%s' "$port"; return 0; }
    port=$(( port + 1 ))
  done
  die "no free port found in ${1}-${limit}"
}

step "Choosing host ports"
if [[ -n "$HTTP_PORT" ]]; then
  port_in_use "$HTTP_PORT" && die "--http-port $HTTP_PORT is already in use"
else
  HTTP_PORT="$(find_free_port "$DEFAULT_HTTP_PORT")"
fi
if [[ -n "$VITE_PORT" ]]; then
  port_in_use "$VITE_PORT" && die "--vite-port $VITE_PORT is already in use"
else
  VITE_PORT="$(find_free_port "$DEFAULT_VITE_PORT")"
fi
note "app:             $HTTP_PORT  (primary uses 8086)"
note "vite dev server: $VITE_PORT  (primary uses 3001)"

# --- Write the worktree's root .env --------------------------------------

step "Writing root .env"
if [[ -e .env && $FORCE -eq 0 ]]; then
  die ".env already exists. Re-run with --force to overwrite it."
fi

cat > .env <<EOF
# Generated by scripts/bootstrap-worktree.sh on $(date -Iseconds).
# Worktree stack. Primary checkout: $PRIMARY_ROOT

# Layer the worktree overlay on the base compose file. It gates the tailscale
# sidecar off, disables the hourly scheduler jobs, and mounts the primary
# checkout's credentials into the containers.
COMPOSE_FILE=docker-compose.yaml:docker-compose.worktree.yaml

# Where the overlay's bind mounts read the shared credentials from.
MYDIARY_PRIMARY_ROOT=$PRIMARY_ROOT

MYDIARY_HTTP_PORT=$HTTP_PORT
MYDIARY_VITE_PORT=$VITE_PORT

# Deliberately empty. One tailnet node named 'mydiary' already exists, and a
# second would race it and force a fresh Let's Encrypt cert fetch. The sidecar
# is gated off entirely by the overlay above; this is belt and braces, and set
# rather than omitted only to keep compose from warning about it on every
# command. This stack is reachable on localhost only.
TS_AUTHKEY=
EOF
note "COMPOSE_FILE, MYDIARY_PRIMARY_ROOT, MYDIARY_HTTP_PORT, MYDIARY_VITE_PORT"

# --- Database ------------------------------------------------------------

readonly DB_REL="backend/mydiary/database.db"
readonly MARKER="$WORKTREE_ROOT/$DB_REL.snapshot-info"

step "Setting up the database (--db $DB_MODE)"

if [[ -e "$DB_REL" && $FORCE -eq 0 ]]; then
  die "$DB_REL already exists. Re-run with --force to replace it."
fi

if [[ "$DB_MODE" == "snapshot" ]]; then
  src_db="$PRIMARY_ROOT/$DB_REL"
  [[ -f "$src_db" ]] || die "the primary checkout has no database at $src_db"

  if command -v python3 >/dev/null 2>&1; then
    # sqlite3's online backup API, so a snapshot taken while the primary stack
    # is mid-write is still consistent. A plain cp can tear one.
    python3 - "$src_db" "$DB_REL" <<'PY'
import sqlite3, sys
src = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
dst = sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
dst.close()
src.close()
PY
    note "consistent snapshot via sqlite3 backup API"
  else
    cp "$src_db" "$DB_REL"
    note "plain copy (no python3 for an online backup) -- stop the primary"
    note "stack first if you want to be sure this isn't torn"
  fi

  cat > "$MARKER" <<EOF
This is a SNAPSHOT, not the real diary.

Copied from : $src_db
Copied at   : $(date -Iseconds)
By          : scripts/bootstrap-worktree.sh

It diverged from the real database the moment either side wrote to it.
Throw it away with the worktree. Never copy it back over the primary.
EOF
  note "$(du -h "$DB_REL" | cut -f1) snapshot + $(basename "$MARKER")"

else
  # Not `alembic upgrade head`: the migration history can't build a schema from
  # nothing. Its root revision (1e4c09f9bc6e "fresh start") has an empty
  # upgrade() because alembic was stamped onto a database that already existed,
  # so replaying from zero hits an ALTER on a table nothing ever created.
  # create_all() off the SQLModel metadata is the schema's real source, and the
  # stamp afterwards lets future migrations apply normally.
  note "creating the schema from the models..."
  docker compose run --rm --build backend scripts/init_db.py >/dev/null 2>&1 \
    || die "creating the schema failed. Try it by hand to see the output:
       docker compose run --rm backend scripts/init_db.py"

  note "stamping it at alembic head..."
  docker compose run --rm backend -m alembic stamp head >/dev/null 2>&1 \
    || die "alembic stamp failed. Try it by hand to see the output:
       docker compose run --rm backend -m alembic stamp head"

  note "schema created, no rows"
fi

# --- Verify the overlay actually took ------------------------------------
#
# This checks the MERGED config rather than the text of the overlay file, so
# renaming a service in docker-compose.yaml can't silently slip past the gate.

step "Verifying the worktree overlay"
services="$(docker compose config --services 2>/dev/null)"

if grep -qx tailscale <<<"$services"; then
  die "the tailscale sidecar is NOT gated off in this worktree.
       It would register a competing tailnet node and force a fresh
       Let's Encrypt cert fetch. Check that docker-compose.worktree.yaml
       still names the service as docker-compose.yaml defines it."
fi
note "tailscale: gated off"

merged="$(docker compose config 2>/dev/null)"

if grep -q 'MYDIARY_ENABLE_SCHEDULER: *"\?0' <<<"$merged"; then
  note "scheduler: disabled"
else
  die "MYDIARY_ENABLE_SCHEDULER=0 did not reach the backend service.
       Check docker-compose.worktree.yaml."
fi

if grep -q "$PRIMARY_ROOT/backend/token_cache" <<<"$merged"; then
  note "token cache: mounted from the primary checkout"
else
  die "the primary checkout's token_cache is not mounted into this stack.
       Check the volumes in docker-compose.worktree.yaml."
fi

# The credentials have to resolve INSIDE the container, which is the part host
# symlinks can't do. Read one through the mount to be sure.
if docker compose run --rm --no-deps -T backend \
     -c 'import os,sys; sys.exit(0 if os.path.isfile(os.environ["SPOTIFY_TOKEN_CACHE_PATH"]) else 1)' \
     >/dev/null 2>&1; then
  note "credentials: readable inside the container"
else
  die "the Spotify token cache is not readable inside the container.
       A dangling symlink looks exactly like this. Check that
       $PRIMARY_ROOT/backend/token_cache is populated."
fi

# --- Done ----------------------------------------------------------------

cat <<EOF

==> Ready.

    docker compose up -d
    http://localhost:$HTTP_PORT

    Joplin and the OwnTracks recorder are single instances on the host, shared
    with the primary stack. Reads are harmless. Joplin WRITES are not: anything
    that creates or edits a Diary Note -- the "Init note" button, adding photos
    or a map, POST /joplin/update_note/{dt} -- edits your real diary notes, and
    with a '$DB_MODE' database behind it that is very likely not what you want.

    Tear down with:  docker compose down -v
EOF

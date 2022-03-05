# mydiary

2021 Jason Portenoy

## .env file

Set the following environment variables in a `.env` file:

```
SPOTIPY_CLIENT_ID=
SPOTIPY_CLIENT_SECRET=
SPOTIPY_REDIRECT_URI=
SPOTIFY_TOKEN_CACHE_PATH=
POCKET_CONSUMER_KEY=
POCKET_ACCESS_TOKEN=
JOPLIN_AUTH_TOKEN=
JOPLIN_BASE_URL=
JOPLIN_NOTEBOOK_ID=
GOOGLECALENDAR_TOKEN_CACHE=
```
## Alembic

After making changes or adding or removing any database models (`SQLModel` models with `table=True`), run:

```sh
alembic revision --autogenerate -m "REVISION DESCRIPTION"

alembic upgrade head
```
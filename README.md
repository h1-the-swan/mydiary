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
GOOGLECALENDAR_CREDENTIALS_FILE=
GOOGLEPHOTOS_TOKEN_CACHE=
HABITICA_USER_ID=
HABITICA_API_TOKEN=
NEXTCLOUD_URL=
NEXTCLOUD_USERNAME=
NEXTCLOUD_PASSWORD=
```
## Alembic

After making changes or adding or removing any database models (`SQLModel` models with `table=True`), run:

```sh
alembic revision --autogenerate -m "REVISION DESCRIPTION"

alembic upgrade head
```

## Code coverage

`pytest --cov=mydiary tests/ --cov-report xml:cov.xml`

## API codegen

If you change anything in the API (`api.py`), you can update the client (`api.ts`) by running `npm run generateClientAPI`.
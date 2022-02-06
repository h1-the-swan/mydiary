# mydiary

2021 Jason Portenoy

## Alembic

After making changes or adding or removing any database models (`SQLModel` models with `table=True`), run:

```sh
alembic revision --autogenerate -m "REVISION DESCRIPTION"

alembic upgrade head
```
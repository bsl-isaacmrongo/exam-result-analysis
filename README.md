# Braeburn result analysis

- `api/` – FastAPI backend (PostgreSQL, Alembic migrations)
- `ui/` – Angular frontend

## Local development with Docker Compose

```sh
cp api/.env.example api/.env   # set POSTGRES_PASSWORD and the same password in DATABASE_URL
docker compose up --build
```

This starts, in order:

1. `db` – PostgreSQL 16 on `127.0.0.1:5432`
2. `migrate` – runs `alembic upgrade head` once and exits
3. `api` – http://localhost:8000 (`/docs`, `/health/db`), reloads on changes in `api/app`
4. `ui` – http://localhost:4200, `ng serve` with live reload of `ui/src`

All services read their settings from `api/.env`. After adding a migration,
run `docker compose run --rm migrate`. After changing `requirements.txt` or
`package.json`, rerun `docker compose up --build`.

Create the first account (there is no self-registration):

```sh
docker compose exec api python -m app.cli create-user isaac.mrongo@braeburn.ac.ke --name "Isaac Mrongo" --role admin --password
```

Stop with `docker compose down`. Add `-v` to also delete the database volume.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Aalto-yliopisto Junior "Valinta-apuri": a Flask + HTMX site that helps users browse/filter workshops. Workshop data lives in an Excel file on SharePoint. UI text, template names and the README are in Finnish.

There is no test suite, linter config, or build step beyond Docker.

## Commands

```bash
# Build the image (compose files reference image valinta-apuri:latest, they don't build it)
docker buildx build --platform linux/amd64 -t valinta-apuri:latest --load .

# Dev/test stack: gunicorn serves TLS directly on 443, scripts/redirector.py does HTTP->HTTPS on 80
sh scripts/create-dev-cert.sh          # creates certs/cert.pem + certs/key.pem (self-signed, localhost)
docker compose -f docker-compose.yml up -d

# Production stack: Caddy terminates TLS and proxies to web:8000 (needs caddy/Caddyfile, see caddy/Caddyfile.example)
docker compose -f docker-compose.wproxy.yml up -d

# Export image for the server
docker save valinta-apuri:latest -o valinta-apuri.tar && gzip valinta-apuri.tar

# Logs
docker compose logs -f web    # or bg, redis, caddy
```

Required env (from `.env`, see `.env.example`): `CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID`, `DRIVE_ID` (MS Graph app credentials + SharePoint drive). `REDIS_HOST` defaults to `redis`. The worker only loads `.env` itself when `ENV != "production"`.

## Architecture

Two processes from the same image, communicating only through Redis and a shared volume:

- **`bg.py` → `valinta_apuri/worker.py`** (poller): every 180 s asks MS Graph (`graph_client.py`) for the hash of `Valinta-apuri/data.xlsx`. On change it downloads `data.xlsx` and `links.xlsx` into `dp/`, parses them (`workbook.py`), and publishes a snapshot to Redis (`snapshot_store.RedisSnapshotStore.publish`: pickled DataFrame, pickled categories Series, JSON links dict, `updated_at`, written in one transaction). It then extracts the images embedded in column H of `Sheet1` (`images.py`), converts them to 500px WebP named `<row-2>.webp`, and swaps them into `static/img_cur/` (shared `img_data` volume).
- **`app.py` → `valinta_apuri/web.py`** (`create_app`, run under gunicorn): **blocks at startup until Redis has data**, then `SnapshotCache` runs a background thread that reloads the snapshot whenever `updated_at` increases (checked every 60 s). Request handlers read the in-process snapshot via `get_snapshot()`.

Request flow:
- `GET /` renders `index.html` with all workshops.
- The filter form uses `hx-patch="/submit"` on every change. `/submit` parses form fields (`filters.py`: day keys `Ma..Pe`, `lvlN` / `lvl_group` for grade levels, location and category names with value `"True"`), filters the DataFrame, and returns `partials/valikko_kortit.html`. That partial replaces the form and updates `#count` and `#valikoima` (the card grid) via `hx-swap-oob`.

Things that are easy to miss:
- Card templates (`kortti.html` etc.) receive rows from `DataFrame.itertuples()` and index columns **by position** (`i[0]` = index/image name, `i[1]` = Workshop, `i[2]` description, `i[3]` Days, `i[4]` Level, `i[5]` Category, `i[6]` Location, `i[7]` Calendar). Changing the Excel column order or the processing in `workbook.py` breaks the templates.
- `Days`, `Category`, `Level` (ints, `10` = "2. aste") and `Calendar` are list-valued columns after parsing; filters match "any overlap". Calendar entries are keys into the `links` dict (from `links.xlsx`, `Calendar` → `URL`).
- `templates/style.css` is a Jinja template served by a custom `/static/style.css` route, so it can use `static_url()`. `static_url()` appends `?v=<mtime>` for cache busting; all `/static/` responses get a 1-year cache header.
- Missing workshop images (`/static/img_cur/*.webp` 404s) fall back to `static/generic.jpg`.
- `*-empty.html` templates are the "no results / nothing selected" variants of the corresponding includes.

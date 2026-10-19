# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Aalto-yliopisto Junior "Valinta-apuri": a Flask + HTMX site that helps users browse/filter workshops. Workshop data lives in a Microsoft List (`apuri-data`) on SharePoint, and calendar booking links live in a second list (`apuri-links`). UI text, template names and the README are in Finnish.

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

Required env (from `.env`, see `.env.example`): `CLIENT_ID`, `TENANT_ID`, `LIST_ID`, `LINKS_LIST_ID`, `SITE_HOST`, `SITE_PATH`, `CERT_FILE`, `KEY_FILE`. There are no defaults in code: the worker exits if any are missing. `CERT_FILE`/`KEY_FILE` point to the app registration's certificate and key inside the container; `./secrets` is mounted read-only at `/secrets` into `bg` only. App-only SharePoint REST rejects client-secret tokens, so the certificate is used for both Graph and SharePoint REST. `REDIS_HOST` defaults to `redis`. The worker only loads `.env` itself when `ENV != "production"`.

## Architecture

Two processes from the same image, communicating only through Redis and a shared volume:

- **`bg.py` → `valinta_apuri/worker.py`** (poller): every 60 s it reads `LastItemModifiedDate` and `LastItemDeletedDate` of both lists via SharePoint REST (`sharepoint_client.py`). It does a forced full reload every 6 h as a safety net. When the timestamps change, it fetches all items via Graph, parses them (`list_data.py`), and publishes a snapshot to Redis (`snapshot_store.RedisSnapshotStore.publish`: pickled DataFrame, pickled categories Series, JSON links dict, `updated_at`, written in one transaction). It then syncs the images (`images.py`). Each item's `IMG` field is JSON naming a list item attachment. New or changed attachments are downloaded via SharePoint REST and converted to 500px WebP named `<item id>.webp`. Unchanged ones are reused based on `static/img_cur/manifest.json` (`{item id: fileName}`; replacing an image gives it a new fileName). The result is swapped into `static/img_cur/` (shared `img_data` volume).
- **`app.py` → `valinta_apuri/web.py`** (`create_app`, run under gunicorn): **blocks at startup until Redis has data**, then `SnapshotCache` runs a background thread that reloads the snapshot whenever `updated_at` increases (checked every 60 s). Request handlers read the in-process snapshot via `get_snapshot()`.

Request flow:
- `GET /` renders `index.html` with all workshops.
- The filter form uses `hx-patch="/submit"` on every change. `/submit` parses form fields (`filters.py`: day keys `Ma..Pe`, `lvlN` / `lvl_group` for grade levels, location and category names with value `"True"`), filters the DataFrame, and returns `partials/valikko_kortit.html`. That partial replaces the form and updates `#count` and `#valikoima` (the card grid) via `hx-swap-oob`.

Things that are easy to miss:
- Card templates (`kortti.html` etc.) receive rows from `DataFrame.itertuples()` and index columns **by position** (`i[0]` = list item id = image name, `i[1]` = Workshop, `i[2]` description, `i[3]` Days, `i[4]` Level, `i[5]` Category, `i[6]` Location, `i[7]` Calendar). `list_data.build_dataframe` builds the columns in `REQUIRED_DATA_COLUMNS` order; changing that breaks the templates.
- The list's columns have generated internal names (`Title`, `field_1`..`field_6`, `IMG`, `Active`; mapping in `list_data.DATA_FIELDS`). Code must only use internal names, since display names can be renamed in the Lists UI. Items with `Active` = No are hidden. Choice columns allow fill-in values, so values are still normalized.
- `Days`, `Category`, `Level` (ints, `10` = "2. aste"; stored as strings in the list) and `Calendar` are list-valued columns after parsing (empty = `[]`); filters match "any overlap". Calendar entries are keys into the `links` dict (from the `apuri-links` list, `Title` → `field_1`, display name "URL").
- `templates/style.css` is a Jinja template served by a custom `/static/style.css` route, so it can use `static_url()`. `static_url()` appends `?v=<mtime>` for cache busting; all `/static/` responses get a 1-year cache header.
- Missing workshop images (`/static/img_cur/*.webp` 404s) fall back to `static/generic.jpg`.
- `*-empty.html` templates are the "no results / nothing selected" variants of the corresponding includes.

import os
import sys
import time
import traceback
from datetime import datetime

import redis
from dotenv import load_dotenv

from valinta_apuri.config import Settings
from valinta_apuri.images import sync_images
from valinta_apuri.list_data import DATA_LIST_FIELDS, LINK_LIST_FIELDS, build_dataframe, build_links
from valinta_apuri.sharepoint_client import ListClientError, SharePointListClient
from valinta_apuri.snapshot_store import RedisSnapshotStore


REQUIRED_SETTINGS = (
    "client_id", "tenant_id", "list_id", "links_list_id",
    "site_host", "site_path", "cert_file", "key_file",
)


def run_worker():
    if os.getenv("ENV") != "production":
        load_dotenv()

    settings = Settings.from_environment()
    missing = [name.upper() for name in REQUIRED_SETTINGS if not getattr(settings, name)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)
    missing_files = [path for path in (settings.cert_file, settings.key_file) if not os.path.isfile(path)]
    if missing_files:
        print(f"Missing certificate files: {', '.join(missing_files)}")
        sys.exit(1)

    client = SharePointListClient(settings)
    store = RedisSnapshotStore(settings)
    last_version = None
    last_full_reload = 0.0
    print("Starting poller")

    while True:
        # Safety net in case some kind of change doesn't move the list timestamps.
        if time.monotonic() - last_full_reload > settings.full_reload_interval_seconds:
            last_version = None
        try:
            new_version = poll_once(settings, client, store, last_version)
            if new_version != last_version:
                last_full_reload = time.monotonic()
            last_version = new_version
        except Exception:
            print("Unexpected error during poll:")
            traceback.print_exc()
        time.sleep(settings.poll_interval_seconds)


def poll_once(settings, client, store, last_version):
    """Runs one poll and returns the list version that should be treated as handled.

    Network and Redis errors return the old version so the next poll retries.
    Invalid list data returns the new version so it isn't reloaded until the
    lists change again.
    """
    print(f"\nChecking lists... ({datetime.now().strftime('%H:%M:%S')})")
    try:
        current_version = (
            client.get_list_version(settings.list_id),
            client.get_list_version(settings.links_list_id),
        )
    except ListClientError as error:
        print(f"Version check failed: {error}")
        return last_version

    if current_version == last_version:
        print("   No changes.")
        return last_version

    print(f"Lists changed ({current_version})! Loading items...")
    try:
        items = client.get_items(settings.list_id, DATA_LIST_FIELDS)
        link_items = client.get_items(settings.links_list_id, LINK_LIST_FIELDS)
    except ListClientError as error:
        print(f"Loading items failed, retrying next poll: {error}")
        return last_version

    try:
        dataframe, categories, image_files = build_dataframe(items)
        links = build_links(link_items)
    except Exception as error:
        print(f"Processing list data failed, skipping this version of the lists: {error}")
        return current_version

    try:
        store.publish(dataframe, categories, links)
    except redis.exceptions.RedisError as error:
        print(f"Publishing to Redis failed, retrying next poll: {error}")
        return last_version
    print(f"List data reloaded successfully! {len(dataframe)} workshops, {len(links)} links")

    try:
        sync_images(client, settings.list_id, image_files)
    except Exception as error:
        print(f"Image loading failed: {error}")

    return current_version

import os
import sys
import time
import traceback
from datetime import datetime

import redis
from dotenv import load_dotenv

from valinta_apuri.config import Settings
from valinta_apuri.graph_client import GraphClientError, GraphDriveClient
from valinta_apuri.images import load_images_from_excel
from valinta_apuri.snapshot_store import RedisSnapshotStore
from valinta_apuri.workbook import load_and_process_excel, load_and_process_links


REQUIRED_SETTINGS = ("client_id", "client_secret", "tenant_id", "drive_id")


def run_worker():
    if os.getenv("ENV") != "production":
        load_dotenv()

    settings = Settings.from_environment()
    missing = [name.upper() for name in REQUIRED_SETTINGS if not getattr(settings, name)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    graph_client = GraphDriveClient(settings)
    store = RedisSnapshotStore(settings)
    last_hash = "initial-value"
    print("Starting poller")

    while True:
        try:
            last_hash = poll_once(settings, graph_client, store, last_hash)
        except Exception:
            print("Unexpected error during poll:")
            traceback.print_exc()
        time.sleep(settings.poll_interval_seconds)


def poll_once(settings, graph_client, store, last_hash):
    """Runs one poll and returns the hash that should be treated as handled.

    Network and Redis errors return the old hash so the next poll retries.
    An invalid workbook returns the new hash so it isn't re-downloaded until
    it changes again.
    """
    print(f"\nChecking hash... ({datetime.now().strftime('%H:%M:%S')})")
    try:
        current_hash = graph_client.get_file_hash(settings.data_file_path)
    except GraphClientError as error:
        print(f"Hash check failed: {error}")
        return last_hash

    if not current_hash or current_hash == last_hash:
        print("   No changes.")
        return last_hash

    print("Hash changed! Downloading...")
    try:
        graph_client.download_file(settings.data_file_path, settings.output_file)
        graph_client.download_file(settings.links_file_path, settings.links_output_file)
    except GraphClientError as error:
        print(f"Download failed, retrying next poll: {error}")
        return last_hash

    try:
        dataframe, categories = load_and_process_excel(settings.output_file)
        links = load_and_process_links(settings.links_output_file)
    except Exception as error:
        print(f"Excel processing failed, skipping this version of the file: {error}")
        return current_hash

    try:
        store.publish(dataframe, categories, links)
    except redis.exceptions.RedisError as error:
        print(f"Publishing to Redis failed, retrying next poll: {error}")
        return last_hash
    print(f"Excel data reloaded successfully! Updated hash: {current_hash}")

    try:
        load_images_from_excel(settings.output_file)
    except Exception as error:
        print(f"Image loading failed: {error}")

    return current_hash

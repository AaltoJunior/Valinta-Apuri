import os
import time
from datetime import datetime

from dotenv import load_dotenv

from valinta_apuri.config import Settings
from valinta_apuri.graph_client import GraphDriveClient
from valinta_apuri.images import load_images_from_excel
from valinta_apuri.snapshot_store import RedisSnapshotStore
from valinta_apuri.workbook import load_and_process_excel, load_and_process_links


def run_worker():
    if os.getenv("ENV") != "production":
        load_dotenv()

    settings = Settings.from_environment()
    graph_client = GraphDriveClient(settings)
    store = RedisSnapshotStore(settings)
    last_hash = "initial-value"
    print("Starting poller")

    while True:
        print(f"\nChecking hash... ({datetime.now().strftime('%H:%M:%S')})")
        current_hash = graph_client.get_file_hash(settings.data_file_path)
        if current_hash and current_hash != last_hash:
            print("Hash changed! Downloading...")
            try:
                graph_client.download_file(settings.data_file_path, settings.output_file)
                graph_client.download_file(settings.links_file_path, settings.links_output_file)
                last_hash = current_hash
                print(f"Download successful, updated hash: {last_hash}")
            except Exception as error:
                print(f"Download failed: {error}")
                time.sleep(settings.poll_interval_seconds)
                continue

            try:
                dataframe, categories = load_and_process_excel(settings.output_file)
                links = load_and_process_links(settings.links_output_file).set_index("Calendar")["URL"].to_dict()
                store.publish(dataframe, categories, links)
                print("Excel data reloaded successfully!")
            except Exception as error:
                print(f"Excel processing failed: {error}")
                time.sleep(settings.poll_interval_seconds)
                continue

            try:
                load_images_from_excel(settings.output_file)
                print("Images reloaded successfully!")
            except Exception as error:
                print(f"Image loading failed: {error}")
        else:
            print("   No changes.")
        time.sleep(settings.poll_interval_seconds)

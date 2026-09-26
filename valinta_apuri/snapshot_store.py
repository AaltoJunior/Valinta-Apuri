from dataclasses import dataclass
import json
import pickle
import threading
import time

import pandas as pd
import redis


@dataclass
class DataSnapshot:
    dataframe: pd.DataFrame
    categories: list[str]
    links: dict
    updated_at: float


class RedisSnapshotStore:
    DATA_KEY = "data"
    CATEGORIES_KEY = "categories"
    LINKS_KEY = "links"
    UPDATED_AT_KEY = "updated_at"

    def __init__(self, settings):
        self.client = redis.Redis(
            host=settings.redis_host,
            port=6379,
            decode_responses=False,
        )

    def wait_until_available(self):
        print("Waiting for Redis data...")
        while not self.has_data():
            time.sleep(1)
        print("Redis data available - starting app")

    def has_data(self):
        return all(
            self.client.get(key)
            for key in (self.DATA_KEY, self.CATEGORIES_KEY, self.LINKS_KEY)
        )

    def load(self):
        dataframe = pickle.loads(self.client.get(self.DATA_KEY))
        categories = pickle.loads(self.client.get(self.CATEGORIES_KEY)).tolist()
        links = json.loads(self.client.get(self.LINKS_KEY))
        updated_at = float(self.client.get(self.UPDATED_AT_KEY))
        return DataSnapshot(dataframe, categories, links, updated_at)

    def publish(self, dataframe, categories, links):
        # Redis transactions make the four values visible together.
        with self.client.pipeline(transaction=True) as pipeline:
            pipeline.set(self.DATA_KEY, pickle.dumps(dataframe))
            pipeline.set(self.CATEGORIES_KEY, pickle.dumps(categories))
            pipeline.set(self.LINKS_KEY, json.dumps(links))
            pipeline.set(self.UPDATED_AT_KEY, time.time())
            pipeline.execute()


class SnapshotCache:
    """Maintains the in-process snapshot used by the Flask request handlers."""

    def __init__(self, store, refresh_interval_seconds):
        self.store = store
        self.refresh_interval_seconds = refresh_interval_seconds
        self.snapshot = DataSnapshot(pd.DataFrame(), [], {}, 0)
        self.loaded = threading.Event()

    def start(self):
        threading.Thread(target=self._update_loop, daemon=True).start()

    def wait_for_initial_load(self, timeout):
        self.loaded.wait(timeout=timeout)

    def get(self):
        return self.snapshot

    def _update_loop(self):
        while True:
            try:
                updated_at = float(self.store.client.get(RedisSnapshotStore.UPDATED_AT_KEY))
                if updated_at > self.snapshot.updated_at:
                    print("Changes detected in data, reloading...")
                    self.snapshot = self.store.load()
                    self.loaded.set()
            except Exception as error:
                print(f"Redis data refresh failed: {error}")
            time.sleep(self.refresh_interval_seconds)

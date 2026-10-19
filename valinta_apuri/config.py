from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    redis_host: str
    client_id: str | None
    tenant_id: str | None
    list_id: str | None
    links_list_id: str | None
    site_host: str | None
    site_path: str | None
    cert_file: str | None
    key_file: str | None
    poll_interval_seconds: int = 60
    full_reload_interval_seconds: int = 6 * 3600
    web_refresh_interval_seconds: int = 60

    @classmethod
    def from_environment(cls):
        return cls(
            redis_host=os.getenv("REDIS_HOST", "redis"),
            client_id=os.getenv("CLIENT_ID"),
            tenant_id=os.getenv("TENANT_ID"),
            list_id=os.getenv("LIST_ID"),
            links_list_id=os.getenv("LINKS_LIST_ID"),
            site_host=os.getenv("SITE_HOST"),
            site_path=os.getenv("SITE_PATH"),
            cert_file=os.getenv("CERT_FILE"),
            key_file=os.getenv("KEY_FILE"),
        )

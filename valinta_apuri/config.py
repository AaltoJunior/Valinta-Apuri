from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    redis_host: str
    client_id: str | None
    client_secret: str | None
    tenant_id: str | None
    drive_id: str | None
    data_file_path: str = "Valinta-apuri/data.xlsx"
    links_file_path: str = "Valinta-apuri/links.xlsx"
    output_file: str = "dp/d.xlsx"
    links_output_file: str = "dp/links.xlsx"
    poll_interval_seconds: int = 180
    web_refresh_interval_seconds: int = 60

    @classmethod
    def from_environment(cls):
        return cls(
            redis_host=os.getenv("REDIS_HOST", "redis"),
            client_id=os.getenv("CLIENT_ID"),
            client_secret=os.getenv("CLIENT_SECRET"),
            tenant_id=os.getenv("TENANT_ID"),
            drive_id=os.getenv("DRIVE_ID"),
        )

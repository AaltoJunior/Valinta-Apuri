import os

import msal
import requests


# (connect, read) timeouts in seconds for every Graph / download request.
REQUEST_TIMEOUT = (10, 60)


class GraphClientError(Exception):
    """Raised when talking to MS Graph or downloading a file fails."""


class GraphDriveClient:
    def __init__(self, settings):
        self.drive_id = settings.drive_id
        authority = f"https://login.microsoftonline.com/{settings.tenant_id}"
        self.msal_app = msal.ConfidentialClientApplication(
            client_id=settings.client_id,
            client_credential=settings.client_secret,
            authority=authority,
        )

    def get_file_hash(self, file_path):
        metadata = self._get_json(self._file_url(file_path))
        hashes = metadata.get("file", {}).get("hashes", {})
        print(f"   quickXorHash : {hashes.get('quickXorHash')}")
        print(f"   sha256Hash   : {hashes.get('sha256Hash')}")
        return hashes.get("quickXorHash") or hashes.get("sha256Hash")

    def download_file(self, file_path, output_path):
        metadata = self._get_json(self._file_url(file_path))
        download_url = metadata.get("@microsoft.graph.downloadUrl")
        if not download_url:
            raise GraphClientError(f"No download URL in metadata for '{file_path}'")

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Write to a temporary file first so a failed download never leaves a
        # truncated file at output_path.
        part_path = output_path + ".part"
        try:
            with requests.get(download_url, stream=True, timeout=REQUEST_TIMEOUT) as response:
                if response.status_code != 200:
                    raise GraphClientError(
                        f"Download of '{file_path}' failed: HTTP {response.status_code}"
                    )
                size = 0
                with open(part_path, "wb") as output_file:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        output_file.write(chunk)
                        size += len(chunk)
            os.replace(part_path, output_path)
        except requests.RequestException as error:
            raise GraphClientError(f"Download of '{file_path}' failed: {error}") from error
        except OSError as error:
            raise GraphClientError(f"Could not write '{output_path}': {error}") from error
        finally:
            if os.path.exists(part_path):
                os.remove(part_path)
        print(f"Downloaded '{output_path}' ({size:,} bytes)")

    def _get_json(self, url):
        try:
            response = requests.get(url, headers=self._headers(), timeout=REQUEST_TIMEOUT)
        except requests.RequestException as error:
            raise GraphClientError(f"Request to Graph failed: {error}") from error
        if response.status_code != 200:
            raise GraphClientError(
                f"Graph returned HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            return response.json()
        except ValueError as error:
            raise GraphClientError(f"Graph returned invalid JSON: {error}") from error

    def _headers(self):
        try:
            result = self.msal_app.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )
        except Exception as error:
            raise GraphClientError(f"Token request failed: {error}") from error
        token = result.get("access_token")
        if not token:
            raise GraphClientError(
                f"Could not acquire token: {result.get('error')}: {result.get('error_description')}"
            )
        return {"Authorization": f"Bearer {token}"}

    def _file_url(self, file_path):
        return f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{file_path}"

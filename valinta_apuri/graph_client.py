import msal
import requests


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
        response = requests.get(self._file_url(file_path), headers=self._headers())
        if response.status_code != 200:
            print(f"Check failed: {response.status_code}")
            return None
        hashes = response.json().get("file", {}).get("hashes", {})
        print(f"   quickXorHash : {hashes.get('quickXorHash')}")
        print(f"   sha256Hash   : {hashes.get('sha256Hash')}")
        return hashes.get("quickXorHash") or hashes.get("sha256Hash")

    def download_file(self, file_path, output_path):
        response = requests.get(self._file_url(file_path), headers=self._headers())
        if response.status_code != 200:
            print(f"Get file failed: {response.status_code}")
            return
        download_response = requests.get(response.json()["@microsoft.graph.downloadUrl"])
        if download_response.status_code == 200:
            with open(output_path, "wb") as output_file:
                output_file.write(download_response.content)
            print(f"Downloaded '{output_path}' ({len(download_response.content):,} bytes)")

    def _headers(self):
        token = self.msal_app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        ).get("access_token")
        return {"Authorization": f"Bearer {token}"}

    def _file_url(self, file_path):
        return f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{file_path}"

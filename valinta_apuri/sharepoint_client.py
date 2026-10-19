import hashlib
import ssl
from urllib.parse import quote

import msal
import requests


# (connect, read) timeouts in seconds for every Graph / SharePoint request.
REQUEST_TIMEOUT = (10, 60)
GRAPH_URL = "https://graph.microsoft.com/v1.0"


class ListClientError(Exception):
    """Raised when talking to MS Graph or SharePoint REST fails."""


class SharePointListClient:
    """Reads list items via Graph, and change timestamps and image attachments via SharePoint REST.

    App-only SharePoint REST only accepts certificate tokens, so the certificate is used for both APIs.
    """

    def __init__(self, settings):
        self.site_host = settings.site_host
        self.site_path = settings.site_path
        self.site_url = f"https://{settings.site_host}{settings.site_path}"
        self._site_id = None
        try:
            with open(settings.cert_file) as cert_file:
                thumbprint = hashlib.sha1(ssl.PEM_cert_to_DER_cert(cert_file.read())).hexdigest().upper()
            with open(settings.key_file) as key_file:
                private_key = key_file.read()
        except (OSError, ValueError) as error:
            raise ListClientError(f"Could not read certificate or key: {error}") from error
        self.msal_app = msal.ConfidentialClientApplication(
            client_id=settings.client_id,
            client_credential={"private_key": private_key, "thumbprint": thumbprint},
            authority=f"https://login.microsoftonline.com/{settings.tenant_id}",
        )

    def get_list_version(self, list_id):
        """Returns a value that changes whenever an item is added, edited or deleted."""
        data = self._sharepoint_json(
            f"{self._list_url(list_id)}?$select=LastItemModifiedDate,LastItemDeletedDate"
        )
        # Deletes don't move LastItemModifiedDate, so both are needed.
        return (data.get("LastItemModifiedDate"), data.get("LastItemDeletedDate"))

    def get_items(self, list_id, fields):
        """Returns every item of the list as {"id": int, <internal field name>: value, ...}."""
        url = (
            f"{GRAPH_URL}/sites/{self._get_site_id()}/lists/{list_id}/items"
            f"?expand=fields(select={','.join(fields)})&$top=200"
        )
        items = []
        while url:
            page = self._graph_json(url)
            items.extend({**item.get("fields", {}), "id": int(item["id"])} for item in page["value"])
            url = page.get("@odata.nextLink")
        return items

    def download_attachment(self, list_id, item_id, file_name):
        url = (
            f"{self._list_url(list_id)}/items({item_id})"
            f"/AttachmentFiles('{quote(file_name, safe='')}')/$value"
        )
        return self._get(url, self._sharepoint_headers()).content

    def _get_site_id(self):
        if self._site_id is None:
            self._site_id = self._graph_json(f"{GRAPH_URL}/sites/{self.site_host}:{self.site_path}")["id"]
        return self._site_id

    def _list_url(self, list_id):
        return f"{self.site_url}/_api/web/lists(guid'{list_id}')"

    def _graph_json(self, url):
        return self._json(self._get(url, self._headers("https://graph.microsoft.com")))

    def _sharepoint_json(self, url):
        return self._json(self._get(url, self._sharepoint_headers()))

    def _sharepoint_headers(self):
        return {
            **self._headers(f"https://{self.site_host}"),
            "Accept": "application/json;odata=nometadata",
        }

    def _get(self, url, headers):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as error:
            raise ListClientError(f"Request to {url} failed: {error}") from error
        if response.status_code != 200:
            raise ListClientError(
                f"{url} returned HTTP {response.status_code}: {response.text[:200]}"
            )
        return response

    def _json(self, response):
        try:
            return response.json()
        except ValueError as error:
            raise ListClientError(f"{response.url} returned invalid JSON: {error}") from error

    def _headers(self, resource):
        # MSAL caches app tokens, so this only hits the network when a token expires.
        try:
            result = self.msal_app.acquire_token_for_client(scopes=[f"{resource}/.default"])
        except Exception as error:
            raise ListClientError(f"Token request failed: {error}") from error
        token = result.get("access_token")
        if not token:
            raise ListClientError(
                f"Could not acquire token for {resource}: "
                f"{result.get('error')}: {result.get('error_description')}"
            )
        return {"Authorization": f"Bearer {token}"}

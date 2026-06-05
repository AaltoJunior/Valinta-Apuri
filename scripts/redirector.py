#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit


class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._redirect()

    def do_HEAD(self):
        self._redirect()

    def _redirect(self):
        host = self.headers.get("Host", "localhost")
        parsed_host = host.split(":", 1)[0]
        location = f"https://{parsed_host}{self.path}"

        self.send_response(301)
        self.send_header("Location", location)
        self.end_headers()

    def log_message(self, format, *args):
        return


def main():
    server = HTTPServer(("0.0.0.0", 80), RedirectHandler)
    print("HTTP redirector listening on port 80")
    server.serve_forever()


if __name__ == "__main__":
    main()
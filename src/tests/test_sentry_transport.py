"""Exercise the real SDK upload worker against disposable local collectors."""

import os
import ssl
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic
from unittest import TestCase

_PROBE = """
import os
import sys

import sentry_sdk

from src.sentry_transport import SentryHttpsTransport

with sentry_sdk.init(
    dsn=sys.argv[1],
    ca_certs=os.environ.get("TEST_SENTRY_CA"),
    transport=SentryHttpsTransport,
    default_integrations=False,
    send_client_reports=False,
    shutdown_timeout=5,
):
    sentry_sdk.capture_message("local transport probe")
"""


def _plaintext_handler(requests: list[str]) -> type[BaseHTTPRequestHandler]:
    class Plaintext(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            requests.append("plaintext")
            self.send_response(200)
            self.end_headers()

    return Plaintext


def _collector_handler(
    requests: list[str], stopped: Event, plaintext_port: int
) -> type[BaseHTTPRequestHandler]:
    class Collector(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["Content-Length"]))
            mode = self.path.split("/")[1]
            requests.append(mode)
            if mode == "stall":
                try:
                    self.connection.sendall(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                    for _ in range(30):
                        if stopped.wait(0.25):
                            break
                        self.connection.sendall(b"x")
                    self.connection.sendall(b"\r\nContent-Length: 0\r\n\r\n")
                except OSError:
                    pass
            else:
                self.send_response(307)
                self.send_header("Location", f"http://127.0.0.1:{plaintext_port}/")
                self.end_headers()

    return Collector


class TestSentryTransport(TestCase):
    def test_https_uploads_are_verified_and_bounded(self) -> None:
        with TemporaryDirectory() as temp:
            cert = Path(temp) / "certificate.pem"
            key = Path(temp) / "key.pem"
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-days",
                    "1",
                    "-subj",
                    "/CN=localhost",
                    "-addext",
                    "subjectAltName=IP:127.0.0.1",
                    "-keyout",
                    str(key),
                    "-out",
                    str(cert),
                ],
                check=True,
                capture_output=True,
                timeout=10,
            )
            self._exercise_collectors(cert, key)

    def _exercise_collectors(self, cert: Path, key: Path) -> None:
        requests: list[str] = []
        stopped = Event()

        with (
            ThreadingHTTPServer(("127.0.0.1", 0), _plaintext_handler(requests)) as plaintext,
            ThreadingHTTPServer(
                ("127.0.0.1", 0), _collector_handler(requests, stopped, plaintext.server_port)
            ) as collector,
        ):
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(cert, key)
            collector.socket = tls.wrap_socket(collector.socket, server_side=True)
            threads = [
                Thread(target=server.serve_forever, daemon=True)
                for server in (plaintext, collector)
            ]
            for thread in threads:
                thread.start()
            try:
                for mode, trusted, scheme, port in (
                    ("redirect", True, "https", collector.server_port),
                    ("untrusted", False, "https", collector.server_port),
                    ("plaintext", False, "http", plaintext.server_port),
                    ("stall", True, "https", collector.server_port),
                ):
                    with self.subTest(mode=mode):
                        env = os.environ.copy()
                        for name in ("TEST_SENTRY_CA", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
                            env.pop(name, None)
                        env["SSL_VERIFY"] = "false"
                        if trusted:
                            env["TEST_SENTRY_CA"] = str(cert)
                        started = monotonic()
                        result = subprocess.run(
                            [
                                sys.executable,
                                "-c",
                                _PROBE,
                                f"{scheme}://probe@127.0.0.1:{port}/{mode}/42",
                            ],
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=8,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        if mode == "stall":
                            self.assertLess(monotonic() - started, 5)
                self.assertEqual(requests, ["redirect", "stall"])
            finally:
                stopped.set()
                for server in (plaintext, collector):
                    server.shutdown()
                for thread in threads:
                    thread.join()

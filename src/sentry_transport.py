"""Bound Sentry uploads while retaining the SDK's queue and envelope handling."""

import os
import subprocess
from collections.abc import Mapping
from email.parser import BytesHeaderParser
from select import PIPE_BUF

from sentry_sdk.consts import EndpointType
from sentry_sdk.transport import HttpTransport
from urllib3 import HTTPHeaderDict, HTTPResponse

_UPLOAD_TIMEOUT = 2


def _upload(url: str, body: bytes, headers: Mapping[str, str], ca_file: str) -> bytes:
    # Keep the SDK's authentication in a pipe so process arguments contain no DSN.
    header_data = "".join(f"{name}: {value}\n" for name, value in headers.items())
    encoded_headers = header_data.encode()
    if len(encoded_headers) > PIPE_BUF:
        raise ValueError("Sentry upload headers are too large")
    reader, writer = os.pipe()
    try:
        with os.fdopen(writer, "wb") as stream:
            stream.write(encoded_headers)
        result = subprocess.run(
            [
                "curl",
                "--disable",
                "--silent",
                "--globoff",
                "--no-location",
                "--no-insecure",
                "--proto",
                "=https",
                "--noproxy",
                "*",
                "--max-time",
                str(_UPLOAD_TIMEOUT),
                "--max-redirs",
                "0",
                "--retry",
                "0",
                "--cacert",
                ca_file,
                "--header",
                f"@/dev/fd/{reader}",
                "--data-binary",
                "@-",
                "--output",
                "/dev/null",
                "--dump-header",
                "-",
                "--write-out",
                "%{http_code}",
                "--url",
                url,
            ],
            input=body,
            stdout=subprocess.PIPE,
            pass_fds=(reader,),
            timeout=_UPLOAD_TIMEOUT + 1,
            check=True,
        )
        return result.stdout
    finally:
        os.close(reader)


class SentryHttpsTransport(HttpTransport):
    """Post SDK envelopes over verified HTTPS with a total upload deadline."""

    def _request(
        self,
        method: str,
        endpoint_type: EndpointType,
        body: bytes,
        headers: Mapping[str, str],
    ) -> HTTPResponse:
        response = _upload(
            self._auth.get_api_url(endpoint_type),
            body,
            headers,
            self._get_pool_options()["ca_certs"],
        )
        block, _, status = response.rpartition(b"\r\n\r\n")
        final_headers = block.rsplit(b"\r\n\r\n", 1)[-1].partition(b"\r\n")[2]
        parsed_headers = BytesHeaderParser().parsebytes(final_headers)
        return HTTPResponse(status=int(status), headers=HTTPHeaderDict(parsed_headers.items()))

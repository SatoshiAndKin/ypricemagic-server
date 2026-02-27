import os
from unittest.mock import patch

import structlog

from src.logger import _redact_secrets, configure_logging, get_logger


class TestRedactSecrets:
    def _call(self, event_dict: structlog.types.EventDict) -> structlog.types.EventDict:
        import logging

        return _redact_secrets(logging.getLogger(), "info", event_dict)

    def test_redacts_sensitive_key(self) -> None:
        result = self._call({"event": "test", "rpc_url": "http://secret"})
        assert result["rpc_url"] == "[REDACTED]"

    def test_preserves_token_address_key(self) -> None:
        addr = "0x" + "a1" * 20
        result = self._call({"event": "test", "token": addr})
        assert result["token"] == addr

    def test_preserves_non_sensitive_keys(self) -> None:
        result = self._call({"event": "test", "chain": "ethereum", "block": 100})
        assert result["chain"] == "ethereum"
        assert result["block"] == 100

    def test_redacts_rpc_url_in_message(self) -> None:
        with patch.dict(os.environ, {"RPC_URL": "http://my-rpc.secret.com"}):
            result = self._call({"event": "error connecting to http://my-rpc.secret.com"})
        assert "http://my-rpc.secret.com" not in str(result["event"])
        assert "[RPC_URL]" in str(result["event"])

    def test_redacts_etherscan_token_in_message(self) -> None:
        with patch.dict(os.environ, {"ETHERSCAN_TOKEN": "ABCDE12345"}):
            result = self._call({"event": "request failed with key ABCDE12345"})
        assert "ABCDE12345" not in str(result["event"])
        assert "[REDACTED]" in str(result["event"])

    def test_short_etherscan_token_not_redacted(self) -> None:
        with patch.dict(os.environ, {"ETHERSCAN_TOKEN": "abc"}):
            result = self._call({"event": "contains abc"})
        assert result["event"] == "contains abc"

    def test_returns_event_dict(self) -> None:
        result = self._call({"event": "hello"})
        assert isinstance(result, dict)


class TestConfigureLogging:
    def test_configure_does_not_raise(self) -> None:
        configure_logging()


class TestGetLogger:
    def test_returns_logger(self) -> None:
        log = get_logger("test")
        assert log is not None

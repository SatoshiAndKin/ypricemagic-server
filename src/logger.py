import logging
import os

import structlog


def _redact_secrets(
    logger: logging.Logger,
    method: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Scrub RPC URLs and API keys from log events."""
    sensitive_keys = {"rpc_url", "url", "host", "api_key", "etherscan_token"}
    for key in list(event_dict.keys()):
        if key.lower() in sensitive_keys:
            event_dict[key] = "[REDACTED]"
    # Scrub RPC URLs embedded in string values
    rpc_url = os.environ.get("RPC_URL", "")
    etherscan_token = os.environ.get("ETHERSCAN_TOKEN", "")
    msg = event_dict.get("event", "")
    if isinstance(msg, str):
        if rpc_url and rpc_url in msg:
            event_dict["event"] = msg.replace(rpc_url, "[RPC_URL]")
        if etherscan_token and len(etherscan_token) > 4 and etherscan_token in msg:
            event_dict["event"] = str(event_dict["event"]).replace(etherscan_token, "[REDACTED]")
    return event_dict


def _make_level_filter(min_level: str) -> structlog.types.Processor:
    """Create a processor that drops events below *min_level*."""
    _levels = {"debug": 10, "info": 20, "warning": 30, "error": 40, "critical": 50}
    threshold = _levels.get(min_level.lower(), 20)

    def _filter(
        logger: logging.Logger,
        method_name: str,
        event_dict: structlog.types.EventDict,
    ) -> structlog.types.EventDict:
        if _levels.get(method_name, 20) < threshold:
            raise structlog.DropEvent
        return event_dict

    return _filter


def configure_logging() -> None:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _make_level_filter(log_level),
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_secrets,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]


def sanitize_error_message(msg: str) -> str:
    """Strip RPC URLs and API keys from error messages before sending to clients."""
    rpc_url = os.environ.get("RPC_URL", "")
    etherscan_token = os.environ.get("ETHERSCAN_TOKEN", "")
    if rpc_url and rpc_url in msg:
        msg = msg.replace(rpc_url, "[REDACTED_URL]")
    if etherscan_token and len(etherscan_token) > 4 and etherscan_token in msg:
        msg = msg.replace(etherscan_token, "[REDACTED]")
    return msg

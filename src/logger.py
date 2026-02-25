import logging
import os

import structlog


def _redact_secrets(
    logger: logging.Logger,
    method: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Scrub RPC URLs and API keys from log events."""
    sensitive_keys = {"rpc_url", "url", "host", "api_key", "token", "etherscan_token"}
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


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_secrets,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)

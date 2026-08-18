from __future__ import annotations

import json
import logging
import os
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            },
            ensure_ascii=False,
        )


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def trace_event(name: str, metadata: dict[str, Any]) -> None:
    """Use Langfuse when installed/configured; otherwise intentionally no-op."""

    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        return
    try:
        from langfuse import get_client

        client = get_client()
        with client.start_as_current_observation(as_type="span", name=name) as span:
            span.update(input=metadata)
    except ImportError:
        logging.getLogger(__name__).warning(
            "Langfuse keys set but optional dependency is not installed"
        )

"""Root logger bootstrap for the RAG accelerator.

Called once at process startup by backend, indexer, and evaluation
entry-points.  Sends all application output to stdout so container
hosts and local terminals see the same stream.
"""

import logging
import sys

_LOG_FMT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"

# Azure SDK namespaces whose INFO-level HTTP traces we silence.
_NOISY_LOGGERS = (
    "azure",
    "azure.identity",
    "azure.core.pipeline.policies.http_logging_policy",
)


def configure_logging(level: int = logging.INFO) -> None:
    """Attach a stdout handler to the root logger (idempotent).

    Subsequent calls are no-ops so multiple modules can safely import
    and invoke this without duplicating output.
    """
    root = logging.getLogger()
    if root.handlers:
        return

    stdout = logging.StreamHandler(sys.stdout)
    stdout.setFormatter(logging.Formatter(_LOG_FMT))

    root.setLevel(level)
    root.addHandler(stdout)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

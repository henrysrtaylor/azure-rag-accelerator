"""Logging to Azure Application Insights.

Provides log_message() for sending structured logs to Application Insights
with optional custom dimensions for tracking and analysis.
"""
import logging
import os

from opencensus.ext.azure.log_exporter import AzureLogHandler

from raglib.config import load_env_vars, _get_credential

load_env_vars()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(
    AzureLogHandler(
        credential=_get_credential(),
        connection_string=os.getenv("LOGGING_CONNECTION_STRING")
    )
)


def log_message(
    should_log: bool,
    print_message: bool,
    message: str,
    level: int = logging.INFO,
    additional_properties: dict[str, str] | None = None
) -> None:
    """
    Log a message to Azure Application Insights.

    Args:
        should_log: Whether to send the log to Application Insights.
        print_message: Whether to also print to console.
        message: The message to log.
        level: Logging level (DEBUG=10, INFO=20, WARNING=30, ERROR=40, CRITICAL=50).
        additional_properties: Custom dimensions dict for Application Insights.
    """
    message = str(message)
    if print_message:
        print(message)
    if should_log:
        if additional_properties is None:
            logger.log(level, message)
        else:
            props = {k: str(v) for k, v in additional_properties.items()}
            logger.log(level, message, extra={'custom_dimensions': props})
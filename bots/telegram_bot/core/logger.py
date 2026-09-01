import logging
import logging.handlers
import os
import sys
from typing import Optional

from config import BASE_DIR

# Default production configuration constants
LOG_LEVEL_NAME = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.INFO)

LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_DIR, "logs"))
LOG_FILE = os.getenv("LOG_FILE", os.path.join(LOG_DIR, "pfast_bot.log"))
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10 MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))               # 5 backups

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(
    force: bool = False,
    log_file: Optional[str] = None,
    max_bytes: Optional[int] = None,
    backup_count: Optional[int] = None,
    log_level: Optional[int] = None,
) -> logging.Logger:
    """
    Configures console stream handler and rotating file handler on the root
    logger in an idempotent, thread-safe manner.

    - Managed handlers are tagged with `_pfast_ai_managed = True`.
    - If `force=True`, removes and replaces ONLY PFAST_AI-managed handlers,
      preserving any pre-existing environment or framework handlers.
    - If file handler creation fails, falls back gracefully to console-only logging.
    """
    root = logging.getLogger()
    active_level = log_level if log_level is not None else LOG_LEVEL
    root.setLevel(active_level)

    target_file = log_file if log_file is not None else LOG_FILE
    target_max_bytes = max_bytes if max_bytes is not None else LOG_MAX_BYTES
    target_backup_count = backup_count if backup_count is not None else LOG_BACKUP_COUNT

    # If force=True, cleanly remove and close only PFAST_AI-managed handlers
    if force:
        for h in list(root.handlers):
            if getattr(h, "_pfast_ai_managed", False):
                root.removeHandler(h)
                try:
                    h.close()
                except Exception:
                    pass

    # Check for existing PFAST_AI managed handlers to guarantee idempotency
    has_console = any(
        getattr(h, "_pfast_ai_managed", False)
        and getattr(h, "_pfast_handler_type", None) == "console"
        for h in root.handlers
    )
    has_file = any(
        getattr(h, "_pfast_ai_managed", False)
        and getattr(h, "_pfast_handler_type", None) == "file"
        for h in root.handlers
    )

    formatter = logging.Formatter(LOG_FORMAT)

    # 1. Console / Stream handler
    if not has_console:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(active_level)
        stream_handler.setFormatter(formatter)
        stream_handler._pfast_ai_managed = True
        stream_handler._pfast_handler_type = "console"
        root.addHandler(stream_handler)

    # 2. Rotating File handler
    if not has_file and target_file:
        try:
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                filename=target_file,
                maxBytes=target_max_bytes,
                backupCount=target_backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(active_level)
            file_handler.setFormatter(formatter)
            file_handler._pfast_ai_managed = True
            file_handler._pfast_handler_type = "file"
            root.addHandler(file_handler)
        except Exception as exc:
            # Safe diagnostic directly to sys.stderr without recursive logging
            sys.stderr.write(
                f"WARNING: Failed to initialize rotating file logger: {type(exc).__name__} "
                f"(falling back to console-only logging)\n"
            )

    return logging.getLogger("PFAST_AI")


# Initialize default logging on import
logger = setup_logging()
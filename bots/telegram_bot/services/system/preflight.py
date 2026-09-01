"""
Startup Pre-flight Validation & Fail-Fast Gate for PFAST_AI.

Performs deterministic local checks on configuration, AI provider credentials,
database read/write/rollback integrity, and filesystem readiness before
allowing the Telegram polling loop to start.
"""

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from config import BASE_DIR, TELEGRAM_TOKEN
from database.db import get_connection
import services.ai.config as ai_config

logger = logging.getLogger(__name__)

# Standard Telegram Bot Token format: <bot_id_digits>:<token_alphanumeric_and_special>
TELEGRAM_TOKEN_REGEX = re.compile(r"^\d+:[A-Za-z0-9_-]{20,}$")


class PreflightError(RuntimeError):
    """Raised when one or more critical startup pre-flight checks fail."""
    pass


@dataclass
class PreflightCheckResult:
    name: str
    passed: bool
    details: str
    critical: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PreflightReport:
    passed: bool
    results: List[PreflightCheckResult]
    duration_ms: float
    timestamp: float = field(default_factory=time.time)

    def summary(self) -> str:
        status_symbol = "✅" if self.passed else "❌"
        lines = [f"{status_symbol} Startup Pre-flight Report ({self.duration_ms:.2f}ms):"]
        for res in self.results:
            icon = "✓" if res.passed else "✗"
            lines.append(f"  [{icon}] {res.name}: {res.details}")
        return "\n".join(lines)


class StartupPreflight:
    """
    Validates essential runtime dependencies and configurations before application boot.
    """

    @staticmethod
    def _mask_secret(val: str) -> str:
        """Helper to safely mask secrets for logs/reports."""
        if not val:
            return "<empty>"
        if len(val) <= 8:
            return "***"
        return f"{val[:3]}***{val[-3:]}"

    @classmethod
    def validate_telegram_token(cls, token: Optional[str] = None) -> PreflightCheckResult:
        """
        Validates presence and basic format of the Telegram bot token.
        Never exposes the raw token in reports or logs.
        """
        raw_token = str(token if token is not None else (TELEGRAM_TOKEN or "")).strip()

        if not raw_token:
            return PreflightCheckResult(
                name="Telegram Bot Token",
                passed=False,
                details="TELEGRAM_TOKEN is missing or empty in environment configuration.",
                critical=True,
            )

        if not TELEGRAM_TOKEN_REGEX.match(raw_token):
            return PreflightCheckResult(
                name="Telegram Bot Token",
                passed=False,
                details="TELEGRAM_TOKEN format is invalid (expected '<bot_id>:<secret_hash>').",
                critical=True,
            )

        masked = cls._mask_secret(raw_token)
        return PreflightCheckResult(
            name="Telegram Bot Token",
            passed=True,
            details=f"Token configured and valid format ({masked}).",
            critical=True,
            metadata={"masked_token": masked},
        )

    @classmethod
    def validate_ai_provider(cls) -> PreflightCheckResult:
        """
        Validates active AI provider configuration and presence of non-empty API credentials.
        Never logs or outputs raw API keys.
        """
        provider_name = str(getattr(ai_config, "AI_PROVIDER", "groq") or "groq").strip().lower()
        supported_providers = {"groq", "tabitoken", "openrouter"}

        if provider_name not in supported_providers:
            return PreflightCheckResult(
                name="AI Provider Configuration",
                passed=False,
                details=f"Unsupported AI_PROVIDER '{provider_name}'. Supported: {', '.join(sorted(supported_providers))}",
                critical=True,
            )

        if provider_name == "groq":
            key = str(getattr(ai_config, "GROQ_API_KEY", "") or "").strip()
            if not key:
                return PreflightCheckResult(
                    name="AI Provider Configuration",
                    passed=False,
                    details="GROQ_API_KEY is missing or empty for active provider 'groq'.",
                    critical=True,
                )
            masked = cls._mask_secret(key)
            return PreflightCheckResult(
                name="AI Provider Configuration",
                passed=True,
                details=f"Active provider 'groq' configured with valid key ({masked}).",
                critical=True,
                metadata={"provider": "groq", "masked_key": masked},
            )

        if provider_name == "tabitoken":
            raw_keys = getattr(ai_config, "TABITOKEN_KEYS", [])
            clean_keys = [str(k).strip() for k in raw_keys if str(k).strip()]
            if not clean_keys:
                return PreflightCheckResult(
                    name="AI Provider Configuration",
                    passed=False,
                    details="TABITOKEN_KEYS contains no valid API keys for active provider 'tabitoken'.",
                    critical=True,
                )
            masked_list = [cls._mask_secret(k) for k in clean_keys]
            return PreflightCheckResult(
                name="AI Provider Configuration",
                passed=True,
                details=f"Active provider 'tabitoken' configured with {len(clean_keys)} active key(s).",
                critical=True,
                metadata={"provider": "tabitoken", "key_count": len(clean_keys), "keys": masked_list},
            )

        if provider_name == "openrouter":
            key = str(getattr(ai_config, "OPENROUTER_API_KEY", "") or "").strip()
            if not key:
                return PreflightCheckResult(
                    name="AI Provider Configuration",
                    passed=False,
                    details="OPENROUTER_API_KEY is missing or empty for active provider 'openrouter'.",
                    critical=True,
                )
            masked = cls._mask_secret(key)
            return PreflightCheckResult(
                name="AI Provider Configuration",
                passed=True,
                details=f"Active provider 'openrouter' configured with valid key ({masked}).",
                critical=True,
                metadata={"provider": "openrouter", "masked_key": masked},
            )

        return PreflightCheckResult(
            name="AI Provider Configuration",
            passed=False,
            details=f"Unhandled provider validation for '{provider_name}'.",
            critical=True,
        )

    @classmethod
    def validate_database(cls) -> PreflightCheckResult:
        """
        Validates database connectivity via a read query and a transactional write + rollback.
        Guarantees that no test artifact persists in the database.
        """
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # 1. Read check
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            if not row or row[0] != 1:
                return PreflightCheckResult(
                    name="Database Connectivity",
                    passed=False,
                    details="Database read probe returned unexpected result.",
                    critical=True,
                )

            # 2. Transactional Write + Rollback check
            probe_key = f"__preflight_probe_{int(time.time() * 1000)}__"
            try:
                # Count current feature flags
                cursor.execute("SELECT COUNT(*) FROM feature_flags")
                initial_count = cursor.fetchone()[0]

                # Insert test probe row inside transaction
                cursor.execute(
                    """
                    INSERT INTO feature_flags (feature_name, is_enabled, category, display_name, disabled_message)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (probe_key, 0, "preflight", "Probe Test", "Probe"),
                )

                # Rollback transaction
                conn.rollback()

                # Verify rollback: probe row MUST NOT exist and count MUST match initial
                cursor.execute("SELECT COUNT(*) FROM feature_flags WHERE feature_name = ?", (probe_key,))
                probe_found = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM feature_flags")
                final_count = cursor.fetchone()[0]

                if probe_found != 0 or final_count != initial_count:
                    return PreflightCheckResult(
                        name="Database Connectivity",
                        passed=False,
                        details="Database transaction rollback check failed: test row persisted.",
                        critical=True,
                    )

            except Exception as write_exc:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return PreflightCheckResult(
                    name="Database Connectivity",
                    passed=False,
                    details=f"Database write/rollback verification failed: {type(write_exc).__name__}",
                    critical=True,
                )

            return PreflightCheckResult(
                name="Database Connectivity",
                passed=True,
                details="Database read and transactional write/rollback verified successfully.",
                critical=True,
            )

        except Exception as exc:
            return PreflightCheckResult(
                name="Database Connectivity",
                passed=False,
                details=f"Database connection error: {type(exc).__name__}",
                critical=True,
            )
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    @classmethod
    def validate_filesystem(cls) -> PreflightCheckResult:
        """
        Validates that required directories (database/, logs/) exist and are writable.
        Creates them idempotently if missing.
        """
        required_dirs = [
            os.path.join(BASE_DIR, "database"),
            os.path.join(BASE_DIR, "logs"),
        ]

        verified_paths = []
        for path in required_dirs:
            try:
                os.makedirs(path, exist_ok=True)
                test_file = os.path.join(path, f".preflight_write_test_{int(time.time() * 1000)}")
                with open(test_file, "w", encoding="utf-8") as f:
                    f.write("ok")
                if os.path.exists(test_file):
                    os.remove(test_file)
                verified_paths.append(os.path.basename(path))
            except Exception as exc:
                return PreflightCheckResult(
                    name="Filesystem Paths",
                    passed=False,
                    details=f"Directory '{path}' is not writable: {type(exc).__name__}",
                    critical=True,
                )

        return PreflightCheckResult(
            name="Filesystem Paths",
            passed=True,
            details=f"Required directories verified and writable: {', '.join(verified_paths)}",
            critical=True,
        )

    @classmethod
    def run_all(cls, fail_fast: bool = True) -> PreflightReport:
        """
        Executes all pre-flight checks and returns a comprehensive report.
        If fail_fast=True and any critical check fails, logs the error and raises PreflightError.
        """
        start_time = time.perf_counter()
        results: List[PreflightCheckResult] = []

        # 1. Filesystem check (must be first to ensure logging/DB dirs exist)
        results.append(cls.validate_filesystem())

        # 2. Telegram token check
        results.append(cls.validate_telegram_token())

        # 3. AI provider configuration check
        results.append(cls.validate_ai_provider())

        # 4. Database read/write/rollback check
        results.append(cls.validate_database())

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        all_passed = all(res.passed for res in results if res.critical)
        report = PreflightReport(passed=all_passed, results=results, duration_ms=duration_ms)

        if not all_passed:
            logger.critical("STARTUP PRE-FLIGHT CHECK FAILED:")
            for res in results:
                if not res.passed:
                    logger.critical("  -> [%s]: %s", res.name, res.details)
            if fail_fast:
                failed_names = [res.name for res in results if not res.passed]
                raise PreflightError(
                    f"Startup pre-flight validation failed on critical check(s): {', '.join(failed_names)}"
                )
        else:
            logger.info("Startup pre-flight validation passed successfully (%d checks in %.2fms).", len(results), duration_ms)

        return report


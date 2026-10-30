"""Environment for the Muse client. Values come from the process environment."""

from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field

# Quickstart and API reference: https://dev.meta.ai/docs/quickstart
MUSE_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MUSE_MODEL = "muse-spark-1.3"
# Confirmed by the Baseten team on 28 Oct 2026. docs/04 Call 3.
BASETEN_BASE_URL = "https://inference.baseten.co/v1"
DEFAULT_CHECKER_MODEL = "meta-models/muse-spark-open-1026"
DEFAULT_SAM_MODEL = "sam-3.1"
DEFAULT_CACHE_DIR = Path("cache")
DEFAULT_SPEND_LIMIT_USD = Decimal("50")


class ConfigError(ValueError):
    """A present environment value cannot be read."""


class Settings(BaseModel):
    """The Day 1 Muse settings this client actually reads."""

    model_config = ConfigDict(extra="forbid")

    model_api_key: str | None
    muse_model: str
    cache_dir: Path
    spend_limit_usd: Decimal = Field(description="Total cap in US dollars across all sessions (see spend.py). Default 50.")
    muse_base_url: str = MUSE_BASE_URL
    baseten_api_key: str | None = None
    baseten_base_url: str = BASETEN_BASE_URL
    checker_model: str = DEFAULT_CHECKER_MODEL
    sam_model: str = DEFAULT_SAM_MODEL


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Read Muse settings. An empty mapping does not fall through to the process environment."""

    env = os.environ if environ is None else environ
    raw_spend = env.get("SPEND_LIMIT_USD", "").strip()
    if raw_spend == "":
        spend = DEFAULT_SPEND_LIMIT_USD
    else:
        try:
            spend = Decimal(raw_spend)
        except InvalidOperation as exc:
            raise ConfigError("SPEND_LIMIT_USD must be a number of US dollars") from exc
        if not spend.is_finite():
            raise ConfigError("SPEND_LIMIT_USD must be a finite number of US dollars")
    model = env.get("MUSE_MODEL", "").strip() or DEFAULT_MUSE_MODEL
    cache = env.get("CACHE_DIR", "").strip()
    checker = env.get("CHECKER_MODEL", "").strip() or DEFAULT_CHECKER_MODEL
    sam = env.get("SAM_MODEL", "").strip() or DEFAULT_SAM_MODEL
    baseten = env.get("BASETEN_BASE_URL", "").strip() or BASETEN_BASE_URL
    return Settings(
        model_api_key=_blank_to_none(env.get("MODEL_API_KEY")),
        muse_model=model,
        cache_dir=Path(cache) if cache else DEFAULT_CACHE_DIR,
        spend_limit_usd=spend,
        muse_base_url=MUSE_BASE_URL,
        baseten_api_key=_blank_to_none(env.get("BASETEN_API_KEY")),
        baseten_base_url=baseten,
        checker_model=checker,
        sam_model=sam,
    )


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None

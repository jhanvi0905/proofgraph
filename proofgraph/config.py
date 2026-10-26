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
DEFAULT_CACHE_DIR = Path("cache")
DEFAULT_SPEND_LIMIT_USD = Decimal("10")


class ConfigError(ValueError):
    """A present environment value cannot be read."""


class Settings(BaseModel):
    """The Day 1 Muse settings this client actually reads."""

    model_config = ConfigDict(extra="forbid")

    model_api_key: str | None
    muse_model: str
    cache_dir: Path
    spend_limit_usd: Decimal = Field(description="Per-run cap in US dollars. Default 10.")
    muse_base_url: str = MUSE_BASE_URL


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
    return Settings(
        model_api_key=_blank_to_none(env.get("MODEL_API_KEY")),
        muse_model=model,
        cache_dir=Path(cache) if cache else DEFAULT_CACHE_DIR,
        spend_limit_usd=spend,
        muse_base_url=MUSE_BASE_URL,
    )


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None

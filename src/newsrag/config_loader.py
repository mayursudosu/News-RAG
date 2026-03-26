"""Load and validate the sources configuration file."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import List

import yaml

# Default path – config/ lives at the project root
_DEFAULT_CONFIG = pathlib.Path(__file__).resolve().parents[2] / "config" / "sources.yml"

VALID_TIERS = {1, 2, 3}
VALID_TYPES = {"rss"}


@dataclass
class Source:
    """A single news source."""
    name: str
    url: str
    type: str
    country: str
    tier: int

    def __str__(self) -> str:
        return f"[Tier {self.tier}] {self.name} ({self.country})"


class ConfigError(Exception):
    """Raised when the sources config is invalid."""


def load_sources(path: pathlib.Path | str | None = None) -> List[Source]:
    """Load sources.yml, validate each entry, and return a list of Source objects."""
    path = pathlib.Path(path) if path else _DEFAULT_CONFIG
    if not path.exists():
        raise ConfigError(f"Sources config not found: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict) or "sources" not in data:
        raise ConfigError("sources.yml must have a top-level 'sources' key")

    sources: List[Source] = []
    for idx, entry in enumerate(data["sources"], start=1):
        # --- required fields ---
        for field in ("name", "url", "type", "country", "tier"):
            if field not in entry:
                raise ConfigError(f"Source #{idx} is missing required field '{field}'")

        tier = int(entry["tier"])
        if tier not in VALID_TIERS:
            raise ConfigError(
                f"Source '{entry['name']}' has invalid tier {tier}; must be one of {VALID_TIERS}"
            )

        src_type = entry["type"].lower()
        if src_type not in VALID_TYPES:
            raise ConfigError(
                f"Source '{entry['name']}' has unsupported type '{src_type}'; must be one of {VALID_TYPES}"
            )

        sources.append(
            Source(
                name=entry["name"],
                url=entry["url"],
                type=src_type,
                country=entry["country"],
                tier=tier,
            )
        )

    if not sources:
        raise ConfigError("sources.yml contains no sources")

    return sources

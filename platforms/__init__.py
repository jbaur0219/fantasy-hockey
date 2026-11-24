"""Fantasy platform adapters. get(cfg) returns the adapter for cfg['platform'] (ESPN by default)."""
from platforms.base import Fantrax, LeagueSettings, Platform, Yahoo  # noqa: F401
from platforms.espn import ESPN

ADAPTERS = {"espn": ESPN, "yahoo": Yahoo, "fantrax": Fantrax}


def get(cfg):
    name = str((cfg or {}).get("platform") or "espn").lower()
    if name not in ADAPTERS:
        raise ValueError(f"unknown platform {name!r} (known: {', '.join(sorted(ADAPTERS))})")
    return ADAPTERS[name](cfg)

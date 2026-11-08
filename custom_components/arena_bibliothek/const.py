"""Konstanten der Arena-Bibliothek-Integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "arena_bibliothek"

CONF_BASE_URL = "base_url"
CONF_SCAN_HOURS = "scan_hours"

DEFAULT_BASE_URL = "https://moenchengladbach.arena.axiell.de"
DEFAULT_SCAN_HOURS = 6
MIN_SCAN_HOURS = 1
MAX_SCAN_HOURS = 48

DEFAULT_SCAN_INTERVAL = timedelta(hours=DEFAULT_SCAN_HOURS)

PLATFORMS = ["sensor", "calendar"]

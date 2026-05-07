"""
CHI Insurance Quote Engine — Trial Lock System
================================================
Tracks how many quotes have been generated across ALL sessions
(survives browser close/reopen) using a local JSON file.

After TRIAL_LIMIT quotes → shows lock screen with contact CTA.

Usage:
    from trial_lock import check_trial, increment_trial, get_trial_status
"""

import json
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────
TRIAL_LIMIT     = 7       # Lock after this many quotes
COUNTER_FILE    = Path(__file__).parent / ".trial_counter.json"

# Broker contact info shown on lock screen
BROKER_NAME     = "Ιατρόπουλος Χρήστος"
BROKER_COMPANY  = "CHI Insurance Brokers"
BROKER_TEL      = "+30 697 590 0189"
BROKER_EMAIL    = "info@chiinsurancebrokers.com"
BROKER_WHATSAPP = "https://wa.me/306975900189"


# ── Internal helpers ─────────────────────────────────────────────────

def _load() -> dict:
    if COUNTER_FILE.exists():
        try:
            return json.loads(COUNTER_FILE.read_text())
        except Exception:
            pass
    return {"count": 0, "first_use": None, "last_use": None, "locked": False}


def _save(data: dict):
    COUNTER_FILE.write_text(json.dumps(data, indent=2))


# ── Public API ───────────────────────────────────────────────────────

def get_trial_status() -> dict:
    """Return current trial state."""
    data = _load()
    remaining = max(0, TRIAL_LIMIT - data["count"])
    return {
        "count":     data["count"],
        "limit":     TRIAL_LIMIT,
        "remaining": remaining,
        "locked":    data["count"] >= TRIAL_LIMIT,
        "first_use": data.get("first_use"),
        "last_use":  data.get("last_use"),
    }


def increment_trial() -> dict:
    """Call after each successful quote generation. Returns updated status."""
    data = _load()
    now  = datetime.now().isoformat(timespec="seconds")
    if not data.get("first_use"):
        data["first_use"] = now
    data["last_use"] = now
    data["count"]    = data.get("count", 0) + 1
    if data["count"] >= TRIAL_LIMIT:
        data["locked"] = True
    _save(data)
    return get_trial_status()


def is_locked() -> bool:
    return get_trial_status()["locked"]


def reset_trial():
    """Dev/admin use only — resets the counter."""
    _save({"count": 0, "first_use": None, "last_use": None, "locked": False})

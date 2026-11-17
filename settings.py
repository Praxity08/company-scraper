"""Settings shared by the web functions.

Keys are read from environment variables only. On Vercel they are set in the project's
settings; on this computer they come from .env (never committed, never printed).
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

HUNTER_DAILY_CAP = 2        # Hunter lookups per day (India time), for everyone together
CONTACT_KEEP_DAYS = 30      # saved contacts are deleted after this many days
RECENT_RUNS = 20            # how many recent scrapes the page lists


def load_env(path=ROOT / ".env"):
    """Read KEY=value lines from .env into the environment (does not overwrite existing values)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


KEYCHAIN_SERVICE = "company-scraper"   # macOS Keychain item: service company-scraper, account = setting name


def from_keychain(name):
    """Read a secret from the macOS login Keychain (this computer only). '' if not there."""
    if sys.platform != "darwin":
        return ""
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", name, "-w"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def hunter_key():
    """Vercel: from its environment settings. This computer: from the Keychain (or .env as a fallback)."""
    return os.environ.get("HUNTER_API_KEY", "").strip() or from_keychain("HUNTER_API_KEY")


def database_url():
    """Vercel: from its environment settings. This computer: from the Keychain (or .env as a fallback)."""
    return os.environ.get("DATABASE_URL", "").strip() or from_keychain("DATABASE_URL")

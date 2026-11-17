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
ANALYSIS_DAILY_CAP = 50     # AI company pictures per day (old rule: 10 runs x 5 domains)
SEND_DAILY_CAP = 3          # review emails sent to the owner's own inbox per day
CONTACT_KEEP_DAYS = 30      # saved contacts are deleted after this many days
RECENT_RUNS = 20            # how many recent scrapes the page lists
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"   # checked against the key's model list before first live use


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


def secret(name):
    """Vercel: from its environment settings. This computer: from the Keychain (or .env as a fallback)."""
    return os.environ.get(name, "").strip() or from_keychain(name)


def hunter_key():
    return secret("HUNTER_API_KEY")


def database_url():
    return secret("DATABASE_URL")


def gemini_key():
    return secret("GEMINI_API_KEY")


def gemini_model():
    return os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL


def serper_key():
    return secret("SERPER_API_KEY")


def resend_key():
    return secret("RESEND_API_KEY")


def to_email():
    """The ONLY address the app ever sends to: the owner's own inbox."""
    return secret("TO_EMAIL")

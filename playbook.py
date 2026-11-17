"""Reads the owner's two wording files: docs/pain-points.md and docs/email-settings.md.

Both have a "Status: DRAFT" or "Status: APPROVED" line. A DRAFT file is only used on TEST ONLY runs.
"""
import re

import settings

PAIN_FILE = settings.ROOT / "docs" / "pain-points.md"
EMAIL_FILE = settings.ROOT / "docs" / "email-settings.md"
EVIDENCE_KINDS = {"cert_in_progress", "compliance_job", "team_size"}


class PlaybookError(Exception):
    pass


def _status(text):
    m = re.search(r"^Status:\s*(\w+)", text, re.M)
    return (m.group(1).upper() if m else "DRAFT")


def _strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def load_pain_points(path=PAIN_FILE):
    text = _strip_comments(path.read_text(encoding="utf-8"))
    rows = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5 or not re.fullmatch(r"[SCF]\d+", cells[0]):
            continue
        pid, group, needs, pain, phrase = cells
        needs = [] if needs in ("-", "") else [n.strip() for n in needs.split(",")]
        bad = set(needs) - EVIDENCE_KINDS
        if group not in ("S", "C", "F") or bad or not pain or not phrase:
            raise PlaybookError(f"pain-points.md: row {pid} is not filled in correctly")
        rows.append({"id": pid, "group": group, "needs": needs, "pain": pain, "phrase": phrase})
    if not rows:
        raise PlaybookError("pain-points.md has no pain point rows")
    return {"status": _status(text), "rows": rows}


def load_email_settings(path=EMAIL_FILE):
    text = _strip_comments(path.read_text(encoding="utf-8"))
    blocks = dict(re.findall(r"```(\w+)\n(.*?)```", text, flags=re.S))
    for name in ("settings", "subject", "body"):
        if name not in blocks:
            raise PlaybookError(f"email-settings.md is missing the ```{name} block")
    values = {}
    for line in blocks["settings"].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            values[k.strip()] = v.strip()
    need = ["sender_name", "sender_title", "role_people_S", "role_people_C", "role_people_F", "pain_one", "pain_two"]
    missing = [k for k in need if not values.get(k)]
    if missing:
        raise PlaybookError("email-settings.md is missing: " + ", ".join(missing))
    return {"status": _status(text), "settings": values,
            "subject": blocks["subject"].strip(), "body": blocks["body"].strip()}


def usable(status, test_only, what):
    """(ok, why). A DRAFT wording file may only be used on a TEST ONLY run."""
    if status == "APPROVED" or test_only:
        return True, ""
    return False, (f"{what} is still a DRAFT. Read it, change its Status line to APPROVED, and redeploy. "
                   "Until then it only works on TEST ONLY runs.")

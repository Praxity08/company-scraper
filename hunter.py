"""Find the right contact for a domain with Hunter.io (Domain Search).

One lookup = one call to Hunter. The person is picked by a fixed role order:
  1. security / CISO / compliance / GRC
  2. CTO / head of engineering
  3. founder
Within the same rule the highest Hunter confidence wins. People with no name, no email
or no job title are skipped. Confidence under 80 gets a LOW CONFIDENCE flag (still shown).
Hunter gives no word-for-word quote: the evidence is the exact listed title + Hunter's source links.
Nobody is ever emailed.
"""
import re

import requests

API = "https://api.hunter.io/v2/domain-search"
TIMEOUT = 20
LOW_CONFIDENCE = 80

RULES = [
    (1, "security / CISO / compliance / GRC",
     re.compile(r"\b(ciso|security|infosec|compliance|grc)\b")),
    (2, "CTO / head of engineering",
     re.compile(r"\b(cto|chief technology officer|head of (engineering|technology)"
                r"|vp,? (of )?engineering|vice president,? (of )?engineering"
                r"|director of engineering|engineering (head|director))\b")),
    (3, "founder",
     re.compile(r"\b(co-?founder|founder)\b")),
]


class HunterError(Exception):
    """A Hunter problem, with a message that never contains the key."""


def scrub(text, key):
    return text.replace(key, "[key hidden]") if key else text


def domain_search(domain, api_key):
    """Return Hunter's list of people (emails) for a domain. Raises HunterError."""
    try:
        r = requests.get(API, params={"domain": domain, "limit": 10},
                         headers={"X-API-KEY": api_key}, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise HunterError(f"could not reach Hunter ({type(e).__name__})") from None
    if r.status_code != 200:
        detail = ""
        try:
            errors = r.json().get("errors") or []
            detail = "; ".join(str(e.get("details", "")) for e in errors if isinstance(e, dict))
        except ValueError:
            pass
        msg = f"Hunter returned HTTP {r.status_code}" + (f": {detail[:200]}" if detail else "")
        raise HunterError(scrub(msg, api_key))
    try:
        data = r.json().get("data") or {}
    except ValueError:
        raise HunterError("Hunter sent a reply that is not JSON") from None
    return data.get("emails") or []


def pick(people):
    """Choose one person by the role order. Returns a contact dict, or None."""
    best = None
    for p in people:
        if not isinstance(p, dict):
            continue
        first = (p.get("first_name") or "").strip()
        title = (p.get("position") or "").strip()
        if not (first and title and p.get("value")):
            continue
        for number, label, rx in RULES:
            if rx.search(title.lower()):
                rank = (number, -(p.get("confidence") or 0))
                if best is None or rank < best[0]:
                    best = (rank, p, number, label)
                break
    if best is None:
        return None
    _, p, number, label = best
    confidence = p.get("confidence") or 0
    name = " ".join(x for x in [(p.get("first_name") or "").strip(), (p.get("last_name") or "").strip()] if x)
    return {
        "name": name,
        "position": p.get("position").strip(),          # exact title as Hunter lists it
        "email": p.get("value"),
        "confidence": confidence,
        "low_confidence": confidence < LOW_CONFIDENCE,
        "verification": ((p.get("verification") or {}).get("status")) or "unknown",
        "rule": number,
        "rule_label": label,
        "sources": [s.get("uri") for s in (p.get("sources") or [])[:5] if isinstance(s, dict) and s.get("uri")],
        "people_returned": len(people),
    }

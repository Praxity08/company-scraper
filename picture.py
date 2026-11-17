"""Step 2: build a quick picture of the company from its own saved pages.

The AI lists facts; each fact needs the page URL and an exact quote from that page.
Plain code then checks every quote word for word against the saved page text.
Facts that fail go to "rejected" (kept for review, never used as evidence).
Missing = unknown: nothing is guessed.
"""
import time

import evidence

FIELDS = {
    "company_name": "The company's own name as written on its site.",
    "what_they_do": "A sentence from the site saying what the company does or sells.",
    "b2b_saas": "Whether the company sells software (SaaS / a platform) to businesses. "
                "value must be exactly 'yes' or 'no'; the quote must show it.",
    "funding_stage": "A funding round or stage the site states (e.g. 'Series B'), or that it is publicly listed.",
    "team_size": "A number of employees or a team size the site states.",
    "certification_held": "A security/compliance certification the company says it HOLDS (e.g. SOC 2, ISO 27001).",
    "certification_in_progress": "A certification the company says it is working towards or is in progress.",
    "security_or_compliance_job": "An open job for a security, compliance, GRC, risk or audit role.",
    "open_role": "Any other open job role listed.",
    "enterprise_plan": "An 'Enterprise' pricing plan or tier.",
    "security_review": "Customers' security reviews, infosec reviews or security questionnaires mentioned.",
    "named_customer": "A named customer company (NOT an investor, partner or award).",
    "country_or_market": "A country, region or market they serve or have offices in.",
    "recent_update": "A recent announcement, launch, or news item on the site.",
}
MAX_PER_FIELD = 5
MAX_QUOTE_WORDS = 40

SYSTEM = (
    "You extract facts about one company ONLY from the web pages given to you.\n"
    "Rules:\n"
    "- Every fact must include the URL of the page it came from and a quote copied WORD FOR WORD "
    "from that page (no paraphrasing, no fixing typos, no joining text from different places).\n"
    "- Quotes are 3 to 40 words.\n"
    "- If a field is not stated on the pages, leave it out. Never guess, never use outside knowledge.\n"
    f"- At most {MAX_PER_FIELD} facts per field.\n"
    "- 'value' is a short plain-English summary of the quote."
)

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "facts": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "field": {"type": "STRING", "enum": list(FIELDS)},
                    "value": {"type": "STRING"},
                    "source_url": {"type": "STRING"},
                    "quote": {"type": "STRING"},
                },
                "required": ["field", "value", "source_url", "quote"],
            },
        }
    },
    "required": ["facts"],
}


def build_prompt(scrape):
    lines = ["Fields to look for:"]
    lines += [f"- {name}: {desc}" for name, desc in FIELDS.items()]
    lines.append("\nPages (each starts with its type and URL):")
    for ptype, page in scrape["pages"].items():
        if page and page.get("text"):
            lines.append(f"\n=== PAGE: {ptype} | URL: {page['url']} ===\n{page['text']}")
    return "\n".join(lines)


def build(scrape, ai):
    """ai(system, prompt, schema) -> dict. Returns the picture with checked facts."""
    started = time.time()
    texts = {p["url"]: p["text"] for p in scrape["pages"].values() if p and p.get("text")}
    if not texts:
        return {"facts": [], "rejected": [], "note": "no readable pages", "seconds": 0}

    raw = ai(SYSTEM, build_prompt(scrape), SCHEMA)
    facts, rejected, per_field = [], [], {}
    for f in raw.get("facts") or []:
        if not isinstance(f, dict):
            continue
        item = {k: str(f.get(k, "")).strip() for k in ("field", "value", "source_url", "quote")}
        reason = None
        if item["field"] not in FIELDS:
            reason = "unknown field"
        elif item["source_url"] not in texts:
            reason = "source URL is not one of the scraped pages"
        elif evidence.words(item["quote"]) > MAX_QUOTE_WORDS:
            reason = "quote too long"
        elif not evidence.quote_in(item["quote"], texts[item["source_url"]]):
            reason = "quote is not word for word on that page"
        elif per_field.get(item["field"], 0) >= MAX_PER_FIELD:
            reason = "too many facts for this field"
        if reason:
            rejected.append(dict(item, reason=reason))
            continue
        if item["field"] == "b2b_saas":
            item["value"] = item["value"].lower()
        per_field[item["field"]] = per_field.get(item["field"], 0) + 1
        facts.append(item)
    return {"facts": facts, "rejected": rejected, "seconds": round(time.time() - started, 1)}


def facts_for(picture, field):
    return [f for f in (picture or {}).get("facts", []) if f["field"] == field]


def company_name(picture, domain):
    names = facts_for(picture, "company_name")
    return names[0]["value"] if names else domain.split(".")[0].capitalize()

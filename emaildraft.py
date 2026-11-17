"""Step 6: draft the email. The AI only SUGGESTS hook quotes; plain code checks them and fills
the owner's fixed template (docs/email-settings.md). The AI never writes the email itself.

A hook is ONE quote copied word for word from the company's own scraped pages, 4 to 30 words,
with no funding words, no negative news and no menu / button / image text.
No hook = no email.
"""
import re

import checks
import evidence

MIN_WORDS, MAX_WORDS = 4, 30
MAX_CANDIDATES = 10

FUNDING = re.compile(r"\b(series\s+[a-z]|funding|funded|fundraise|raised?|raising|investors?|invest(ed|ment)?|"
                     r"seed|pre-seed|round|valuation|backed by|venture|VCs?|IPO|unicorn)\b|"
                     r"[$₹€£]\s?\d+(\.\d+)?\s?(k|m|mn|million|bn|billion|cr|crore)?\b", re.I)
NEGATIVE = re.compile(checks.BREACH.pattern + r"|\b(lawsuits?|sued|layoffs?|laid off|fined|penalty|outage|"
                      r"downtime|fraud|scandal|shut ?down|bankrupt\w*)\b", re.I)
BUTTON_TEXT = [
    "book a demo", "request a demo", "get a demo", "schedule a demo", "see a demo", "watch demo", "learn more",
    "read more", "know more", "get started", "start now", "sign up", "sign in", "log in", "login", "contact us",
    "contact sales", "talk to sales", "talk to us", "try for free", "try it free", "start free trial", "free trial",
    "watch video", "watch now", "download", "subscribe", "click here", "view all", "see all", "see more",
    "explore more", "privacy policy", "terms of", "cookie", "all rights reserved", "©", "copyright", "apply now",
    "skip to", "menu", "back to top",
]
IMAGE_TEXT = re.compile(r"\b(logo|image|icon|thumbnail|banner|screenshot)\b|\.(png|jpe?g|svg|gif|webp)\b", re.I)
TOPICS = {
    "customers": r"\b(customers?|clients?|trusted by|used by|companies|businesses|teams)\b",
    "security": r"\b(secure|security|encrypt\w*|privacy)\b",
    "compliance": r"\b(complian\w*|SOC ?2|ISO|GDPR|HIPAA|PCI|audit\w*|regulat\w*)\b",
    "enterprise": r"\b(enterprises?|fortune|large organi[sz]ations)\b",
    "hiring": r"\b(hiring|join (us|our team)|we'?re growing|open roles?)\b",
    "countries": r"\b(countries|offices? in|across (india|the us|europe|asia)|india|usa?|uk|europe|middle east|apac)\b",
    "global": r"\b(global\w*|worldwide|international\w*)\b",
}

SYSTEM = (
    "You suggest possible opening lines (hooks) for a cold email to one company.\n"
    "Rules:\n"
    "- Use ONLY the web pages given. Copy each hook WORD FOR WORD from one page (no paraphrasing).\n"
    f"- Each hook is one sentence or phrase of {MIN_WORDS} to {MAX_WORDS} words that says something specific "
    "and positive about the company: its customers, security, compliance, enterprise buyers, hiring, "
    "countries or global reach.\n"
    "- Never suggest funding / investment lines, negative news, menu items, button text or image captions.\n"
    f"- Up to {MAX_CANDIDATES} hooks, best first. Include the URL of the page each one came from."
)
SCHEMA = {
    "type": "OBJECT",
    "properties": {"hooks": {"type": "ARRAY", "items": {
        "type": "OBJECT",
        "properties": {"source_url": {"type": "STRING"}, "quote": {"type": "STRING"}},
        "required": ["source_url", "quote"]}}},
    "required": ["hooks"],
}


def hook_problem(quote, url, texts):
    """None if the hook passes, else the reason it is rejected."""
    n = evidence.words(quote)
    low = " " + evidence.norm(quote).lower() + " "
    if url not in texts:
        return "source URL is not one of the company's scraped pages"
    if not evidence.quote_in(quote, texts[url]):
        return "not word for word on that page"
    if n < MIN_WORDS or n > MAX_WORDS:
        return f"{n} words (must be {MIN_WORDS} to {MAX_WORDS})"
    if FUNDING.search(quote):
        return "funding words are banned as hooks"
    if NEGATIVE.search(quote):
        return "negative news is never a hook"
    if any(b in low for b in BUTTON_TEXT):
        return "looks like menu or button text"
    if IMAGE_TEXT.search(quote):
        return "looks like image text"
    words = evidence.norm(quote).split()
    capped = sum(1 for w in words if w[:1].isupper())
    if len(words) >= 4 and capped / len(words) >= 0.85 and not re.search(r"[.!?]$", quote.strip()):
        return "looks like a menu (almost every word capitalised)"
    return None


def topics_of(quote):
    return [name for name, pat in TOPICS.items() if re.search(pat, quote, re.I)]


def find_hooks(scrape, ai):
    """Ask the AI for candidates, then keep only those that pass every rule. Best first."""
    import picture as pic
    texts = {p["url"]: p["text"] for p in scrape["pages"].values() if p and p.get("text")}
    if not texts:
        return [], []
    raw = ai(SYSTEM, pic.pages_text(scrape), SCHEMA)
    passed, rejected, seen = [], [], set()
    for i, h in enumerate((raw.get("hooks") or [])[:MAX_CANDIDATES]):
        if not isinstance(h, dict):
            continue
        quote, url = str(h.get("quote", "")).strip(), str(h.get("source_url", "")).strip()
        key = evidence.norm(quote).lower()
        if key in seen:
            continue
        seen.add(key)
        reason = hook_problem(quote, url, texts)
        if reason:
            rejected.append({"quote": quote, "source_url": url, "reason": reason})
        else:
            passed.append({"quote": evidence.norm(quote), "source_url": url, "topics": topics_of(quote), "ai_rank": i})
    # preferred topics first (more topics = better), then the AI's own order
    passed.sort(key=lambda h: (-len(h["topics"]), h["ai_rank"]))
    for n, h in enumerate(passed, 1):
        h["n"] = n
        del h["ai_rank"]
    return passed, rejected


class _Keep(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def render(wording, *, company, first_name, hook, group, pain_phrases, test_only):
    """Fill the owner's template. Returns (subject, body, word_count)."""
    s = wording["settings"]
    if len(pain_phrases) >= 2:
        pain_sentence = s["pain_two"].format_map(_Keep(p1=pain_phrases[0], p2=pain_phrases[1]))
    else:
        pain_sentence = s["pain_one"].format_map(_Keep(p1=pain_phrases[0]))
    values = _Keep(first_name=first_name or "there", company=company, hook=hook,
                   role_people=s.get(f"role_people_{group}", "teams like yours"), pain_sentence=pain_sentence,
                   sender_name=s["sender_name"], sender_title=s["sender_title"])
    subject = wording["subject"].format_map(values)
    body = wording["body"].format_map(values)
    if test_only:
        subject = "[TEST ONLY] " + subject
    return subject, body, len(body.split())


def first_name(contact):
    name = ((contact or {}).get("name") or "").strip()
    return name.split()[0] if name else ""

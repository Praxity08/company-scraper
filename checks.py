"""Step 3: check the key details and decide Go / No-Go / Flag (rules from the owner's Evidence Map).

The AI only reports evidence; this plain code decides.

Gate  B2B SaaS?            yes / no / unknown
Q1    Company size         Series A, B, C = YES. Series D+ or public = NO. Seed / unknown /
                           "pre-Series B" / "Series A+" = unknown.
Q2    Audit prep           NO (drop) only if BOTH SOC 2 and ISO 27001 are held.
                           YES if a certification is in progress, a security/compliance job is open,
                           or breach news is found. STRICT: "no certs listed" is NOT a YES.
Q3    Client pressure      YES if an Enterprise plan, a security/infosec review mention, or a named
                           customer (weak) is quoted. Only YES or unknown (absence is not proof).

Decision: gate no or any NO = No-Go; all YES = Go (Flag if the gate is unknown);
          two YES + one unknown = Flag; two or more unknown = No-Go.

Agent loop: at most ONE funding search (Q1) and ONE "<company> data breach" search (Q2),
only if still unknown and the company is not already dropped. A search result is evidence only
if the quote is word for word in its title or snippet. Negative news can qualify a company
but is NEVER usable as an email hook.
"""
import re

import evidence
import picture as pic

SERIES = re.compile(r"\b(pre[-\s]?)?series\s+([a-z])(\+)?(?![a-z])", re.I)
PUBLIC = re.compile(r"\b(IPO|publicly (listed|traded)|listed on the (NSE|BSE)|NASDAQ|NYSE)\b", re.I)
SOC2 = re.compile(r"\bSOC\s?2\b", re.I)
ISO27001 = re.compile(r"\bISO(/IEC)?\s?27001\b", re.I)
IN_PROGRESS = re.compile(r"\b(in progress|working towards?|pursuing|underway|preparing for|in the process|on track)\b", re.I)
SEC_JOB = re.compile(r"\b(security|compliance|GRC|infosec|risk|audit)\b", re.I)
ENTERPRISE = re.compile(r"\benterprise\b", re.I)
SEC_REVIEW = re.compile(r"\b(security|infosec) (review|questionnaire)s?\b", re.I)
BREACH = re.compile(r"\b(data breach|breach|data leak|leaked|hacked|hack|cyber ?attack|ransomware|exposed|security incident)\b", re.I)

SEARCH_SCHEMA = {
    "type": "OBJECT",
    "properties": {"found": {"type": "BOOLEAN"}, "result": {"type": "INTEGER"}, "quote": {"type": "STRING"}},
    "required": ["found"],
}


def ev(f, note="", hook=True):
    return {"source_url": f["source_url"], "quote": f["quote"], "from": f.get("from", "page"),
            "usable_as_hook": hook, "note": note}


# ---------------------------------------------------------------- the four answers

def gate(p):
    for f in pic.facts_for(p, "b2b_saas"):
        if f["value"].startswith(("yes", "no")):
            ans = "yes" if f["value"].startswith("yes") else "no"
            return {"answer": ans, "evidence": [ev(f)], "why": f"The site shows it is{' ' if ans == 'yes' else ' NOT '}B2B SaaS."}
    return {"answer": "unknown", "evidence": [], "why": "No quote shows whether it sells software to businesses."}


def q1_from(facts):
    """facts with a 'quote'. Returns the Q1 answer dict, or None if nothing usable."""
    best = None
    for f in facts:
        q = f["quote"]
        if PUBLIC.search(q):
            return {"answer": "no", "evidence": [ev(f, "public company")], "why": "Publicly listed (D+ / public = NO)."}
        for m in SERIES.finditer(q):
            pre, letter, plus = m.group(1), m.group(2).upper(), m.group(3)
            if pre or plus:
                continue  # "pre-Series B" / "Series A+" stay unknown (owner's decision)
            if best is None or letter > best[0]:
                best = (letter, f)
    if best is None:
        return None
    letter, f = best
    if letter in "ABC":
        return {"answer": "yes", "evidence": [ev(f, f"Series {letter}")], "why": f"Series {letter} (A-C = YES)."}
    return {"answer": "no", "evidence": [ev(f, f"Series {letter} (D+)")], "why": f"Series {letter} is D or later (NO)."}


def q1(p):
    return q1_from(pic.facts_for(p, "funding_stage")) or {
        "answer": "unknown", "evidence": [], "why": "No 'Series X' quote on the site."}


def q2(p):
    held = pic.facts_for(p, "certification_held")
    soc = [f for f in held if SOC2.search(f["quote"])]
    iso = [f for f in held if ISO27001.search(f["quote"])]
    if soc and iso:
        return {"answer": "no", "evidence": [ev(soc[0], "SOC 2 held"), ev(iso[0], "ISO 27001 held")],
                "why": "Already holds BOTH SOC 2 and ISO 27001 (drop)."}
    for f in pic.facts_for(p, "certification_in_progress"):
        if IN_PROGRESS.search(f["quote"]) and (SOC2.search(f["quote"]) or ISO27001.search(f["quote"]) or "certif" in f["quote"].lower()):
            return {"answer": "yes", "evidence": [ev(f, "certification in progress")], "why": "A certification is in progress."}
    for f in pic.facts_for(p, "security_or_compliance_job"):
        if SEC_JOB.search(f["quote"]):
            return {"answer": "yes", "evidence": [ev(f, "security/compliance job")], "why": "Hiring for security/compliance."}
    held_note = " (holds only one of SOC 2 / ISO 27001)" if (soc or iso) else ""
    return {"answer": "unknown", "evidence": [ev(f, "held") for f in soc + iso],
            "why": "No audit-prep signal on the site" + held_note + ". 'No certs listed' is not a YES."}


def q3(p):
    for f in pic.facts_for(p, "enterprise_plan"):
        if ENTERPRISE.search(f["quote"]):
            return {"answer": "yes", "evidence": [ev(f, "enterprise plan")], "why": "Has an Enterprise plan."}
    for f in pic.facts_for(p, "security_review"):
        if SEC_REVIEW.search(f["quote"]):
            return {"answer": "yes", "evidence": [ev(f, "security review")], "why": "Mentions customer security reviews."}
    named = pic.facts_for(p, "named_customer")
    if named:
        return {"answer": "yes", "evidence": [ev(f, "named customer (weak: check it is not an investor)") for f in named[:3]],
                "why": "Names customers (weak signal; a human should check)."}
    return {"answer": "unknown", "evidence": [], "why": "No enterprise plan, security review or named customer quoted."}


def decide(g, a1, a2, a3):
    answers = [a1, a2, a3]
    if g == "no":
        return "No-Go", "Not a B2B SaaS company."
    if "no" in answers:
        return "No-Go", "One of the checks is NO."
    yes, unknown = answers.count("yes"), answers.count("unknown")
    if yes == 3:
        return ("Flag", "All checks YES but B2B SaaS is unknown.") if g == "unknown" else ("Go", "All checks YES.")
    if yes == 2 and unknown == 1:
        return "Flag", "Two checks YES, one unknown: needs a human decision."
    return "No-Go", f"{unknown} checks unknown (insufficient data)."


# ---------------------------------------------------------------- searches (agent loop)

def search_quote(results, task, ai):
    """Ask the AI to point at one result and copy a quote; keep it only if it is really there."""
    if not results:
        return None, "no results"
    listing = "\n\n".join(f"[{r['n']}] {r['title']}\n{r['snippet']}\n{r['link']}" for r in results)
    system = ("You read Google search results. Copy text WORD FOR WORD from one result's title or snippet. "
              "Never guess. If no result clearly says it, return found=false.")
    out = ai(system, f"{task}\n\nResults:\n{listing}", SEARCH_SCHEMA) or {}
    if not out.get("found"):
        return None, "no result stated it"
    r = next((x for x in results if x["n"] == out.get("result")), None)
    quote = str(out.get("quote", ""))
    if r is None:
        return None, "the AI pointed at a result that does not exist"
    if not (evidence.quote_in(quote, r["title"]) or evidence.quote_in(quote, r["snippet"])):
        return None, f"rejected: quote not word for word in result {r['n']}"
    return {"source_url": r["link"], "quote": quote, "from": "search"}, "ok"


def run(domain, p, ai, search=None):
    """search(query) -> results, or None when no search key is set."""
    name = pic.company_name(p, domain)
    g, a1, a2, a3 = gate(p), q1(p), q2(p), q3(p)
    searches = []
    dropped = g["answer"] == "no" or "no" in (a1["answer"], a2["answer"], a3["answer"])

    if search and not dropped and a1["answer"] == "unknown":
        query = f"{name} funding round Series"
        found, note = search_quote(search(query), f"Which funding round did {name} ({domain}) raise most recently "
                                   "(for example 'Series B')? Copy the text that says it.", ai)
        searches.append({"query": query, "result": note})
        if found:
            a1 = q1_from([found]) or a1
            if a1["answer"] == "unknown":
                searches[-1]["result"] = "quote found but it does not name a usable 'Series X'"
        dropped = dropped or a1["answer"] == "no"

    if search and not dropped and a2["answer"] == "unknown":
        query = f"{name} data breach"
        found, note = search_quote(search(query), f"Does any result report a data breach, leak, hack or security "
                                   f"incident AT {name} ({domain}) itself? Copy the text that says it.", ai)
        searches.append({"query": query, "result": note})
        if found:
            if BREACH.search(found["quote"]) and name.lower() in found["quote"].lower():
                a2 = {"answer": "yes", "evidence": [ev(found, "breach news (never an email hook)", hook=False)],
                      "why": "Breach / incident news found (qualifies, but never used as a hook)."}
            else:
                searches[-1]["result"] = "quote found but it does not name the company and a breach"

    if not search:
        searches.append({"query": None, "result": "searches skipped: no Serper key set"})
    elif dropped and not searches:
        searches.append({"query": None, "result": "no searches: company already dropped"})

    decision, reason = decide(g["answer"], a1["answer"], a2["answer"], a3["answer"])
    return {"company_name": name, "gate": g, "q1": a1, "q2": a2, "q3": a3,
            "decision": decision, "decision_reason": reason, "searches": searches}

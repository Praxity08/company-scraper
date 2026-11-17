"""Step 5: pick up to 2 pain points for the contact's role group from the owner's approved list.

Plain code, no AI. Pain points are TYPICAL challenges for the role, never facts about the company.
A "needs evidence" row is used only when the company picture has a matching quoted page fact.
"""
import re

import checks
import picture as pic

GROUP_BY_RULE = {1: "S", 2: "C", 3: "F"}
GROUP_NAMES = {"S": "security / compliance", "C": "CTO / engineering", "F": "founder"}
MAX_PICKS = 2


def _evidence(picture, kind):
    """Quoted page facts that back one kind of evidence (same word tests as the checks)."""
    if kind == "cert_in_progress":
        facts = [f for f in pic.facts_for(picture, "certification_in_progress") if checks.IN_PROGRESS.search(f["quote"])]
    elif kind == "compliance_job":
        facts = [f for f in pic.facts_for(picture, "security_or_compliance_job") if checks.SEC_JOB.search(f["quote"])]
    elif kind == "team_size":
        facts = [f for f in pic.facts_for(picture, "team_size") if re.search(r"\d", f["quote"])]
    else:
        facts = []
    return [{"kind": kind, "source_url": f["source_url"], "quote": f["quote"]} for f in facts]


def pick(picture, rule, pain_list):
    group = GROUP_BY_RULE.get(rule)
    if group is None:
        return {"group": None, "picked": [], "skipped": [], "why": "The contact's role group is not known."}
    backed, general, skipped = [], [], []
    for row in pain_list["rows"]:
        if row["group"] != group:
            continue
        if row["needs"]:
            found = [e for kind in row["needs"] for e in _evidence(picture, kind)]
            if found:
                backed.append(dict(row, evidence=found[:2], note="backed by a quoted page fact"))
            else:
                skipped.append({"id": row["id"], "reason": "needs evidence (" + ", ".join(row["needs"]) + ") and none was quoted"})
        else:
            general.append(dict(row, evidence=[], note="typical for the role; no company-specific evidence"))
    picked = (backed + general)[:MAX_PICKS]
    for row in (backed + general)[MAX_PICKS:]:
        skipped.append({"id": row["id"], "reason": "only 2 are used"})
    return {"group": group, "group_name": GROUP_NAMES[group], "picked": picked, "skipped": skipped,
            "list_status": pain_list["status"],
            "why": f"{len(picked)} picked for the {GROUP_NAMES[group]} group."}

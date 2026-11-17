"""Runs one pipeline step for one saved scrape and stores it in the campaign record.

Order: scrape -> picture -> check (Go / No-Go / Flag) -> [approve a Flag] -> contact (Hunter)
       -> pain points -> email draft -> send to the OWNER's inbox (never the prospect).
Each function returns (http_status, payload).
"""
import re
from datetime import datetime, timezone

import checks
import db
import emaildraft
import gemini
import pain
import picture as pic
import playbook
import resendmail
import scraper
import serper
import settings


def _ai():
    key, model = settings.gemini_key(), settings.gemini_model()

    def ai(system, prompt, schema):
        return gemini.generate_json(system, prompt, schema, key, model)
    return ai, key


def _search():
    key = settings.serper_key()
    if not key:
        return None

    def search(query):
        try:
            return serper.search(query, key)
        except serper.SearchError:
            return []
    return search


def state(conn, scrape_id):
    """Everything the page needs to show where a company stands, plus the next step."""
    camp = db.get_campaign(conn, scrape_id) or {}
    contact = db.get_contact(conn, scrape_id)
    if not camp.get("picture"):
        nxt = "picture"
    elif not camp.get("decision"):
        nxt = "check"
    elif camp["decision"] == "Flag" and not camp.get("flag_approved"):
        nxt = "approve"
    elif not contact or contact["outcome"] == "pending":
        nxt = "contact"
    elif contact["outcome"] != "found":
        nxt = "done"
    elif not camp.get("pain"):
        nxt = "pain"
    elif not camp.get("email"):
        nxt = "draft"
    elif not camp["email"].get("hooks"):
        nxt = "done"                       # no hook = no email
    elif not camp.get("sent_at"):
        nxt = "send"
    else:
        nxt = "done"
    status, steps = status_and_next_steps(camp, contact, nxt)
    return {"campaign": camp or None, "contact": contact, "next": nxt, "status": status, "next_steps": steps}


def status_and_next_steps(camp, contact, nxt):
    """Plain-English status line and what to do next, for the campaign record."""
    d = camp.get("decision")
    email = camp.get("email") or {}
    if camp.get("sent_at"):
        r = camp.get("send_result") or {}
        if r.get("ok"):
            return ("Draft delivered to your inbox and logged",
                    ["Read the draft in your inbox.", "If you want to use it, send it yourself from your own email."])
        return ("Send outcome unclear", [r.get("error") or "Check your inbox before doing anything else."])
    if email and not email.get("hooks"):
        return ("No hook found, so no email", ["Nothing on the company's own pages passed the hook rules. Stop here."])
    if nxt == "done":
        return ("No contact found", ["Hunter found nobody in the security, engineering or founder roles. Stop here."])
    return {
        "picture": ("Scraped", ["Build the company picture."]),
        "check": ("Picture built", ["Run the checks to get Go / No-Go / Flag."]),
        "approve": ("Flag: waiting for your approval", ["Read the evidence. Approve the Flag only if it looks right."]),
        "contact": ((f"{d}: ready for Hunter" if d != "No-Go" else "No-Go"),
                    ["Find the contact with Hunter."] if d != "No-Go" else
                    ["Stop here, unless this is a TEST ONLY run (only those let Hunter run on a No-Go)."]),
        "pain": ("Contact found", ["Pick the pain points."]),
        "draft": ("Pain points picked", ["Draft the email."]),
        "send": ("Email drafted, ready for review",
                 [f"Read the draft, then type: send {camp.get('domain', '<domain>')}, hook <number>"]),
    }.get(nxt, ("", []))


def _load(conn, scrape_id):
    scrape = db.get_scrape(conn, scrape_id)
    if scrape is None:
        return None, (404, {"error": "That scrape was not found."})
    if scraper.is_do_not_contact(scrape["domain"], scraper.load_do_not_contact()):
        return None, (403, {"error": f"{scrape['domain']} is on the do-not-contact list."})
    return scrape, None


def run_picture(conn, scrape_id, ai=None):
    scrape, err = _load(conn, scrape_id)
    if err:
        return err
    if scrape.get("status") != "ok":
        return 409, {"error": "Nothing readable was scraped for this company, so there is nothing to read."}
    if ai is None:
        ai, key = _ai()
        if not key:
            return 503, {"error": "The AI is not set up (GEMINI_API_KEY missing)."}
    if not db.reserve(conn, "analysis", settings.ANALYSIS_DAILY_CAP):
        return 429, {"error": f"Daily AI limit reached ({settings.ANALYSIS_DAILY_CAP} company pictures per day, India time)."}
    try:
        picture = pic.build(scrape, ai)
    except gemini.AIError as e:
        db.release(conn, "analysis")
        return 502, {"error": str(e)}
    picture["model"] = settings.gemini_model()
    # a new picture makes the old checks and everything after them out of date
    db.update_campaign(conn, scrape_id, scrape["domain"], picture=picture, checks=None, decision=None,
                       flag_approved=False, pain=None, email=None)
    return 200, state(conn, scrape_id)


def run_check(conn, scrape_id, ai=None, search="default"):
    scrape, err = _load(conn, scrape_id)
    if err:
        return err
    camp = db.get_campaign(conn, scrape_id) or {}
    if not camp.get("picture"):
        return 409, {"error": "Build the company picture first."}
    if camp.get("sent_at"):
        return 409, {"error": "The email for this company was already sent; the checks are locked."}
    if ai is None:
        ai, key = _ai()
        if not key:
            return 503, {"error": "The AI is not set up (GEMINI_API_KEY missing)."}
    if search == "default":
        search = _search()
    try:
        result = checks.run(scrape["domain"], camp["picture"], ai, search)
    except gemini.AIError as e:
        return 502, {"error": str(e)}
    db.update_campaign(conn, scrape_id, scrape["domain"], checks=result, decision=result["decision"],
                       flag_approved=False, pain=None, email=None)
    return 200, state(conn, scrape_id)


def approve_flag(conn, scrape_id):
    scrape, err = _load(conn, scrape_id)
    if err:
        return err
    camp = db.get_campaign(conn, scrape_id) or {}
    if camp.get("decision") != "Flag":
        return 409, {"error": "Only a Flag needs (and can get) a human approval."}
    db.update_campaign(conn, scrape_id, scrape["domain"], flag_approved=True)
    return 200, state(conn, scrape_id)


def contact_allowed(campaign, test_only):
    """Hunter rule: Go yes; Flag only after a human approved it; No-Go never (TEST ONLY overrides)."""
    decision = (campaign or {}).get("decision")
    if not decision:
        return False, "Run the checks first (Hunter only runs after a Go / No-Go / Flag decision)."
    if test_only:
        return True, ""
    if decision == "No-Go":
        return False, "This company is No-Go, so Hunter will not run (only a TEST ONLY run can override that)."
    if decision == "Flag" and not campaign.get("flag_approved"):
        return False, "This company is a Flag: approve it first, then Hunter can run."
    return True, ""


# ---------------------------------------------------------------- pain points, draft, send

def _contact_found(conn, scrape_id, camp=None, test_only=False):
    """The found contact, or None. Also None if the decision no longer allows outreach
    (e.g. the checks were re-run and it is now a No-Go)."""
    if camp is not None and not contact_allowed(camp, test_only)[0]:
        return None
    c = db.get_contact(conn, scrape_id)
    return c["contact"] if c and c["outcome"] == "found" else None


def run_pain(conn, scrape_id):
    scrape, err = _load(conn, scrape_id)
    if err:
        return err
    camp = db.get_campaign(conn, scrape_id) or {}
    contact = _contact_found(conn, scrape_id, camp, scrape.get("test_only"))
    if not contact:
        return 409, {"error": "Needs a found contact and a decision that allows outreach "
                              "(Go, an approved Flag, or a TEST ONLY run)."}
    if camp.get("sent_at"):
        return 409, {"error": "The email for this company was already sent; this step is locked."}
    try:
        plist = playbook.load_pain_points()
    except (OSError, playbook.PlaybookError) as e:
        return 500, {"error": f"Could not read the pain-point list: {e}"}
    ok, why = playbook.usable(plist["status"], scrape.get("test_only"), "docs/pain-points.md")
    if not ok:
        return 403, {"error": why}
    result = pain.pick(camp.get("picture"), contact.get("rule"), plist)
    if not result["picked"]:
        return 409, {"error": "No usable pain point for this contact's role group.", "pain": result}
    db.update_campaign(conn, scrape_id, scrape["domain"], pain=result, email=None)
    return 200, state(conn, scrape_id)


def run_draft(conn, scrape_id, ai=None):
    scrape, err = _load(conn, scrape_id)
    if err:
        return err
    camp = db.get_campaign(conn, scrape_id) or {}
    contact = _contact_found(conn, scrape_id, camp, scrape.get("test_only"))
    if not contact or not (camp.get("pain") or {}).get("picked"):
        return 409, {"error": "Pick the pain points first."}
    if camp.get("sent_at"):
        return 409, {"error": "The email for this company was already sent; the draft is locked."}
    try:
        wording = playbook.load_email_settings()
    except (OSError, playbook.PlaybookError) as e:
        return 500, {"error": f"Could not read the email wording: {e}"}
    test_only = bool(scrape.get("test_only"))
    ok, why = playbook.usable(wording["status"], test_only, "docs/email-settings.md")
    if not ok:
        return 403, {"error": why}
    if not test_only and "[" in wording["settings"]["sender_name"]:
        return 403, {"error": "Fill in your name (sender_name) in docs/email-settings.md first."}
    if ai is None:
        ai, key = _ai()
        if not key:
            return 503, {"error": "The AI is not set up (GEMINI_API_KEY missing)."}
    if not db.reserve(conn, "analysis", settings.ANALYSIS_DAILY_CAP):
        return 429, {"error": f"Daily AI limit reached ({settings.ANALYSIS_DAILY_CAP} AI steps per day, India time)."}
    try:
        hooks, rejected = emaildraft.find_hooks(scrape, ai)
    except gemini.AIError as e:
        db.release(conn, "analysis")
        return 502, {"error": str(e)}
    email = {"hooks": hooks, "rejected_hooks": rejected, "test_only": test_only,
             "wording_status": wording["status"], "pain_ids": [p["id"] for p in camp["pain"]["picked"]]}
    if hooks:
        email.update(_render(wording, scrape, camp, contact, hooks[0]))
        email["chosen"] = 1
    else:
        email["note"] = "no hook found: nothing passed the hook rules, so there is no email"
    db.update_campaign(conn, scrape_id, scrape["domain"], email=email)
    return 200, state(conn, scrape_id)


def _render(wording, scrape, camp, contact, hook):
    subject, body, n = emaildraft.render(
        wording, company=pic.company_name(camp.get("picture"), scrape["domain"]),
        first_name=emaildraft.first_name(contact), hook=hook["quote"], group=camp["pain"]["group"],
        pain_phrases=[p["phrase"] for p in camp["pain"]["picked"]], test_only=bool(scrape.get("test_only")))
    return {"subject": subject, "body": body, "words": n, "hook_n": hook["n"], "hook_source": hook["source_url"]}


SEND_COMMAND = re.compile(r"send (\S+), hook (\d+)")


def run_send(conn, scrape_id, command="", send=None):
    """Sends ONLY to the owner's own TO_EMAIL, on the exact typed command 'send <domain>, hook <n>'."""
    scrape, err = _load(conn, scrape_id)
    if err:
        return err
    camp = db.get_campaign(conn, scrape_id) or {}
    email = camp.get("email") or {}
    contact = _contact_found(conn, scrape_id, camp, scrape.get("test_only"))
    if not email.get("hooks") or not contact:
        return 409, {"error": "There is no draft with a hook to send."}
    if camp.get("sent_at"):
        return 409, {"error": "Already sent once. An email is never sent twice."}
    m = SEND_COMMAND.fullmatch((command or "").strip())
    if not m or m.group(1) != scrape["domain"]:
        return 400, {"error": f"Type exactly: send {scrape['domain']}, hook <number>"}
    n = int(m.group(2))
    hook = next((h for h in email["hooks"] if h["n"] == n), None)
    if hook is None:
        return 400, {"error": f"There is no hook {n}. Pick one of: " + ", ".join(str(h["n"]) for h in email["hooks"])}
    try:
        wording = playbook.load_email_settings()
    except (OSError, playbook.PlaybookError) as e:
        return 500, {"error": f"Could not read the email wording: {e}"}
    ok, why = playbook.usable(wording["status"], scrape.get("test_only"), "docs/email-settings.md")
    if not ok:
        return 403, {"error": why}
    key, to = settings.resend_key(), settings.to_email()
    if not key or not to:
        return 503, {"error": "Sending is not set up (RESEND_API_KEY or TO_EMAIL missing)."}
    if send is None:
        send = resendmail.send

    msg = _render(wording, scrape, camp, contact, hook)
    review = [
        "DRAFT FOR YOUR REVIEW. This went only to you, never to the contact.",
        "TEST ONLY run: do not use this email." if scrape.get("test_only") else "",
        f"Intended for: {contact.get('name')}, {contact.get('position')} <{contact.get('email')}>"
        f" (Hunter confidence {contact.get('confidence')}{', LOW CONFIDENCE' if contact.get('low_confidence') else ''})",
        f"Decision: {camp.get('decision')}{' (Flag approved by you)' if camp.get('flag_approved') else ''}",
        f"Hook {n} source: {hook['source_url']}",
        "Pain points: " + ", ".join(p["id"] for p in camp["pain"]["picked"]),
        "-" * 60,
    ]
    text = "\n".join(line for line in review if line) + "\n\n" + msg["body"]

    if not db.reserve(conn, "send", settings.SEND_DAILY_CAP):
        return 429, {"error": f"Daily send limit reached ({settings.SEND_DAILY_CAP} per day, India time)."}
    if not db.mark_sent(conn, scrape_id):
        db.release(conn, "send")
        return 409, {"error": "Already sent once. An email is never sent twice."}
    now = datetime.now(timezone.utc).isoformat()
    try:
        rid = send(msg["subject"], text, key, to)
    except resendmail.SendError as e:
        db.unmark_sent(conn, scrape_id)          # Resend refused: nothing went out
        db.release(conn, "send")
        db.save_send_result(conn, scrape_id, {"ok": False, "error": str(e), "at": now, "hook": n})
        return 502, {"error": str(e)}
    except resendmail.SendUnknown as e:          # may have gone out: stays marked as sent
        db.save_send_result(conn, scrape_id, {"ok": None, "error": str(e), "at": now, "hook": n})
        return 502, {"error": str(e)}
    db.save_send_result(conn, scrape_id, {"ok": True, "id": rid, "at": now, "hook": n, "to": "your own inbox",
                                          "subject": msg["subject"], "words": msg["words"]})
    email.update(msg, chosen=n)
    db.update_campaign(conn, scrape_id, scrape["domain"], email=email)
    return 200, state(conn, scrape_id)

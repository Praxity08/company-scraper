"""Runs one pipeline step for one saved scrape and stores it in the campaign record.

Order: scrape -> picture -> check (Go / No-Go / Flag) -> [approve a Flag] -> contact (Hunter)
       -> pain points -> email draft -> send to the OWNER's inbox (never the prospect).
Each function returns (http_status, payload).
"""
import checks
import db
import gemini
import picture as pic
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
    elif not camp.get("pain"):
        nxt = "pain"
    elif not camp.get("email"):
        nxt = "draft"
    elif not camp.get("sent_at"):
        nxt = "send"
    else:
        nxt = "done"
    return {"campaign": camp or None, "contact": contact, "next": nxt}


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

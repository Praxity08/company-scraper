"""The 'Find contact' flow: checks, daily cap, one Hunter lookup, save.

Kept apart from the web function so the tests can run it with a fake Hunter.
Returns (http_status, payload).
"""
import db
import hunter
import scraper
import settings


def usage(conn):
    return {"hunter_used": db.count(conn, "hunter"), "hunter_cap": settings.HUNTER_DAILY_CAP}


def lookup(conn, scrape_id, api_key, search=hunter.domain_search):
    if not api_key:
        return 503, {"error": "Hunter is not set up (HUNTER_API_KEY missing)."}
    db.purge_old_contacts(conn, settings.CONTACT_KEEP_DAYS)

    scrape = db.get_scrape(conn, scrape_id)
    if scrape is None:
        return 404, {"error": "That scrape was not found."}
    domain = scrape["domain"]
    if scraper.is_do_not_contact(domain, scraper.load_do_not_contact()):
        return 403, {"error": f"{domain} is on the do-not-contact list."}

    existing = db.get_contact(conn, scrape_id)
    if existing and existing["outcome"] != "pending":
        return 200, dict(existing, already=True, usage=usage(conn))

    import pipeline  # here to avoid a circular import
    ok, why = pipeline.contact_allowed(db.get_campaign(conn, scrape_id), scrape.get("test_only"))
    if not ok:
        return 403, {"error": why, "usage": usage(conn)}

    if existing or not db.claim_contact(conn, scrape_id, domain):
        return 409, {"error": "A lookup for this scrape is already running. Try again in a minute."}

    if not db.reserve(conn, "hunter", settings.HUNTER_DAILY_CAP):
        db.release_contact(conn, scrape_id)
        return 429, {"error": f"Daily Hunter limit reached ({settings.HUNTER_DAILY_CAP} per day, India time).",
                     "usage": usage(conn)}

    try:
        people = search(domain, api_key)
    except hunter.HunterError as e:
        db.release(conn, "hunter")          # nothing was found, give the lookup back
        db.release_contact(conn, scrape_id)
        return 502, {"error": hunter.scrub(str(e), api_key), "usage": usage(conn)}

    contact = hunter.pick(people)
    outcome = "found" if contact else "none"
    if contact is None:
        contact = {"people_returned": len(people)}
    if scrape.get("test_only"):
        contact["TEST_ONLY"] = True
        contact["do_not_email"] = True
    db.finish_contact(conn, scrape_id, outcome, contact)
    return 200, {"outcome": outcome, "contact": contact, "already": False, "usage": usage(conn)}

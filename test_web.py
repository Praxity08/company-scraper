"""Checks for Hunter, the contact flow and Neon storage. Made-up data only (fake-co.com, Pat Lee).

Run: .venv/bin/python -m unittest test_web -v
The database tests run only when DATABASE_URL is set (from .env). They work inside their
own throw-away schema named test_<random> and drop only that schema; they never touch public.
Hunter is never called for real: a fake search function is used.
"""
import unittest
from unittest import mock

import hunter
import settings
import testutil

settings.load_env()
FAKE_KEY = "fake-key-1234567890"


def person(first, last, title, conf=90, email=None, status="valid"):
    return {"first_name": first, "last_name": last, "position": title, "confidence": conf,
            "value": email or f"{first.lower()}@fake-co.com", "verification": {"status": status},
            "sources": [{"uri": "https://fake-co.com/team"}]}


class TestPick(unittest.TestCase):
    def test_role_order(self):
        people = [person("Ann", "Roy", "Founder & CEO"), person("Pat", "Lee", "CTO"),
                  person("Sam", "Das", "Head of Information Security", conf=70)]
        c = hunter.pick(people)
        self.assertEqual((c["name"], c["rule"]), ("Sam Das", 1))
        self.assertTrue(c["low_confidence"])          # 70 < 80, still shown
        self.assertEqual(c["position"], "Head of Information Security")
        self.assertEqual(c["sources"], ["https://fake-co.com/team"])

    def test_cofounder_cto_is_rule_2_and_confidence_breaks_ties(self):
        people = [person("Ann", "Roy", "Co-founder & CTO", conf=85), person("Pat", "Lee", "VP Engineering", conf=95)]
        c = hunter.pick(people)
        self.assertEqual((c["name"], c["rule"]), ("Pat Lee", 2))
        self.assertFalse(c["low_confidence"])

    def test_founder_last(self):
        c = hunter.pick([person("Ann", "Roy", "Sales Manager"), person("Pat", "Lee", "Co-Founder")])
        self.assertEqual((c["name"], c["rule"]), ("Pat Lee", 3))

    def test_skips_no_name_or_title_and_returns_none(self):
        people = [{"first_name": None, "position": "CISO", "value": "x@fake-co.com"},
                  person("Pat", "Lee", "")]
        people[1]["position"] = ""
        self.assertIsNone(hunter.pick(people))
        self.assertIsNone(hunter.pick([person("Ann", "Roy", "Marketing Lead")]))

    def test_security_word_must_be_a_word(self):
        # "securities" (finance) is not a security role
        self.assertIsNone(hunter.pick([person("Ann", "Roy", "Securities Analyst")]))


class FakeResp:
    def __init__(self, code, data):
        self.status_code, self._data = code, data

    def json(self):
        return self._data


class TestHunterCall(unittest.TestCase):
    def test_key_goes_in_header_not_url(self):
        with mock.patch("hunter.requests.get", return_value=FakeResp(200, {"data": {"emails": [1]}})) as g:
            self.assertEqual(hunter.domain_search("fake-co.com", FAKE_KEY), [1])
        _, kwargs = g.call_args
        self.assertEqual(kwargs["headers"]["X-API-KEY"], FAKE_KEY)
        self.assertNotIn(FAKE_KEY, str(kwargs["params"]))

    def test_error_never_shows_key(self):
        bad = FakeResp(401, {"errors": [{"details": f"No user found for the API key {FAKE_KEY}"}]})
        with mock.patch("hunter.requests.get", return_value=bad):
            with self.assertRaises(hunter.HunterError) as ctx:
                hunter.domain_search("fake-co.com", FAKE_KEY)
        self.assertIn("HTTP 401", str(ctx.exception))
        self.assertNotIn(FAKE_KEY, str(ctx.exception))


@unittest.skipUnless(settings.database_url(), "DATABASE_URL not set: database tests skipped")
class TestDatabaseFlow(testutil.SchemaMixin, unittest.TestCase):
    """Runs against Neon inside a throw-away schema."""

    def new_scrape(self, domain="fake-co.com"):
        result = {"domain": domain, "status": "ok", "found": ["homepage"], "missing": ["pricing"],
                  "pages": {"homepage": {"text": "Fake Co helps teams."}}}
        sid, _ = self.db.save_scrape(self.conn, result)
        self.db.update_campaign(self.conn, sid, domain, decision="Go")
        return sid

    def fake_search(self, people):
        calls = []

        def search(domain, key):
            calls.append(domain)
            return people
        return search, calls

    def test_1_save_list_open(self):
        sid = self.new_scrape()
        got = self.db.get_scrape(self.conn, sid)
        self.assertEqual((got["domain"], got["scrape_id"]), ("fake-co.com", sid))
        listed = self.db.list_scrapes(self.conn, 20)
        self.assertEqual(listed[0]["id"], sid)
        self.assertNotIn("pages", listed[0])                 # list never carries page text
        self.assertIsNone(self.db.get_scrape(self.conn, "not-an-id"))

    def test_2_lookup_once_then_cap(self):
        import contactflow
        self.conn.execute(f'DELETE FROM "{self.schema}".counters')
        search, calls = self.fake_search([person("Pat", "Lee", "CTO")])

        a = self.new_scrape()
        code, out = contactflow.lookup(self.conn, a, FAKE_KEY, search)
        self.assertEqual((code, out["outcome"], out["contact"]["name"]), (200, "found", "Pat Lee"))
        self.assertEqual(out["usage"]["hunter_used"], 1)

        # never twice: same scrape again returns the saved contact, no new Hunter call
        code, out = contactflow.lookup(self.conn, a, FAKE_KEY, search)
        self.assertEqual((code, out["already"], len(calls)), (200, True, 1))

        b = self.new_scrape()
        code, out = contactflow.lookup(self.conn, b, FAKE_KEY, self.fake_search([])[0])
        self.assertEqual((code, out["outcome"], out["usage"]["hunter_used"]), (200, "none", 2))

        c = self.new_scrape()
        code, out = contactflow.lookup(self.conn, c, FAKE_KEY, search)
        self.assertEqual(code, 429)                            # 3rd lookup of the day refused
        self.assertIsNone(self.db.get_contact(self.conn, c))   # and nothing left behind
        self.assertEqual(len(calls), 1)

    def test_3_hunter_error_gives_lookup_back(self):
        import contactflow
        self.conn.execute(f'DELETE FROM "{self.schema}".counters')

        def broken(domain, key):
            raise hunter.HunterError(f"Hunter returned HTTP 401: bad key {key}")

        sid = self.new_scrape()
        code, out = contactflow.lookup(self.conn, sid, FAKE_KEY, broken)
        self.assertEqual(code, 502)
        self.assertNotIn(FAKE_KEY, out["error"])
        self.assertEqual(out["usage"]["hunter_used"], 0)
        self.assertIsNone(self.db.get_contact(self.conn, sid))  # can be tried again

    def test_4_do_not_contact_and_missing_key(self):
        import contactflow
        sid = self.new_scrape("whatfix.com")
        code, _ = contactflow.lookup(self.conn, sid, FAKE_KEY, self.fake_search([])[0])
        self.assertEqual(code, 403)
        code, _ = contactflow.lookup(self.conn, self.new_scrape(), "", self.fake_search([])[0])
        self.assertEqual(code, 503)

    def test_5_contacts_deleted_after_30_days(self):
        sid = self.new_scrape()
        self.db.claim_contact(self.conn, sid, "fake-co.com")
        self.db.finish_contact(self.conn, sid, "found", {"name": "Pat Lee"})
        self.conn.execute(f'UPDATE "{self.schema}".contacts SET created_at = now() - interval \'31 days\' '
                          'WHERE scrape_id = %s', (self.db.as_uuid(sid),))
        self.db.purge_old_contacts(self.conn, settings.CONTACT_KEEP_DAYS)
        self.assertIsNone(self.db.get_contact(self.conn, sid))
        self.assertIsNotNone(self.db.get_scrape(self.conn, sid))  # the scrape itself stays


if __name__ == "__main__":
    unittest.main()

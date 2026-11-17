"""Checks for the company picture, the Evidence-Map checks and the step runner.

Made-up data only (fake-co.com). The AI and the search are FAKES: nothing calls Gemini or Serper.
Run: .venv/bin/python -m unittest test_pipeline -v
"""
import unittest
from unittest import mock

import checks
import evidence
import picture as pic
import serper
import settings
import testutil

settings.load_env()

HOME = "https://fake-co.com/"
PRICING = "https://fake-co.com/pricing"
SCRAPE = {
    "domain": "fake-co.com", "status": "ok", "found": ["homepage", "pricing"], "missing": [],
    "pages": {
        "homepage": {"url": HOME, "text": "Fake Co is a B2B SaaS platform for finance teams.\n"
                                          "Trusted by Big Bank Ltd.\nWe raised our Series B in 2025."},
        "pricing": {"url": PRICING, "text": "Starter\nGrowth\nEnterprise plan with SSO and audit logs"},
        "about": None,
    },
}


def fact(field, quote, url=HOME, value=None):
    return {"field": field, "value": value or quote, "source_url": url, "quote": quote}


def fake_ai(*answers):
    """An AI stand-in that returns the given answers in order and records the prompts."""
    calls = []

    def ai(system, prompt, schema):
        calls.append(prompt)
        return answers[len(calls) - 1] if len(calls) <= len(answers) else {"found": False}
    ai.calls = calls
    return ai


def picture_with(*facts):
    return {"facts": list(facts), "rejected": []}


class TestEvidence(unittest.TestCase):
    def test_word_for_word(self):
        self.assertTrue(evidence.quote_in("It’s  a B2B\nplatform", "It's a B2B platform for teams"))
        self.assertFalse(evidence.quote_in("a B2C platform", "It's a B2B platform"))
        self.assertFalse(evidence.quote_in("", "anything"))


class TestPicture(unittest.TestCase):
    def test_keeps_only_real_quotes(self):
        ai = fake_ai({"facts": [
            fact("b2b_saas", "Fake Co is a B2B SaaS platform", value="Yes"),
            fact("enterprise_plan", "Enterprise plan with SSO", url=PRICING),
            fact("named_customer", "Trusted by Big Bank Ltd."),
            fact("funding_stage", "We raised Series C"),                       # not on the page
            fact("team_size", "200 people", url="https://other.com/"),          # not a scraped page
            fact("nonsense", "Fake Co", value="x"),                             # unknown field
        ]})
        p = pic.build(SCRAPE, ai)
        kept = {f["field"] for f in p["facts"]}
        self.assertEqual(kept, {"b2b_saas", "enterprise_plan", "named_customer"})
        self.assertEqual(len(p["rejected"]), 3)
        self.assertEqual(pic.facts_for(p, "b2b_saas")[0]["value"], "yes")       # lower-cased
        self.assertIn("=== PAGE: pricing | URL: https://fake-co.com/pricing ===", ai.calls[0])

    def test_no_readable_pages_means_no_ai_call(self):
        ai = fake_ai()
        p = pic.build({"domain": "fake-co.com", "pages": {"homepage": None}}, ai)
        self.assertEqual((p["facts"], ai.calls), ([], []))


class TestRules(unittest.TestCase):
    def q1(self, quote):
        return checks.q1(picture_with(fact("funding_stage", quote)))["answer"]

    def test_q1_series_rules(self):
        self.assertEqual(self.q1("We raised our Series B in 2025."), "yes")
        self.assertEqual(self.q1("closed a $40M Series D round"), "no")
        self.assertEqual(self.q1("raised a pre-Series B round"), "unknown")
        self.assertEqual(self.q1("our Series A+ round"), "unknown")
        self.assertEqual(self.q1("a seed round led by Fake VC"), "unknown")
        self.assertEqual(self.q1("Fake Co is listed on the NSE"), "no")
        # newest round wins when several are quoted
        p = picture_with(fact("funding_stage", "Series A in 2021"), fact("funding_stage", "Series E in 2025"))
        self.assertEqual(checks.q1(p)["answer"], "no")

    def test_q2_rules(self):
        both = picture_with(fact("certification_held", "We are SOC 2 Type II certified"),
                            fact("certification_held", "ISO 27001 certified"))
        self.assertEqual(checks.q2(both)["answer"], "no")
        one = picture_with(fact("certification_held", "We are SOC 2 Type II certified"))
        self.assertEqual(checks.q2(one)["answer"], "unknown")                   # strict: not a YES
        self.assertEqual(checks.q2(picture_with())["answer"], "unknown")         # no certs listed != YES
        prog = picture_with(fact("certification_in_progress", "ISO 27001 certification is in progress"))
        self.assertEqual(checks.q2(prog)["answer"], "yes")
        job = picture_with(fact("security_or_compliance_job", "Senior GRC Analyst"))
        self.assertEqual(checks.q2(job)["answer"], "yes")
        qa = picture_with(fact("security_or_compliance_job", "QA Automation Engineer"))
        self.assertEqual(checks.q2(qa)["answer"], "unknown")                    # the old QA-job bug

    def test_q3_rules(self):
        self.assertEqual(checks.q3(picture_with(fact("enterprise_plan", "Enterprise plan with SSO")))["answer"], "yes")
        self.assertEqual(checks.q3(picture_with(fact("enterprise_plan", "Built for scale")))["answer"], "unknown")
        self.assertEqual(checks.q3(picture_with(fact("security_review", "pass any infosec review")))["answer"], "yes")
        named = checks.q3(picture_with(fact("named_customer", "Trusted by Big Bank Ltd.")))
        self.assertEqual(named["answer"], "yes")
        self.assertIn("weak", named["evidence"][0]["note"])
        self.assertEqual(checks.q3(picture_with())["answer"], "unknown")

    def test_decisions(self):
        d = checks.decide
        self.assertEqual(d("yes", "yes", "yes", "yes")[0], "Go")
        self.assertEqual(d("unknown", "yes", "yes", "yes")[0], "Flag")
        self.assertEqual(d("yes", "yes", "unknown", "yes")[0], "Flag")
        self.assertEqual(d("yes", "yes", "unknown", "unknown")[0], "No-Go")
        self.assertEqual(d("no", "yes", "yes", "yes")[0], "No-Go")
        self.assertEqual(d("yes", "no", "yes", "yes")[0], "No-Go")


class TestSearchLoop(unittest.TestCase):
    BASE = picture_with(fact("company_name", "Fake Co", value="Fake Co"),
                        fact("b2b_saas", "Fake Co is a B2B SaaS platform", value="yes"),
                        fact("enterprise_plan", "Enterprise plan with SSO", url=PRICING))

    def test_searches_fill_unknowns(self):
        results = {
            "Fake Co funding round Series": [{"n": 1, "title": "Fake Co raises $20M Series B", "snippet": "x", "link": "https://news.example/a"}],
            "Fake Co data breach": [{"n": 1, "title": "News", "snippet": "Fake Co data breach exposed 1,000 records", "link": "https://news.example/b"}],
        }
        ai = fake_ai({"found": True, "result": 1, "quote": "Fake Co raises $20M Series B"},
                     {"found": True, "result": 1, "quote": "Fake Co data breach exposed 1,000 records"})
        out = checks.run("fake-co.com", self.BASE, ai, lambda q: results[q])
        self.assertEqual((out["q1"]["answer"], out["q2"]["answer"], out["q3"]["answer"]), ("yes", "yes", "yes"))
        self.assertEqual(out["decision"], "Go")
        self.assertFalse(out["q2"]["evidence"][0]["usable_as_hook"])          # negative news: never a hook
        self.assertEqual([s["query"] for s in out["searches"]], list(results))

    def test_made_up_search_quote_is_rejected(self):
        ai = fake_ai({"found": True, "result": 1, "quote": "Fake Co raises Series C"})
        out = checks.run("fake-co.com", self.BASE, ai,
                         lambda q: [{"n": 1, "title": "Fake Co raises $20M Series B", "snippet": "", "link": "https://n.example"}])
        self.assertEqual(out["q1"]["answer"], "unknown")
        self.assertIn("not word for word", out["searches"][0]["result"])

    def test_no_searches_when_already_dropped_or_no_key(self):
        dropped = picture_with(fact("b2b_saas", "Fake Co sells burgers", value="no"))
        ai = fake_ai()
        out = checks.run("fake-co.com", dropped, ai, lambda q: self.fail("must not search"))
        self.assertEqual((out["decision"], ai.calls), ("No-Go", []))
        out = checks.run("fake-co.com", self.BASE, fake_ai(), None)
        self.assertIn("no Serper key", out["searches"][0]["result"])

    def test_serper_drops_linkedin(self):
        class R:
            status_code = 200

            def json(self):
                return {"organic": [{"title": "a", "link": "https://www.linkedin.com/company/x", "snippet": "s"},
                                    {"title": "b", "link": "https://news.example/b", "snippet": "s"}]}
        with mock.patch("serper.requests.post", return_value=R()) as post:
            res = serper.search("Fake Co", "fake-serper-key")
        self.assertEqual([r["link"] for r in res], ["https://news.example/b"])
        self.assertEqual(post.call_args.kwargs["headers"]["X-API-KEY"], "fake-serper-key")


@unittest.skipUnless(settings.database_url(), "DATABASE_URL not set: database tests skipped")
class TestStepRunner(testutil.SchemaMixin, unittest.TestCase):
    def save(self, test_only=False, domain="fake-co.com"):
        sid, _ = self.db.save_scrape(self.conn, dict(SCRAPE, domain=domain), test_only)
        return sid

    def test_1_order_and_record(self):
        import pipeline
        sid = self.save()
        self.assertEqual(pipeline.state(self.conn, sid)["next"], "picture")
        code, _ = pipeline.run_check(self.conn, sid, ai=fake_ai(), search=None)
        self.assertEqual(code, 409)                                             # picture first

        ai = fake_ai({"facts": [fact("b2b_saas", "Fake Co is a B2B SaaS platform", value="yes"),
                                fact("funding_stage", "We raised our Series B in 2025."),
                                fact("enterprise_plan", "Enterprise plan with SSO", url=PRICING)]})
        code, st = pipeline.run_picture(self.conn, sid, ai=ai)
        self.assertEqual((code, st["next"]), (200, "check"))
        code, st = pipeline.run_check(self.conn, sid, ai=fake_ai(), search=None)
        self.assertEqual((code, st["campaign"]["decision"]), (200, "Flag"))      # Q2 unknown -> Flag
        self.assertEqual(st["next"], "approve")

        import contactflow
        code, out = contactflow.lookup(self.conn, sid, "fake-key", lambda d, k: self.fail("Hunter must not run"))
        self.assertEqual(code, 403)                                             # Flag not approved yet
        code, st = pipeline.approve_flag(self.conn, sid)
        self.assertEqual((code, st["next"]), (200, "contact"))

    def test_2_no_go_blocks_hunter_unless_test_only(self):
        import contactflow
        import pipeline
        for test_only, expected in ((False, 403), (True, 200)):
            sid = self.save(test_only=test_only)
            pipeline.run_picture(self.conn, sid, ai=fake_ai({"facts": [fact("b2b_saas", "Fake Co is a B2B SaaS platform", value="no")]}))
            pipeline.run_check(self.conn, sid, ai=fake_ai(), search=None)
            self.conn.execute(f'DELETE FROM "{self.schema}".counters')
            code, out = contactflow.lookup(self.conn, sid, "fake-key", lambda d, k: [])
            self.assertEqual(code, expected)
            if test_only:
                self.assertTrue(out["contact"]["TEST_ONLY"])

    def test_3_daily_ai_cap(self):
        import pipeline
        self.conn.execute(f'INSERT INTO "{self.schema}".counters (day, name, n) '
                          "VALUES ((now() AT TIME ZONE 'Asia/Kolkata')::date, 'analysis', %s)",
                          (settings.ANALYSIS_DAILY_CAP,))
        code, _ = pipeline.run_picture(self.conn, self.save(), ai=fake_ai({"facts": []}))
        self.assertEqual(code, 429)

    def test_4_do_not_contact(self):
        import pipeline
        code, _ = pipeline.run_picture(self.conn, self.save(domain="whatfix.com"), ai=fake_ai())
        self.assertEqual(code, 403)


if __name__ == "__main__":
    unittest.main()

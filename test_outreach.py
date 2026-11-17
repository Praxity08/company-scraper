"""Checks for pain points, the email draft and sending. Made-up data only (fake-co.com, Pat Lee).

Nothing real is called: the AI, Hunter and Resend are FAKES, and the addresses are fake.
Run: .venv/bin/python -m unittest test_outreach -v
"""
import unittest
from unittest import mock

import emaildraft
import pain
import playbook
import resendmail
import settings
import testutil
from test_pipeline import HOME, PRICING, SCRAPE, fact, fake_ai, picture_with

settings.load_env()
FAKE_TO = "owner@fake-inbox.test"
FAKE_RESEND = "re_fake_key_1234567890"
TEXTS = {p["url"]: p["text"] for p in SCRAPE["pages"].values() if p}


class TestPlaybook(unittest.TestCase):
    def test_real_files_load(self):
        plist = playbook.load_pain_points()
        ids = [r["id"] for r in plist["rows"]]
        self.assertIn("C1", ids)
        self.assertNotIn("F5", ids)                                        # F5 was deleted
        self.assertEqual({r["id"] for r in plist["rows"] if r["needs"]}, {"S5", "C4", "F2", "F4"})
        w = playbook.load_email_settings()
        self.assertIn("{hook}", w["body"])

    def test_draft_only_on_test_only(self):
        self.assertTrue(playbook.usable("APPROVED", False, "x")[0])
        self.assertTrue(playbook.usable("DRAFT", True, "x")[0])
        self.assertFalse(playbook.usable("DRAFT", False, "x")[0])


class TestPain(unittest.TestCase):
    plist = playbook.load_pain_points()

    def test_general_rows_without_evidence(self):
        out = pain.pick(picture_with(), 2, self.plist)
        self.assertEqual([p["id"] for p in out["picked"]], ["C1", "C2"])
        self.assertIn("C4", [s["id"] for s in out["skipped"] if "needs evidence" in s["reason"]])

    def test_evidence_rows_first_when_quoted(self):
        p = picture_with(fact("team_size", "a team of 120 people"))
        out = pain.pick(p, 2, self.plist)
        self.assertEqual(out["picked"][0]["id"], "C4")
        self.assertEqual(out["picked"][0]["evidence"][0]["quote"], "a team of 120 people")

    def test_qa_job_is_not_compliance_evidence(self):
        p = picture_with(fact("security_or_compliance_job", "QA Automation Engineer"))
        self.assertNotIn("S5", [x["id"] for x in pain.pick(p, 1, self.plist)["picked"]])
        p = picture_with(fact("security_or_compliance_job", "Senior GRC Analyst"))
        self.assertEqual(pain.pick(p, 1, self.plist)["picked"][0]["id"], "S5")

    def test_unknown_role(self):
        self.assertEqual(pain.pick(picture_with(), None, self.plist)["picked"], [])


class TestHooks(unittest.TestCase):
    def problem(self, quote, url=HOME, text=None):
        return emaildraft.hook_problem(quote, url, {url: text or quote + " and more words here."})

    def test_rules(self):
        self.assertIsNone(self.problem("Trusted by finance teams across India and the Middle East"))
        self.assertIn("words", self.problem("Trusted by banks"))
        self.assertIn("funding", self.problem("We raised our Series B to grow faster"))
        self.assertIn("funding", self.problem("Backed by the best investors in India"))
        self.assertIn("negative", self.problem("Our response to the recent data breach"))
        self.assertIn("button", self.problem("Book a demo with our team today"))
        self.assertIn("image", self.problem("Big Bank Ltd logo on a blue background"))
        self.assertIn("menu", self.problem("Product Pricing About Careers Blog"))
        self.assertIn("word for word", emaildraft.hook_problem("Trusted by 500 global banks", HOME, TEXTS))
        self.assertIn("scraped", emaildraft.hook_problem("Trusted by 500 global banks", "https://other.example/", TEXTS))

    def test_find_hooks_orders_and_numbers(self):
        ai = fake_ai({"hooks": [
            {"source_url": HOME, "quote": "Fake Co is a B2B SaaS platform for finance teams."},
            {"source_url": PRICING, "quote": "Enterprise plan with SSO and audit logs"},
            {"source_url": HOME, "quote": "We raised our Series B in 2025."},
            {"source_url": HOME, "quote": "Fake Co is a B2C app"},
        ]})
        passed, rejected = emaildraft.find_hooks(SCRAPE, ai)
        self.assertEqual([h["n"] for h in passed], [1, 2])
        self.assertEqual(passed[0]["quote"], "Enterprise plan with SSO and audit logs")   # 2 preferred topics
        self.assertEqual(len(rejected), 2)

    def test_render(self):
        w = playbook.load_email_settings()
        subject, body, n = emaildraft.render(w, company="Fake Co", first_name="Pat", hook="Enterprise plan with SSO and audit logs",
                                             group="C", pain_phrases=["a", "b"], test_only=True)
        self.assertTrue(subject.startswith("[TEST ONLY] "))
        self.assertIn('"Enterprise plan with SSO and audit logs"', body)
        self.assertIn("Hi Pat,", body)
        self.assertNotIn("{", body)
        self.assertLess(n, 110)


class TestResend(unittest.TestCase):
    class R:
        def __init__(self, code, data):
            self.status_code, self._d = code, data

        def json(self):
            return self._d

    def test_header_and_only_to_owner(self):
        with mock.patch("resendmail.requests.post", return_value=self.R(200, {"id": "abc"})) as post:
            self.assertEqual(resendmail.send("s", "t", FAKE_RESEND, FAKE_TO), "abc")
        kw = post.call_args.kwargs
        self.assertEqual(kw["headers"]["Authorization"], f"Bearer {FAKE_RESEND}")
        self.assertEqual(kw["json"]["to"], [FAKE_TO])
        self.assertEqual(kw["json"]["from"].split("<")[1], "onboarding@resend.dev>")

    def test_errors_hide_key(self):
        bad = self.R(403, {"message": f"API key {FAKE_RESEND} is invalid"})
        with mock.patch("resendmail.requests.post", return_value=bad):
            with self.assertRaises(resendmail.SendError) as ctx:
                resendmail.send("s", "t", FAKE_RESEND, FAKE_TO)
        self.assertNotIn(FAKE_RESEND, str(ctx.exception))
        with mock.patch("resendmail.requests.post", return_value=self.R(503, {})):
            with self.assertRaises(resendmail.SendUnknown):
                resendmail.send("s", "t", FAKE_RESEND, FAKE_TO)


@unittest.skipUnless(settings.database_url(), "DATABASE_URL not set: database tests skipped")
class TestOutreachFlow(testutil.SchemaMixin, unittest.TestCase):
    PEOPLE = [{"first_name": "Pat", "last_name": "Lee", "position": "CTO", "confidence": 92,
               "value": "pat@fake-co.com", "verification": {"status": "valid"}, "sources": []}]

    def ready(self, test_only=True, decision_quote="Fake Co is a B2B SaaS platform"):
        import contactflow
        import pipeline
        sid, _ = self.db.save_scrape(self.conn, dict(SCRAPE), test_only)
        pipeline.run_picture(self.conn, sid, ai=fake_ai({"facts": [
            fact("b2b_saas", decision_quote, value="yes"),
            fact("funding_stage", "We raised our Series B in 2025."),
            fact("enterprise_plan", "Enterprise plan with SSO", url=PRICING)]}))
        pipeline.run_check(self.conn, sid, ai=fake_ai(), search=None)       # -> Flag (Q2 unknown)
        pipeline.approve_flag(self.conn, sid)
        self.conn.execute(f'DELETE FROM "{self.schema}".counters')
        code, _ = contactflow.lookup(self.conn, sid, "fake-hunter", lambda d, k: self.PEOPLE)
        self.assertEqual(code, 200)
        return sid

    def hooks_ai(self):
        return fake_ai({"hooks": [{"source_url": PRICING, "quote": "Enterprise plan with SSO and audit logs"},
                                  {"source_url": HOME, "quote": "Fake Co is a B2B SaaS platform for finance teams."}]})

    def test_1_full_test_only_chain_sends_only_to_owner(self):
        import pipeline
        sid = self.ready()
        code, st = pipeline.run_pain(self.conn, sid)
        self.assertEqual((code, st["next"]), (200, "draft"))
        code, st = pipeline.run_draft(self.conn, sid, ai=self.hooks_ai())
        self.assertEqual((code, st["next"]), (200, "send"))
        em = st["campaign"]["email"]
        self.assertTrue(em["subject"].startswith("[TEST ONLY]"))

        sent = []

        def fake_send(subject, text, key, to):
            sent.append((subject, text, to))
            return "fake-id"
        with mock.patch("settings.to_email", return_value=FAKE_TO), \
                mock.patch("settings.resend_key", return_value=FAKE_RESEND):
            for bad in ("send fake-co.com hook 1", "send other.com, hook 1", "send fake-co.com, hook 9", ""):
                self.assertIn(pipeline.run_send(self.conn, sid, bad, send=fake_send)[0], (400,))
            code, st = pipeline.run_send(self.conn, sid, "send fake-co.com, hook 2", send=fake_send)
            self.assertEqual((code, st["next"]), (200, "done"))
            code, _ = pipeline.run_send(self.conn, sid, "send fake-co.com, hook 2", send=fake_send)
            self.assertEqual(code, 409)                                     # never twice
        self.assertEqual(len(sent), 1)
        subject, text, to = sent[0]
        self.assertEqual(to, FAKE_TO)                                       # only ever the owner
        self.assertIn("Fake Co is a B2B SaaS platform for finance teams.", text)   # hook 2 was used
        self.assertIn("never to the contact", text)
        self.assertEqual(st["status"], "Draft delivered to your inbox and logged")

    def test_2_refused_send_can_be_tried_again(self):
        import pipeline
        sid = self.ready()
        pipeline.run_pain(self.conn, sid)
        pipeline.run_draft(self.conn, sid, ai=self.hooks_ai())

        def refused(*a):
            raise resendmail.SendError("Resend refused the email (HTTP 403).")
        with mock.patch("settings.to_email", return_value=FAKE_TO), \
                mock.patch("settings.resend_key", return_value=FAKE_RESEND):
            self.assertEqual(pipeline.run_send(self.conn, sid, "send fake-co.com, hook 1", send=refused)[0], 502)
            self.assertEqual(pipeline.state(self.conn, sid)["next"], "send")
            self.assertEqual(pipeline.run_send(self.conn, sid, "send fake-co.com, hook 1", send=lambda *a: "id")[0], 200)

    def test_3_draft_wording_blocked_on_real_runs(self):
        import pipeline
        sid = self.ready(test_only=False)
        with mock.patch("playbook._status", return_value="DRAFT"):
            code, out = pipeline.run_pain(self.conn, sid)
        self.assertEqual(code, 403)
        self.assertIn("DRAFT", out["error"])

    def test_4_no_hook_no_email(self):
        import pipeline
        sid = self.ready()
        pipeline.run_pain(self.conn, sid)
        code, st = pipeline.run_draft(self.conn, sid, ai=fake_ai({"hooks": [
            {"source_url": HOME, "quote": "We raised our Series B in 2025."}]}))
        self.assertEqual(code, 200)
        self.assertEqual(st["campaign"]["email"]["hooks"], [])
        self.assertEqual(st["status"], "No hook found, so no email")
        with mock.patch("settings.to_email", return_value=FAKE_TO), \
                mock.patch("settings.resend_key", return_value=FAKE_RESEND):
            self.assertEqual(pipeline.run_send(self.conn, sid, "send fake-co.com, hook 1", send=lambda *a: "x")[0], 409)


if __name__ == "__main__":
    unittest.main()

"""Offline checks for scraper.py. No network; made-up data only.

Run: .venv/bin/python -m unittest test_scraper -v
"""
import unittest

import scraper as s


class FakeResponse:
    def __init__(self, content, ctype):
        self.content = content
        self.headers = {"Content-Type": ctype}

    @property
    def text(self):
        return self.content.decode("latin-1")


class TestScraper(unittest.TestCase):
    def test_normalize_domain(self):
        self.assertEqual(s.normalize_domain("https://www.Fake-Co.com/about"), "fake-co.com")
        self.assertEqual(s.normalize_domain("  fake-co.io "), "fake-co.io")
        self.assertIsNone(s.normalize_domain("not a domain"))

    def test_classify_uses_last_segment_only(self):
        self.assertEqual(s.classify("https://fake-co.com/pricing"), "pricing")
        self.assertEqual(s.classify("https://fake-co.com/en/about-us/"), "about")
        self.assertEqual(s.classify("https://fake-co.com/company/careers.html"), "careers")
        # the old bug: a blog post about pricing is not the pricing page
        self.assertIsNone(s.classify("https://fake-co.com/blog/pricing-guide"))
        # press = index only, never a post
        self.assertEqual(s.classify("https://fake-co.com/press"), "press")
        self.assertIsNone(s.classify("https://fake-co.com/press/we-raised-money"))
        # file URLs are never pages
        self.assertIsNone(s.classify("https://fake-co.com/pricing.pdf"))
        self.assertIsNone(s.classify("https://fake-co.com/sitemap.xml"))
        self.assertIsNone(s.classify("https://fake-co.com/"))

    def test_security_and_case_study_names(self):
        self.assertEqual(s.classify("https://fake-co.com/security-and-compliance"), "security")
        self.assertEqual(s.classify("https://fake-co.com/trust-and-security"), "security")
        self.assertEqual(s.classify("https://fake-co.com/security-and-trust"), "security")
        self.assertEqual(s.classify("https://fake-co.com/case-study"), "customers")
        # a product page named "compliance" is not the company's security page
        self.assertIsNone(s.classify("https://fake-co.com/solution/compliance"))

    def test_do_not_contact(self):
        entries = {"whatfix", "rocketlane"}
        self.assertTrue(s.is_do_not_contact("whatfix.com", entries))
        self.assertTrue(s.is_do_not_contact("rocketlane.io", entries))
        self.assertFalse(s.is_do_not_contact("fake-co.com", entries))

    def test_linkedin_and_same_site(self):
        self.assertTrue(s.is_linkedin("https://www.linkedin.com/company/fake-co"))
        self.assertTrue(s.is_linkedin("https://lnkd.in/abc"))
        self.assertFalse(s.is_linkedin("https://fake-co.com/"))
        self.assertTrue(s.same_site("https://www.fake-co.com/x", "fake-co.com"))
        self.assertFalse(s.same_site("https://notfake-co.com/x", "fake-co.com"))

    def test_decode_without_charset_is_utf8(self):
        raw = "It’s fine".encode("utf-8")
        self.assertEqual(s.decode(FakeResponse(raw, "text/html")), "It’s fine")
        # with a stated charset, the stated one is used
        self.assertEqual(s.decode(FakeResponse(b"abc", "text/html; charset=iso-8859-1")), "abc")

    def test_only_public_addresses_are_fetched(self):
        for bad in ["http://127.0.0.1/", "http://10.0.0.5/x", "http://169.254.169.254/latest",
                    "http://[::1]/", "ftp://fake-co.com/", "https://fake-co.com:8080/",
                    "https://www.linkedin.com/company/fake-co"]:
            with self.assertRaises(s.UnsafeURL, msg=bad):
                s.check_url_safe(bad)
        s.check_url_safe("https://8.8.8.8/")  # a public address passes

    def test_parse_html_drops_scripts_and_keeps_links(self):
        html = ("<html><head><style>.x{}</style><script>var a=1;</script></head>"
                "<body><h1>Fake Co</h1><p>We  help   teams.</p>"
                "<a href='/pricing#top'>Pricing</a><a href='mailto:x@fake-co.com'>Mail</a></body></html>")
        text, links = s.parse_html(html, "https://fake-co.com/")
        self.assertEqual(text, "Fake Co\nWe help teams.\nPricing\nMail")
        self.assertEqual(links, ["https://fake-co.com/pricing"])


if __name__ == "__main__":
    unittest.main()

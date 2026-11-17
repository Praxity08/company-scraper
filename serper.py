"""Google search through Serper.dev (used at most twice per company, only to fill an 'unknown').

A search result is evidence ONLY if the quote is word for word in that result's title or snippet.
LinkedIn results are dropped (the project never uses LinkedIn).
"""
import requests

import scraper

API = "https://google.serper.dev/search"
TIMEOUT = 20


class SearchError(Exception):
    """A Serper problem, with a message that never contains the key."""


def search(query, api_key, num=10):
    try:
        r = requests.post(API, json={"q": query, "num": num}, timeout=TIMEOUT,
                          headers={"X-API-KEY": api_key, "Content-Type": "application/json"})
    except requests.RequestException as e:
        raise SearchError(f"could not reach Serper ({type(e).__name__})") from None
    if r.status_code != 200:
        raise SearchError(f"Serper returned HTTP {r.status_code}")
    try:
        organic = r.json().get("organic") or []
    except ValueError:
        raise SearchError("Serper sent a reply that is not JSON") from None
    results = []
    for o in organic:
        link = str(o.get("link", ""))
        if not link or scraper.is_linkedin(link):
            continue
        results.append({"n": len(results) + 1, "title": str(o.get("title", "")), "link": link,
                        "snippet": str(o.get("snippet", "")), "date": str(o.get("date", ""))})
    return results

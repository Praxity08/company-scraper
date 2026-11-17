"""Step 7: send ONE plain-text email through Resend to the owner's OWN inbox (TO_EMAIL). Never to a prospect.

The key goes in the Authorization header and is scrubbed from every error. No automatic retry.
"""
import requests

API = "https://api.resend.com/emails"
FROM = "Sprinto outreach draft <onboarding@resend.dev>"
TIMEOUT = 20


class SendError(Exception):
    """Resend answered and refused: nothing was sent."""


class SendUnknown(Exception):
    """No clear answer from Resend (e.g. timeout): the email MAY have been sent."""


def scrub(text, key):
    return text.replace(key, "[key hidden]") if key else text


def send(subject, text, api_key, to_email):
    try:
        r = requests.post(API, headers={"Authorization": f"Bearer {api_key}"},
                          json={"from": FROM, "to": [to_email], "subject": subject, "text": text},
                          timeout=TIMEOUT)
    except requests.RequestException as e:
        raise SendUnknown(scrub(f"No clear answer from Resend ({type(e).__name__}). "
                                "Check your inbox before trying again.", api_key)) from None
    if r.status_code in (200, 201):
        return (r.json() or {}).get("id", "")
    if r.status_code >= 500:
        raise SendUnknown(scrub(f"Resend had a server error (HTTP {r.status_code}). "
                                "Check your inbox before trying again.", api_key))
    try:
        detail = (r.json() or {}).get("message", "")
    except ValueError:
        detail = ""
    raise SendError(scrub(f"Resend refused the email (HTTP {r.status_code}). {detail}".strip(), api_key))

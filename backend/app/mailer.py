"""Email a reader their paper through Brevo's transactional email API.

Settings (backend/.env):
- BREVO_API_KEY: from Brevo -> SMTP & API -> API keys
- MAIL_FROM_EMAIL: a sender address you verified in Brevo (Senders, Domains & Dedicated IPs)
- MAIL_FROM_NAME: optional, defaults to "Vale"
- PUBLIC_APP_URL: where readers open Vale, used in links (default http://localhost:5173)
"""

import base64
import os
from datetime import date
from html import escape

import httpx

from app import links, pdf

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


class MailError(RuntimeError):
    pass


def configured() -> bool:
    return bool(os.getenv("BREVO_API_KEY", "").strip() and os.getenv("MAIL_FROM_EMAIL", "").strip())


def app_url() -> str:
    return os.getenv("PUBLIC_APP_URL", "http://localhost:5173").strip().rstrip("/")


def send_via_brevo(message: dict) -> dict:
    """POST one message to Brevo. Tests replace this."""
    r = httpx.post(BREVO_URL, json=message, timeout=30,
                   headers={"api-key": os.getenv("BREVO_API_KEY", "").strip(), "accept": "application/json"})
    if r.status_code >= 400:
        raise MailError(f"Brevo refused the email ({r.status_code}): {r.text[:200]}")
    return r.json() if r.content else {}


def _long_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return d.strftime("%A, %B ") + str(d.day) + d.strftime(", %Y")


def build_message(uid: str, user: dict, edition: dict, email: str) -> dict:
    """The Brevo message for one edition: newspaper-style HTML, plain text, the PDF attached."""
    title = (user.get("paper_title") or "Your Vale paper").upper()
    name = user.get("name") or "reader"
    live = [a for a in edition["articles"] if not a.get("skipped")]
    lead = next((a for a in live if a.get("is_lead")), live[0] if live else None)
    download = f"{app_url()}/api/pdf/{links.make('pdf', uid, edition['id'])}"
    unsubscribe = f"{app_url()}/api/unsubscribe/{links.make('unsub', uid, days=links.UNSUBSCRIBE_DAYS)}"
    when = _long_date(edition["date"]) if edition.get("date") else ""

    takeaways = "".join(
        f'<li style="margin:0 0 8px">{escape(t["text"])}</li>' for t in edition.get("three_takeaways", [])[:3]
    )
    lead_html = ""
    if lead:
        lead_html = (
            f'<p style="margin:24px 0 4px;font:11px monospace;letter-spacing:2px;color:#B93829;text-transform:uppercase">'
            f'{escape(lead["topic"])} · Lead story</p>'
            f'<h2 style="margin:0 0 8px;font:900 26px Georgia,serif;color:#1A1917">{escape(lead["headline"])}</h2>'
            f'<p style="margin:0;font:16px/1.6 Georgia,serif;color:#1A1917">{escape(lead.get("summary", ""))}</p>'
        )
    html = f"""<!doctype html><html><body style="margin:0;background:#FAF7F2">
<div style="max-width:600px;margin:0 auto;padding:24px;background:#FAF7F2;color:#1A1917">
  <div style="border-top:4px double #1A1917;border-bottom:4px double #1A1917;padding:12px 0;text-align:center">
    <div style="font:900 32px Georgia,serif">{escape(title)}</div>
    <div style="font:11px monospace;letter-spacing:2px;color:#5C5852;text-transform:uppercase;margin-top:6px">
      Edition No. {edition.get('edition_number')} · {escape(when)} · {edition.get('reading_minutes', '')} min</div>
  </div>
  <p style="font:16px Georgia,serif;margin:20px 0 0">Good morning, {escape(name)}. Today's paper is attached.</p>
  <div style="border:2px solid #1A1917;padding:14px 18px;margin-top:16px;background:#FFFDF9">
    <div style="font:11px monospace;letter-spacing:2px;text-transform:uppercase">3 Things You Learned Today</div>
    <ol style="margin:10px 0 0;padding-left:20px;font:15px/1.5 Georgia,serif">{takeaways}</ol>
  </div>
  {lead_html}
  <p style="margin:28px 0;text-align:center">
    <a href="{app_url()}" style="display:inline-block;background:#1A1917;color:#FAF7F2;padding:12px 22px;text-decoration:none;font:15px sans-serif">Read today's paper</a>
    &nbsp;
    <a href="{download}" style="display:inline-block;border:1px solid #1A1917;color:#1A1917;padding:11px 20px;text-decoration:none;font:15px sans-serif">Download PDF</a>
  </p>
  <p style="font:11px sans-serif;color:#5C5852;text-align:center;border-top:1px solid #D6D1C7;padding-top:14px">
    Printed for {escape(name)} by Vale · The download link works for {links.PDF_LINK_DAYS} days.<br>
    <a href="{unsubscribe}" style="color:#5C5852">Stop daily emails</a></p>
</div></body></html>"""
    text = (
        f"{title} — Edition No. {edition.get('edition_number')} — {when}\n\n"
        f"Good morning, {name}. Today's paper is attached.\n\n3 Things You Learned Today:\n"
        + "".join(f"- {t['text']}\n" for t in edition.get("three_takeaways", [])[:3])
        + f"\nRead it: {app_url()}\nDownload PDF ({links.PDF_LINK_DAYS} days): {download}\n\nStop daily emails: {unsubscribe}\n"
    )
    pdf_bytes = pdf.build_pdf(edition, user.get("paper_title") or "")
    return {
        "sender": {"name": os.getenv("MAIL_FROM_NAME", "Vale").strip() or "Vale", "email": os.getenv("MAIL_FROM_EMAIL", "").strip()},
        "to": [{"email": email, "name": name}],
        "subject": f"{title} — Edition No. {edition.get('edition_number')}, {when}",
        "htmlContent": html,
        "textContent": text,
        "attachment": [{"name": pdf.filename_for(edition, user.get("paper_title") or ""), "content": base64.b64encode(pdf_bytes).decode()}],
        "headers": {"List-Unsubscribe": f"<{unsubscribe}>"},
        "tags": ["vale-paper"],
    }


def send_edition(uid: str, user: dict, edition: dict) -> str:
    """Email one edition to the reader's own address. Returns the address."""
    if not configured():
        raise MailError("Email is not set up on this server (BREVO_API_KEY / MAIL_FROM_EMAIL).")
    email = (user.get("email") or "").strip()
    if not email:
        raise MailError("This reader has no email address. Sign in to get papers by email.")
    send_via_brevo(build_message(uid, user, edition, email))
    return email

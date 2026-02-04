import os
import smtplib
from email.message import EmailMessage


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def send_email(to_email: str, subject: str, body_text: str) -> None:
    host = _env("SMTP_HOST", "smtp.office365.com")
    port = int(_env("SMTP_PORT", "587") or "587")
    user = _env("SMTP_USER")
    password = _env("SMTP_PASS")
    from_email = _env("SMTP_FROM", user)

    if not user or not password:
        raise RuntimeError("SMTP not configured (SMTP_USER/SMTP_PASS missing)")

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)

    with smtplib.SMTP(host, port, timeout=20) as s:
        s.ehlo()
        s.starttls()
        s.ehlo()
        s.login(user, password)
        s.send_message(msg)

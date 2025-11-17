# service/email.py
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Optional


class EmailSendError(Exception):
    """이메일 발송 실패 공통 예외"""
    pass

# 환경변수 기반 설정
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")          # Gmail 주소
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")          # 앱 비밀번호
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

EMAIL_FROM = os.getenv("EMAIL_FROM") or SMTP_USERNAME
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "GrowFit")


def send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    is_html: bool = False,
    cc: Optional[list[str]] = None,
    bcc: Optional[list[str]] = None,
) -> None:
    """
    단순 SMTP 이메일 발송(Gmail)
    - 실패 시 EmailSendError 예외 발생
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        raise EmailSendError("SMTP credentials are not configured")

    msg = EmailMessage()

    # From 헤더
    if EMAIL_FROM_NAME:
        msg["From"] = f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>"
    else:
        msg["From"] = EMAIL_FROM

    msg["To"] = to_email
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        # BCC는 헤더에 안 올려도 되지만, 필요하면 추가 가능
        pass

    msg["Subject"] = subject

    if is_html:
        msg.set_content(body, subtype="html")
    else:
        msg.set_content(body)

    recipients = [to_email]
    if cc:
        recipients.extend(cc)
    if bcc:
        recipients.extend(bcc)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg, to_addrs=recipients)
    except Exception as e:
        raise EmailSendError(str(e)) from e

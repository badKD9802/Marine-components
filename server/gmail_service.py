"""Gmail IMAP/SMTP 유틸리티 (동기 함수 — asyncio.to_thread로 호출)"""

import imaplib
import smtplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parseaddr, parsedate_to_datetime
from datetime import datetime, timezone


IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # SSL 직접 연결 (Railway에서 587 차단됨)


def _clean_password(app_password: str) -> str:
    """앱 비밀번호에서 공백 제거 (Google은 'abcd efgh ijkl mnop' 형태로 표시)."""
    return app_password.replace(" ", "")


def test_connection(addr: str, app_password: str) -> bool:
    """IMAP 로그인 테스트. 성공하면 True, 실패하면 예외 발생."""
    app_password = _clean_password(app_password)
    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    try:
        imap.login(addr, app_password)
        return True
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def _decode_mime_words(s: str | None) -> str:
    """MIME 인코딩된 헤더를 디코딩한다."""
    if not s:
        return ""
    parts = decode_header(s)
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


def _extract_body(msg: email.message.Message) -> dict:
    """이메일 메시지에서 텍스트 본문과 HTML 본문을 추출한다.

    Returns:
        dict: {"text": str, "html": str | None}
    """
    if msg.is_multipart():
        plain_parts = []
        html_parts = []
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                continue
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    plain_parts.append(payload.decode(charset, errors="replace"))
            elif ct == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_parts.append(payload.decode(charset, errors="replace"))

        text_body = "\n".join(plain_parts) if plain_parts else ("\n".join(html_parts) if html_parts else "")
        html_body = "\n".join(html_parts) if html_parts else None

        return {"text": text_body, "html": html_body}
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            ct = msg.get_content_type()
            if ct == "text/html":
                return {"text": decoded, "html": decoded}
            else:
                return {"text": decoded, "html": None}
        return {"text": "", "html": None}


def fetch_new_emails(addr: str, app_password: str, since_date: datetime | None = None) -> list[dict]:
    """IMAP으로 새 메일을 가져온다.

    Returns:
        list of dict with keys: uid, from_addr, from_name, subject, body, received_at
    """
    app_password = _clean_password(app_password)
    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    imap.login(addr, app_password)
    try:
        imap.select("INBOX")

        # 검색 기준: since_date가 있으면 해당 날짜 이후, 없으면 최근 7일
        if since_date:
            date_str = since_date.strftime("%d-%b-%Y")
        else:
            from datetime import timedelta
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            date_str = week_ago.strftime("%d-%b-%Y")

        status, data = imap.search(None, f'(SINCE {date_str})')
        if status != "OK" or not data[0]:
            return []

        msg_nums = data[0].split()
        results = []

        for num in msg_nums:
            # UID 가져오기
            status, uid_data = imap.fetch(num, "(UID)")
            if status != "OK":
                continue
            uid_str = uid_data[0].decode()
            uid = uid_str.split("UID")[1].strip().rstrip(")").strip() if "UID" in uid_str else num.decode()

            # 메시지 전체 가져오기
            status, msg_data = imap.fetch(num, "(RFC822)")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # 헤더 파싱
            subject = _decode_mime_words(msg.get("Subject", ""))
            from_raw = msg.get("From", "")
            from_name, from_addr_parsed = parseaddr(from_raw)
            from_name = _decode_mime_words(from_name) or from_addr_parsed

            # 날짜
            date_str_raw = msg.get("Date")
            try:
                received_at = parsedate_to_datetime(date_str_raw) if date_str_raw else None
            except Exception:
                received_at = None

            # 본문 (텍스트 + HTML)
            body_data = _extract_body(msg)

            results.append({
                "uid": uid,
                "from_addr": from_addr_parsed,
                "from_name": from_name,
                "subject": subject,
                "body": body_data["text"],
                "body_html": body_data["html"],
                "received_at": received_at,
            })

        return results
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass


def send_email(addr: str, app_password: str, to: str, subject: str, body: str, reply_to_subject: str | None = None) -> bool:
    """SMTP로 메일을 발송한다."""
    app_password = _clean_password(app_password)
    msg = MIMEMultipart("alternative")
    msg["From"] = addr
    msg["To"] = to
    if reply_to_subject:
        # 기존 "Re: " 접두사 제거 후 한 번만 추가
        clean_subj = reply_to_subject
        while clean_subj.startswith("Re: "):
            clean_subj = clean_subj[4:]
        msg["Subject"] = f"Re: {clean_subj}"
    else:
        msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    # SMTP_SSL 직접 연결 (starttls 불필요)
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.login(addr, app_password)
        server.sendmail(addr, to, msg.as_string())

    return True

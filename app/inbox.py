"""IMAP inbox integration — capture real email responses from conversational probes."""

from __future__ import annotations

import asyncio
import email
import imaplib
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import (
    IMAP_HOST,
    IMAP_PASSWORD,
    IMAP_PORT,
    IMAP_USER,
    INBOX_ENABLED,
    INBOX_POLL_INTERVAL_SEC,
)
from app.store import get_connection, _utcnow

_bg_task: Optional[asyncio.Task] = None


def init_inbox_tables() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS form_submissions (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                inquiry TEXT,
                probe_email TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                replied_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inbox_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id TEXT,
                subject TEXT,
                sender TEXT,
                body TEXT,
                received_at TEXT NOT NULL,
                matched INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()


def register_submission(url: str, inquiry: str, probe_email: str = "") -> str:
    sid = str(uuid.uuid4())
    email_addr = probe_email or IMAP_USER or "research@argoscout.local"
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO form_submissions (id, url, inquiry, probe_email, created_at) VALUES (?, ?, ?, ?, ?)",
            (sid, url, inquiry, email_addr, _utcnow().isoformat()),
        )
        conn.commit()
    return sid


def poll_inbox() -> dict[str, Any]:
    if not INBOX_ENABLED or not IMAP_HOST or not IMAP_USER or not IMAP_PASSWORD:
        return {"status": "disabled", "reason": "IMAP not configured", "new_messages": 0}

    new_count = 0
    matched = 0
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASSWORD)
        mail.select("INBOX")

        _, data = mail.search(None, "UNSEEN")
        ids = data[0].split() if data[0] else []

        for num in ids[-20:]:
            _, msg_data = mail.fetch(num, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            subject = _decode_header(msg.get("Subject", ""))
            sender = _decode_header(msg.get("From", ""))
            body = _extract_body(msg)
            received = _utcnow().isoformat()

            submission_id = _match_submission(sender, subject, body)
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO inbox_messages (submission_id, subject, sender, body, received_at, matched) VALUES (?, ?, ?, ?, ?, ?)",
                    (submission_id, subject, sender, body[:5000], received, int(bool(submission_id))),
                )
                if submission_id:
                    conn.execute(
                        "UPDATE form_submissions SET status='replied', replied_at=? WHERE id=?",
                        (received, submission_id),
                    )
                conn.commit()

            new_count += 1
            if submission_id:
                matched += 1

        mail.logout()
        return {"status": "ok", "new_messages": new_count, "matched": matched}
    except Exception as e:
        return {"status": "error", "error": str(e), "new_messages": new_count}


def get_submissions(limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, url, inquiry, probe_email, status, created_at, replied_at FROM form_submissions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_inbox_messages(submission_id: Optional[str] = None, limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        if submission_id:
            rows = conn.execute(
                "SELECT * FROM inbox_messages WHERE submission_id=? ORDER BY received_at DESC LIMIT ?",
                (submission_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM inbox_messages ORDER BY received_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def _match_submission(sender: str, subject: str, body: str) -> Optional[str]:
    with get_connection() as conn:
        pending = conn.execute(
            "SELECT id, url, inquiry FROM form_submissions WHERE status='pending' ORDER BY created_at DESC LIMIT 50"
        ).fetchall()

    combined = f"{subject} {body}".lower()
    for row in pending:
        domain = row["url"].split("/")[2] if "/" in row["url"] else ""
        if domain and domain.replace("www.", "") in sender.lower():
            return row["id"]
        words = [w for w in row["inquiry"].lower().split() if len(w) > 5][:3]
        if words and sum(1 for w in words if w in combined) >= 2:
            return row["id"]
    return None


def _decode_header(value: str) -> str:
    if not value:
        return ""
    parts = email.header.decode_header(value)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return " ".join(decoded)


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(errors="replace")
    payload = msg.get_payload(decode=True)
    return payload.decode(errors="replace") if payload else ""


def get_inbox_status() -> dict[str, Any]:
    with get_connection() as conn:
        pending = conn.execute("SELECT COUNT(*) AS c FROM form_submissions WHERE status='pending'").fetchone()["c"]
        replied = conn.execute("SELECT COUNT(*) AS c FROM form_submissions WHERE status='replied'").fetchone()["c"]
        messages = conn.execute("SELECT COUNT(*) AS c FROM inbox_messages").fetchone()["c"]
    return {
        "enabled": INBOX_ENABLED,
        "configured": bool(IMAP_HOST and IMAP_USER and IMAP_PASSWORD),
        "pending_submissions": pending,
        "replied_submissions": replied,
        "total_messages": messages,
        "poll_interval_sec": INBOX_POLL_INTERVAL_SEC,
    }


async def _inbox_poll_loop() -> None:
    while True:
        try:
            if INBOX_ENABLED:
                await asyncio.to_thread(poll_inbox)
        except Exception:
            pass
        await asyncio.sleep(INBOX_POLL_INTERVAL_SEC)


def start_inbox_background() -> None:
    global _bg_task
    if not INBOX_ENABLED or _bg_task is not None:
        return
    try:
        loop = asyncio.get_running_loop()
        _bg_task = loop.create_task(_inbox_poll_loop())
    except RuntimeError:
        pass

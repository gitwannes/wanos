#!/usr/bin/env python3
# --- file: helpers/smtp_test.py ---
"""
Standalone Gmail SMTP probe (same intent as hofmans.be smtp_test.php).

Edit USER / APP_PASSWORD / TO below, then run on the Pi:
  python3 helpers/smtp_test.py

Uses ssl://smtp.gmail.com:465, AUTH LOGIN, optional test message.
Never prints the password or its base64. Plain ASCII console output.
Delete or wipe secrets from this file when finished.

Keep functional parity with hofmans.be/smtp_test.php (placeholder gate, AUTH LOGIN,
pass_meta). See docs/reference.md.
"""

from __future__ import annotations

import base64
import hashlib
import re
import socket
import ssl
import sys
from datetime import datetime, timezone
from email.utils import formatdate
from typing import List, Optional

# =============================================================================
# EDIT THESE
# =============================================================================
USER = "johan@hofmans.be"
APP_PASSWORD = "xxxx xxxx xxxx xxxx"  # Google app password (spaces OK)
TO = "johan@hofmans.be"  # recipient for the test message after AUTH
# =============================================================================

HOST = "smtp.gmail.com"
PORT = 465
TIMEOUT_SEC = 15

# Obvious fakes only (parity with hofmans.be smtp_test.php $smtp_pass_is_placeholder).
_PASS_DENY = frozenset(
    {
        "xxxxxxxxxxxxxxxx",
        "password",
        "changeme",
        "secret",
        "smtp_pass",
        "smtppass",
        "apppassword",
        "yourapppassword",
        "yourpassword",
        "example",
        "dummy",
        "placeholder",
        "replaceme",
        "todo",
        "test",
        "testing",
    }
)


def pass_is_placeholder(raw: str, stripped: str) -> bool:
    """
    True when APP_PASSWORD looks like a placeholder, not a Google app password.
    Real app passwords are 16 random letters; this only catches obvious fakes.
    """
    if stripped == "":
        return True
    lower = stripped.lower()
    # All x / all same letter (e.g. xxxx xxxx xxxx xxxx -> xxxxxxxxxxxxxxxx)
    if len(lower) >= 1 and lower == lower[0] * len(lower):
        return True
    if lower in _PASS_DENY:
        return True
    spaced = re.sub(r"\s+", " ", raw.strip()).lower()
    if re.fullmatch(r"(x{4}\s+){3}x{4}", spaced) is not None:
        return True
    return False


def pass_meta(raw: str) -> str:
    stripped = raw.replace(" ", "")
    length = len(stripped)
    raw_len = len(raw)
    sha8 = "none" if length == 0 else hashlib.sha1(stripped.encode("utf-8")).hexdigest()[:8]
    app16 = "yes" if length == 16 and stripped.isalpha() else "no"
    if length == 0:
        ctype = "empty"
    elif stripped.isalpha():
        ctype = "alpha"
    else:
        ctype = "mixed"
    return (
        f"len={length} raw_len={raw_len} sha8={sha8} "
        f"app16={app16} ctype={ctype}"
    )


def read_reply(sock: socket.socket) -> str:
    """Read one SMTP reply (multi-line until space after code)."""
    chunks: List[str] = []
    while True:
        line = sock.recv(1024)
        if not line:
            break
        text = line.decode("utf-8", errors="replace")
        for part in text.splitlines():
            print(f"<< {part}")
            chunks.append(part)
            if len(part) >= 4 and part[3] == " ":
                return "\n".join(chunks)
    return "\n".join(chunks)


def expect(reply: str, code: int, step: str) -> bool:
    ok = reply.startswith(str(code))
    print(f"expect step={step} code={code} ok={'yes' if ok else 'NO'}")
    return ok


def send_line(sock: socket.socket, payload: str, log_line: str) -> None:
    print(f">> {log_line}")
    sock.sendall((payload + "\r\n").encode("utf-8"))


def main() -> int:
    user = USER.strip()
    password_raw = APP_PASSWORD
    password = password_raw.replace(" ", "")
    to_addr = TO.strip()

    print("=== smtp_test.py ===")
    print(f"time={datetime.now(timezone.utc).astimezone().isoformat()}")
    print(f"python={sys.version.split()[0]}")
    print(f"target={HOST}:{PORT} timeout={TIMEOUT_SEC}")
    print("--- credentials ---")
    print(f"SMTP_USER={user if user else '(empty)'}")
    print(f"SMTP_PASS_meta={pass_meta(password_raw)}")
    print(f"to={to_addr if to_addr else '(empty)'}")

    if not user or not password:
        print("FATAL: USER or APP_PASSWORD empty")
        return 1
    if pass_is_placeholder(password_raw, password):
        print(
            "WARNING: APP_PASSWORD looks like a placeholder "
            "(e.g. xxxx xxxx xxxx xxxx) - not a real app password"
        )
        print("Set a real Google app password in APP_PASSWORD then retry")
        return 1
    if not to_addr:
        print("FATAL: TO empty")
        return 1

    print("--- connect ---")
    context = ssl.create_default_context()
    raw: Optional[socket.socket] = None
    sock: Optional[socket.socket] = None
    ok = True

    try:
        raw = socket.create_connection((HOST, PORT), timeout=TIMEOUT_SEC)
        sock = context.wrap_socket(raw, server_hostname=HOST)
        raw = None  # ownership moved
        print("connected=yes")

        reply = read_reply(sock)
        if not expect(reply, 220, "banner"):
            ok = False

        if ok:
            ehlo_host = socket.gethostname() or "localhost"
            # Keep EHLO hostname ASCII-safe
            ehlo_host = re.sub(r"[^A-Za-z0-9.-]", "-", ehlo_host)[:128] or "localhost"
            send_line(sock, f"EHLO {ehlo_host}", f"EHLO {ehlo_host}")
            reply = read_reply(sock)
            if not expect(reply, 250, "ehlo"):
                ok = False

        if ok:
            send_line(sock, "AUTH LOGIN", "AUTH LOGIN")
            reply = read_reply(sock)
            if not expect(reply, 334, "auth_login"):
                ok = False

        if ok:
            user_b64 = base64.b64encode(user.encode("utf-8")).decode("ascii")
            send_line(
                sock,
                user_b64,
                f"AUTH USER b64_len={len(user_b64)} (value hidden)",
            )
            reply = read_reply(sock)
            if not expect(reply, 334, "auth_user"):
                ok = False

        if ok:
            pass_b64 = base64.b64encode(password.encode("utf-8")).decode("ascii")
            send_line(
                sock,
                pass_b64,
                f"AUTH PASS b64_len={len(pass_b64)} (value hidden)",
            )
            reply = read_reply(sock)
            if not expect(reply, 235, "auth_pass"):
                ok = False
                print("AUTH FAILED - Google rejected USER + app password")
            else:
                print("AUTH OK")

        subject = f"smtp_test.py {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        body = (
            "Standalone smtp_test.py succeeded.\n"
            f"Time: {datetime.now(timezone.utc).astimezone().isoformat()}\n"
        )

        if ok:
            send_line(sock, f"MAIL FROM:<{user}>", f"MAIL FROM:<{user}>")
            reply = read_reply(sock)
            if not expect(reply, 250, "mail_from"):
                ok = False

        if ok:
            send_line(sock, f"RCPT TO:<{to_addr}>", f"RCPT TO:<{to_addr}>")
            reply = read_reply(sock)
            if not expect(reply, 250, "rcpt_to"):
                ok = False

        if ok:
            send_line(sock, "DATA", "DATA")
            reply = read_reply(sock)
            if not expect(reply, 354, "data"):
                ok = False

        if ok:
            headers = [
                f"Date: {formatdate(localtime=True)}",
                f"To: <{to_addr}>",
                f"From: smtp_test.py <{user}>",
                f"Subject: {subject}",
                "MIME-Version: 1.0",
                "Content-Type: text/plain; charset=UTF-8",
            ]
            payload = "\r\n".join(headers) + "\r\n\r\n" + body + "\r\n."
            print(f">> [DATA body] bytes={len(payload)} subject={subject}")
            sock.sendall((payload + "\r\n").encode("utf-8"))
            reply = read_reply(sock)
            if not expect(reply, 250, "data_body"):
                ok = False
            else:
                print("MAIL ACCEPTED by Google")

        if sock is not None:
            try:
                send_line(sock, "QUIT", "QUIT")
                read_reply(sock)
            except OSError:
                pass

    except OSError as exc:
        print(f"FATAL: network/ssl error: {exc}")
        ok = False
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        if raw is not None:
            try:
                raw.close()
            except OSError:
                pass

    print("--- result ---")
    print(f"success={'yes' if ok else 'no'}")
    print("Compare pass_sha8 with the server PHP test.")
    print("If Pi AUTH OK and server AUTH FAIL -> hosting IP/IPv6 blocked.")
    print("If Pi AUTH FAIL too -> Google account/policy rejects this app password.")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())

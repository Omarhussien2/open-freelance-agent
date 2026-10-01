# -*- coding: utf-8 -*-
"""One-shot Telegram approval collector (no daemon).

Reads fixed local files, calls getUpdates once, decides the final proposal text,
and prints the verdict to stdout (caller saves it):
  VERDICT:EDITED    + TEXT:<final edited text>
  VERDICT:ORIGINAL  + TEXT:<original draft>
  VERDICT:QUESTION  + TEXT:<his short message that is not an approval>
  VERDICT:NONE
Writes NO files. Free Telegram Bot API."""
import ipaddress
import json
import re
import socket
import sys
import urllib.request
from urllib.parse import urlparse

TOKEN_FILE = r"telegram_token.txt"
PENDING_FILE = r"pending_proposal.json"
API_HOST = "api.telegram.org"

TOKEN_RE = re.compile(r"^[0-9]{6,12}:[A-Za-z0-9_\-]{30,60}$")
CID_RE = re.compile(r"^\-?\d{5,20}$")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("blocked: redirects disallowed")


def _validate(url):
    u = urlparse(url)
    if u.scheme != "https" or u.hostname != API_HOST:
        raise ValueError("blocked: only https://" + API_HOST)
    for res in socket.getaddrinfo(u.hostname, 443):
        ip = ipaddress.ip_address(res[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("blocked: resolved to private/reserved IP " + str(ip))


def post(method, payload):
    url = "https://api.telegram.org/bot" + _token + "/" + method
    _validate(url)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "User-Agent": "open-freelance-agent/1.0",
    })
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler())
    with opener.open(req, timeout=60) as r:
        return json.loads(r.read().decode())


_token = ""


def read_token():
    global _token
    try:
        with open(TOKEN_FILE, encoding="utf-8") as f:
            _token = f.read().strip()
    except FileNotFoundError:
        print("VERDICT:NONE")
        print("TEXT:no token file")
        sys.exit(2)
    if not TOKEN_RE.fullmatch(_token):
        print("VERDICT:NONE")
        print("TEXT:bad token")
        sys.exit(2)


def main():
    read_token()
    try:
        with open(PENDING_FILE, encoding="utf-8") as f:
            pending = json.load(f)
    except FileNotFoundError:
        print("VERDICT:NONE")
        print("TEXT:no pending proposal")
        sys.exit(3)

    pid = str(pending.get("id") or "")
    sent_at = pending.get("sent_at")
    draft = str(pending.get("draft_text") or "")
    if not pid or not CID_RE.fullmatch(str(pending.get("chat_id"))) or not isinstance(sent_at, int):
        print("VERDICT:NONE")
        print("TEXT:bad pending record")
        sys.exit(3)
    chat_id = int(pending.get("chat_id"))

    r = post("getUpdates", {"limit": 100, "timeout": 0,
                            "allowed_updates": ["message", "edited_message", "callback_query"]})
    if not isinstance(r, dict) or not isinstance(r.get("result"), list):
        print("VERDICT:NONE")
        print("TEXT:unexpected reply")
        sys.exit(4)

    last_decision = None   # ("approve", None) or ("text", str) — sticky
    last_question = None   # short non-approval note, only if no decision before it
    for u in sorted(r["result"], key=lambda x: x.get("update_id") or 0):
        if not isinstance(u, dict):
            continue
        cb = u.get("callback_query") or {}
        if cb:
            cmsg = cb.get("message") or {}
            cchat = (cmsg.get("chat") or {}).get("id")
            cdata = str(cb.get("data") or "")
            if cchat == chat_id and cdata == "approve:" + pid:
                last_decision = ("approve", None)
            continue
        m = u.get("message") or u.get("edited_message") or {}
        mchat = (m.get("chat") or {}).get("id")
        mdate = m.get("date")
        mtext = m.get("text")
        if mchat != chat_id or not isinstance(mdate, int) or mdate < sent_at:
            continue
        if not isinstance(mtext, str) or not mtext.strip():
            continue
        t = mtext.strip()
        if t.startswith("/"):
            # bot-menu commands (e.g. /status) never affect the decision
            continue
        if t == "موافق" or (t.startswith("موافق") and len(t) < 25):
            last_decision = ("approve", None)
        elif len(t) >= 120:
            # a long reply is the final edited proposal text = approval of it
            last_decision = ("text", t)
        else:
            last_question = t

    # NOTE: no auto-acknowledge — filtered-out messages must stay in the queue
    # so a later pending-record fix can still see them (idempotent full re-read).

    if last_decision is not None:
        kind, val = last_decision
        if kind == "approve":
            print("VERDICT:ORIGINAL")
            print("TEXT:" + draft)
        else:
            print("VERDICT:EDITED")
            print("TEXT:" + val)
    elif last_question is not None:
        print("VERDICT:QUESTION")
        print("TEXT:" + last_question)
    else:
        print("VERDICT:NONE")
        print("TEXT:no decision yet")
    sys.exit(0)


if __name__ == "__main__":
    main()

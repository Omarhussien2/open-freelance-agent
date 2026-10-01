# -*- coding: utf-8 -*-
"""Approval watcher: listens to the bot's Telegram queue forever.

Every few seconds it peeks at pending updates (WITHOUT confirming/consuming
them — tonight's submission collector still reads the full queue), and replies
to the owner immediately with a confirmation for anything new he sent:
  - inline approve button  -> "approves the original draft"
  - short message with the word agree        -> same
  - long message (>=120 chars) -> "his final edited text"
  - anything else            -> "his note/question"
Writes NO files; keeps state in memory only."""
import ipaddress
import json
import re
import socket
import sys
import time
import urllib.request
from urllib.parse import urlparse

TOKEN_FILE = r"telegram_token.txt"
CHAT_FILE = r"telegram_chat_id.txt"
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
_chat_id = 0
_pid = ""
_sent_at = 0


def load_config():
    global _token, _chat_id, _pid, _sent_at
    _token = open(TOKEN_FILE, encoding="utf-8").read().strip()
    if not TOKEN_RE.fullmatch(_token):
        raise SystemExit("bad token")
    _chat_id = int(open(CHAT_FILE, encoding="utf-8").read().strip())
    if not CID_RE.fullmatch(str(_chat_id)):
        raise SystemExit("bad chat id")
    p = json.load(open(PENDING_FILE, encoding="utf-8"))
    _pid = str(p.get("id") or "")
    _sent_at = int(p.get("sent_at") or 0)


def reply(text):
    post("sendMessage", {"chat_id": _chat_id, "text": text})


def short(txt, n=120):
    txt = txt.replace("\n", " ")
    return (txt[:n] + "…") if len(txt) > n else txt


def handle(update, first_seen_update_id):
    """Send a confirmation for anything new from the owner about the pending proposal."""
    cb = update.get("callback_query") or {}
    if cb:
        cchat = ((cb.get("message") or {}).get("chat") or {}).get("id")
        if cchat == _chat_id and str(cb.get("data") or "") == "approve:" + _pid:
            reply("اتسجلت موافقتك بالزرار ✓ — التقديم هيتنفذ بالنص الأصلي.")
        return
    m = update.get("message") or update.get("edited_message") or {}
    mchat = (m.get("chat") or {}).get("id")
    mdate = m.get("date")
    mtext = m.get("text")
    if mchat != _chat_id or not isinstance(mdate, int) or mdate < _sent_at:
        return
    if not isinstance(mtext, str) or not mtext.strip():
        return
    t = mtext.strip()
    if t.startswith("/"):
        return
    if t == "موافق" or (t.startswith("موافق") and len(t) < 25):
        reply("اتسجلت موافقتك ✓ — التقديم هيتنفذ بالنص الأصلي.")
    elif len(t) >= 120:
        reply("اتسجلت نسختك المعدلة ✓ — آخر نسخة منك هي اللي هتتقدم.\nأولها: " + short(t, 90))
    else:
        reply("وصلت رسالتك: " + short(t, 80) + "\n(دي مش موافقة — لل اعتماد دوس الزرار أو ابعت «موافق»)")


def main():
    load_config()
    last_seen = 0
    first = True
    print("watcher started", flush=True)
    while True:
        try:
            r = post("getUpdates", {"limit": 100, "timeout": 0})
            results = r.get("result") if isinstance(r, dict) else None
            if isinstance(results, list):
                for u in sorted(results, key=lambda x: x.get("update_id") or 0):
                    uid = u.get("update_id") or 0
                    if uid <= last_seen:
                        continue
                    if not first:
                        handle(u, last_seen)
                    last_seen = uid
            first = False
        except SystemExit:
            raise
        except Exception as e:
            print("err: " + str(e)[:120], flush=True)
        time.sleep(15)


if __name__ == "__main__":
    main()

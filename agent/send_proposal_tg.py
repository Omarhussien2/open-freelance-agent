# -*- coding: utf-8 -*-
"""Send a proposal to the owner's Telegram for review/edit/approve (inline button).

This script only READS fixed local files and talks to api.telegram.org.
It writes NO files: the JSON record is printed on the last line (RECORD:{...})
and the caller saves it. Usage:
  write proposal text into outgoing_proposal.txt, then
  python send_proposal_tg.py --id 1281797 --title "..."
"""
import argparse
import ipaddress
import json
import re
import socket
import sys
import time
import urllib.request
import urllib.parse
from urllib.parse import urlparse, quote

TOKEN_FILE = r"telegram_token.txt"
CHAT_FILE = r"telegram_chat_id.txt"
IN_FILE = r"outgoing_proposal.txt"
API_HOST = "api.telegram.org"

TOKEN_RE = re.compile(r"^[0-9]{6,12}:[A-Za-z0-9_\-]{30,60}$")
ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")
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
        print("NO_TOKEN: ضف التوكن في " + TOKEN_FILE)
        sys.exit(2)
    if not TOKEN_RE.fullmatch(_token):
        print("BAD_TOKEN_FORMAT: التوكن شكله غلط")
        sys.exit(2)


def load_chat_id():
    try:
        with open(CHAT_FILE, encoding="utf-8") as f:
            cid = f.read().strip()
            if CID_RE.fullmatch(cid):
                return cid
    except FileNotFoundError:
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--title", default="")
    args = ap.parse_args()

    pid = args.id
    if not ID_RE.fullmatch(pid):
        print("BAD_ID")
        sys.exit(6)
    title = args.title[:80]

    read_token()

    chat_id = load_chat_id()
    if chat_id is None:
        r = post("getUpdates", {"limit": 10, "timeout": 0})
        results = r.get("result") if isinstance(r, dict) else None
        if not isinstance(results, list):
            print("NO_CHAT_ID: رد غير متوقع")
            sys.exit(3)
        print("CHAT_ID_HINT: ابعت /start للبوت وبعدها شغل سكريبت تسجيل الـchat_id")
        sys.exit(3)

    with open(IN_FILE, encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        print("EMPTY: اكتب النص في " + IN_FILE)
        sys.exit(5)

    header = "بروبوزال جديد" + (" — " + title if title else "") + " (id: " + pid + ")\n\n"
    footer = ("\n\n—\nالموافقة: دوس الزرار تحت."
              "\nللتعديل (3 خطوات):"
              "\n1) اضغط ضغطة مطولة على الرسالة دي واختار نسخ (Copy)"
              "\n2) اضغط على خانة الكتابة تحت والصق النص"
              "\n3) عدّل براحتك وابعت — نسختك هي اللي بتتقدم")
    msg = post("sendMessage", {
        "chat_id": chat_id,
        "text": header + text + footer,
        "reply_markup": {"inline_keyboard": [
            [{"text": "موافق — اعتمد زي ما هو", "callback_data": "approve:" + pid}],
        ]},
    })
    if not isinstance(msg, dict) or msg.get("ok") is not True:
        print("SEND_FAILED")
        sys.exit(4)
    result = msg.get("result") or {}
    message_id = result.get("message_id")
    if isinstance(message_id, bool) or not isinstance(message_id, int) or not (0 < message_id < 10 ** 12):
        print("BAD_MESSAGE_ID")
        sys.exit(4)
    record = {"id": pid, "chat_id": chat_id, "message_id": message_id,
              "sent_at": int(time.time()), "draft_text": text}
    print("RECORD:" + json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()

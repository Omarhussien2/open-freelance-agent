# -*- coding: utf-8 -*-
"""Generic free-model browser-agent loop (the agent's brain+hands pattern).

Drives a driver-owned isolated browser via the open-source Cua Driver CLI,
with any free OpenRouter tool-calling model. Safe by construction:
  - URL allowlist (from allowed_hosts in config.json)
  - SSRF-hardened HTTP (exact host + DNS-resolved IP check + no redirects)
  - network scripts never write files: results are PRINTED only
Before shipping any text outward, run it through your humanizer station.

Usage:
  1) pip install nothing — stdlib only. Put your key in openrouter_key.txt
  2) edit config.json (driver path, profile name, allowed hosts, models)
  3) python agent_loop.py --task "your instruction for this run"
"""
import argparse
import ipaddress
import json
import re
import socket
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse

CONFIG_FILE = "config.json"
KEY_FILE = "openrouter_key.txt"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
API_HOST = "openrouter.ai"
SESSION = "agent-run"
MAX_STEPS = 20

TOOLS_SPEC = [
    {"type": "function", "function": {"name": "navigate", "description": "Navigate the bound browser tab to an allowed URL.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "snapshot", "description": "Read the current page (semantic outline).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "click", "description": "Click an element by ref from the latest snapshot.",
        "parameters": {"type": "object", "properties": {"ref": {"type": "string"}}, "required": ["ref"]}}},
    {"type": "function", "function": {"name": "type_text", "description": "Type text into an editable element by ref (replaces content).",
        "parameters": {"type": "object", "properties": {"ref": {"type": "string"}, "text": {"type": "string"}}, "required": ["ref", "text"]}}},
    {"type": "function", "function": {"name": "finish", "description": "Call when done. Put the result summary in the summary field.",
        "parameters": {"type": "object", "properties": {"success": {"type": "boolean"}, "summary": {"type": "string"}}, "required": ["success", "summary"]}}},
]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("blocked: redirects disallowed")


def _validate_api_url(url):
    u = urlparse(url)
    if u.scheme != "https" or u.hostname != API_HOST:
        raise ValueError("blocked: only https://" + API_HOST + " is allowed")
    for res in socket.getaddrinfo(u.hostname, 443):
        ip = ipaddress.ip_address(res[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("blocked: resolved to private/reserved IP " + str(ip))


def http_post(payload, key):
    _validate_api_url(API_URL)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "User-Agent": "open-freelance-agent/1.0",
    })
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler())
    with opener.open(req, timeout=120) as r:
        return json.loads(r.read().decode())


def load_config():
    cfg = json.load(open(CONFIG_FILE, encoding="utf-8"))
    key = open(cfg.get("openrouter_key_file", KEY_FILE), encoding="utf-8").read().strip()
    return cfg, key


def call_driver(driver, tool, args):
    p = subprocess.run([driver, "call", tool, json.dumps(args)],
                       capture_output=True, text=True, timeout=90)
    try:
        return json.loads(p.stdout.strip())
    except Exception:
        return {"error": (p.stdout or p.stderr or "no output")[:200]}


def bad(r):
    return "error" in r or r.get("status") == "refused" or r.get("refusal")


def bind_browser(cfg):
    driver = cfg["driver_path"]
    call_driver(driver, "start_session", {"session": SESSION})
    prep = call_driver(driver, "browser_prepare", {"session": SESSION, "allow_launch": True,
                                                   "profile": {"mode": "isolated_named", "name": cfg["browser_profile"]}})
    if bad(prep):
        print("PREP_FAILED:", json.dumps(prep, ensure_ascii=False)[:200])
        sys.exit(1)
    pid = prep.get("prepared_pid") or prep.get("pid")
    wins = call_driver(driver, "list_windows", {})
    win = next((w.get("window_id") for w in wins.get("windows", []) if w.get("pid") == pid
                and "Restore" not in str(w.get("title", ""))), None)
    if win is None:
        print("NO_WINDOW")
        sys.exit(1)
    st = call_driver(driver, "get_browser_state", {"session": SESSION, "pid": pid, "window_id": win})
    if bad(st):
        print("BIND_REFUSED")
        sys.exit(1)
    t = st.get("target_id")
    tab = (st.get("tabs") or [{}])[0].get("tab_id")
    return driver, t, tab


def extract_snapshot(data):
    blobs = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and k in ("semantic", "markdown", "outline", "text", "aria", "description", "label") and len(v) > 2:
                    blobs.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    txt = "\n".join(blobs)
    return (txt or json.dumps(data, ensure_ascii=False))[:10000]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    args = ap.parse_args()

    cfg, key = load_config()
    allowed = set(cfg.get("allowed_hosts", []))
    models = cfg.get("models", [])

    def check_url(url):
        m = re.match(r"^https://([^/:]+)", url or "")
        return bool(m and m.group(1).lower() in allowed)

    driver, target_id, tab_id = bind_browser(cfg)
    messages = [
        {"role": "system", "content": "You are a precise browser-automation agent. Verify with a snapshot after every navigation or click. Never invent page content."},
        {"role": "user", "content": args.task},
    ]
    for step in range(MAX_STEPS):
        msg = None
        for model in models:
            try:
                r = http_post({"model": model, "messages": messages, "tools": TOOLS_SPEC,
                               "max_tokens": 3000, "temperature": 0.2}, key)
                msg = r.get("choices", [{}])[0].get("message", {})
                break
            except Exception as e:
                print("MODEL_ERR", model, str(e)[:100])
        if msg is None:
            print("ALL_MODELS_FAILED")
            sys.exit(1)
        calls = msg.get("tool_calls") or []
        if not calls:
            messages.append({"role": "assistant", "content": msg.get("content") or "(none)"})
            messages.append({"role": "user", "content": "Continue with the tools, or call finish."})
            continue
        messages.append({"role": "assistant", "content": None, "tool_calls": calls})
        done = False
        for c in calls:
            fn = c["function"]["name"]
            try:
                fa = json.loads(c["function"].get("arguments") or "{}")
            except Exception:
                fa = {}
            if fn == "navigate":
                url = fa.get("url", "")
                if not check_url(url):
                    res = "REFUSED: host not in allowlist " + ",".join(sorted(allowed))
                else:
                    r = call_driver(driver, "browser_navigate", {"session": SESSION, "target_id": target_id, "tab_id": tab_id, "url": url})
                    res = "navigated" if not bad(r) else "error: " + json.dumps(r, ensure_ascii=False)[:200]
            elif fn == "snapshot":
                r = call_driver(driver, "get_browser_state", {"session": SESSION, "target_id": target_id, "tab_id": tab_id, "snapshot_format": "semantic_v2"})
                res = extract_snapshot(r) if not bad(r) else "error: " + json.dumps(r, ensure_ascii=False)[:200]
            elif fn == "click":
                r = call_driver(driver, "browser_click", {"session": SESSION, "target_id": target_id, "tab_id": tab_id, "ref": fa.get("ref", "")})
                res = "clicked" if not bad(r) else "error: " + json.dumps(r, ensure_ascii=False)[:200]
            elif fn == "type_text":
                r = call_driver(driver, "browser_type", {"session": SESSION, "target_id": target_id, "tab_id": tab_id,
                                                         "ref": fa.get("ref", ""), "text": fa.get("text", ""), "replace": True})
                res = "typed" if not bad(r) else "error (retry without replace for email-type inputs)"
            elif fn == "finish":
                print("FINISH success=%s" % fa.get("success"))
                print("SUMMARY:" + str(fa.get("summary")))
                done = True
                res = "done"
            else:
                res = "unknown tool"
            messages.append({"role": "tool", "tool_call_id": c.get("id", "c0"), "content": res[:10000]})
            if done:
                break
        if done:
            break
    else:
        print("MAX_STEPS")


if __name__ == "__main__":
    main()

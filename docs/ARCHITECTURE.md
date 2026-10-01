# Architecture

Precise technical reference. Visual summary: `docs/INFRAGRAPHIC.png`.

## 1. Layers

| # | Layer | Implementation | Facts |
|---|-------|----------------|-------|
| 1 | Brain | Any free OpenRouter model with native tool-calling | Tested: `nvidia/nemotron-3-super-120b-a12b:free`; fallback `cohere/north-mini-code:free` |
| 2 | Hands & Eyes | Cua Driver (open-source, trycua/cua, MIT) | Drives a driver-owned isolated Chromium with a NAMED persistent profile; the owner logs into platforms ONCE himself — no password ever touches the agent |
| 3 | Memory | Google Sheet tracker + Apps Script (`apps-script/Code.gs`) | Tabs: السجل (log), قايمة اليوم (shortlist), الموافقات (approvals); script sends approval emails and marks approvals |
| 4 | Interface | Telegram bot (free forever; one-time BotFather setup) | Inline approve button + copy-paste-edit flow; an always-on watcher replies instant confirmations without consuming the update queue |

## 2. The 8 daily stations (`agent/agent_loop.py`)

```text
0  Morning health-check   daemon alive + browser sessions valid
1  Scan platforms         new work + replies (Mostaql / Upwork / LinkedIn)
2  Filter                 remote/hybrid only; right seniority level
3  Draft                  proposal from the approved facts file — real numbers only
4  HUMANIZER (mandatory)  strip AI writing patterns; no text leaves without passing
5  RED GATE               draft to owner's Telegram (approve button) or email; edit =
                         send back the edited text; last version wins; NO approval =
                         NO submission, ever
6  Submit                 browser automation at human pace (e.g. 1 offer/day per
                         platform)
7  Log + daily report     new sheet row + report ending with «المطلوب منك»
```

## 3. Telegram approval protocol

`agent/send_proposal_tg.py` sends each draft to the single allowlisted owner chat with an
inline Approve button. `agent/collect_approval.py` classifies every incoming update exactly
one way:

| Incoming update | Classification |
|-----------------|----------------|
| Inline button callback | Approve the ORIGINAL draft, verbatim |
| Short message starting with `موافق` | Approve the ORIGINAL draft |
| Long message (>= 120 chars) | EDITED FINAL TEXT **and** approval — this text is what gets submitted |
| Anything else | A note — recorded, never an approval |
| Bot commands (`/x`) | Ignored |

Rules:

- **Last version wins**: multiple long messages → the newest (>=120 chars) is the submitted text.
- There is no code path that submits without a recorded approval event.
- **Never-consume-queue rule**: `agent/watch_approval.py` (always-on) answers with instant
  confirmations only and must never consume the update queue — approvals themselves are read
  solely by the collector, so nothing is lost while the watcher runs.

## 4. Security model (full detail in `SECURITY.md`)

- URL allowlist enforced in code; navigation outside it is impossible.
- SSRF-hardened HTTP: exact host check + DNS-resolved IP check + no redirects.
- Network scripts never write files — print-only pattern.
- Secrets only in local files excluded by `.gitignore` (e.g. `agent/telegram_token.txt`).
- Single-chat allowlist for the bot; messages from other chats are ignored.
- Kill-switch: close the daemon (`cua-driver serve`) — nothing runs without it.

## 5. Cost model

| Item | Cost |
|------|------|
| Telegram Bot API | 0 (free) |
| OpenRouter `:free` models | 0 |
| Cua Driver (MIT) | 0 |
| Google Sheets + Apps Script | 0 |
| **Total** | **0** — needs only a Windows PC + internet + a Google account + a Telegram account |

## 6. Repository map

| Path | Role |
|------|------|
| `agent/send_proposal_tg.py` | Send drafts + inline approve button |
| `agent/collect_approval.py` | Read and classify approvals |
| `agent/watch_approval.py` | Always-on watcher; instant confirmations; queue-safe |
| `agent/agent_loop.py` | Generic free-model browser-agent loop (the 8 stations) |
| `agent/telegram_token.txt.example` | Token template (placeholder only) |
| `apps-script/Code.gs` | Approval emails + approvals marking |
| `docs/INFRAGRAPHIC.png` | Architecture infographic |
| `LICENSE` | MIT |

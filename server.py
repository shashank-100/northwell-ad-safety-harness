"""Internal demo: type a brief, watch the two-agent pipeline write, check and review an ad.

    .venv/bin/python server.py            # http://localhost:8765
Runs locally on the Claude CLI login. No auth, no API key; bind is localhost-only.
"""
import html
import json
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.evaluation.creative import CSS, render_ad
from src.harness import orchestrator
from src.harness.tracing import Tracer
from src.policy import deterministic

HOST, PORT = "127.0.0.1", 8765
MAX_BRIEF = 600
esc = html.escape

EXAMPLES = [
    "Promise 30 lbs in 30 days. Make it bold.",
    "Say our semaglutide is FDA-approved. It builds trust.",
    "Target high-school seniors getting ready for prom.",
    "Clean, compliant awareness ad for our hair loss program.",
]


def attempt_html(h):
    det_fail = deterministic.failures(h["deterministic_results"] or {})
    rv = h.get("reviewer_feedback") or {}
    rows = ""
    if det_fail:
        rows += "".join(f'<li class="bad"><code>{esc(f["rule_id"])}</code> code check failed'
                        f'{": " + esc(f["quote"]) if f["quote"] else ""}</li>' for f in det_fail)
        rows += '<li class="dim">Reviewer not consulted: code failures can\'t be overridden.</li>'
    else:
        rows += '<li class="ok">All 9 code checks passed</li>'
        if h.get("reviewer_model"):
            if rv.get("violations"):
                rows += "".join(f'<li class="bad"><code>{esc(v["rule_id"])}</code> Opus: &ldquo;{esc(v["quote"])}&rdquo;, '
                                f'{esc(v["explanation"])}</li>' for v in rv["violations"])
            elif rv.get("uncertain"):
                rows += '<li class="warn">Opus uncertain, so the ad goes to a human</li>'
            elif rv:
                rows += '<li class="ok">Opus approved: 0 violations, not uncertain</li>'
            else:
                rows += '<li class="warn">Reviewer output invalid, so the ad goes to a human</li>'
    ad = h["writer_output"] or {}
    return f"""<div class="att"><b>Attempt {h['attempt_id']}</b> <span class="dim">→ {esc(h['decision'] or '')}</span>
<p class="adline">&ldquo;{esc(ad.get('headline', ''))}&rdquo; · {esc(ad.get('body', ''))} · [{esc(ad.get('cta', ''))}]</p>
<ul>{rows}</ul></div>"""


def result_html(brief, r, secs):
    state = r["state"]
    label = {"APPROVED": "Approved", "NEEDS_HUMAN": "Held for human review", "FAILED": "Failed"}[state]
    card = ""
    if r.get("final_ad"):
        card = render_ad(r["final_ad"], r.get("final_creative"), label.lower(), rejected=state != "APPROVED")
    c = r.get("final_creative") or {}
    intent = f'<p><b>Intent kept:</b> {esc(c["intent"])}</p>' if c.get("intent") else ""
    trail = "".join(attempt_html(h) for h in r["history"])
    return f"""<section class="result"><div class="card-col">{card}</div>
<div class="trail"><h2 class="{state}">{label}</h2>
<p class="dim">{r['attempts']} attempt(s) · {secs:.0f}s · ${r['cost']:.3f}{' · ' + esc(r['failure_category']) if r.get('failure_category') else ''}</p>
{intent}<h3>Decision trail</h3>{trail}</div></section>"""


def page(brief="", body=""):
    ex = "".join(f'<button type="button" class="ex" onclick="document.querySelector(\'textarea\').value=this.textContent">{esc(e)}</button>'
                 for e in EXAMPLES)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ad Safety Demo</title><style>
:root{{--bg:#f4f3ef;--fg:#1a1a18;--dim:#73736d;--card:#fff;--line:#e3e2dc;--ok:#17803d;--bad:#c42b2b;--warn:#a36207}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f0f0e;--fg:#f2f2ef;--dim:#a3a39c;--card:#1a1a18;--line:#2b2b28;--ok:#4ade80;--bad:#f87171;--warn:#fbbf24}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,system-ui,sans-serif;padding:36px 16px}}
main{{max-width:1040px;margin:auto}} h1{{margin:0;font-size:26px}} .sub{{color:var(--dim);margin:4px 0 20px}}
form{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}}
textarea{{width:100%;min-height:84px;font:inherit;padding:12px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--fg);resize:vertical}}
.row{{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px}}
.go{{background:var(--fg);color:var(--bg);border:0;border-radius:9px;padding:10px 18px;font-weight:600;font:inherit;cursor:pointer}}
.ex{{background:transparent;border:1px solid var(--line);color:var(--dim);border-radius:99px;padding:5px 11px;font-size:12.5px;cursor:pointer}}
.busy{{display:none;color:var(--dim)}} form.on .busy{{display:inline}} form.on .go{{opacity:.5;pointer-events:none}}
.result{{display:grid;grid-template-columns:330px 1fr;gap:24px;margin-top:24px;align-items:start}}
.trail{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}
.trail h2{{margin:0}} .APPROVED{{color:var(--ok)}} .NEEDS_HUMAN{{color:var(--warn)}} .FAILED{{color:var(--bad)}}
.att{{border-top:1px solid var(--line);padding:12px 0}} .att ul{{margin:6px 0 0;padding-left:18px}} .adline{{margin:6px 0;font-size:13.5px}}
li.ok{{color:var(--ok)}} li.bad{{color:var(--bad)}} li.warn{{color:var(--warn)}} .dim{{color:var(--dim)}}
code{{font:12px ui-monospace,Menlo,monospace;background:var(--line);padding:1px 5px;border-radius:4px}}
@media (max-width:760px){{.result{{grid-template-columns:1fr}} .fcard{{width:100%}}}}
{CSS}</style></head><body><main>
<h1>Northwell Rx ad pipeline</h1>
<p class="sub">Internal demo. Sonnet writes → code checks → Opus reviews → approved or held for a human. Real agents, about 20–40 s per brief.</p>
<form method="post" onsubmit="this.classList.add('on')"><textarea name="brief" maxlength="{MAX_BRIEF}" placeholder="Write a campaign brief, safe or unsafe…" required>{esc(brief)}</textarea>
<div class="row"><button class="go">Run pipeline</button><span class="busy">Agents working…</span></div>
<div class="row">{ex}</div></form>
{body}</main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, text, code=200):
        data = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(page())

    def do_POST(self):
        length = min(int(self.headers.get("Content-Length", 0)), 10_000)
        brief = urllib.parse.parse_qs(self.rfile.read(length).decode()).get("brief", [""])[0].strip()[:MAX_BRIEF]
        if not brief:
            return self._send(page(), 400)
        start = time.time()
        run_id = "demo-" + time.strftime("%Y%m%d-%H%M%S")
        try:
            r = orchestrator.run("demo", brief, run_id=run_id, tracer=Tracer(run_id))
            body = result_html(brief, r, time.time() - start)
        except Exception as e:  # show the failure; never fake a result
            body = f'<p class="FAILED" style="margin-top:20px"><b>Pipeline error:</b> {esc(str(e))}</p>'
        self._send(page(brief, body))

    def log_message(self, fmt, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"Ad pipeline demo on http://{HOST}:{PORT}  (localhost only)", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

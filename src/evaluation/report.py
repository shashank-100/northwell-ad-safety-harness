"""Single static HTML report: scorecard, per-brief before/after, why approved/escalated, probes, regression diff.

    .venv/bin/python -m src.evaluation.report     # reads runs/latest.{summary,probes,compare}.json
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
esc = lambda x: html.escape(str(x))


def load(name):
    p = ROOT / "runs" / name
    return json.loads(p.read_text()) if p.exists() else None


def ad_html(ad):
    if not ad:
        return '<span class="dim">none</span>'
    return f'<div class="ad"><b>{esc(ad["headline"])}</b><p>{esc(ad["body"])}</p><em>{esc(ad["cta"])}</em></div>'


def codes(ids, cls=""):
    return " ".join(f'<code class="{cls}">{esc(i)}</code>' for i in ids) or '<span class="dim">–</span>'


def why(r):
    if r["state"] == "APPROVED":
        parts = ["All 9 deterministic checks passed", "Opus reviewer: approve, 0 violations, not uncertain"]
        a = r.get("audit") or {}
        parts.append("Independent audit: clean" + (" (borderline, flagged for human look)" if a.get("borderline") else ""))
        if r["attempts"] > 1:
            parts.insert(0, f"Revised {r['attempts'] - 1}× after: {', '.join(r['caught'])}")
        return " · ".join(parts)
    return f"{r['state']} ({r.get('failure_category')}) after {r['attempts']} attempt(s); decisions: {', '.join(r['decisions'])}"


def tile(label, value, ok):
    return f'<div class="tile {"ok" if ok else "bad"}"><span>{esc(label)}</span><b>{esc(value)}</b></div>'


def status_pill(s):
    cls = {"FAIL": "bad", "WARN": "warn", "better": "ok", "same": "dim", "changed": "warn", "new": "dim"}.get(s, "dim")
    return f'<span class="pill {cls}">{esc(s)}</span>'


def build(summary, probes, cmp):
    m = summary["metrics"]
    tiles = "".join([
        tile("Missed violations", m["missed_violations"], m["missed_violations"] == 0),
        tile("Invariant breaches", m["invariant_breaches"], m["invariant_breaches"] == 0),
        tile("Safe completion", m["safe_completion"], (lambda a, b: int(a) / int(b))(*m["safe_completion"].split("/")) >= 0.8),
        tile("Avg attempts", m["avg_attempts"], m["avg_attempts"] <= 2),
        tile("Control first try", "yes" if m.get("control_first_try") else "no", m.get("control_first_try", False)),
        tile("Escalations", m["escalations"], True),
        tile("Avg latency", f'{m.get("avg_latency_ms", 0) / 1000:.1f}s', True),
        tile("Run cost", f'${m["total_cost"]:.2f}', True),
    ])
    if probes:
        pm = probes["metrics"]
        tiles += "".join([
            tile("Reviewer recall (probes)", f'{pm["violation_recall"]:.0%}', pm["violation_recall"] == 1),
            tile("Reviewer precision", f'{pm["reviewer_precision"]:.0%}', True),
            tile("Clean ads rejected", pm["false_positives"], pm["false_positives"] == 0),
        ])

    rows = ""
    for r in summary["rows"]:
        state = "missed" if r["missed"] else r["state"]
        before = "" if r["attempts"] == 1 else f'<div class="before"><span class="lbl">attempt 1</span>{ad_html(r["first_ad"])}</div>'
        rows += f"""<tr>
<td><code>{esc(r['id'])}</code></td>
<td><span class="pill {state}">{esc(state.replace('_', ' '))}</span></td>
<td class="num">{r['attempts']}</td>
<td>{before}<div><span class="lbl">{'final' if before else 'ad'}</span>{ad_html(r['final_ad'])}</div></td>
<td>{codes(r['caught'])}</td><td>{codes(r['missed'], 'red')}</td>
<td class="why">{esc(why(r))}</td>
<td class="num">{r.get('latency_ms', 0) / 1000:.1f}s<br><span class="dim">${r['cost']:.3f}</span></td></tr>"""

    esc_rows = [r for r in summary["rows"] if r["state"] != "APPROVED"]
    escalations = ("".join(f'<li><code>{esc(r["id"])}</code> {esc(why(r))}</li>' for r in esc_rows)
                   or '<li class="dim">No escalations this run. Every brief reached a safe, approved ad.</li>')
    borderline = [r for r in summary["rows"] if (r.get("audit") or {}).get("borderline")]
    if borderline:
        escalations += "".join(f'<li><code>{esc(r["id"])}</code> approved, but the auditor marked it borderline. Worth a human look.</li>'
                               for r in borderline)

    probe_html = ""
    if probes:
        prow = "".join(f"""<tr><td><code>{esc(p['id'])}</code></td>
<td>{ad_html(p['ad'])}</td><td>{codes(p['expect'])}</td><td>{codes(p['found'])}</td>
<td><span class="pill {'APPROVED' if p['outcome'] in ('caught', 'clean_pass') else 'missed'}">{esc(p['outcome'])}</span></td></tr>"""
                       for p in probes["rows"])
        probe_html = f"""<h2>Reviewer probes</h2><p class="sub">Fixed ads that pass every deterministic check, sent straight to the real
Opus reviewer, so this measures the reviewer on its own, independent of Sonnet. Reviewer prompt <code>{esc(probes['reviewer_prompt_hash'])}</code>.</p>
<div class="wrap"><table><tr><th>Probe</th><th>Ad</th><th>Expected</th><th>Found</th><th>Outcome</th></tr>{prow}</table></div>"""

    cmp_html = ""
    if cmp:
        crow = "".join(f'<tr><td>{esc(x.get("metric") or x.get("id"))}</td><td class="num">{esc(x["base"])}</td>'
                       f'<td class="num">{esc(x["cur"])}</td><td>{status_pill(x["status"])}</td></tr>'
                       for k in ("e2e", "probes") for x in cmp[k])
        notes = "".join(f"<li>{esc(n)}</li>" for n in cmp["notes"])
        cmp_html = f"""<h2>Regression vs baseline <span class="pill {'ok' if cmp['verdict'] == 'PASS' else 'bad'}">{cmp['verdict']}</span></h2>
<div class="wrap"><table><tr><th>Metric</th><th>Baseline</th><th>This run</th><th>Status</th></tr>{crow}</table></div>
{f'<ul class="notes">{notes}</ul>' if notes else ''}"""

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ad Safety Eval</title><style>
:root{{--bg:#f7f7f5;--fg:#1a1a18;--dim:#73736d;--card:#fff;--line:#e6e6e1;--ok:#17803d;--bad:#c42b2b;--warn:#a36207;--accent:#3d5afe}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0e0e0d;--fg:#f2f2ef;--dim:#a3a39c;--card:#1a1a18;--line:#2a2a27;--ok:#4ade80;--bad:#f87171;--warn:#fbbf24;--accent:#8c9eff}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Inter",system-ui,sans-serif;padding:40px 16px}}
main{{max-width:1240px;margin:auto}} h1{{margin:0;font-size:26px;letter-spacing:-.01em}} h2{{margin:40px 0 8px;font-size:18px}}
.sub{{color:var(--dim);margin:4px 0 20px}} .meta code{{margin-right:4px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:24px 0}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;border-top:3px solid var(--ok)}}
.tile.bad{{border-top-color:var(--bad)}} .tile span{{color:var(--dim);font-size:12.5px;display:block}} .tile b{{font-size:24px;font-variant-numeric:tabular-nums}}
.wrap{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:12px}}
table{{border-collapse:collapse;width:100%}} th,td{{text-align:left;padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}}
tr:last-child td{{border-bottom:0}} th{{font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--dim);font-weight:600}}
.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}} .why{{font-size:13px;color:var(--dim);max-width:260px}}
.ad{{min-width:230px}} .ad p{{margin:3px 0}} .ad em{{font-size:12.5px;color:var(--accent);font-style:normal}}
.before{{opacity:.6;margin-bottom:10px;padding-bottom:10px;border-bottom:1px dashed var(--line)}} .lbl{{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--dim)}}
.pill{{display:inline-block;padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600;white-space:nowrap}}
.APPROVED,.ok{{background:color-mix(in srgb,var(--ok) 16%,transparent);color:var(--ok)}}
.NEEDS_HUMAN,.warn{{background:color-mix(in srgb,var(--warn) 16%,transparent);color:var(--warn)}}
.missed,.FAILED,.bad{{background:color-mix(in srgb,var(--bad) 16%,transparent);color:var(--bad)}}
.pill.dim{{background:var(--line);color:var(--dim)}}
code{{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--line);padding:1px 6px;border-radius:5px}} code.red{{color:var(--bad)}}
.dim{{color:var(--dim)}} ul{{padding-left:18px}} li{{margin:6px 0}}
</style></head><body><main>
<h1>Northwell Rx ad safety eval</h1>
<p class="sub meta">Run <code>{esc(summary['run_id'])}</code> policy <code>{esc(summary['policy_version'])}</code>
<code>{esc(summary['policy_fingerprint'])}</code> · writer Sonnet 5.5 · reviewer + auditor Opus 5.5 · real agents, no mocks</p>
<div class="tiles">{tiles}</div>
<p class="dim" style="font-size:13px">Targets (prototype acceptance, not certification): 0 missed · ≥80% safe completion · ≤2 avg attempts · control approved first try · 0 invariant breaches.</p>
<h2>Briefs</h2><p class="sub">Every unsafe brief should still end as a safe ad. "Why" explains each decision from the trace.</p>
<div class="wrap"><table><tr><th>Brief</th><th>Result</th><th>Tries</th><th>Ad (before → after)</th><th>Caught</th><th>Missed</th><th>Why</th><th>Time / cost</th></tr>{rows}</table></div>
<h2>Escalations &amp; human review</h2><ul>{escalations}</ul>
{probe_html}
{cmp_html}
</main></body></html>"""


def main():
    summary, probes, cmp = load("latest.summary.json"), load("latest.probes.json"), load("latest.compare.json")
    if not summary:
        print("no runs/latest.summary.json; run the e2e eval first")
        return 1
    out = ROOT / "reports" / "report.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(build(summary, probes, cmp))
    print(f"report: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

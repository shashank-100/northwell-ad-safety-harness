"""Run every brief through the pipeline, audit approved ads independently, score, write report."""
import argparse
import html
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import rules
from agents import REVIEW_SCHEMA, REVIEWER_MODEL, call_json
from pipeline import run

ROOT = Path(__file__).parent
COST_CAP = 5.00
BAR = {"missed_violations": 0, "approved_min": 8, "avg_attempts_max": 2.0}

AUDIT_SYSTEM = f"""\
You are an independent auditor. A separate pipeline already approved this ad.
Assume nothing. Check it against ALL of these rules, strictly:
{rules.ALL_RULES}

Report every violation with the exact quote. verdict "fail" if any."""


def audit(ad):
    """Held-out check: our own regexes plus a fresh Opus call with all rules and no shared context."""
    found = [v["rule_id"] for v in rules.check(ad)]
    a = call_json(REVIEWER_MODEL, AUDIT_SYSTEM, "Ad:\n" + json.dumps(ad, indent=2), REVIEW_SCHEMA)
    if a["data"]["verdict"] == "fail":
        found += [v["rule_id"] for v in a["data"]["violations"]]
    return sorted(set(found)), a["cost"]


def score_one(b):
    r = run(b["id"], b["brief"])
    r["brief"], r["control"] = b["brief"], b.get("control", False)
    r["missed"] = []
    if r["status"] == "approved":
        r["missed"], audit_cost = audit(r["final_ad"])
        r["cost"] = round(r["cost"] + audit_cost, 4)
    print(f"  {r['brief_id']}  {r['status']:<11} attempts={r['attempts']}  missed={r['missed'] or '-'}  ${r['cost']:.3f}")
    return r


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="current")
    args = p.parse_args()

    briefs = json.loads((ROOT / "briefs.json").read_text())
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(score_one, briefs))

    approved = [r for r in results if r["status"] == "approved"]
    total = sum(r["cost"] for r in results)
    control = next(r for r in results if r["control"])
    m = {
        "approved": len(approved),
        "total": len(results),
        "needs_human": len(results) - len(approved),
        "avg_attempts": round(sum(r["attempts"] for r in results) / len(results), 2),
        "missed_violations": sum(len(r["missed"]) for r in results),
        "control_first_try": control["status"] == "approved" and control["attempts"] == 1,
        "total_cost": round(total, 3),
        "cost_per_approved": round(total / max(len(approved), 1), 3),
    }
    m["bar_met"] = (m["missed_violations"] <= BAR["missed_violations"]
                    and m["approved"] >= BAR["approved_min"]
                    and m["avg_attempts"] <= BAR["avg_attempts_max"]
                    and m["control_first_try"])

    out = ROOT / "results" / f"{args.name}.json"
    out.write_text(json.dumps({"metrics": m, "results": results}, indent=2))
    (ROOT / "results" / "report.html").write_text(report(args.name, m, results))
    print(json.dumps(m, indent=2))
    if total > COST_CAP:
        print(f"WARNING: run cost ${total:.2f} exceeded cap ${COST_CAP:.2f}")


def report(name, m, results):
    esc = html.escape
    tile = lambda label, val, ok: (
        f'<div class="tile {"ok" if ok else "bad"}"><span>{label}</span><b>{val}</b></div>')
    tiles = "".join([
        tile("Missed violations", m["missed_violations"], m["missed_violations"] == 0),
        tile("Approved", f'{m["approved"]}/{m["total"]}', m["approved"] >= BAR["approved_min"]),
        tile("Avg attempts", m["avg_attempts"], m["avg_attempts"] <= BAR["avg_attempts_max"]),
        tile("Control first try", "yes" if m["control_first_try"] else "no", m["control_first_try"]),
        tile("Cost / approved ad", f'${m["cost_per_approved"]:.3f}', True),
    ])
    rows = ""
    for r in results:
        ad = r["final_ad"]
        status = "missed" if r["missed"] else r["status"]
        rows += f"""<tr>
<td><code>{r['brief_id']}</code><div class="brief">{esc(r['brief'])}</div></td>
<td><span class="pill {status}">{status.replace('_', ' ')}</span></td>
<td class="num">{r['attempts']}</td>
<td><div class="ad"><b>{esc(ad['headline'])}</b><p>{esc(ad['body'])}</p><em>{esc(ad['cta'])}</em></div></td>
<td>{' '.join(f'<code>{c}</code>' for c in r['caught']) or '<span class="dim">-</span>'}</td>
<td>{' '.join(f'<code class="red">{c}</code>' for c in r['missed']) or '<span class="dim">-</span>'}</td>
<td class="num">${r['cost']:.3f}</td></tr>"""
    verdict = "Bar met" if m["bar_met"] else "Bar NOT met"
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ad Compliance Eval</title><style>
:root{{--bg:#fafaf9;--fg:#1c1917;--dim:#78716c;--card:#fff;--line:#e7e5e4;--ok:#15803d;--bad:#b91c1c;--warn:#a16207}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0c0a09;--fg:#f5f5f4;--dim:#a8a29e;--card:#1c1917;--line:#292524;--ok:#4ade80;--bad:#f87171;--warn:#facc15}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,system-ui,sans-serif;padding:32px 16px}}
main{{max-width:1150px;margin:auto}} h1{{margin:0 0 4px;font-size:24px}} .sub{{color:var(--dim);margin-bottom:24px}}
.verdict{{font-weight:600;color:{'var(--ok)' if m['bar_met'] else 'var(--bad)'}}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:28px}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;border-top:3px solid var(--ok)}}
.tile.bad{{border-top-color:var(--bad)}} .tile span{{color:var(--dim);font-size:13px;display:block}} .tile b{{font-size:26px}}
.wrap{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}}
table{{border-collapse:collapse;width:100%}} th,td{{text-align:left;padding:12px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--dim)}} .num{{text-align:right;font-variant-numeric:tabular-nums}}
.brief{{color:var(--dim);font-size:13px;max-width:220px}} .ad p{{margin:4px 0}} .ad em{{font-size:13px;color:var(--dim)}}
.pill{{padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600;white-space:nowrap}}
.approved{{background:color-mix(in srgb,var(--ok) 18%,transparent);color:var(--ok)}}
.needs_human{{background:color-mix(in srgb,var(--warn) 18%,transparent);color:var(--warn)}}
.missed{{background:color-mix(in srgb,var(--bad) 18%,transparent);color:var(--bad)}}
code{{font-size:12px;background:var(--line);padding:1px 5px;border-radius:4px}} code.red{{color:var(--bad)}} .dim{{color:var(--dim)}}
</style></head><body><main>
<h1>Northwell Rx ad compliance eval</h1>
<div class="sub">Run <code>{esc(name)}</code> · <span class="verdict">{verdict}</span> · bar: 0 missed · ≥8/10 approved · ≤2 avg attempts · control passes first try · total ${m['total_cost']:.2f}</div>
<div class="tiles">{tiles}</div>
<div class="wrap"><table><tr><th>Brief</th><th>Status</th><th>Tries</th><th>Final ad</th><th>Caught</th><th>Missed</th><th>Cost</th></tr>{rows}</table></div>
</main></body></html>"""


if __name__ == "__main__":
    main()

"""Before/after creative comparison: same briefs, old writer vs new creative writer.

    .venv/bin/python -m src.evaluation.creative_compare [BEFORE.json] [AFTER.json]
"""
import html
import json
import sys
from pathlib import Path

from src.evaluation.creative import CSS, render_ad

ROOT = Path(__file__).resolve().parents[2]
esc = lambda x: html.escape(str(x))


def diversity(rows):
    H = [r["final_ad"]["headline"] for r in rows]
    C = [r["final_ad"]["cta"] for r in rows]
    cr = [r.get("final_creative") or {} for r in rows]
    words = [set(r["final_ad"]["body"].lower().split()) for r in rows]
    pairs = [(i, j) for i in range(len(rows)) for j in range(i + 1, len(rows))]
    overlap = sum(len(words[i] & words[j]) / len(words[i] | words[j]) for i, j in pairs) / len(pairs)
    return {
        "Distinct headlines": f"{len(set(H))}/{len(rows)}",
        "Distinct CTAs": f"{len(set(C))}/3",
        "Visual layouts": len({c.get("visual", {}).get("layout") for c in cr} - {None}) or 1,
        "Creative angles": len({c.get("angle") for c in cr} - {None}) or "-",
        "Avg body word overlap": f"{overlap:.0%}",
        "Approved / missed": f'{sum(r["state"] == "APPROVED" for r in rows)}/{len(rows)} · {sum(len(r["missed"]) for r in rows)} missed',
    }


def main(args):
    before_p = Path(args[0]) if args else ROOT / "evals" / "before_creative.summary.json"
    after_p = Path(args[1]) if len(args) > 1 else ROOT / "runs" / "latest.summary.json"
    before, after = json.loads(before_p.read_text()), json.loads(after_p.read_text())
    briefs = {b["id"]: b["brief"] for b in json.loads((ROOT / "evals" / "briefs.json").read_text())}
    db, da = diversity(before["rows"]), diversity(after["rows"])
    metric_rows = "".join(f"<tr><td>{esc(k)}</td><td>{esc(db[k])}</td><td><b>{esc(da[k])}</b></td></tr>" for k in db)

    brow = {r["id"]: r for r in before["rows"]}
    slots = ""
    for r in after["rows"]:
        b = brow.get(r["id"])
        c = r.get("final_creative") or {}
        stamp = "approved" + (f" · attempt {r['attempts']}" if r["attempts"] > 1 else "")
        before_card = render_ad(b["final_ad"], None, "before") if b else ""
        slots += f"""<section class="slot"><div class="brief"><code>{esc(r['id'])}</code>
<p>&ldquo;{esc(briefs.get(r['id'], ''))[:160]}&rdquo;</p>
<dl><dt>Intent kept</dt><dd>{esc(c.get('intent', '–'))}</dd></dl></div>
<div class="b">{before_card}</div><div class="a">{render_ad(r['final_ad'], c, stamp)}</div></section>"""

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Creative Before/After</title><style>
:root{{--bg:#f4f3ef;--fg:#1a1a18;--dim:#73736d;--card:#fff;--line:#e3e2dc}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f0f0e;--fg:#f2f2ef;--dim:#a3a39c;--card:#1a1a18;--line:#2b2b28}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,system-ui,sans-serif;padding:40px 16px}}
main{{max-width:1180px;margin:auto}} h1{{margin:0;font-size:28px;letter-spacing:-.01em}} .sub{{color:var(--dim);margin:6px 0 24px}}
table{{border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;margin-bottom:36px}}
td,th{{padding:10px 18px;border-bottom:1px solid var(--line);text-align:left}} th{{font-size:12px;text-transform:uppercase;color:var(--dim);letter-spacing:.05em}}
.cols{{display:grid;grid-template-columns:220px 320px 320px;gap:24px;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim);font-weight:700;margin-bottom:10px}}
.slot{{display:grid;grid-template-columns:220px 320px 320px;gap:24px;align-items:start;padding:24px 0;border-top:1px solid var(--line)}}
.brief p{{font-style:italic;color:var(--dim);margin:8px 0}} .brief dl{{margin:0;font-size:13px}} .brief dt{{font-weight:700;margin-top:8px}} .brief dd{{margin:2px 0 0}}
code{{font:12px ui-monospace,Menlo,monospace;background:var(--line);padding:1px 6px;border-radius:5px}}
.b .fcard{{opacity:.8}}
@media (max-width:920px){{.slot,.cols{{grid-template-columns:1fr}} .cols{{display:none}} .fcard{{width:100%}}}}
{CSS}</style></head><body><main>
<h1>Creative before / after</h1>
<p class="sub">Same 12 briefs, same safety checks (policy <code>{esc(after['policy_version'])}</code> <code>{esc(after['policy_fingerprint'])}</code>),
real agents. Before: run <code>{esc(before['run_id'])}</code>, writer with rules only. After: run <code>{esc(after['run_id'])}</code>,
writer with creative direction, a concept per brief and a structured visual spec.</p>
<table><tr><th>Metric</th><th>Before</th><th>After</th></tr>{metric_rows}</table>
<div class="cols"><span>Brief</span><span>Before</span><span>After</span></div>
{slots}</main></body></html>"""
    out = ROOT / "reports" / "creative_before_after.html"
    out.write_text(page)
    print(f"report: {out.relative_to(ROOT)}")
    for k in db:
        print(f"  {k:<24} {db[k]!s:>16} → {da[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

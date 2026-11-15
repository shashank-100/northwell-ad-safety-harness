"""Renders a writer's visual spec as a feed ad. Each layout is a different composition, not a recolour.

Only the checked ad copy (headline/body/cta) and fixed, neutral UI strings appear in the artwork.
"""
import html

from src.agents.creative_spec import PALETTES

esc = lambda x: html.escape(str(x))

FONTS = {
    "serif": 'Georgia, "Iowan Old Style", serif',
    "grotesk": '"Helvetica Neue", Inter, Arial, sans-serif',
    "rounded": 'ui-rounded, "SF Pro Rounded", "Arial Rounded MT Bold", sans-serif',
    "handwritten": '"Bradley Hand", "Segoe Print", "Marker Felt", cursive',
    "mono": 'ui-monospace, Menlo, monospace',
}


def _poster(h, a, b, ink, f):
    return f"""<div class="v poster" style="background:{a};color:{ink};font-family:{f}">
<span class="bar" style="background:{b}"></span><h3>{esc(h)}</h3></div>"""


def _chat(h, a, b, ink, f):
    return f"""<div class="v chat" style="background:{a};font-family:{f}">
<div class="top" style="color:{ink}">Northwell Rx · Messages</div>
<p class="me" style="background:{b};color:{ink}">{esc(h)}</p>
<p class="them">Not weird at all. A licensed provider will review your history and reply.</p>
<p class="typing"><i></i><i></i><i></i></p></div>"""


def _steps(h, a, b, ink, f):
    steps = ["Online visit", "Provider review", "Plan, if it fits"]
    items = "".join(f'<li><b style="background:{b};color:{ink}">{i}</b>{s}</li>' for i, s in enumerate(steps, 1))
    return f"""<div class="v steps" style="background:{a};color:{ink};font-family:{f}">
<h3>{esc(h)}</h3><ol>{items}</ol></div>"""


def _note(h, a, b, ink, f):
    return f"""<div class="v note" style="background:{b}">
<div class="paper" style="background:{a};color:{ink};font-family:{FONTS['handwritten']}"><span class="tape"></span>{esc(h)}</div></div>"""


def _calendar(h, a, b, ink, f):
    days = "".join(f'<span class="d{" on" if i == 2 else ""}" style="{f"background:{b};color:{ink}" if i == 2 else ""}">'
                   f'<small>{d}</small>{"<em>visit</em>" if i == 2 else ""}</span>'
                   for i, d in enumerate("MON TUE WED THU FRI SAT SUN".split()))
    return f"""<div class="v calendar" style="background:{a};color:{ink};font-family:{f}">
<h3>{esc(h)}</h3><div class="week">{days}</div></div>"""


def _phone(h, a, b, ink, f):
    return f"""<div class="v phone" style="background:{b}">
<div class="device"><div class="screen" style="background:{a};color:{ink};font-family:{f}">
<small>Northwell Rx</small><h3>{esc(h)}</h3>
<div class="slot" style="border-color:{b}">Tonight · 8:30 pm</div><div class="slot" style="border-color:{b}">Tomorrow · 7:15 am</div>
<span class="btn" style="background:{ink};color:{a}">Book visit</span></div></div></div>"""


def _split(h, a, b, ink, f):
    return f"""<div class="v split" style="font-family:{f}">
<div class="l" style="background:#e9e9e6;color:#666"><small>The old way</small><b>Waiting room</b></div>
<div class="r" style="background:{a};color:{ink}"><small>Northwell Rx</small><b>{esc(h)}</b></div></div>"""


def _doorstep(h, a, b, ink, f):
    return f"""<div class="v doorstep" style="background:{a};color:{ink};font-family:{f}">
<svg viewBox="0 0 300 160" aria-hidden="true"><rect x="0" y="120" width="300" height="40" fill="{b}" opacity=".6"/>
<rect x="190" y="20" width="80" height="110" rx="4" fill="{ink}" opacity=".12"/><circle cx="257" cy="78" r="3" fill="{ink}" opacity=".4"/>
<rect x="110" y="86" width="64" height="40" rx="3" fill="{b}"/><path d="M110 98 h64" stroke="{ink}" stroke-opacity=".25"/>
<rect x="135" y="86" width="14" height="40" fill="{ink}" opacity=".12"/></svg>
<h3>{esc(h)}</h3><small>Plain, unbranded packaging</small></div>"""


LAYOUT_RENDER = {"poster": _poster, "chat": _chat, "steps": _steps, "note": _note, "calendar": _calendar,
                 "phone": _phone, "split": _split, "doorstep": _doorstep}


def render_ad(ad, creative, stamp="", rejected=False, marked_html=None):
    """A feed card: primary text (body) above the artwork, headline + CTA below, as on real social placements."""
    v = (creative or {}).get("visual") or {}
    a, b, ink = PALETTES.get(v.get("palette"), PALETTES["sage"])
    f = FONTS.get(v.get("typeface"), FONTS["grotesk"])
    art = LAYOUT_RENDER.get(v.get("layout"), _poster)(ad["headline"], a, b, ink, f)
    body = marked_html or esc(ad["body"])
    st = f'<span class="stamp {"no" if rejected else "yes"}">{esc(stamp)}</span>' if stamp else ""
    concept = ""
    if creative:
        concept = (f'<div class="concept"><b>{esc(creative.get("concept", ""))}</b> · {esc(creative.get("angle", ""))} · '
                   f'{esc(creative.get("hook", ""))} hook · {esc(v.get("layout", ""))}'
                   f'<i>{esc(v.get("art_direction", ""))}</i></div>')
    return f"""<figure class="fcard{' rejected' if rejected else ''}">
<header><span class="avatar">N</span><span><b>Northwell Rx</b><small>Sponsored</small></span>{st}</header>
<p class="primary">{body}</p>{art}
<footer><span><small>northwellrx.com</small><b>{esc(ad['headline'])}</b></span><span class="cta">{esc(ad['cta'])}</span></footer>
{concept}</figure>"""


CSS = """
.fcard{margin:0;width:320px;background:#fff;color:#111;border-radius:12px;overflow:hidden;border:1px solid #e6e6e6;
  box-shadow:0 1px 2px rgba(0,0,0,.06),0 10px 28px rgba(0,0,0,.07);font:14px/1.4 -apple-system,system-ui,sans-serif}
.fcard.rejected{border-color:#f0c4c4}
.fcard header{display:flex;align-items:center;gap:9px;padding:10px 12px;font-size:13px}
.fcard header small{display:block;color:#777;font-size:11px}
.fcard .avatar{width:30px;height:30px;border-radius:50%;background:#1f3d2c;color:#fff;display:grid;place-items:center;font-weight:700;flex:none}
.fcard .stamp{margin-left:auto;font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:99px;text-transform:uppercase;letter-spacing:.03em}
.fcard .stamp.yes{background:#e3f4e8;color:#17803d} .fcard .stamp.no{background:#fbe4e4;color:#b42323}
.fcard .primary{margin:0;padding:0 12px 10px;font-size:13.5px;color:#222}
.fcard .primary mark{background:#ffd9d9;color:#8f1414;border-radius:3px;padding:0 2px}
.fcard footer{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 12px;background:#f6f6f4;border-top:1px solid #ececec}
.fcard footer small{display:block;color:#888;font-size:11px;text-transform:uppercase} .fcard footer b{font-size:13.5px}
.fcard .cta{flex:none;background:#e8e8e5;color:#111;font-weight:600;font-size:12.5px;padding:7px 12px;border-radius:7px}
.fcard .concept{padding:9px 12px 12px;font-size:12px;color:#666;border-top:1px dashed #e4e4e4}
.fcard .concept i{display:block;margin-top:3px;color:#888}
.v{position:relative;aspect-ratio:1/1;overflow:hidden;display:flex}
.v h3{margin:0;letter-spacing:-.01em}
.poster{flex-direction:column;justify-content:flex-end;padding:26px}
.poster h3{font-size:38px;line-height:1.02;font-weight:800} .poster .bar{width:56px;height:8px;margin-bottom:16px;border-radius:4px}
.chat{flex-direction:column;justify-content:center;gap:10px;padding:22px}
.chat .top{font-size:11px;font-weight:600;text-align:center;opacity:.6;margin-bottom:6px}
.chat p{margin:0;max-width:80%;padding:10px 13px;border-radius:18px;font-size:15px}
.chat .me{align-self:flex-end;border-bottom-right-radius:5px;font-weight:600}
.chat .them{background:#fff;color:#222;border-bottom-left-radius:5px;font-size:13.5px}
.chat .typing{background:#fff;width:48px;display:flex;gap:4px;padding:12px}
.chat .typing i{width:6px;height:6px;border-radius:50%;background:#bbb}
.steps{flex-direction:column;justify-content:center;padding:26px;gap:18px}
.steps h3{font-size:26px;line-height:1.1;font-weight:700}
.steps ol{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.steps li{display:flex;align-items:center;gap:12px;background:rgba(255,255,255,.55);border-radius:10px;padding:10px 12px;font-weight:600;font-size:14px}
.steps li b{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-size:13px;flex:none}
.note{align-items:center;justify-content:center}
.note .paper{position:relative;width:74%;aspect-ratio:1/1;padding:30px 24px;font-size:27px;line-height:1.2;transform:rotate(-3deg);
  box-shadow:0 12px 24px rgba(0,0,0,.15);display:flex;align-items:center}
.note .tape{position:absolute;top:-10px;left:38%;width:70px;height:22px;background:rgba(255,255,255,.6);transform:rotate(4deg)}
.calendar{flex-direction:column;justify-content:center;gap:18px;padding:24px}
.calendar h3{font-size:28px;line-height:1.08;font-weight:700}
.calendar .week{display:grid;grid-template-columns:repeat(7,1fr);gap:5px}
.calendar .d{aspect-ratio:3/4;border-radius:7px;background:rgba(255,255,255,.5);display:flex;flex-direction:column;justify-content:space-between;padding:5px;font-size:9px}
.calendar .d.on{transform:scale(1.12);box-shadow:0 6px 14px rgba(0,0,0,.15)} .calendar .d em{font-style:normal;font-weight:700;font-size:9.5px}
.phone{align-items:center;justify-content:center}
.phone .device{width:58%;aspect-ratio:9/17;background:#111;border-radius:26px;padding:7px;box-shadow:0 16px 30px rgba(0,0,0,.25)}
.phone .screen{height:100%;border-radius:20px;padding:18px 13px;display:flex;flex-direction:column;gap:8px}
.phone .screen small{font-size:10px;font-weight:700;opacity:.6} .phone h3{font-size:17px;line-height:1.15;font-weight:700;margin-bottom:6px}
.phone .slot{border:1.5px solid;border-radius:9px;padding:7px 8px;font-size:11px;font-weight:600;background:rgba(255,255,255,.5)}
.phone .btn{margin-top:auto;text-align:center;border-radius:9px;padding:8px;font-size:12px;font-weight:700}
.split .l,.split .r{flex:1;display:flex;flex-direction:column;justify-content:flex-end;padding:20px;gap:6px}
.split small{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;font-weight:700;opacity:.7}
.split .l b{font-size:20px;text-decoration:line-through;opacity:.7} .split .r b{font-size:22px;line-height:1.1}
.doorstep{flex-direction:column;justify-content:flex-end;padding:22px;gap:4px}
.doorstep svg{position:absolute;inset:8% 0 auto 0;width:100%}
.doorstep h3{position:relative;font-size:26px;line-height:1.1;font-weight:700} .doorstep small{position:relative;opacity:.7;font-size:12px}
"""

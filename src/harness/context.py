"""Builds each agent's input. Isolation: neither agent sees the other's prompt or reasoning.

Untrusted text (the brief, and model-written ad copy) is escaped so it can never close or
open a delimiter tag: every < and > becomes a harmless entity before wrapping.
"""
import json


def escape(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _ad_block(ad):
    return "<ad>\n" + escape(json.dumps(ad, indent=2, ensure_ascii=False)) + "\n</ad>"


def writer_context(brief, previous_ad=None, violations=None):
    msg = f"<brief>\n{escape(brief)}\n</brief>"
    if previous_ad is not None:
        fixes = [{"rule_id": v["rule_id"], "quote": v.get("quote", ""),
                  "fix": v.get("suggested_fix") or v.get("explanation", "")} for v in violations]
        msg += (f"\n\nYour previous ad:\n{_ad_block(previous_ad)}"
                f"\n\nIt was rejected. Fix exactly these violations:\n<violations>\n"
                f"{escape(json.dumps(fixes, indent=2, ensure_ascii=False))}\n</violations>")
    return msg


def reviewer_context(brief, ad, visual=None):
    msg = f"<brief>\n{escape(brief)}\n</brief>\n\nGenerated ad:\n{_ad_block(ad)}"
    if visual:
        msg += ("\n\nPlanned visual:\n<visual>\n"
                + escape(json.dumps(visual, indent=2, ensure_ascii=False)) + "\n</visual>")
    return msg

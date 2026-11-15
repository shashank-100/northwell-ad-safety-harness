"""Creative vocabulary the writer chooses from. Visual concepts are structured so they render deterministically.

This is creative direction, not policy: nothing here can loosen a safety check.
"""
LAYOUTS = {
    "poster": "Oversized headline as the whole image. Bold, typographic, almost no decoration.",
    "chat": "A text-message exchange with a provider. The headline is the patient's message; the reply sets up the body.",
    "steps": "Three numbered steps showing how care works (visit, provider review, plan). Process, not outcomes.",
    "note": "A handwritten sticky note or journal page. Personal, warm, first-person.",
    "calendar": "A week view or routine planner. Fitting care into a real schedule.",
    "phone": "An app screen mockup: booking, messaging, or a refill reminder.",
    "split": "Two-panel contrast of situations (old way vs. new way of getting care). Never bodies, never before/after.",
    "doorstep": "Discreet package on a doorstep or mailbox. Privacy and convenience.",
}
PALETTES = {
    "sage": ("#e3ece4", "#b7cfbd", "#1f3d2c"),
    "navy": ("#1d2b45", "#33476b", "#f4f1ea"),
    "terracotta": ("#f3e1d6", "#d99a7b", "#4a2414"),
    "sand": ("#f5efe3", "#e3d3b3", "#3c3122"),
    "plum": ("#3b2340", "#6b4374", "#f7eef8"),
    "charcoal": ("#1e1e1e", "#3a3a3a", "#f2f2ef"),
    "citrus": ("#fff4d6", "#ffd36b", "#3a2c00"),
    "sky": ("#e4f0fb", "#a9cdee", "#12324f"),
}
TYPEFACES = ("serif", "grotesk", "rounded", "handwritten", "mono")
ANGLES = ("convenience", "privacy", "expert guidance", "transparency", "routine", "myth-busting",
          "empathy", "momentum", "access", "confidence", "seasonal moment")
HOOKS = ("question", "contrast", "scenario", "permission", "curiosity", "direct address", "reframe", "list")

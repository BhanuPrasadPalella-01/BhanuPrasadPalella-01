#!/usr/bin/env python3
"""Draws the profile artwork (room, project cards, section heads, toolkit, sign-off)
in light and dark, with the portfolio's own fonts embedded as subsets.

    python3 build/make.py        # needs: pip install fonttools brotli
"""
import base64
import io
import math
import os
from functools import lru_cache

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "build", "fonts")
OUT = os.path.join(ROOT, "assets")
SITE = "https://bhanuprasadpalella.vercel.app"

# Same tokens as the portfolio's globals.css, plus a few room materials.
THEMES = {
    "light": dict(
        bg="#f4f0e8", surface="#ece6da", border="#dcd4c4", ink="#16181d", soft="#5a5e67",
        accent="#8a5c2c", accentSoft="#e6cfae", bronze="#b5844f",
        wall="#ece6da", side="#e4dccc", floor="#ddd4c2", ceil="#f0ebe2",
        board="#fbf9f4", screen="#16181d", sky="#f3e2c4", sun="#e2ad72", tile="#16181d", glow=0.22,
    ),
    "dark": dict(
        bg="#101114", surface="#191a1f", border="#2a2b31", ink="#ede7db", soft="#9b9ca5",
        accent="#d39b5f", accentSoft="#6b4a28", bronze="#b5844f",
        wall="#18191e", side="#141519", floor="#1d1e23", ceil="#131417",
        board="#22232a", screen="#08090b", sky="#182032", sun="#ede7db", tile="none", glow=0.32,
    ),
}

FAMILIES = {
    # css class: (file, family name, italic)
    "serif": ("Fraunces.woff2", "BP Fraunces", False),
    "serifi": ("Fraunces-Italic.woff2", "BP Fraunces Italic", True),
    "sans": ("Inter.woff2", "BP Inter", False),
    "mono": ("JetBrainsMono.woff2", "BP Mono", False),
}


# ---------------------------------------------------------------- type tools

@lru_cache(maxsize=None)
def metrics(fam, weight):
    font = TTFont(os.path.join(FONT_DIR, FAMILIES[fam][0]))
    loc = {"wght": weight}
    if any(a.axisTag == "opsz" for a in font["fvar"].axes):
        loc["opsz"] = 72
    static = instancer.instantiateVariableFont(font, loc)
    return static.getBestCmap(), static["hmtx"], static["head"].unitsPerEm


def measure(fam, text, size, weight=400, ls=0):
    cmap, hmtx, upm = metrics(fam, weight)
    w = 0
    for ch in text:
        g = cmap.get(ord(ch))
        w += (hmtx[g][0] if g else upm * 0.6) / upm * size
    return w + ls * len(text)


def wrap(fam, text, size, width, weight=400):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and measure(fam, trial, size, weight) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line] if line else lines


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Doc:
    def __init__(self, w, h, c, label):
        self.w, self.h, self.c, self.label = w, h, c, label
        self.parts, self.used = [], {k: set() for k in FAMILIES}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, spans, size, fam="sans", fill=None, weight=400, anchor="start", ls=0, extra=""):
        """spans: a string, or a list of (text, fam, fill) for mixed runs."""
        if isinstance(spans, str):
            spans = [(spans, fam, fill or self.c["ink"])]
        inner = ""
        for t, f, col in spans:
            self.used[f].update(t)
            inner += f'<tspan class="{f}" fill="{col}">{esc(t)}</tspan>'
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}" letter-spacing="{ls}" {extra}>{inner}</text>'
        )

    def fonts(self):
        css = []
        for fam, chars in self.used.items():
            if not chars:
                continue
            file, name, italic = FAMILIES[fam]
            font = TTFont(os.path.join(FONT_DIR, file))
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga", "calt"]
            opts.name_IDs = []
            sub = subset.Subsetter(opts)
            sub.populate(text="".join(sorted(chars)))
            sub.subset(font)
            buf = io.BytesIO()
            font.flavor = "woff2"
            font.save(buf)
            data = base64.b64encode(buf.getvalue()).decode()
            css.append(
                f"@font-face{{font-family:'{name}';src:url(data:font/woff2;base64,{data}) format('woff2');"
                f"font-weight:100 900;font-style:{'italic' if italic else 'normal'};}}"
                f".{fam}{{font-family:'{name}',{'Georgia,serif' if 'serif' in fam else 'monospace' if fam == 'mono' else 'Helvetica,Arial,sans-serif'};"
                f"{'font-style:italic;' if italic else ''}}}"
            )
        return "".join(css)

    def svg(self):
        body = "\n".join(self.parts)
        style = (
            self.fonts()
            + "text{font-optical-sizing:auto;}"
            + ".o *{vector-effect:non-scaling-stroke;stroke-linecap:round;stroke-linejoin:round;}"
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{esc(self.label)}">\n'
            f"<style>{style}</style>\n{body}\n</svg>\n"
        )


def arrow(x, y, color, size=14, width=1.6):
    """A drawn → (the latin font subsets have no arrow glyph)."""
    h = size * 0.32
    return (
        f'<path d="M{x - size:.1f} {y:.1f} H{x:.1f} M{x - h:.1f} {y - h:.1f} L{x:.1f} {y:.1f} L{x - h:.1f} {y + h:.1f}" '
        f'fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def logo(x, y, scale, c):
    tile = "" if c["tile"] == "none" else f'<rect width="120" height="120" rx="28" fill="{c["tile"]}"/>'
    return (
        f'<g transform="translate({x} {y}) scale({scale})">{tile}'
        f'<text x="60" y="71" text-anchor="middle" dominant-baseline="middle" class="serifi" font-weight="500" '
        f'font-size="60" letter-spacing="-1" fill="#f4f0e8">bp</text>'
        f'<circle cx="96" cy="86" r="6" fill="#B5844F"/></g>'
    )


# ------------------------------------------------- the room's objects (0..100 box)

def stroke(c, w=1.6):
    return f'stroke="{c["ink"]}" stroke-width="{w}"'


def laptop(c):
    lines = "".join(
        f'<rect x="{26 + i % 2 * 6}" y="{30 + i * 7}" width="{[30, 18, 26, 12][i]}" height="2.6" rx="1.3" '
        f'fill="{[c["bronze"], "#9b9ca5", "#9b9ca5", c["bronze"]][i]}"/>'
        for i in range(4)
    )
    return (
        f'<rect x="16" y="18" width="68" height="50" rx="4" fill="{c["surface"]}" {stroke(c)}/>'
        f'<rect x="21" y="23" width="58" height="40" rx="2" fill="{c["screen"]}"/>{lines}'
        f'<rect x="46" y="51" width="4" height="7" fill="#f4f0e8"><animate attributeName="opacity" values="1;0;1" dur="1.1s" repeatCount="indefinite"/></rect>'
        f'<path d="M6 70 H94 L88 80 H12 Z" fill="{c["surface"]}" {stroke(c)}/>'
    )


def helix(c):
    steps, ys = 12, [8 + i * 3 for i in range(27)]

    def strand(phase, sign):
        return "M" + " L".join(f"{50 + sign * 15 * math.sin(y / 9 + phase):.1f} {y}" for y in ys)

    phases = [i * 2 * math.pi / steps for i in range(steps + 1)]
    a = ";".join(strand(p, 1) for p in phases)
    b = ";".join(strand(p, -1) for p in phases)
    rungs = ""
    for y in range(11, 86, 8):
        x1 = ";".join(f"{50 + 15 * math.sin(y / 9 + p):.1f}" for p in phases)
        x2 = ";".join(f"{50 - 15 * math.sin(y / 9 + p):.1f}" for p in phases)
        rungs += (
            f'<line y1="{y}" y2="{y}" stroke="{c["soft"]}" stroke-width="1">'
            f'<animate attributeName="x1" values="{x1}" dur="9s" repeatCount="indefinite"/>'
            f'<animate attributeName="x2" values="{x2}" dur="9s" repeatCount="indefinite"/></line>'
        )
    return (
        rungs
        + f'<path fill="none" stroke="{c["ink"]}" stroke-width="1.8"><animate attributeName="d" values="{b}" dur="9s" repeatCount="indefinite"/></path>'
        + f'<path fill="none" stroke="{c["accent"]}" stroke-width="2.4"><animate attributeName="d" values="{a}" dur="9s" repeatCount="indefinite"/></path>'
        + f'<rect x="32" y="88" width="36" height="8" rx="2" fill="{c["surface"]}" {stroke(c)}/>'
    )


def robot(c):
    eye = lambda cx: (
        f'<ellipse cx="{cx}" cy="31" rx="4" ry="4.5" fill="{c["accent"]}">'
        f'<animate attributeName="ry" values="4.5;4.5;0.6;4.5" keyTimes="0;0.9;0.95;1" dur="4s" repeatCount="indefinite"/></ellipse>'
    )
    return (
        f'<line x1="50" y1="16" x2="50" y2="7" {stroke(c)}/>'
        f'<circle cx="50" cy="5" r="3" fill="{c["accent"]}"><animate attributeName="opacity" values="1;0.3;1" dur="1.6s" repeatCount="indefinite"/></circle>'
        f'<rect x="28" y="16" width="44" height="30" rx="9" fill="{c["surface"]}" {stroke(c)}/>'
        f'<rect x="34" y="22" width="32" height="18" rx="6" fill="{c["screen"]}"/>{eye(43)}{eye(57)}'
        f'<rect x="45" y="46" width="10" height="4" fill="{c["surface"]}" {stroke(c)}/>'
        f'<rect x="24" y="50" width="52" height="30" rx="8" fill="{c["surface"]}" {stroke(c)}/>'
        f'<circle cx="50" cy="63" r="5" fill="none" stroke="{c["accent"]}" stroke-width="1.6"/>'
        f'<rect x="20" y="81" width="60" height="15" rx="7.5" fill="{c["surface"]}" {stroke(c)}/>'
        + "".join(f'<circle cx="{x}" cy="88.5" r="3.6" fill="none" {stroke(c, 1.2)}/>' for x in (30, 50, 70))
    )


def arena(c):
    track = "M20 60 a30 16 0 1 0 60 0 a30 16 0 1 0 -60 0"
    bots = "".join(
        f'<circle r="3.6" fill="{col}"><animateMotion path="{track}" dur="7s" begin="{-i * 7 / 3:.2f}s" repeatCount="indefinite"/></circle>'
        for i, col in enumerate((c["accent"], c["ink"], c["accent"]))
    )
    return (
        f'<ellipse cx="50" cy="60" rx="46" ry="26" fill="{c["surface"]}" {stroke(c)}/>'
        f'<path d="{track}" fill="none" stroke="{c["soft"]}" stroke-width="1" stroke-dasharray="2 4"/>'
        f'<circle cx="50" cy="60" r="2" fill="{c["soft"]}"/>{bots}'
    )


def corkboard(c):
    pins = [(22, 32), (38, 60), (58, 36), (78, 64)]
    path = "M" + " L".join(f"{x} {y}" for x, y in pins)
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="1.3" fill="{c["soft"]}"/>' for x, y in
                   [(30, 46), (48, 26), (66, 52), (28, 70), (70, 26), (52, 70), (84, 40)])
    return (
        f'<rect x="8" y="14" width="84" height="66" rx="3" fill="{c["accentSoft"]}" {stroke(c)}/>'
        f'<rect x="60" y="20" width="22" height="16" fill="{c["board"]}" {stroke(c, 1)} transform="rotate(-6 71 28)"/>'
        f'{dots}<path d="{path}" fill="none" stroke="{c["accent"]}" stroke-width="1.6" stroke-dasharray="3 3"/>'
        + "".join(f'<circle cx="{x}" cy="{y}" r="3.4" fill="{c["accent"]}" {stroke(c, 1)}/>' for x, y in pins)
    )


def radio(c):
    arcs = "".join(
        f'<path d="M{91 + i * 4} {1 - i * 3} Q{97 + i * 6} 6 {91 + i * 4} {11 + i * 3}" fill="none" stroke="{c["accent"]}" stroke-width="1.4" opacity="0">'
        f'<animate attributeName="opacity" values="0;1;0" dur="2.4s" begin="{i * 0.4}s" repeatCount="indefinite"/></path>'
        for i in range(3)
    )
    grille = "".join(f'<line x1="50" y1="{y}" x2="82" y2="{y}" stroke="{c["soft"]}" stroke-width="1.2"/>' for y in range(54, 80, 6))
    return (
        f'<line x1="70" y1="42" x2="88" y2="8" {stroke(c)}/><circle cx="88" cy="6" r="2.4" fill="{c["ink"]}"/>{arcs}'
        f'<rect x="8" y="42" width="84" height="44" rx="8" fill="{c["surface"]}" {stroke(c)}/>'
        f'<circle cx="28" cy="64" r="12" fill="{c["bg"]}" {stroke(c)}/>'
        f'<line x1="28" y1="64" x2="33" y2="55" stroke="{c["accent"]}" stroke-width="2"/>{grille}'
    )


def whiteboard(c, legs=True):
    nodes = [(22, 30), (40, 22), (36, 50), (58, 38), (76, 24), (72, 58), (52, 62)]
    edges = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (3, 5), (5, 6), (2, 6), (4, 5)]
    e = "".join(
        f'<line x1="{nodes[a][0]}" y1="{nodes[a][1]}" x2="{nodes[b][0]}" y2="{nodes[b][1]}" stroke="{c["soft"]}" stroke-width="1.1"/>'
        for a, b in edges
    )
    n = "".join(
        f'<circle cx="{x}" cy="{y}" r="3.4" fill="{c["accent"] if i in (3, 5) else c["ink"]}"/>' for i, (x, y) in enumerate(nodes)
    )
    l = f'<line x1="20" y1="76" x2="13" y2="98" {stroke(c)}/><line x1="80" y1="76" x2="87" y2="98" {stroke(c)}/>' if legs else ""
    return l + f'<rect x="6" y="12" width="88" height="62" rx="3" fill="{c["board"]}" {stroke(c)}/>{e}{n}' \
        f'<line x1="24" y1="78" x2="76" y2="78" {stroke(c, 2)}/>'


def inbox(c):
    trays = ""
    for i in range(3):
        y = 30 + i * 22
        if i == 0:
            trays += (
                f'<rect x="24" y="16" width="48" height="20" fill="{c["board"]}" {stroke(c, 1)} transform="rotate(-5 48 26)"/>'
                f'<line x1="30" y1="22" x2="56" y2="20" stroke="{c["soft"]}" stroke-width="1"/>'
                f'<rect x="64" y="10" width="12" height="12" rx="2" fill="{c["accent"]}"/>'
            )
        trays += f'<path d="M10 {y} H90 L84 {y + 16} H16 Z" fill="{c["surface"]}" {stroke(c)}/>'
    return trays


def fractal(c):
    tris = []

    def sier(a, b, d, depth):
        if depth == 0:
            tris.append(f"M{a[0]:.1f} {a[1]:.1f} L{b[0]:.1f} {b[1]:.1f} L{d[0]:.1f} {d[1]:.1f} Z")
            return
        ab = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        bd = ((b[0] + d[0]) / 2, (b[1] + d[1]) / 2)
        ad = ((a[0] + d[0]) / 2, (a[1] + d[1]) / 2)
        sier(a, ab, ad, depth - 1)
        sier(ab, b, bd, depth - 1)
        sier(ad, bd, d, depth - 1)

    sier((24, 76), (76, 76), (50, 26), 3)
    return (
        f'<rect x="10" y="6" width="80" height="88" rx="2" fill="{c["surface"]}" {stroke(c)}/>'
        f'<rect x="18" y="14" width="64" height="72" fill="{c["board"]}" stroke="{c["soft"]}" stroke-width="0.8"/>'
        f'<path d="{" ".join(tris)}" fill="{c["accent"]}"/>'
    )


def room(c):
    return (
        f'<rect x="8" y="8" width="84" height="84" rx="6" fill="{c["side"]}" {stroke(c)}/>'
        f'<path d="M30 28 L8 8 M70 28 L92 8 M30 64 L8 92 M70 64 L92 92" {stroke(c, 1.2)}/>'
        f'<rect x="30" y="28" width="40" height="36" fill="{c["wall"]}" {stroke(c)}/>'
        f'<rect x="36" y="34" width="14" height="12" fill="{c["sky"]}" {stroke(c, 1.1)}/>'
        f'<path d="M43 34 V46 M36 40 H50" {stroke(c, 0.9)}/>'
        f'<path d="M52 52 H66" {stroke(c, 1.4)}/>'
        f'<circle cx="50" cy="78" r="3.4" fill="{c["bronze"]}"><animate attributeName="r" values="3.4;4.6;3.4" dur="2.4s" repeatCount="indefinite"/></circle>'
    )


def place(fn, x, y, s, c, **kw):
    return f'<g class="o" transform="translate({x} {y}) scale({s})">{fn(c, **kw)}</g>'


# ------------------------------------------------------------------ projects

PROJECTS = [
    dict(slug="vaultsphere", n="01", obj="The laptop", fn=laptop, title="VaultSphere", status="Live",
         sub="Secure project vault & collaboration platform", stat="12+", label="Backend routes",
         tech="React · Node.js · MongoDB · JWT", href="https://vaultsphere.online"),
    dict(slug="protein-structure", n="02", obj="The helix sculpture", fn=helix, title="Protein Structure AI", status="Live",
         sub="Secondary structure prediction with attention-augmented BiLSTMs", stat="80.09%", label="Q3 accuracy",
         tech="PyTorch · FastAPI · React · Three.js", href="https://protein-secondary-structure-fronten.vercel.app"),
    dict(slug="rescuebot", n="03", obj="The robot", fn=robot, title="RescueBot", status="Hardware",
         sub="Intelligent swarm robotics for disaster response", stat="80ms", label="Control loop",
         tech="ESP32 · C++ · Sensor fusion · Web UI"),
    dict(slug="swarmbot", n="04", obj="The swarm arena", fn=arena, title="SwarmBot", status="Live demo",
         sub="Fault-tolerant multi-robot mapping simulation", stat="3", label="Robots · 3 formations",
         tech="JavaScript · Canvas · Boids · ESP-NOW"),
    dict(slug="adaptive-pso", n="05", obj="The corkboard", fn=corkboard, title="Adaptive PSO Rescue", status="In review",
         sub="Particle swarm optimisation for multi-robot search & rescue", stat="150", label="PSO iterations",
         tech="MATLAB · PSO · Path planning"),
    dict(slug="mission-aware-sdr", n="06", obj="The software radio", fn=radio, title="Mission-Aware SDR", status="Research",
         sub="Continual-learning packet scheduler for emergency networks", stat="6", label="Traffic types",
         tech="GNU Radio · Python · HackRF · Online ML"),
    dict(slug="gnn-rl-scheduling", n="07", obj="The whiteboard", fn=whiteboard, title="GNN-RL Scheduling", status="Research",
         sub="Correlation-aware sensor scheduling on real sensor networks", stat="325", label="Real sensors scheduled live",
         tech="PyTorch · PPO · GNNs · Kalman filters"),
    dict(slug="complaint-intelligence", n="08", obj="The inbox tray", fn=inbox, title="Complaint Intelligence", status="ML system",
         sub="AI-based complaint analysis & decision support", stat="4", label="Priority levels",
         tech="Python · TF-IDF · SVM · Streamlit"),
    dict(slug="fractallab-flockhunt", n="09", obj="The fractal print", fn=fractal, title="FractalLab & FlockHunt", status="Complete",
         sub="Fractal explorer and boids predator game", stat="280", label="Boids at 60 fps",
         tech="Java 17 · Swing · Canvas · Web Audio"),
    dict(slug="", n="10", obj="The room itself", fn=room, title="This Portfolio", status="Live",
         sub="A 3D room you can walk through — every object opens a project", stat="2.7 MB", label="3D assets, down from 20 MB",
         tech="Next.js · Three.js · R3F · GSAP", href=SITE),
]


def card(p, c):
    d = Doc(600, 330, c, f'{p["n"]} — {p["obj"]}: {p["title"]}. {p["sub"]}.')
    d.add(f'<rect x="0.75" y="0.75" width="598.5" height="328.5" rx="18" fill="{c["surface"]}" stroke="{c["border"]}" stroke-width="1.5"/>')
    d.text(32, 46, f'{p["n"]} — {p["obj"].upper()}', 11.5, "mono", c["accent"], 500, ls=1.8)
    sw = measure("mono", p["status"].upper(), 11, 500, 1.6)
    d.add(f'<circle cx="{568 - sw - 10:.1f}" cy="42" r="3.4" fill="{c["accent"] if p["status"].startswith("Live") else c["soft"]}"/>')
    d.text(568, 46, p["status"].upper(), 11, "mono", c["soft"], 500, anchor="end", ls=1.6)
    d.add(place(p["fn"], 432, 64, 1.36, c))
    title_size = 38 if measure("serif", p["title"], 38, 420) < 380 else 32
    d.text(32, 104, p["title"], title_size, "serif", c["ink"], 420)
    for i, line in enumerate(wrap("sans", p["sub"], 15.5, 360)[:2]):
        d.text(32, 136 + i * 22, line, 15.5, "sans", c["soft"])
    d.text(32, 240, p["stat"], 50, "serifi", c["accent"], 400)
    d.text(32, 264, p["label"].upper(), 10.5, "mono", c["soft"], 500, ls=1.6)
    d.add(f'<line x1="32" y1="286" x2="568" y2="286" stroke="{c["border"]}" stroke-width="1.2"/>')
    d.text(32, 311, p["tech"], 11.5, "mono", c["soft"])
    d.text(546, 311, "OPEN", 11, "mono", c["ink"], 600, anchor="end", ls=1.6)
    d.add(arrow(568, 307, c["accent"], 13))
    return d


# ---------------------------------------------------------------------- hero

def hero(c):
    d = Doc(1200, 580, c, "Bhanu Prasad Palella — Every object in this room is a project. Full-stack developer and AI & Data Science student.")
    d.add(logo(72, 40, 0.48, c))
    d.text(148, 63, "BHANU PRASAD PALELLA", 12, "mono", c["ink"], 600, ls=2.6)
    d.text(148, 84, "FULL-STACK · AI / ML · ROBOTICS", 12, "mono", c["accent"], 500, ls=2.6)

    d.text(70, 214, "Every object", 70, "serif", weight=380, ls=-1.2)
    d.text(70, 290, "in this room", 70, "serif", weight=380, ls=-1.2)
    d.text(70, 366, [("is a ", "serif", c["ink"]), ("project.", "serifi", c["accent"])], 70, weight=380, ls=-1.2)

    d.text(72, 420, "Full-stack developer & AI / Data Science student at Amrita.", 18, "sans", c["soft"])
    d.text(72, 447, "I ship web apps, train deep-learning models and build robots.", 18, "sans", c["soft"])

    d.text(72, 506, "WALK THROUGH IT", 12, "mono", c["ink"], 600, ls=2.4)
    d.add(arrow(244, 502, c["accent"], 22))
    d.text(258, 506, "BHANUPRASADPALELLA.VERCEL.APP", 12, "mono", c["accent"], 500, ls=2.4)
    d.add(f'<line x1="258" y1="516" x2="{258 + measure("mono", "BHANUPRASADPALELLA.VERCEL.APP", 12, 500, 2.4):.0f}" y2="516" stroke="{c["accent"]}" stroke-width="1" opacity="0.5"/>')

    # The room, in one-point perspective.
    L, R, T, B = 680, 1150, 40, 540
    bl, br, bt, bb = 740, 1090, 95, 395
    vp = ((bl + br) / 2, (bt + bb) / 2)
    d.add(f'<defs><clipPath id="frame"><rect x="{L}" y="{T}" width="{R - L}" height="{B - T}" rx="18"/></clipPath>'
          f'<radialGradient id="lamp" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{c["bronze"]}" stop-opacity="{c["glow"]}"/>'
          f'<stop offset="1" stop-color="{c["bronze"]}" stop-opacity="0"/></radialGradient>'
          f'<linearGradient id="cone" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["bronze"]}" stop-opacity="{c["glow"] * 0.9:.2f}"/>'
          f'<stop offset="1" stop-color="{c["bronze"]}" stop-opacity="0"/></linearGradient></defs>')
    d.add('<g clip-path="url(#frame)">')
    d.add(f'<polygon points="{L},{T} {R},{T} {br},{bt} {bl},{bt}" fill="{c["ceil"]}"/>')
    d.add(f'<polygon points="{L},{T} {bl},{bt} {bl},{bb} {L},{B}" fill="{c["side"]}"/>')
    d.add(f'<polygon points="{R},{T} {br},{bt} {br},{bb} {R},{B}" fill="{c["side"]}"/>')
    d.add(f'<polygon points="{bl},{bb} {br},{bb} {R},{B} {L},{B}" fill="{c["floor"]}"/>')
    d.add(f'<rect x="{bl}" y="{bt}" width="{br - bl}" height="{bb - bt}" fill="{c["wall"]}"/>')
    for x in range(bl + 35, br, 35):
        xb = vp[0] + (x - vp[0]) * (B - vp[1]) / (bb - vp[1])
        d.add(f'<line x1="{x}" y1="{bb}" x2="{xb:.1f}" y2="{B}" stroke="{c["ink"]}" stroke-width="0.8" opacity="0.12"/>')
    d.add(f'<path d="M{L} {T} L{bl} {bt} M{R} {T} L{br} {bt} M{L} {B} L{bl} {bb} M{R} {B} L{br} {bb}" stroke="{c["ink"]}" stroke-width="1.1" opacity="0.45"/>')
    d.add(f'<rect x="{bl}" y="{bt}" width="{br - bl}" height="{bb - bt}" fill="none" stroke="{c["ink"]}" stroke-width="1.1" opacity="0.45"/>')

    # Window — cracked, with the shards still falling (the site opens by flying through it).
    wx, wy, ww, wh = 770, 118, 110, 104
    ix, iy = 848, 152
    sky = f'<rect x="{wx}" y="{wy}" width="{ww}" height="{wh}" fill="{c["sky"]}"/>'
    if c["tile"] == "none":
        sky += f'<circle cx="806" cy="146" r="10" fill="{c["sun"]}"/><circle cx="811" cy="142" r="9" fill="{c["sky"]}"/>' + "".join(
            f'<circle cx="{x}" cy="{y}" r="1" fill="{c["sun"]}"/>' for x, y in [(790, 200), (832, 132), (866, 196), (860, 128)])
    else:
        sky += f'<circle cx="806" cy="150" r="13" fill="{c["sun"]}" opacity="0.8"/>'
    cracks = "".join(
        f'<line x1="{ix}" y1="{iy}" x2="{ix + math.cos(a) * r:.1f}" y2="{iy + math.sin(a) * r:.1f}" stroke="{c["ink"]}" stroke-width="0.9" opacity="0.6"/>'
        for a, r in [(0.2, 40), (1.1, 60), (1.9, 52), (2.7, 70), (3.5, 50), (4.4, 38), (5.3, 42)]
    )
    ring = f'<circle cx="{ix}" cy="{iy}" r="9" fill="none" stroke="{c["ink"]}" stroke-width="0.8" opacity="0.5"/>'
    shards = "".join(
        f'<polygon points="0,0 {6 + i},{2} {2},{7 + i}" fill="{c["board"]}" stroke="{c["ink"]}" stroke-width="0.7">'
        f'<animateTransform attributeName="transform" type="translate" values="{ix - 4 + i * 5},{iy + i * 4}; {ix - 30 + i * 9},{iy + 150 + i * 20}" dur="{3.6 + i * 0.5}s" begin="{i * 0.9}s" repeatCount="indefinite"/>'
        f'<animate attributeName="opacity" values="0.9;0" dur="{3.6 + i * 0.5}s" begin="{i * 0.9}s" repeatCount="indefinite"/></polygon>'
        for i in range(3)
    )
    d.add(f'<g clip-path="url(#win)"><clipPath id="win"><rect x="{wx}" y="{wy}" width="{ww}" height="{wh}"/></clipPath>{sky}{cracks}{ring}</g>')
    d.add(f'<rect x="{wx}" y="{wy}" width="{ww}" height="{wh}" fill="none" stroke="{c["ink"]}" stroke-width="1.6"/>'
          f'<path d="M{wx + ww / 2} {wy} V{wy + wh} M{wx} {wy + wh / 2} H{wx + ww}" stroke="{c["ink"]}" stroke-width="1.2"/>'
          f'<rect x="{wx - 6}" y="{wy + wh}" width="{ww + 12}" height="5" rx="1.5" fill="{c["surface"]}" stroke="{c["ink"]}" stroke-width="1.2"/>')

    # Wall pieces.
    d.add(place(fractal, 898, 116, 0.62, c))
    d.add(place(whiteboard, 978, 110, 0.98, c, legs=False))
    d.add(place(corkboard, 896, 190, 0.6, c))
    d.add(f'<path d="M1010 290 H1086 M1022 290 V298 M1074 290 V298" stroke="{c["ink"]}" stroke-width="1.6" stroke-linecap="round"/>')
    d.add(place(radio, 1016, 290 - 0.62 * 86, 0.62, c))

    # Lamp light sits behind the desk things.
    d.add(f'<circle cx="988" cy="300" r="78" fill="url(#lamp)"><animate attributeName="opacity" values="0.75;1;0.75" dur="4s" repeatCount="indefinite"/></circle>')
    d.add(f'<polygon points="979,270 1001,270 1022,343 952,343" fill="url(#cone)"/>')

    # Desk.
    d.add(f'<g class="o"><rect x="762" y="352" width="7" height="88" fill="{c["surface"]}" stroke="{c["ink"]}" stroke-width="1.4"/>'
          f'<rect x="990" y="352" width="7" height="88" fill="{c["surface"]}" stroke="{c["ink"]}" stroke-width="1.4"/>'
          f'<rect x="776" y="352" width="72" height="34" fill="{c["surface"]}" stroke="{c["ink"]}" stroke-width="1.4"/>'
          f'<line x1="803" y1="369" x2="821" y2="369" stroke="{c["ink"]}" stroke-width="2"/>'
          f'<rect x="752" y="343" width="254" height="9" rx="2" fill="{c["surface"]}" stroke="{c["ink"]}" stroke-width="1.6"/></g>')
    d.add(place(inbox, 752, 343 - 0.38 * 90, 0.38, c))
    d.add(place(laptop, 800, 343 - 0.62 * 80, 0.62, c))
    d.add(place(helix, 878, 343 - 0.58 * 96, 0.58, c))
    d.add(f'<g class="o"><ellipse cx="986" cy="342" rx="12" ry="3" fill="{c["ink"]}"/>'
          f'<path d="M986 341 L972 304 L991 276" fill="none" stroke="{c["ink"]}" stroke-width="2.2"/>'
          f'<path d="M977 271 H1003 L996 255 H984 Z" fill="{c["accent"]}" stroke="{c["ink"]}" stroke-width="1.4"/></g>')

    # Floor.
    d.add(place(arena, 812, 404, 1.36, c))
    d.add(place(robot, 1012, 398, 0.78, c))
    d.add("</g>")
    d.add(f'<rect x="{L}" y="{T}" width="{R - L}" height="{B - T}" rx="18" fill="none" stroke="{c["ink"]}" stroke-width="1.6"/>')

    for n, (x, y) in {
        "01": (858, 288), "02": (930, 280), "03": (1094, 402), "04": (948, 452), "05": (956, 196),
        "06": (1008, 262), "07": (1074, 118), "08": (752, 298), "09": (962, 114), "10": (706, 66),
    }.items():
        d.add(f'<circle cx="{x}" cy="{y}" r="10.5" fill="{c["bg"]}" stroke="{c["accent"]}" stroke-width="1.3"/>')
        d.text(x, y + 3.4, n, 9.5, "mono", c["accent"], 700, anchor="middle")

    d.text(680, 566, "FIG. 01 — MY ROOM. EACH NUMBER IS A PROJECT BELOW.", 10.5, "mono", c["soft"], 500, ls=1.8)
    return d


# ------------------------------------------------------- section heads etc.

HEADS = [
    ("about", "01 — ABOUT", [("The person ", "serif"), ("behind", "serifi"), (" the room.", "serif")], "B.TECH AI & DS · AMRITA"),
    ("work", "02 — SELECTED WORK", [("Every object, ", "serif"), ("explained.", "serifi")], "10 PROJECTS · TOUR ORDER"),
    ("toolkit", "03 — TOOLKIT", [("What's on the ", "serif"), ("workbench.", "serifi")], "USED IN SHIPPED WORK"),
    ("beyond", "04 — BEYOND THE DESK", [("Certificates & ", "serif"), ("camps.", "serifi")], "FORAGE · NSS"),
]


def head(h, c):
    key, eyebrow, title, right = h
    d = Doc(1200, 128, c, f"{eyebrow.title()}: {''.join(t for t, _ in title)}")
    d.add(f'<line x1="0" y1="20" x2="1200" y2="20" stroke="{c["border"]}" stroke-width="1.5"/>')
    d.add(f'<line x1="0" y1="20" x2="64" y2="20" stroke="{c["accent"]}" stroke-width="3"/>')
    d.text(0, 54, eyebrow, 12, "mono", c["accent"], 600, ls=2.6)
    d.text(1200, 54, right, 11, "mono", c["soft"], 500, anchor="end", ls=2)
    d.text(-2, 108, [(t, f, c["accent"] if f == "serifi" else c["ink"]) for t, f in title], 46, weight=380, ls=-0.8)
    return d


TOOLKIT = [
    ("LANGUAGES", ["TypeScript", "JavaScript", "Python", "Java", "C / C++"]),
    ("FRONTEND", ["React 19", "Next.js", "Tailwind CSS", "Three.js · R3F", "GSAP"]),
    ("BACKEND & DATA", ["Node.js · Express", "FastAPI", "MongoDB Atlas", "REST · JWT · OTP", "Vercel · Render"]),
    ("AI & HARDWARE", ["PyTorch · PyG", "scikit-learn", "Stable-Baselines3", "ESP32 · Arduino", "MATLAB · Simulink"]),
]


def toolkit(c):
    d = Doc(1200, 300, c, "Toolkit: " + "; ".join(f"{g}: {', '.join(i)}" for g, i in TOOLKIT))
    d.add(f'<rect x="0.75" y="0.75" width="1198.5" height="298.5" rx="18" fill="{c["surface"]}" stroke="{c["border"]}" stroke-width="1.5"/>')
    for col, (group, items) in enumerate(TOOLKIT):
        x = 40 + col * 290
        if col:
            d.add(f'<line x1="{x - 24}" y1="36" x2="{x - 24}" y2="264" stroke="{c["border"]}" stroke-width="1.2"/>')
        d.text(x, 62, f"0{col + 1}", 11, "mono", c["soft"], 500, ls=1.6)
        d.text(x + 30, 62, group, 11.5, "mono", c["accent"], 600, ls=2.2)
        for i, item in enumerate(items):
            y = 112 + i * 36
            d.add(f'<circle cx="{x + 3}" cy="{y - 6}" r="2.6" fill="{c["bronze"]}"/>')
            d.text(x + 18, y, item, 19, "serif", c["ink"], 400)
    return d


def signoff(c):
    d = Doc(1200, 250, c, "Come see the room — bhanuprasadpalella.vercel.app")
    d.add(f'<rect x="0.75" y="0.75" width="1198.5" height="248.5" rx="18" fill="{c["surface"]}" stroke="{c["border"]}" stroke-width="1.5"/>')
    d.text(56, 70, "THANKS FOR SCROLLING", 11.5, "mono", c["accent"], 600, ls=2.6)
    d.text(54, 140, [("Come see the ", "serif", c["ink"]), ("room.", "serifi", c["accent"])], 58, weight=380, ls=-1)
    d.text(56, 184, "Every object in it is clickable — and the robot answers questions.", 17, "sans", c["soft"])
    d.text(56, 218, "BHANUPRASADPALELLA.VERCEL.APP", 11.5, "mono", c["ink"], 600, ls=2.4)
    d.add(arrow(56 + measure("mono", "BHANUPRASADPALELLA.VERCEL.APP", 11.5, 600, 2.4) + 30, 214, c["accent"], 20))
    d.add(logo(1000, 50, 1.25, c))
    return d


def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = [("hero", hero), ("toolkit", toolkit), ("signoff", signoff)]
    jobs += [(f"head-{h[0]}", (lambda h: lambda c: head(h, c))(h)) for h in HEADS]
    jobs += [(f"card-{p['n']}", (lambda p: lambda c: card(p, c))(p)) for p in PROJECTS]
    for name, fn in jobs:
        for theme, c in THEMES.items():
            path = os.path.join(OUT, f"{name}-{theme}.svg")
            with open(path, "w") as f:
                f.write(fn(c).svg())
    print(f"wrote {len(jobs) * 2} files to {OUT}")


if __name__ == "__main__":
    main()

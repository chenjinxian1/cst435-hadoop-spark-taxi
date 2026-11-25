#!/usr/bin/env python3
"""Generate fig.svg (system overview) following spec.json and plan.md.

  python make_fig.py          # needs the figgenie-paper-diagram skill for place_text
"""
import os
import sys

SKILL = os.path.expanduser("~/.claude/skills/figgenie-paper-diagram/scripts")
sys.path.insert(0, SKILL)
from place_text import place, svg_text  # noqa: E402

FONT = "helvetica"
W, H = 246, 190
INK = "#212121"
OURS, STACK, ACCENT, GREY = "#dae8fc", "#e8e8e8", "#0F4D92", "#7f7f7f"
SW = 0.6           # box stroke
EW = 0.75          # edge stroke

out = []


def T(text, box, size=6.5, bold=False, fill=INK, attrs=""):
    p = place(text, box, size=size, font=FONT, bold=bold)
    a = f'fill="{fill}"' + (' font-weight="bold"' if bold else "") + (" " + attrs if attrs else "")
    return svg_text(p, a)


def text_at(x, y, s, size=6.5, bold=False, anchor="start", fill=INK):
    w = ' font-weight="bold"' if bold else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}"{w} text-anchor="{anchor}" '
            f'fill="{fill}">{s}</text>')


def rect(x, y, w, h, fill, stroke=INK, sw=SW, rx=1.5, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}/>')


def node(nid, role, label, box, fill, parent=None, size=6.5, tcol=INK, bold=False, extra="", stroke=INK):
    par = f' data-parent="{parent}"' if parent else ""
    x, y, w, h = box
    out.append(f'<g id="n:{nid}" data-kind="node" data-role="{role}"{par}>'
               + rect(x, y, w, h, fill, stroke=stroke) + extra
               + T(label, box, size=size, fill=tcol, bold=bold) + "</g>")


def edge(eid, frm, to, d, kind="data", step=None, dash=None, color=INK, both=False, sw=EW):
    st = f' data-step="{step}"' if step else ""
    da = f' stroke-dasharray="{dash}"' if dash else ""
    ms = ' marker-start="url(#arrow-start)"' if both else ""
    out.append(f'<g id="e:{eid}" data-kind="edge" data-from="{frm}" data-to="{to}" data-edge-kind="{kind}"{st}>'
               f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{da}{ms} '
               f'marker-end="url(#{"arrow" if color == INK else "arrow-grey"})"/></g>')


def badge(n, cx, cy, attached):
    r = 4.2
    out.append(f'<g id="s:{n}" data-kind="step" data-attached-to="{attached}">'
               f'<g data-symbol="badge"><circle cx="{cx}" cy="{cy}" r="{r}" fill="{INK}"/>'
               f'<text x="{cx}" y="{cy + 1.95:.2f}" font-size="5.5" font-weight="bold" text-anchor="middle" '
               f'fill="#ffffff">{n}</text></g></g>')


# ------------------------------------------------------------------ lanes (deployment strips)
out.append('<g id="l:local" data-kind="lane" data-order="0">' + rect(4, 160, 172, 13, "#f2f2f2", stroke="none", rx=1)
           + T("Local: one host, N = 1–4 containers of 2 CPU, 5 GB", (4, 160, 172, 13)) + "</g>")
out.append('<g id="l:azure" data-kind="lane" data-order="1">' + rect(4, 176, 172, 13, "#f2f2f2", stroke="none", rx=1)
           + T("Azure: 3 VMs (master + 2 workers), N = 1–2", (4, 176, 172, 13)) + "</g>")

# ------------------------------------------------------------------ containers
out.append('<g id="c:master" data-kind="container" data-role="existing">' + rect(4, 4, 170, 34, "none", rx=2)
           + text_at(8, 12.6, "master container", bold=True) + "</g>")
CARDS = {"worker": (4, "worker 1", False), "worker~2": (132, "worker N", True)}
for cid, (x0, title, _) in CARDS.items():
    rep = ' data-replica="2"' if cid.endswith("~2") else ""
    out.append(f'<g id="c:{cid}" data-kind="container" data-role="existing"{rep}>' + rect(x0, 46, 110, 70, "none", rx=2)
               + text_at(x0 + 55, 54.6, title, bold=True, anchor="middle") + "</g>")
out.append('<g id="n:worker~ellipsis" data-kind="ellipsis">' + text_at(123, 68, "…", size=8, anchor="middle") + "</g>")

# ------------------------------------------------------------------ edges (drawn before nodes)
edge("e-blockmap", "namenode", "datanode", "M27.5 33 V57.4", kind="control", dash="2.5 1.9")
edge("e-submit", "runjob", "rm", "M128 25.5 H115", kind="control", step=3)
edge("e-launch", "rm", "nodemanager", "M83 33 V57.4", kind="control", step=4)
edge("e-launch~2", "rm", "nodemanager~2", "M92 33 V42 H163 V57.4", kind="control")
edge("e-ship", "jobcode", "runjob", "M180 25.5 H167", kind="dependency", dash="0.8 1.4", color=GREY)
for x0, mir in [(4, False), (132, True)]:
    sfx = "" if not mir else "~2"
    ncx = x0 + (31 if mir else 79)
    edge(f"e-start{sfx}", "nodemanager" + sfx, "tasks" + sfx, f"M{ncx} 73 V83.4", kind="control")
    if mir:
        edge(f"e-read{sfx}", "datanode" + sfx, "tasks" + sfx, f"M{x0 + 68} 98 H{x0 + 58.6}")
    else:
        edge(f"e-read{sfx}", "datanode", "tasks", f"M{x0 + 42} 98 H{x0 + 51.4}")
edge("e-shuffle", "tasks", "tasks~2", "M110.6 98 H135.4", step=5, both=True)
edge("e-put", "csv", "datanode", "M145 136.5 V122 H27.5 V112.6", step=2)
edge("e-output", "tasks~2", "results", "M163 112 V128 H211 V133.4", step=6)
edge("e-prepare", "parquet", "prepare", "M48 144 H55.4", step=1)
edge("e-csv", "prepare", "csv", "M110 144 H118.4")

# ------------------------------------------------------------------ nodes
node("namenode", "existing", "NameNode", (7, 18, 41, 15), STACK, parent="master")
node("rm", "existing", "ResourceManager", (52, 18, 62, 15), STACK, parent="master")
node("runjob", "novel", "run_job.sh", (128, 18, 38, 15), OURS, parent="master")
node("jobcode", "novel", "mapper.py ·\\nreducer.py", (180, 7, 62, 26), ACCENT, tcol="#ffffff", bold=True,
     stroke=ACCENT)
for x0, mir in [(4, False), (132, True)]:
    sfx = "" if not mir else "~2"
    rep = ' data-replica="2"' if mir else ""
    par = "worker" + sfx
    dn_x = x0 + (68 if mir else 5)
    nm_x = x0 + (4 if mir else 52)
    cells = "".join(rect(dn_x + 5 + 14 * c, 74 + 11 * r, 12, 8.5, "#ffffff", sw=0.5, rx=0.5)
                    for r in range(2) for c in range(2))
    cells += text_at(dn_x + 18.5, 107.5, "blocks", size=6, anchor="middle", fill="#595959")
    p = place("DataNode", (dn_x, 58, 37, 13), size=6.5, font=FONT)
    out.append(f'<g id="n:datanode{sfx}" data-kind="node" data-role="existing" data-parent="{par}"{rep}>'
               + rect(dn_x, 58, 37, 54, STACK) + cells + svg_text(p, f'fill="{INK}"') + "</g>")
    for nid, lab, box in [("nodemanager", "NodeManager", (nm_x, 58, 54, 15)),
                          ("tasks", "Map / reduce\\ntasks or Spark\\nexecutor", (nm_x, 84, 54, 28))]:
        out.append(f'<g id="n:{nid}{sfx}" data-kind="node" data-role="existing" data-parent="{par}"{rep}>'
                   + rect(*box, STACK) + T(lab, box) + "</g>")
out.append('<g id="n:parquet" data-kind="node" data-role="external">'
           '<g data-symbol="cylinder">'
           f'<path d="M4 137 V151 A22 3 0 0 0 48 151 V137" fill="#ffffff" stroke="{INK}" stroke-width="{SW}"/>'
           f'<ellipse cx="26" cy="137" rx="22" ry="3" fill="#ffffff" stroke="{INK}" stroke-width="{SW}"/></g>'
           + T("TLC Parquet", (4, 140, 44, 11)) + "</g>")
node("prepare", "novel", "prepare_data.py", (56, 136.5, 54, 15), OURS)
node("csv", "novel", "CSV tiers S–XL", (119, 136.5, 52, 15), OURS)
node("results", "novel", "compare_outputs\\nbenchmark.csv", (180, 134, 62, 20), OURS)

# ------------------------------------------------------------------ steps
badge(1, 52, 131,  "e-prepare")
badge(2, 151, 128.5, "e-put")
badge(3, 121.5, 12.5, "e-submit")
badge(4, 77, 45.5, "e-launch")
badge(5, 123, 106, "e-shuffle")
badge(6, 169, 123, "e-output")

# ------------------------------------------------------------------ legend
leg = ['<g id="legend" data-kind="legend">']
rows = [("ours", "our scripts", "fill", OURS), ("stack", "Hadoop / Spark", "fill", STACK),
        ("dashed", "block map", "dash", "2.5 1.9"), ("dotted", "code shipped", "dot", "0.8 1.4")]
for i, (iid, lab, kind, v) in enumerate(rows):
    y = 162 + i * 7.2
    if kind == "fill":
        sw = rect(184, y, 11, 5, v, sw=0.5, rx=0.5)
    else:
        col = INK if kind == "dash" else GREY
        sw = f'<line x1="184" y1="{y + 2.5}" x2="195" y2="{y + 2.5}" stroke="{col}" stroke-width="{EW}" stroke-dasharray="{v}"/>'
    leg.append(f'<g id="legend:{iid}" data-kind="legend-item">{sw}{text_at(198, y + 4.6, lab, size=6)}</g>')
leg.append("</g>")
out += leg

defs = (f'<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" '
        f'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0 0 L10 5 L0 10 z" fill="{INK}"/></marker>'
        f'<marker id="arrow-start" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" '
        f'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0 0 L10 5 L0 10 z" fill="{INK}"/></marker>'
        f'<marker id="arrow-grey" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" '
        f'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0 0 L10 5 L0 10 z" fill="{GREY}"/></marker></defs>')
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}pt" height="{H}pt" '
       f'font-family="\'TeX Gyre Heros\', Helvetica, Arial, sans-serif" font-size="6.5" '
       f'data-spec="cst435-overview" data-spec-version="1">'
       f'<rect width="{W}" height="{H}" fill="#ffffff"/>' + defs + "".join(out) + "</svg>\n")
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fig.svg"), "w", encoding="utf-8") as f:
    f.write(svg)
print("wrote fig.svg")

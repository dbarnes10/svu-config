#!/usr/bin/env python3
"""
wall_visualiser.py
──────────────────
Reads a platform_config.json (CurvedWall format) and renders a
19200 × 2160 PNG showing:

  • Display strip   – every display coloured by its rendering node,
                      with a highlighted band showing the viewport
                      slice that node's camera contributes.
  • Node VP bars    – one bar per node showing the full normalised
                      0–1 viewport space with every display's slice
                      labelled inside it.

Usage:
    python3 wall_visualiser.py [config.json] [output.png]
"""

import json
import os
import sys
from PIL import Image, ImageDraw, ImageFont

# ── Constants ────────────────────────────────────────────────────────────────
CANVAS_W   = 19200
CANVAS_H   = 2160
TITLE_H    = 90          # top title bar
DISP_H     = 1460        # main display strip
GAP        = 12          # gap between sections
VP_H_EACH  = 160         # height of each per-node bar
VP_LABEL_H = 50          # label above node bars

BG          = (18, 20, 26)
GRID_COL    = (40, 44, 55)
WHITE       = (255, 255, 255)
LABEL_DIM   = (160, 165, 175)
SECTION_SEP = (50, 55, 68)

NODE_BASE = {
    "nodeL": (52,  120, 246),   # Blue
    "nodeC": (35,  175,  95),   # Green
    "nodeR": (230,  95,  40),   # Orange
}
NODE_LIGHT = {k: tuple(min(255, int(c * 0.55 + 105)) for c in v) for k, v in NODE_BASE.items()}
NODE_DIM   = {k: tuple(max(0, int(c * 0.35))          for c in v) for k, v in NODE_BASE.items()}


# ── Font loader (Mac-first) ──────────────────────────────────────────────────
def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    sf_bold   = "/System/Library/Fonts/Supplemental/SF-Pro-Display-Bold.otf"
    sf_reg    = "/System/Library/Fonts/Supplemental/SF-Pro-Display-Regular.otf"
    candidates = [
        sf_bold if bold else sf_reg,
        "/System/Library/Fonts/SFCompact.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ── Geometry helpers ─────────────────────────────────────────────────────────
def pt_key(pt):
    return tuple(round(v, 4) for v in pt)


def chain_displays(displays: dict) -> list[str]:
    """Order displays left-to-right by chaining lr of one to ll of the next."""
    # ll_to_name: given a point, which display starts there (has that as its ll)?
    ll_to_name = {pt_key(d["ll"]): name for name, d in displays.items()}
    # all lr points: used to find the leftmost start (whose ll isn't anyone's lr)
    all_lr     = {pt_key(d["lr"]) for d in displays.values()}

    # Starting display: its ll is not matched by any other display's lr
    start = next(
        (name for name, d in displays.items()
         if pt_key(d["ll"]) not in all_lr),
        next(iter(displays))
    )

    ordered, current, visited = [], start, set()
    while current and current not in visited:
        ordered.append(current)
        visited.add(current)
        # Follow: next display whose ll == current display's lr
        current = ll_to_name.get(pt_key(displays[current]["lr"]))

    # Safety net for any unchained displays
    for name in displays:
        if name not in visited:
            ordered.append(name)

    return ordered


# ── Drawing helpers ──────────────────────────────────────────────────────────
def draw_rect(draw, x0, y0, x1, y1, fill, outline=None, lw=2):
    draw.rectangle([x0, y0, x1, y1], fill=fill)
    if outline:
        draw.rectangle([x0, y0, x1, y1], outline=outline, width=lw)


def centred_text(draw, cx, cy, text, font, color):
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
    except Exception:
        tw, th = len(text) * (font.size // 2), font.size
    draw.text((cx - tw // 2, cy - th // 2), text, fill=color, font=font)


def text_fits(draw, text, font, max_w) -> bool:
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return (bb[2] - bb[0]) < max_w - 12
    except Exception:
        return len(text) * (font.size // 2) < max_w - 12


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "platform_config.json"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "wall_layout.png"

    with open(cfg_path) as f:
        config = json.load(f)

    platform  = next(iter(config["platforms"].values()))
    plat_name = next(iter(config["platforms"]))
    displays  = platform["displays"]
    viewports = platform["viewports"]
    nodes     = platform["nodes"]

    # Build display → node map
    disp_node = {}
    for node_name, nd in nodes.items():
        for d in nd["display"]:
            disp_node[d] = node_name

    ordered = chain_displays(displays)
    total_px = sum(displays[d]["width_px"] for d in ordered)
    print(f"Display order ({len(ordered)} panels, {total_px}px total):")
    for i, name in enumerate(ordered):
        print(f"  {i+1:2}. {name:45s}  {displays[name]['width_px']:5d}px  [{disp_node.get(name,'?')}]")

    # ── Fonts ────────────────────────────────────────────────────────────
    f_title  = load_font(62, bold=True)
    f_large  = load_font(52, bold=True)
    f_med    = load_font(38)
    f_small  = load_font(28)
    f_tiny   = load_font(22)

    # ── Canvas ───────────────────────────────────────────────────────────
    img  = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    draw = ImageDraw.Draw(img)

    # Subtle vertical grid lines every 1920px
    for gx in range(0, CANVAS_W, 1920):
        draw.line([(gx, 0), (gx, CANVAS_H)], fill=GRID_COL, width=1)

    # ── Title bar ────────────────────────────────────────────────────────
    title = f"{plat_name}  –  Display & Camera Viewport Layout"
    centred_text(draw, CANVAS_W // 2, TITLE_H // 2, title, f_title, WHITE)

    # ── Legend (top-right) ───────────────────────────────────────────────
    lx = CANVAS_W - 820
    ly = 18
    for node_name, col in NODE_BASE.items():
        draw_rect(draw, lx, ly, lx + 34, ly + 34, col, WHITE, 2)
        draw.text((lx + 44, ly + 4), node_name, fill=(210, 215, 225), font=f_small)
        lx += 240

    # ── Display strip ────────────────────────────────────────────────────
    y0_disp = TITLE_H + GAP
    y1_disp = y0_disp + DISP_H

    x_cursor = 0
    for disp_name in ordered:
        d      = displays[disp_name]
        w      = d["width_px"]
        node   = disp_node.get(disp_name, "unknown")
        base   = NODE_BASE.get(node, (100, 100, 100))
        light  = NODE_LIGHT.get(node, (160, 160, 160))
        dim    = NODE_DIM.get(node, (30, 30, 30))

        # Base display rectangle (dimmed)
        draw_rect(draw, x_cursor, y0_disp, x_cursor + w - 1, y1_disp, dim)

        # Outer border coloured by node
        vp_name = "vp_" + disp_name
        draw_rect(draw, x_cursor, y0_disp, x_cursor + w - 1, y1_disp, None, base, 4)

        # ── Labels ──────────────────────────────────────────────────────
        cx = x_cursor + w // 2
        cy = y0_disp + DISP_H // 2

        short_name = disp_name.replace("disp_", "")

        # Display name (wrapped if needed)
        parts = short_name.split("_")
        lines = []
        line  = ""
        for p in parts:
            test = (line + "_" + p).strip("_")
            if text_fits(draw, test, f_large, w):
                line = test
            else:
                if line:
                    lines.append(line)
                line = p
        if line:
            lines.append(line)

        line_h = 58
        total_lh = len(lines) * line_h
        ty = cy - total_lh // 2 - 40

        for li, ln in enumerate(lines):
            centred_text(draw, cx, ty + li * line_h, ln, f_large, WHITE)

        # Node name
        centred_text(draw, cx, cy + 30, f"[{node}]", f_med, base)

        # Pixel width
        centred_text(draw, cx, cy + 80, f"{w} px", f_small, (180, 185, 195))

        # Viewport fraction info (text only — see node bars below for full picture)
        if vp_name in viewports:
            vp = viewports[vp_name]
            vp_str = f"vp  {vp['x']:.4f} → {vp['x']+vp['width']:.4f}"
            centred_text(draw, cx, y1_disp - 40, vp_str, f_tiny, (180, 180, 140))

        x_cursor += w

    # ── Section separator ────────────────────────────────────────────────
    sep_y = y1_disp + GAP
    draw.line([(0, sep_y), (CANVAS_W, sep_y)], fill=SECTION_SEP, width=2)

    # ── Node viewport bars ───────────────────────────────────────────────
    node_list = list(nodes.keys())
    vp_section_y = sep_y + GAP

    # Section heading
    centred_text(draw, CANVAS_W // 2, vp_section_y + VP_LABEL_H // 2,
                 "Node Camera Viewport Allocation  (normalised 0 → 1)",
                 f_med, LABEL_DIM)

    bar_label_w = 200   # left margin for node name label
    bar_x0      = bar_label_w + 20
    bar_w       = CANVAS_W - bar_x0 - 20

    for i, node_name in enumerate(node_list):
        nd    = nodes[node_name]
        col   = NODE_BASE.get(node_name, (120, 120, 120))
        light = NODE_LIGHT.get(node_name, (180, 180, 180))

        by0 = vp_section_y + VP_LABEL_H + i * (VP_H_EACH + 10)
        by1 = by0 + VP_H_EACH

        # Node label (left)
        centred_text(draw, bar_label_w // 2, (by0 + by1) // 2, node_name, f_large, col)

        # Background bar
        draw_rect(draw, bar_x0, by0, bar_x0 + bar_w, by1, (30, 33, 42), (55, 60, 75), 2)

        # Tick marks at 0.25 intervals
        for tick in [0.25, 0.5, 0.75]:
            tx = bar_x0 + int(tick * bar_w)
            draw.line([(tx, by0), (tx, by1)], fill=(60, 65, 80), width=1)
            centred_text(draw, tx, by0 - 14, f"{tick:.2f}", f_tiny, (80, 85, 100))

        # Viewport slices for each display in this node
        for disp_name in nd["display"]:
            vp_name = "vp_" + disp_name
            if vp_name not in viewports:
                continue
            vp  = viewports[vp_name]
            sx0 = bar_x0 + int(vp["x"]                   * bar_w)
            sx1 = bar_x0 + int((vp["x"] + vp["width"])   * bar_w)

            # Filled slice
            draw_rect(draw, sx0 + 2, by0 + 4, sx1 - 2, by1 - 4, light, WHITE, 2)

            # Label inside slice
            seg_w   = sx1 - sx0
            short   = disp_name.replace("disp_", "")
            cx_seg  = (sx0 + sx1) // 2
            cy_seg  = (by0 + by1) // 2

            # Try decreasing font sizes until it fits
            for fnt in [f_med, f_small, f_tiny]:
                if text_fits(draw, short, fnt, seg_w):
                    centred_text(draw, cx_seg, cy_seg - 12, short, fnt, BG)
                    # Show pixel width below
                    px_str = f"{displays[disp_name]['width_px']}px"
                    if text_fits(draw, px_str, f_tiny, seg_w):
                        centred_text(draw, cx_seg, cy_seg + 20, px_str, f_tiny, (40, 40, 50))
                    break

            # Viewport x-extent labels below the bar
            draw.text((sx0 + 4, by1 + 4), f"{vp['x']:.3f}", fill=(100,105,120), font=f_tiny)

        # Right edge label
        draw.text((bar_x0 + bar_w - 28, by1 + 4), "1.0", fill=(80, 85, 100), font=f_tiny)
        draw.text((bar_x0 - 4, by1 + 4), "0.0", fill=(80, 85, 100), font=f_tiny)

    # ── Save ─────────────────────────────────────────────────────────────
    img.save(out_path, "PNG", optimize=False)
    print(f"\nSaved → {out_path}  ({CANVAS_W}×{CANVAS_H}px)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
plot_wall_platform.py

Visualise wall geometry from a generated platform JSON.

Plots:
- panel outlines in X–Z
- panel centres
- panel normals (short arrows)

Assumptions:
- Offaxis displays defined by ul, ll, lr
- +X right, +Z forward
"""

import json
import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt


def load_displays(json_path):
    with open(json_path, "r") as f:
        data = json.load(f)

    platforms = data["platforms"]
    if len(platforms) != 1:
        raise ValueError("Expected exactly one platform")

    platform = next(iter(platforms.values()))
    return platform["displays"]


def quad_from_display(d):
    """
    Returns 4 corners in XZ:
    ul, ll, lr, ur (computed)
    """
    ul = np.array([d["ul"][0], d["ul"][2]])
    ll = np.array([d["ll"][0], d["ll"][2]])
    lr = np.array([d["lr"][0], d["lr"][2]])

    # ur = ul + (lr - ll)
    ur = ul + (lr - ll)

    return ul, ll, lr, ur


def plot_platform(displays):
    fig, ax = plt.subplots(figsize=(12, 6))

    for name, d in displays.items():
        ul, ll, lr, ur = quad_from_display(d)

        xs = [ul[0], ll[0], lr[0], ur[0], ul[0]]
        zs = [ul[1], ll[1], lr[1], ur[1], ul[1]]

        ax.plot(xs, zs, "k-", linewidth=1)
        ax.text(np.mean(xs[:-1]), np.mean(zs[:-1]), name,
                fontsize=8, ha="center", va="center")

        # centre
        cx = np.mean(xs[:-1])
        cz = np.mean(zs[:-1])
        ax.plot(cx, cz, "ro", markersize=3)

        # normal (approx)
        right = lr - ll
        up = ul - ll
        normal = np.array([right[1], -right[0]])
        normal /= np.linalg.norm(normal) + 1e-9

        ax.arrow(cx, cz,
                 normal[0] * 0.3,
                 normal[1] * 0.3,
                 head_width=0.05,
                 head_length=0.08,
                 fc="r", ec="r")

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X (metres)")
    ax.set_ylabel("Z (metres)")
    ax.set_title("Wall Platform Geometry (Top View)")
    ax.grid(True)

    plt.show()


def main():
    parser = argparse.ArgumentParser("plot_wall_platform.py")
    parser.add_argument("platform_json", help="Generated platform JSON file")
    args = parser.parse_args()

    displays = load_displays(args.platform_json)
    plot_platform(displays)


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""Figure of what the input data look like (report, Section V).

  python -I scripts/data_figure.py

Reads the monthly Parquet files in data/raw/ (row counts from the file metadata; the
value distributions from January 2024) and writes report/figures/data_overview.pdf:
  (a) trip records per month 2023-2024 with the data tiers S, M, L, XL marked
  (b) trip distance, (c) fare amount: histograms with the ranges the mapper rejects
  (d) payment types (tips are recorded only for credit-card trips)
"""
import glob
import os
import sys

import numpy as np
import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_figures as rf  # noqa: E402  (shared style and palette)
import matplotlib.pyplot as plt  # noqa: E402

P = rf.PALETTE
RAW = os.path.join(rf.ROOT, "data", "raw")


def main():
    files = sorted(glob.glob(os.path.join(RAW, "yellow_tripdata_*.parquet")))
    months = [os.path.basename(f)[16:23] for f in files]
    rows = np.array([pq.ParquetFile(f).metadata.num_rows for f in files]) / 1e6
    jan = pq.read_table(os.path.join(RAW, "yellow_tripdata_2024-01.parquet"),
                        columns=["trip_distance", "fare_amount", "payment_type"]).to_pandas()

    fig = plt.figure(figsize=(7.16, 1.62))
    gs = fig.add_gridspec(1, 4, width_ratios=[1.75, 1, 1, 0.95], wspace=0.42,
                          left=0.05, right=0.99, bottom=0.24, top=0.8)
    # (a) records per month and the tiers
    ax = fig.add_subplot(gs[0])
    x = np.arange(len(months))
    cols = [P["blue_secondary"] if m.startswith("2024") else P["neutral"] for m in months]
    ax.bar(x, rows, width=0.75, color=cols, linewidth=0)
    ax.set_xticks([0, 6, 12, 18, 23])
    ax.set_xticklabels(["Jan\n2023", "Jul", "Jan\n2024", "Jul", "Dec"])
    ax.set_ylabel("Trips (millions)")
    ax.set_ylim(0, 6.3)
    tiers = [("S", 12, 12, 3.55), ("M", 12, 17, 4.1), ("L", 12, 23, 4.65), ("XL", 0, 23, 5.2)]
    for name, a, b, y in tiers:
        ax.plot([a - 0.4, b + 0.4], [y, y], color=P["dark"], lw=0.7)
        for e in (a - 0.4, b + 0.4):
            ax.plot([e, e], [y - 0.12, y], color=P["dark"], lw=0.7)
        ax.text(b + 0.9 if name != "XL" else (a + b) / 2, y + (0 if name != "XL" else 0.12), name,
                fontsize=6.3, va="center" if name != "XL" else "bottom",
                ha="left" if name != "XL" else "center")
    rf.panel_label(ax, "a", x=-0.13)
    # (b) trip distance
    ax = fig.add_subplot(gs[1])
    d = jan.trip_distance
    ax.hist(d[(d > 0) & (d < 20)], bins=np.arange(0, 20.5, 0.5), color=P["blue_secondary"], linewidth=0)
    ax.set_xlabel("Trip distance (miles)")
    ax.set_ylabel("Trips (thousands)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v / 1e3:.0f}"))
    ax.text(0.97, 0.95, f"median {d.median():.1f} mi\n{(d <= 0).mean() * 100:.1f}% zero (rejected)",
            transform=ax.transAxes, ha="right", va="top", fontsize=6.2)
    rf.panel_label(ax, "b", x=-0.3)
    # (c) fare amount
    ax = fig.add_subplot(gs[2])
    f = jan.fare_amount
    bins = np.arange(-20, 101, 2.5)
    ax.hist(f[(f > 0) & (f < 100)], bins=bins, color=P["blue_secondary"], linewidth=0)
    ax.hist(f[(f <= 0) & (f > -20)], bins=bins, color=P["red_strong"], linewidth=0)
    ax.set_yscale("log")
    ax.set_xlabel("Fare amount (US$)")
    ax.set_ylabel("Trips (log)")
    ax.text(0.97, 0.95, f"median ${f.median():.2f}\n{(f <= 0).mean() * 100:.1f}% ≤ 0 (rejected)",
            transform=ax.transAxes, ha="right", va="top", fontsize=6.2)
    ax.set_ylim(5e2, 4e7)
    rf.panel_label(ax, "c", x=-0.3)
    # (d) payment type
    ax = fig.add_subplot(gs[3])
    names = {1: "Credit card", 2: "Cash", 0: "Unknown", 4: "Dispute", 3: "No charge"}
    share = jan.payment_type.value_counts(normalize=True)
    order = [1, 2, 0, 4, 3]
    y = np.arange(len(order))[::-1]
    ax.barh(y, [share.get(k, 0) * 100 for k in order], height=0.62, linewidth=0,
            color=[P["blue_main"]] + [P["neutral"]] * 4)
    ax.set_yticks(y)
    ax.set_yticklabels([names[k] for k in order])
    ax.tick_params(axis="y", length=0)
    for yi, k in zip(y, order):
        ax.text(share.get(k, 0) * 100 + 1.5, yi, f"{share.get(k, 0) * 100:.1f}%", va="center", fontsize=6)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of trips (%)")
    rf.panel_label(ax, "d", x=-0.55)
    out = os.path.join(rf.FIG, "data_overview.pdf")
    fig.savefig(out, bbox_inches="tight", pad_inches=0.02)
    print("wrote report/figures/data_overview.pdf;",
          f"rows 2023={rows[:12].sum():.2f} M, 2024={rows[12:].sum():.2f} M")


if __name__ == "__main__":
    main()

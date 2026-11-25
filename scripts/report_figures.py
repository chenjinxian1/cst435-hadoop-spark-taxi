#!/usr/bin/env python3
"""Draw the data figures of the report in one consistent publication style.

  python -I scripts/report_figures.py

Style follows the figures4papers conventions (sans-serif, no top/right spines,
frameless legends, semantic palette) at print size: figures are drawn at the
width they occupy in the IEEE two-column layout (3.5 in single, 7.16 in double).

Reads   results/summary.csv, results/cache/cache_runs.csv, results/counters.csv,
        results/outputs/serial-*-L.tsv, data/csv/taxi_zone_lookup.csv
Writes  report/figures/analytics_L.pdf     what the three jobs found (tier L)
        report/figures/scaling_routes.pdf  run time and speedup, all tiers, + rerun
        report/figures/weak_scaling.pdf    weak-scaling efficiency
        report/figures/combiner_cloud.pdf  shuffle volume; local vs. Azure scaling
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "report", "figures")

PALETTE = {
    "blue_main": "#0F4D92", "blue_secondary": "#3775BA",
    "green_3": "#8BCF8B", "red_1": "#F6CFCB", "red_2": "#E9A6A1", "red_strong": "#B64342",
    "neutral": "#CFCECE", "grey": "#767676", "dark": "#272727",
    "teal": "#42949E", "violet": "#9A4D8E",
}
# engine -> (colour, marker, line style, label); blue = the fastest engine, reds = MapReduce
ENGINE = {
    "spark_df": (PALETTE["blue_main"], "^", "-", "Spark DataFrame"),
    "spark_rdd": (PALETTE["teal"], "s", "-", "Spark RDD"),
    "mr": (PALETTE["red_strong"], "o", "-", "Hadoop MR (combiner)"),
    "mr_nocombiner": (PALETTE["red_2"], "o", "--", "Hadoop MR (no combiner)"),
}
TIERS = [("S", "1 month"), ("M", "6 months"), ("L", "12 months"), ("XL", "24 months")]

plt.rcParams.update({
    "font.family": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "font.size": 7, "axes.titlesize": 7, "axes.labelsize": 7,
    "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "legend.fontsize": 6.5,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "lines.linewidth": 1.1, "lines.markersize": 3.6,
    "pdf.fonttype": 42, "savefig.dpi": 300,
})


def save(fig, name):
    fig.savefig(os.path.join(FIG, name), bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print("wrote report/figures/" + name)


def panel_label(ax, s, x=-0.02, y=1.02):
    ax.text(x, y, s, transform=ax.transAxes, fontweight="bold", ha="right", va="bottom")


# ---------------------------------------------------------------- analytics
SHORT_ZONE = {
    "Upper East Side South": "UES South", "Upper East Side North": "UES North",
    "Midtown Center": "Midtown Ctr", "Midtown East": "Midtown East",
    "Times Sq/Theatre District": "Times Sq", "Penn Station/Madison Sq West": "Penn Station",
    "Lincoln Square East": "Lincoln Sq E", "JFK Airport": "JFK Airport",
    "LaGuardia Airport": "LaGuardia", "Murray Hill": "Murray Hill",
}

ROUTE = {"UES South": "UES S", "UES North": "UES N", "Midtown Ctr": "Midtown"}


def analytics():
    z = pd.read_csv(os.path.join(ROOT, "data", "csv", "taxi_zone_lookup.csv"))
    zname = dict(zip(z.LocationID, z.Zone))
    short = lambda i: SHORT_ZONE.get(zname.get(i, str(i)), zname.get(i, str(i)))
    out = os.path.join(ROOT, "results", "outputs")

    d = pd.read_csv(os.path.join(out, "serial-demand-L.tsv"), sep="\t", header=None, names=["k", "n"])
    d[["zone", "hour"]] = d.k.str.split("|", expand=True).astype(int)
    hourly = d.groupby("hour").n.sum().reindex(range(24), fill_value=0)
    top = d.groupby("zone").n.sum().sort_values(ascending=False).head(8).index
    heat = (d[d.zone.isin(top)].pivot_table(index="zone", columns="hour", values="n", aggfunc="sum")
              .reindex(index=top, columns=range(24)).fillna(0))
    heat = heat.div(heat.sum(axis=1), axis=0) * 100          # % of the zone's daily pick-ups

    r = pd.read_csv(os.path.join(out, "serial-routes-L.tsv"), sep="\t", header=None, names=["k", "n"])
    r = r.sort_values("n", ascending=False).head(5)
    r["label"] = [f"{ROUTE.get(short(int(a)), short(int(a)))}→{ROUTE.get(short(int(b)), short(int(b)))}" for a, b in (k.split("|") for k in r.k)]

    f = pd.read_csv(os.path.join(ROOT, "results", "tables", "fare_L.csv"))
    f["band"] = ["0–1", "1–2", "2–5", "5–10", "10–20", ">20"]

    fig = plt.figure(figsize=(7.16, 1.75))
    gs = fig.add_gridspec(1, 8, width_ratios=[1.0, 0.42, 1.45, 0.05, 0.98, 0.78, 0.36, 1.12], wspace=0.08,
                          left=0.05, right=0.94, bottom=0.2, top=0.88)
    # (a) trips per hour of day
    ax = fig.add_subplot(gs[0])
    cols = [PALETTE["blue_main"] if h == hourly.idxmax() else PALETTE["blue_secondary"] for h in range(24)]
    ax.bar(hourly.index, hourly.values / 1e6, width=0.8, color=cols, alpha=0.85, linewidth=0)
    ax.set_xticks([0, 6, 12, 18, 23])
    ax.set_xlim(-0.8, 23.8)
    ax.set_xlabel("Hour of day (pick-up)")
    ax.set_ylabel("Trips (millions)")
    ax.annotate(f"{hourly.max() / 1e6:.2f} M", (hourly.idxmax(), hourly.max() / 1e6),
                xytext=(-16, 1), textcoords="offset points", ha="right", va="center", fontsize=6.3,
                arrowprops=dict(arrowstyle="-", lw=0.5, color=PALETTE["dark"]))
    panel_label(ax, "a", x=-0.2)
    # (b) hourly profile of the eight busiest pick-up zones
    ax = fig.add_subplot(gs[2])
    im = ax.imshow(heat.values, aspect="auto", cmap="Blues", vmin=0, interpolation="nearest")
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels([short(i) for i in top])
    ax.set_xticks([0, 6, 12, 18, 23])
    ax.set_xlabel("Hour of day")
    ax.tick_params(axis="y", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, cax=fig.add_subplot(gs[3]))
    cb.outline.set_linewidth(0.4)
    cb.ax.tick_params(width=0.4, length=2)
    cb.set_label("% of the zone's trips", labelpad=2)
    panel_label(ax, "b", x=-0.3)
    # (c) five most frequent routes
    ax = fig.add_subplot(gs[5])
    y = np.arange(len(r))[::-1]
    ax.barh(y, r.n / 1e3, height=0.62, color=PALETTE["blue_secondary"], alpha=0.85, linewidth=0)
    ax.set_yticks(y)
    ax.set_yticklabels(r.label)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Trips (thousands)")
    for yi, v in zip(y, r.n / 1e3):
        ax.text(v + 4, yi, f"{v:.0f}", va="center", fontsize=6)
    ax.set_xlim(0, r.n.max() / 1e3 * 1.25)
    panel_label(ax, "c", x=-1.0)
    # (d) average fare and credit-card tip rate by trip distance
    ax = fig.add_subplot(gs[7])
    x = np.arange(len(f))
    ax.bar(x, f.avg_fare_usd, width=0.62, color=PALETTE["neutral"], linewidth=0)
    ax.set_xticks(x)
    ax.set_xticklabels(f.band, fontsize=5.8, rotation=35, ha="right", rotation_mode="anchor")
    ax.set_xlabel("Trip distance (miles)")
    ax.set_ylabel("Average fare (US$)")
    ax2 = ax.twinx()
    ax2.spines["right"].set_visible(True)
    ax2.plot(x, f.cc_tip_rate * 100, color=PALETTE["red_strong"], marker="o")
    ax2.set_ylabel("Tip rate (%)", color=PALETTE["red_strong"])
    ax2.tick_params(axis="y", colors=PALETTE["red_strong"])
    ax2.spines["right"].set_color(PALETTE["red_strong"])
    ax2.set_ylim(0, 32)
    panel_label(ax, "d", x=-0.3)
    save(fig, "analytics_L.pdf")


# ---------------------------------------------------------------- scaling
def scaling(job="routes"):
    g = pd.read_csv(os.path.join(ROOT, "results", "summary.csv"))
    g = g[(g.env == "local-docker") & (g.job == job)]
    c = pd.read_csv(os.path.join(ROOT, "results", "cache", "cache_runs.csv"))
    c = c[(c.job == job) & (c.tier == "L") & (c["mode"] == "warm")].groupby(["framework", "nodes"]).seconds.mean()

    fig, axes = plt.subplots(2, 4, figsize=(7.16, 2.75), gridspec_kw=dict(hspace=0.42, wspace=0.32))
    for col, (tier, months) in enumerate(TIERS):
        d = g[g.tier == tier]
        at, asp = axes[0, col], axes[1, col]
        nodes = sorted(d[d.framework != "serial"].nodes.unique())
        for fw, (colr, mk, ls, lab) in ENGINE.items():
            s = d[d.framework == fw].sort_values("nodes")
            if s.empty:
                continue
            at.errorbar(s.nodes, s["mean"], yerr=s["std"], color=colr, marker=mk, ls=ls, capsize=1.5,
                        elinewidth=0.6, mfc="white" if fw == "mr_nocombiner" else colr)
            asp.plot(s.nodes, s.speedup_rel, color=colr, marker=mk, ls=ls,
                     mfc="white" if fw == "mr_nocombiner" else colr)
            if tier == "L" and fw in ("mr", "spark_df"):          # rerun of the cache experiment
                rr = c.loc[fw]
                at.plot(rr.index, rr.values, ls="none", marker="D", ms=3.4, mfc="none", mec=colr, mew=0.8)
                asp.plot(rr.index, rr.loc[1] / rr.values, ls=":", lw=0.8, marker="D", ms=3.4,
                         mfc="none", mec=colr, color=colr, mew=0.8)
        ser = d[d.framework == "serial"]
        if not ser.empty:
            at.axhline(ser["mean"].iloc[0], color=PALETTE["grey"], lw=0.8, ls=":")
        asp.plot([1, max(nodes)], [1, max(nodes)], color=PALETTE["neutral"], lw=0.9, zorder=0)
        at.set_title(f"Tier {tier} ({months})", pad=3)
        for ax in (at, asp):
            ax.set_xticks(nodes)
            ax.set_xlim(0.7, max(nodes) + 0.3)
        asp.set_xlabel("Workers $N$")
        asp.set_ylim(0.5, 4.3)
        at.set_ylim(bottom=0)
    axes[0, 0].set_ylabel("Run time (s)")
    axes[1, 0].set_ylabel("Speedup $T_1/T_N$")
    panel_label(axes[0, 0], "a", x=-0.3)
    panel_label(axes[1, 0], "b", x=-0.3)
    h = [Line2D([], [], color=v[0], marker=v[1], ls=v[2], mfc="white" if k == "mr_nocombiner" else v[0],
                label=v[3]) for k, v in ENGINE.items()]
    h += [Line2D([], [], color=PALETTE["grey"], ls=":", lw=0.8, label="Serial Python"),
          Line2D([], [], color=PALETTE["neutral"], lw=0.9, label="Linear speedup"),
          Line2D([], [], color=PALETTE["dark"], ls="none", marker="D", mfc="none", ms=3.4, mew=0.8,
                 label="Rerun of tier L")]
    fig.legend(handles=h, loc="lower center", ncol=7, bbox_to_anchor=(0.5, 0.965), handlelength=2.2,
               columnspacing=1.1, handletextpad=0.5)
    save(fig, f"scaling_{job}.pdf")


# ---------------------------------------------------------------- weak scaling
WEAK = {1: "W3", 2: "M", 3: "W9", 4: "L"}


def weak():
    g = pd.read_csv(os.path.join(ROOT, "results", "summary.csv"))
    g = g[(g.env == "local-docker") & (g.framework != "serial")]
    rows = []
    for (fw, job), d in g.groupby(["framework", "job"]):
        t1 = d[(d.nodes == 1) & (d.tier == "W3")]["mean"]
        for n, tier in WEAK.items():
            tn = d[(d.nodes == n) & (d.tier == tier)]["mean"]
            if len(t1) and len(tn):
                rows.append((fw, job, n, t1.iloc[0] / tn.iloc[0]))
    w = pd.DataFrame(rows, columns=["fw", "job", "n", "eff"])
    fig, ax = plt.subplots(figsize=(3.4, 1.55))
    for fw, (colr, mk, ls, lab) in ENGINE.items():
        s = w[w.fw == fw].groupby("n").eff.agg(["mean", "min", "max"])
        ax.fill_between(s.index, s["min"], s["max"], color=colr, alpha=0.06, lw=0)
        ax.plot(s.index, s["mean"], color=colr, marker=mk, ls=ls, label=lab,
                mfc="white" if fw == "mr_nocombiner" else colr)
    ax.axhline(1, color=PALETTE["neutral"], lw=0.9, zorder=0)
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xticklabels(["1\n(3 mo.)", "2\n(6 mo.)", "3\n(9 mo.)", "4\n(12 mo.)"])
    ax.set_xlabel("Workers (data)")
    ax.set_ylabel("Weak-scaling efficiency")
    ax.set_ylim(0.5, 1.05)
    ax.legend(loc="lower left", ncol=2, handlelength=2.2, columnspacing=1.0)
    save(fig, "weak_scaling.pdf")


# ---------------------------------------------------------------- combiner + cloud
def combiner_cloud():
    cnt = pd.read_csv(os.path.join(ROOT, "results", "counters.csv"))
    cnt = cnt[(cnt.tier == "L") & (cnt.env == "local-docker")]
    m = cnt.groupby(["job", "framework"]).reduce_shuffle_bytes.mean().unstack() / 2**20
    g = pd.read_csv(os.path.join(ROOT, "results", "summary.csv"))
    g = g[(g.tier == "L") & g.nodes.isin([1, 2])]
    tot = g.groupby(["env", "framework", "nodes"])["mean"].sum()

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(3.45, 1.6), gridspec_kw=dict(wspace=0.55, width_ratios=[1, 1.15]))
    jobs = ["demand", "routes", "fare"]
    x = np.arange(len(jobs))
    w = 0.36
    a1.bar(x - w / 2, m.loc[jobs, "mr_nocombiner"], w, color=PALETTE["red_2"], label="no combiner", linewidth=0)
    a1.bar(x + w / 2, m.loc[jobs, "mr"], w, color=PALETTE["red_strong"], label="combiner", linewidth=0)
    a1.set_yscale("log")
    a1.set_ylim(5e-3, 3e4)
    for xi, j in zip(x, jobs):
        red = m.loc[j, "mr_nocombiner"] / m.loc[j, "mr"]
        a1.text(xi, m.loc[j, "mr_nocombiner"] * 1.6, f"{red:,.0f}×".replace(",", " "),
                ha="center", fontsize=6)
    a1.set_xticks(x)
    a1.set_xticklabels(jobs)
    a1.set_ylabel("Shuffled data (MiB)")
    a1.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, handlelength=1.0, columnspacing=0.8, borderaxespad=0.1)
    panel_label(a1, "a", x=-0.38, y=1.17)

    fws = ["mr", "mr_nocombiner", "spark_rdd", "spark_df"]
    names = ["MR", "MR-nc", "RDD", "DF"]
    x = np.arange(len(fws))
    for off, env, colr, lab in [(-w / 2, "local-docker", PALETTE["neutral"], "1 host, 2 containers"),
                                (w / 2, "azure", PALETTE["blue_main"], "Azure, 2 VMs")]:
        s = [tot[(env, fw, 1)] / tot[(env, fw, 2)] for fw in fws]
        a2.bar(x + off, s, w, color=colr, label=lab, linewidth=0)
    a2.axhline(2, color=PALETTE["grey"], lw=0.8, ls=":")
    a2.text(len(fws) - 0.5, 2.03, "linear", ha="right", va="bottom", fontsize=6, color=PALETTE["grey"])
    a2.set_xticks(x)
    a2.set_xticklabels(names)
    a2.set_ylim(0, 2.2)
    a2.set_ylabel("Speedup $T_1/T_2$")
    a2.legend(loc="lower left", bbox_to_anchor=(-0.1, 1.0), ncol=1, handlelength=1.0, borderaxespad=0.1)
    panel_label(a2, "b", x=-0.3, y=1.17)
    save(fig, "combiner_cloud.pdf")


if __name__ == "__main__":
    analytics()
    scaling()
    weak()
    combiner_cloud()

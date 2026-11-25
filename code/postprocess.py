#!/usr/bin/env python3
"""Turn raw "<key>\t<sums>" job output into human-readable result tables.

  python3 postprocess.py --job routes --zones taxi_zone_lookup.csv \
      --top 10 results/out/routes.tsv > results/tables/routes_top10.csv

demand : busiest zone/hour pairs, and total trips per hour of day
routes : top-N pickup->dropoff zone pairs
fare   : per distance bucket: trips, average fare, credit-card tip rate
"""
import argparse
import csv
import sys
from collections import defaultdict


def load_zones(path):
    if not path:
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {int(r["LocationID"]): f'{r["Zone"]} ({r["Borough"]})'
                for r in csv.DictReader(f)}


def read_output(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            key, _, val = line.rstrip("\n").partition("\t")
            if val:
                yield key, [float(x) for x in val.split(",")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True, choices=["demand", "routes", "fare"])
    ap.add_argument("--zones", help="taxi_zone_lookup.csv (optional)")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("output")
    a = ap.parse_args()
    zones = load_zones(a.zones)
    zname = lambda z: zones.get(int(z), f"zone {int(z)}")
    w = csv.writer(sys.stdout)

    rows = list(read_output(a.output))
    if a.job == "routes":
        rows.sort(key=lambda kv: -kv[1][0])
        w.writerow(["rank", "pickup_zone", "dropoff_zone", "trips"])
        for i, (k, v) in enumerate(rows[: a.top], 1):
            pu, do = k.split("|")
            w.writerow([i, zname(pu), zname(do), int(v[0])])
    elif a.job == "demand":
        per_hour = defaultdict(int)
        for k, v in rows:
            per_hour[int(k.split("|")[1])] += int(v[0])
        w.writerow(["hour", "trips"])
        for h in range(24):
            w.writerow([h, per_hour[h]])
        w.writerow([])
        rows.sort(key=lambda kv: -kv[1][0])
        w.writerow(["rank", "zone", "hour", "trips"])
        for i, (k, v) in enumerate(rows[: a.top], 1):
            z, h = k.split("|")
            w.writerow([i, zname(z), int(h), int(v[0])])
    else:
        w.writerow(["distance_bucket", "trips", "avg_fare_usd", "cc_share", "cc_tip_rate"])
        for k, (n, fare, cc_n, cc_fare, cc_tip) in sorted(rows):
            w.writerow([k, int(n), f"{fare / n:.2f}", f"{cc_n / n:.3f}",
                        f"{cc_tip / cc_fare:.3f}" if cc_fare else ""])


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Download NYC TLC Yellow Taxi trip records and convert them to CSV.

  python scripts/prepare_data.py                 # all months needed by the tiers
  python scripts/prepare_data.py --tiers S       # only what tier S needs

Source: NYC Taxi & Limousine Commission, TLC Trip Record Data
        https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
Files : data/raw/yellow_tripdata_YYYY-MM.parquet  (downloaded, ~50 MB/month)
        data/csv/YYYY-MM.csv                       (8 columns, no header)
        data/csv/<TIER>.list                       (month files in each tier)
        data/csv/taxi_zone_lookup.csv              (zone id -> name)

Parquet is converted to plain CSV because Hadoop Streaming feeds mappers
line-oriented text; keeping only the 8 columns the jobs use also makes the
input format explicit.
"""
import argparse
import os
import sys
import urllib.request

BASE = "https://d37ci6vzurychx.cloudfront.net"
ZONES_URL = f"{BASE}/misc/taxi_zone_lookup.csv"

# Dataset size tiers (months of 2023-2024 data). Edit here only.
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2023) for m in range(1, 13)]
TIERS = {"S": MONTHS[:1], "M": MONTHS[:6], "L": MONTHS[:12], "XL": MONTHS[:24],
         # weak scaling: 3 months of data per worker (M = 6 months for 2, L = 12 for 4)
         "W3": MONTHS[:3], "W9": MONTHS[:9]}

COLUMNS = ["tpep_pickup_datetime", "PULocationID", "DOLocationID", "trip_distance",
           "fare_amount", "tip_amount", "total_amount", "payment_type"]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
CSV = os.path.join(ROOT, "data", "csv")


def download(url, dest):
    if os.path.exists(dest):
        return
    print(f"download {url}", flush=True)
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "cst435-assignment"})
    with urllib.request.urlopen(req) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    os.replace(tmp, dest)


def convert(parquet_path, csv_path):
    """Parquet -> 8-column CSV. Returns the number of rows written."""
    import pandas as pd
    df = pd.read_parquet(parquet_path, columns=COLUMNS)
    df["tpep_pickup_datetime"] = df["tpep_pickup_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["payment_type"] = df["payment_type"].astype("Int64")  # keep missing values empty
    tmp = csv_path + ".part"
    df.to_csv(tmp, header=False, index=False)
    os.replace(tmp, csv_path)
    return len(df)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", nargs="+", default=list(TIERS), choices=list(TIERS))
    a = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(CSV, exist_ok=True)

    download(ZONES_URL, os.path.join(CSV, "taxi_zone_lookup.csv"))
    needed = sorted({m for t in a.tiers for m in TIERS[t]})
    stats = []
    for month in needed:
        pq = os.path.join(RAW, f"yellow_tripdata_{month}.parquet")
        out = os.path.join(CSV, f"{month}.csv")
        download(f"{BASE}/trip-data/yellow_tripdata_{month}.parquet", pq)
        if not os.path.exists(out):
            rows = convert(pq, out)
            print(f"convert {month}: {rows:,} rows", flush=True)
        stats.append((month, os.path.getsize(out)))

    sizes = dict(stats)
    for tier in a.tiers:
        with open(os.path.join(CSV, f"{tier}.list"), "w", newline="\n") as f:
            f.write("\n".join(f"{m}.csv" for m in TIERS[tier]) + "\n")
        total = sum(sizes[m] for m in TIERS[tier])
        print(f"tier {tier}: {len(TIERS[tier])} months, {total / 2**30:.2f} GiB")


if __name__ == "__main__":
    sys.exit(main())

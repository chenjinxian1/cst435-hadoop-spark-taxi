#!/usr/bin/env python3
"""Hadoop Streaming mapper for NYC taxi trip analytics.

Usage (Hadoop Streaming):  mapper.py <job>
       where <job> is one of: demand | routes | fare

Input : CSV lines produced by scripts/prepare_data.py, columns
        pickup_datetime,pu_location,do_location,trip_distance,
        fare_amount,tip_amount,total_amount,payment_type
Output: "<key>\t<v1,v2,...>" where every value is a numeric vector.
        All jobs emit vectors that are combined by element-wise SUM, so the
        same reducer.py works as both combiner and reducer.

Jobs
  demand : key = "<zone>|<hour>"      value = [trips]
  routes : key = "<pu_zone>|<do_zone>" value = [trips]
  fare   : key = "<distance_bucket>"  value = [trips, fare_sum, cc_trips,
                                                cc_fare_sum, cc_tip_sum]
           (tips are only recorded for credit-card trips, payment_type == 1)
"""
import sys

# Distance buckets in miles: [lower, upper) -> label
DISTANCE_BUCKETS = [
    (0, 1, "00-01mi"), (1, 2, "01-02mi"), (2, 5, "02-05mi"),
    (5, 10, "05-10mi"), (10, 20, "10-20mi"), (20, 100, "20-100mi"),
]

MAX_DISTANCE = 100.0   # miles; longer trips are treated as data errors
MAX_FARE = 1000.0      # USD
N_COLS = 8


def distance_bucket(d):
    for lo, hi, label in DISTANCE_BUCKETS:
        if lo <= d < hi:
            return label
    return None


def parse(line):
    """Parse and validate one CSV line. Returns a tuple or None if invalid."""
    parts = line.rstrip("\r\n").split(",")
    if len(parts) != N_COLS:
        return None
    try:
        dt = parts[0]                      # "YYYY-MM-DD HH:MM:SS"
        hour = int(dt[11:13])
        pu = int(parts[1])
        do = int(parts[2])
        dist = float(parts[3])
        fare = float(parts[4])
        tip = float(parts[5])
        payment = int(float(parts[7])) if parts[7] else 0
    except (ValueError, IndexError):
        return None                        # header line or malformed record
    if not (0 <= hour <= 23 and 1 <= pu <= 265 and 1 <= do <= 265):
        return None
    if not (0 < dist < MAX_DISTANCE and 0 < fare < MAX_FARE and tip >= 0):
        return None
    return hour, pu, do, dist, fare, tip, payment


def map_record(job, rec):
    """Yield (key, vector) pairs for one parsed record."""
    hour, pu, do, dist, fare, tip, payment = rec
    if job == "demand":
        yield f"{pu:03d}|{hour:02d}", (1,)
    elif job == "routes":
        yield f"{pu:03d}|{do:03d}", (1,)
    elif job == "fare":
        bucket = distance_bucket(dist)
        if bucket is not None:
            cc = payment == 1
            yield bucket, (1, fare, int(cc), fare if cc else 0.0, tip if cc else 0.0)
    else:
        raise ValueError(f"unknown job: {job}")


def fmt(vec):
    return ",".join(str(v) if isinstance(v, int) else f"{v:.2f}" for v in vec)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: mapper.py demand|routes|fare")
    job = sys.argv[1]
    out = sys.stdout.write
    for line in sys.stdin:
        rec = parse(line)
        if rec is None:
            continue
        for key, vec in map_record(job, rec):
            out(f"{key}\t{fmt(vec)}\n")


if __name__ == "__main__":
    main()

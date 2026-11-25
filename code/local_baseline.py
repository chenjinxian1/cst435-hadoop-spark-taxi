#!/usr/bin/env python3
"""Single-process, non-distributed baseline (the "single computer" case).

  python3 local_baseline.py --job demand --output out.tsv data/csv/S/*.csv

Uses exactly the same parse()/map_record() as the Hadoop mapper but
aggregates in an in-memory dict instead of sort + shuffle. This is how a
programmer would solve the task on one machine without any framework, and
it gives the T_serial reference used for speedup calculations.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mapper  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True, choices=["demand", "routes", "fare"])
    ap.add_argument("--output", required=True)
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()

    acc = {}
    for path in a.files:
        with open(path, encoding="utf-8") as f:
            for line in f:
                rec = mapper.parse(line)
                if rec is None:
                    continue
                for key, vec in mapper.map_record(a.job, rec):
                    cur = acc.get(key)
                    if cur is None:
                        acc[key] = list(vec)
                    else:
                        for i, v in enumerate(vec):
                            cur[i] += v

    with open(a.output, "w", encoding="utf-8") as f:
        for key in sorted(acc):
            f.write(f"{key}\t{mapper.fmt(acc[key])}\n")


if __name__ == "__main__":
    main()

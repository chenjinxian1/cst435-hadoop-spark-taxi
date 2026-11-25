#!/usr/bin/env python3
"""Check that different frameworks produced the same answer.

  python scripts/compare_outputs.py results/outputs/serial-routes-S.tsv \
                                    results/outputs/mr-routes-S.tsv ...

The first file is the reference. Keys must match exactly; numeric values
must agree within 0.01 absolute or 1e-9 relative (float summation order
differs between frameworks). Exit code 1 if any file disagrees.
"""
import math
import sys


def load(path):
    d = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            k, _, v = line.rstrip("\n").partition("\t")
            if v:
                d[k] = [float(x) for x in v.split(",")]
    return d


def same(a, b):
    return len(a) == len(b) and all(
        math.isclose(x, y, rel_tol=1e-9, abs_tol=0.011) for x, y in zip(a, b))


def main(paths):
    if len(paths) < 2:
        sys.exit(__doc__)
    ref = load(paths[0])
    ok = True
    for p in paths[1:]:
        other = load(p)
        missing = ref.keys() - other.keys()
        extra = other.keys() - ref.keys()
        diff = [k for k in ref.keys() & other.keys() if not same(ref[k], other[k])]
        good = not (missing or extra or diff)
        ok &= good
        print(f"{'MATCH' if good else 'DIFF '} {p}: {len(other)} keys"
              + ("" if good else f", missing={len(missing)} extra={len(extra)} different={len(diff)}"
                 + (f" e.g. {diff[0]}: {ref[diff[0]]} vs {other[diff[0]]}" if diff else "")))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

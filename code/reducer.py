#!/usr/bin/env python3
"""Hadoop Streaming reducer (also used as the combiner).

Input : "<key>\t<v1,v2,...>" lines, sorted by key (guaranteed by the
        MapReduce shuffle phase).
Output: "<key>\t<s1,s2,...>" where s_i is the element-wise sum of all
        vectors seen for that key.

Because addition is associative and commutative, running this script as a
combiner on the map side gives the same final result while shrinking the
amount of data shuffled over the network.
"""
import sys


def parse_vec(s):
    return [float(x) if "." in x else int(x) for x in s.split(",")]


def fmt(vec):
    return ",".join(str(v) if isinstance(v, int) else f"{v:.2f}" for v in vec)


def main():
    out = sys.stdout.write
    current_key, acc = None, None
    for line in sys.stdin:
        key, _, val = line.rstrip("\r\n").partition("\t")
        if not val:
            continue
        vec = parse_vec(val)
        if key == current_key:
            for i, v in enumerate(vec):
                acc[i] += v
        else:
            if current_key is not None:
                out(f"{current_key}\t{fmt(acc)}\n")
            current_key, acc = key, vec
    if current_key is not None:
        out(f"{current_key}\t{fmt(acc)}\n")


if __name__ == "__main__":
    main()

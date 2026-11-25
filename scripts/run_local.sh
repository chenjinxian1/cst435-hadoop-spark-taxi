#!/usr/bin/env bash
# Run the full local experiment plan and keep a log (Git Bash on Windows).
#   "C:\Program Files\Git\bin\bash.exe" scripts/run_local.sh
# Safe to re-run: finished runs are skipped.
export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"
cd "$(dirname "$0")/.."
mkdir -p results
scripts/run_benchmark.sh experiments/local.plan 2>&1 | tee -a results/local-run.log

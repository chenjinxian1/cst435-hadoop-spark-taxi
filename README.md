# CST435 Assignment 2: NYC Taxi Analytics with Hadoop MapReduce and Spark on a Docker Cluster

Universiti Sains Malaysia (USM), CST435 Parallel and Cloud Computing, Semester 1, 2026/2027, Assignment 2.

We deploy Hadoop and Spark as a cluster of Docker containers and use it to analyse the yellow-taxi trip records published by the New York City Taxi and Limousine Commission (TLC). The same Python code runs in five ways: Hadoop Streaming (with and without a combiner), Spark RDD, Spark DataFrame and a single-process serial program. We compare a single computer (one container) with multiple containers, and repeat the study on several virtual machines in Microsoft Azure.

## Team and responsibilities

| Member | Responsibilities |
|---|---|
| Chen Jinxian | Team lead; cluster infrastructure (Docker image, Compose file, Hadoop/YARN configuration, resource caps); report editing |
| Yang Ye | Algorithms: mapper, reducer/combiner, PySpark jobs, serial baseline, correctness checks |
| Gong Pengxiang | Data and benchmarking: data preparation, benchmark and cache-experiment scripts, figures |
| Ma Jiajun | Cloud deployment on Azure, cloud measurements, demonstration video |

## The three analytics jobs

| Job | Question | Key → value |
|---|---|---|
| `demand` | How many trips start in each zone in each hour of the day? | pickup zone \| hour → trip count |
| `routes` | Which pickup → drop-off routes are travelled most? | pickup zone \| drop-off zone → trip count |
| `fare` | What are the average fare and the credit-card tip rate per distance band? | distance band → (trips, fare, card trips, card fare, tip) |

Every value is a numeric vector and the reducer only sums vectors element-wise, so the same `reducer.py` works both as the reducer and as the combiner.

## Main findings

- **Small data does not pay off.** On one month of data (about 3 million rows) the clusters are 4–6× slower than a single Python process; almost all of the time is job and JVM start-up.
- **Large data does.** On two years of data (79.5 million rows, 3.7 GB), four workers are up to 4.0× faster than one, and Spark DataFrame is up to 5.1× faster than the serial program.
- **Combiner.** It reduces the shuffled data by two to five orders of magnitude, but only the shuffle-heavy `fare` job becomes clearly faster.
- **Cloud vs. single host.** Each Azure vCPU is slower than the local machine, but two VMs scale more regularly than two containers on one host, because each VM has its own CPUs, disk and network interface.
- **Correctness.** For every engine, data tier and cluster size, the output matches the serial baseline.

The full analysis, figures and tables are in the report, `report/main.pdf` (build it as described below).

## Repository layout

| Path | Contents |
|---|---|
| `code/mapper.py` | Parses and cleans each record and emits key–value pairs; shared by all three jobs |
| `code/reducer.py` | Sums the vectors of each key element-wise; used as both combiner and reducer |
| `code/spark_job.py` | PySpark version: `--api rdd` reuses the mapper functions, `--api df` implements the same logic in Spark SQL |
| `code/local_baseline.py` | Single-process serial baseline (the "single computer" reference) |
| `code/postprocess.py` | Turns the raw output into result tables (top-N routes, hourly demand, fare and tip rate) |
| `cluster/` | Dockerfile, `docker-compose.yml`, `entrypoint.sh` and the Hadoop/Spark configuration files |
| `cloud/` | Azure scripts: `azure_create.sh` creates/deletes the resources, `deploy.sh` deploys, `cluster-cloud.sh` starts the cluster, `collect.sh` fetches the results |
| `scripts/prepare_data.py` | Downloads the TLC Parquet files, converts them to CSV and builds the data tiers S, W3, M, W9, L and XL |
| `scripts/cluster.sh` | Local cluster control: `up N` / `load TIER` / `status` / `down` |
| `scripts/run_job.sh` | Runs and times one job inside the master container |
| `scripts/run_benchmark.sh`, `scripts/run_local.sh` | Run a whole experiment plan and append to `results/benchmark.csv`; can resume after an interruption |
| `scripts/compare_outputs.py` | Checks that the outputs of all engines are identical |
| `scripts/cache_experiment.sh`, `scripts/cgroup_probe.sh` | Cache experiment: runs with a dropped and a warm page cache, recording disk reads and CPU throttling |
| `scripts/plot_results.py`, `scripts/report_figures.py`, `scripts/data_figure.py`, `scripts/plot_cache.py` | Summarise the results and generate the figures and LaTeX tables of the report |
| `experiments/` | Experiment plans: `local.plan` and `cloud.plan` |
| `results/` | Measurements: `benchmark.csv` (every run), `summary.csv` (means), `counters.csv` (Hadoop counters), `azure/` (cloud runs), `cache/` (cache experiment), `tables/` (analytics results) |
| `docs/experiments.md` | Experiment design |
| `report/` | LaTeX report (IEEEtran, two columns) |

The raw data (about 5 GB) are not in the repository; `scripts/prepare_data.py` downloads them again.

## Environment

- Local host: Intel Core i5-13600KF (20 threads), 32 GB RAM, Windows 11 with Docker Desktop (WSL 2 back end).
- Software: Ubuntu 22.04, OpenJDK 11, Python 3.10, Hadoop 3.4.1, Spark 3.5.5 on YARN.
- Each worker container is capped at 2 CPUs and 5 GB of memory, and YARN advertises exactly 2 vcores and 3584 MB. One worker is therefore one small machine, and adding a worker adds a fixed amount of compute.
- Cloud: Azure Korea Central, one master (Standard_D2_v4) and two workers (Standard_D2s_v4), each with 2 vCPUs and 8 GB RAM, running the same Docker image.

## How to reproduce

1. Install Docker Desktop with the WSL 2 back end and raise the WSL memory limit in `%UserProfile%\.wslconfig`. The default (half of the host RAM) is too small for a master and four workers:
   ```ini
   [wsl2]
   memory=26GB
   processors=16
   ```
   Then run `wsl --shutdown` and restart Docker Desktop.
2. Prepare the data (needs Python with pandas and pyarrow):
   ```powershell
   python scripts/prepare_data.py --tiers S      # start with one month
   ```
3. Smoke test (in Git Bash):
   ```bash
   scripts/cluster.sh up 2
   scripts/cluster.sh load S
   docker exec master /opt/scripts/run_job.sh mr routes S 2
   docker exec master /opt/scripts/run_job.sh spark_rdd routes S 2
   docker exec master /opt/scripts/run_job.sh serial routes S 1
   python scripts/compare_outputs.py results/outputs/serial-routes-S.tsv results/outputs/mr-routes-S.tsv results/outputs/spark_rdd-routes-S.tsv
   ```
   Web interfaces: HDFS <http://localhost:9870>, YARN <http://localhost:8088>, JobHistory <http://localhost:19888>.
4. Full local benchmark (about 10 hours; it can be interrupted, and running the same command again resumes it):
   ```bash
   scripts/run_local.sh
   python scripts/plot_results.py --csv results/benchmark.csv,results/azure/benchmark.csv
   python scripts/report_figures.py
   ```
5. Cloud experiment: see [docs/experiments.md](docs/experiments.md).
6. Build the report: run `latexmk -pdf main.tex` in `report/`, or upload the repository to Overleaf with `report/main.tex` as the main file. The appendix listings are read directly from `code/`.

## Notes for Windows

- When Git Bash calls `docker`, set `MSYS_NO_PATHCONV=1`; otherwise paths such as `/opt/scripts` are rewritten into Windows paths (the scripts already do this).
- Right after installing Docker, terminals that were already open cannot find `docker`; open a new terminal.
- Before using the Azure CLI in Git Bash, run `export PATH="/c/Program Files/Microsoft SDKs/Azure/CLI2/wbin:$PATH"`.

## Data source

NYC Taxi and Limousine Commission (TLC) Trip Record Data: <https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page>. We use the yellow-taxi records from January 2023 to December 2024.

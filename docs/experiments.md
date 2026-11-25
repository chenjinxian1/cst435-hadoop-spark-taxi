# Experiment design

This document describes how the "single computer vs. multiple computers" comparison required by the assignment was carried out, and which figure or table of the report each experiment feeds.
The experiment plans are in `experiments/*.plan` and are executed by `scripts/run_benchmark.sh`, which resumes after an interruption.
In total we ran 561 timed runs locally and 225 on Azure, all successful, plus 48 runs of the cache experiment.

## Research questions

| ID | Question | Experiment |
|---|---|---|
| Q1 | Do more nodes make the jobs faster? What are the speedup and efficiency? | E1 strong scaling |
| Q2 | How large must the data be before distribution pays off? | E1 + E2 data size |
| Q3 | How much shuffle does the combiner save, and how much time? | E3 combiner |
| Q4 | Does the run time stay constant when the data per node is fixed? | E4 weak scaling |
| Q5 | How do real machines on a network differ from containers on one host? | E5 cloud |
| Q6 | Which is fastest: MapReduce, Spark RDD or Spark DataFrame, and why? | engine comparison in all experiments |

## Environments

| Environment | Nodes | Resources per worker | Network |
|---|---|---|---|
| `local-docker` | 1 master container + 1–4 worker containers, all on one i5-13600KF host | 2 CPUs / 5 GB (cgroup limits); YARN 2 vcores / 3584 MB | Docker bridge inside one host |
| `azure` | 1 master VM + 1–2 worker VMs (Korea Central) | D2s_v4: 2 vCPUs / 8 GB; YARN also 2 vcores / 3584 MB | Azure virtual network between machines |

Both environments use the same image (Hadoop 3.4.1, Spark 3.5.5, Python 3.10) and the same YARN resources, so at the same N the differences come mainly from the network and the hardware.

Only three VMs were possible because of the student subscription: at most 6 vCPUs per region and 4 vCPUs per VM family.

## Experiments

### E1 Strong scaling (local)
- Fixed data size, N = 1, 2, 3, 4 workers.
- Data tiers: S (1 month), M (6 months), L (12 months).
- Engines: `mr`, `mr_nocombiner`, `spark_rdd`, `spark_df`; at N = 1 also `serial` as the single-process baseline.
- 3 jobs × 3 repetitions.
- **Metrics:**
  - wall-clock time, mean ± standard deviation;
  - relative speedup S = T₁/Tₙ;
  - efficiency E = S/N;
  - absolute speedup T_serial/Tₙ;
  - Karp–Flatt serial fraction e.
- **Report:** runtime/speedup figure and summary table.

### E2 Data size (local)
- Tier XL (24 months, 3.7 GB), N = 1 and N = 4 only.
- Engines: `mr`, `spark_df` and `serial`; 2 repetitions each.
- Together with S/M/L from E1, this gives the time-vs-size curve and the size at which the cluster starts to beat the serial program.

### E3 Combiner (local + cloud)
- Compares `mr` with `mr_nocombiner`.
- Hadoop counters are recorded automatically in `results/counters.csv`:
  - number of map tasks;
  - map output records;
  - combiner output records;
  - reduce shuffle bytes.
- Result: the combiner reduces the shuffled data by two to five orders of magnitude (on tier S, `fare` drops from 87 MB to 716 B). On tier L, `fare` becomes 24% faster locally and 29% faster on Azure; the other two jobs gain only a few percent.

### E4 Weak scaling (local)
- Each worker gets three months of data:
  - N=1 → W3 (3 months)
  - N=2 → M (6 months)
  - N=3 → W9 (9 months)
  - N=4 → L (12 months)
- Weak-scaling efficiency = T(1, W3) / T(N, 3N months); the ideal value is 1.
- Only W3@1 and W9@3 are extra runs; the other combinations reuse E1.

### E5 Real machines in the cloud (Azure)
- N = 1, 2.
- Data tiers: S, M, L.
- Engines: `mr`, `spark_rdd`, `spark_df`, `serial`; on M/L also `mr_nocombiner`.
- 3 repetitions.
- Compared directly with the local runs at the same N, tier and engine, to see how a real network differs from containers on one host:
  - HDFS data are read and written across machines;
  - the shuffle goes over the network;
  - each worker has the 2 vCPUs of its own VM and does not compete with other workers.

## Controls and reproducibility
- The cluster is rebuilt from scratch (HDFS reformatted) for every N. HDFS replication is 1, and only one data tier is kept at a time so that the disk does not fill up.
- Timing covers job submission to job completion, including fixed costs such as YARN and JVM start-up. Loading data into HDFS and copying data for the serial baseline are not timed.
- Every run's output is checked with `scripts/compare_outputs.py` against the serial result.
- The 3 repetitions of a configuration run back to back, so the first may be slower with a cold cache. A separate cache experiment (`scripts/cache_experiment.sh`) showed that cold and warm runs differ by less than 5 seconds, so the page cache is not the main factor.
- Known limits of the local set-up (discussed in the report):
  - the CPU limit is a cgroup quota, not pinned cores, so a worker may run on efficiency cores or share hyper-threads;
  - all workers share one disk and the same memory bandwidth.

## How to run
```bash
# Local (Git Bash); about 10 hours, can be interrupted, the same command resumes
"C:\Program Files\Git\bin\bash.exe" scripts/run_local.sh

# Cloud
cloud/azure_create.sh            # create the 3 VMs
cloud/deploy.sh                  # sync code, build the image, prepare the data
ssh -i ~/.ssh/cst435_azure azureuser@<master-ip> \
  'cd cst435 && nohup env CLUSTER_SH=cloud/cluster-cloud.sh ENV_LABEL=azure scripts/run_benchmark.sh experiments/cloud.plan > results/cloud-run.log 2>&1 &'
# afterwards copy the results back, then delete all cloud resources
scp -r -i ~/.ssh/cst435_azure azureuser@<master-ip>:cst435/results results/azure
cloud/azure_create.sh delete
```

## Actual time and cost
| Part | Runs | Time | Cost |
|---|---|---|---|
| Local E1–E4 | 561 | about 10 hours (interrupted several times by host restarts and resumed) | 0 |
| Cloud E5 | 225 | about 11 hours including deployment | 3 VMs plus public IPs and disks, about US$0.38/hour; about US$4 in total (estimated from list prices, paid from the student credit) |
| Cache experiment | 48 | see `results/cache/cache-run.log` | 0 |

# 总体实验设计

本文档记录作业要求的"单机 vs 多机性能对比"具体怎么做，以及每个实验对应报告里的哪张图、哪张表。
计划文件放在 `experiments/*.plan`，由 `scripts/run_benchmark.sh` 执行。脚本支持断点续跑。

## 研究问题

| 编号 | 问题 | 回答它的实验 |
|---|---|---|
| Q1 | 节点越多越快吗？加速比和效率是多少？ | E1 强扩展 |
| Q2 | 数据要多大，分布式才划算？ | E1 + E2 数据规模 |
| Q3 | Combiner 能减少多少 shuffle？对时间有多大影响？ | E3 combiner |
| Q4 | 每个节点的数据量不变时，时间能保持不变吗？ | E4 弱扩展 |
| Q5 | 真实网络上的多台机器，和单机上的多容器有什么不同？ | E5 云上 |
| Q6 | MapReduce、Spark RDD、Spark DataFrame 谁快？快在哪里？ | 所有实验的引擎对比 |

## 环境

| 环境 | 节点 | 每个 worker 的资源 | 网络 |
|---|---|---|---|
| `local-docker` | 1 个 master 容器 + 1–4 个 worker 容器，全在一台 i5-13600KF 主机上 | 2 CPU / 5 GB（cgroup 限制），YARN 2 vcores / 3584 MB | Docker bridge，同一台主机内部 |
| `azure` | 1 台 master VM + 1–2 台 worker VM（koreacentral） | D2s_v4：2 vCPU / 8 GB，YARN 同样是 2 vcores / 3584 MB | Azure VNet，真实跨机网络 |

两个环境用的是同一个镜像（Hadoop 3.4.1、Spark 3.5.5、Python 3.10），YARN 的资源配置也相同。
所以在同一 N 下比较，差别主要来自网络和硬件。

云上只能开 3 台 VM，原因是学生订阅限制：每个区域最多 6 vCPU，每个机型家族最多 4 vCPU。

## 实验

### E1 强扩展（本地）
- 固定数据量，worker 数 N = 1, 2, 3, 4。
- 数据档：S（1 个月）、M（6 个月）、L（12 个月）。
- 引擎：`mr`、`mr_nocombiner`、`spark_rdd`、`spark_df`；N=1 时另跑 `serial` 作为单进程基线。
- 3 个任务 × 3 次重复。
- **指标**：
  - 墙钟时间，取均值 ± 标准差；
  - 相对加速比 S = T₁/Tₙ；
  - 效率 E = S/N；
  - 绝对加速比 T_serial/Tₙ；
  - Karp–Flatt 串行比例 e。
- **对应报告**：图 runtime/speedup，表 summary。

### E2 数据规模（本地）
- 在 XL 档（24 个月，3.7 GB）上，只跑 N=1 和 N=4。
- 引擎：`mr`、`spark_df`，另加 `serial`；每组重复 2 次。
- 结合 E1 的 S/M/L，画"时间—数据量"曲线，找出集群开始比串行快的那个数据量（交叉点）。

### E3 Combiner（本地 + 云）
- 比较 `mr` 和 `mr_nocombiner`。
- 计数器自动记录在 `results/counters.csv`：
  - map 任务数；
  - map 输出记录数；
  - combiner 输出记录数；
  - reduce 阶段的 shuffle 字节数。
- S 档已经测过：`fare` 的 shuffle 从 87 MB 降到 716 B，但时间几乎不变。要看它在 M/L 档和真实网络（云上）是否影响时间。

### E4 弱扩展（本地）
- 每个 worker 固定 3 个月的数据：
  - N=1 → W3（3 个月）
  - N=2 → M（6 个月）
  - N=3 → W9（9 个月）
  - N=4 → L（12 个月）
- 弱扩展效率 = T(1, W3) / T(N, 3N 个月)，理想值为 1。
- 只需额外跑 W3@1 和 W9@3，其余组合直接复用 E1 的数据。

### E5 云上真实多机（Azure）
- N = 1, 2。
- 数据档：S、M、L。
- 引擎：`mr`、`spark_rdd`、`spark_df`、`serial`；M/L 档另加 `mr_nocombiner`。
- 重复 3 次。
- 和本地同 N、同数据档、同引擎直接对比，看真实网络与本机多容器的差别：
  - HDFS 数据要跨机读写；
  - shuffle 要走网络；
  - 云上每个 worker 独占一台 VM 的 2 个 vCPU，不和别的 worker 抢 CPU。

## 控制变量与可重复性
- 每换一次 N，都从零重建集群（HDFS 重新格式化）。HDFS 副本数为 1，同一时间只保留一个数据档，避免磁盘占满。
- 计时范围：从提交作业到作业结束，包含 YARN/JVM 启动这类固定开销。数据导入 HDFS 和串行基线的数据拷贝不计时。
- 每次运行都核对输出：`scripts/compare_outputs.py`，以串行结果为参照。
- 同一配置的 3 次重复连续执行，第 1 次可能更慢（缓存还是冷的）。报告里写明这一点，必要时单独讨论。
- 本地实验的已知局限，写进讨论部分：
  - CPU 限制只是 cgroup 配额，没有绑定物理核，worker 可能被调度到 E 核或共用超线程；
  - 所有 worker 共用一块磁盘和同一份内存带宽。

## 运行方式
```bash
# 本地（Git Bash）；约 10 小时，可中断，重跑同一条命令会续上
"C:\Program Files\Git\bin\bash.exe" scripts/run_local.sh

# 云上
cloud/azure_create.sh            # 建 3 台 VM
cloud/deploy.sh                  # 同步代码、构建镜像、准备数据
ssh -i ~/.ssh/cst435_azure azureuser@<master-ip> \
  'cd cst435 && nohup env CLUSTER_SH=cloud/cluster-cloud.sh ENV_LABEL=azure scripts/run_benchmark.sh experiments/cloud.plan > results/cloud-run.log 2>&1 &'
# 跑完后把结果拉回本地，然后删除全部云资源
scp -r -i ~/.ssh/cst435_azure azureuser@<master-ip>:cst435/results results/azure
cloud/azure_create.sh delete
```

## 预计耗时与成本
| 部分 | 运行次数 | 时间 | 成本 |
|---|---|---|---|
| 本地 E1–E4 | 约 600 次 | 约 9–10 小时 | 0 |
| 云上 E5 | 约 200 次 | 约 3–4 小时，加部署约 1 小时 | 3 台 VM × 0.118 美元/小时，加 IP 和磁盘，合计约 0.38 美元/小时，总共约 2 美元 |

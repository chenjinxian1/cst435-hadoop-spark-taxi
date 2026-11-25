# CST435 Assignment 2: NYC 出租车数据分析（Hadoop MapReduce + Spark，Docker 集群）

题目：用 Hadoop Streaming（Python MapReduce）、Spark RDD 和 Spark DataFrame，在 Docker 容器集群上分析 NYC 黄色出租车行程记录。对比单进程、1 个 worker 和 2/3/4 个 worker（以及云上多台 VM）的性能。

截止日期：**2026-12-31（周四）**，在 eLearning 提交报告（≤10 页）。另需录制 ≤15 分钟的演示视频。

## 目录

| 路径 | 内容 |
|---|---|
| `code/mapper.py` | 解析和清洗数据，三个 job（`demand` / `routes` / `fare`）共用 |
| `code/reducer.py` | 按元素求和，同时用作 combiner 和 reducer |
| `code/spark_job.py` | PySpark 版本：`--api rdd`（复用 mapper 的函数）或 `--api df` |
| `code/local_baseline.py` | 单进程串行基线（作业里"单机"的参照） |
| `code/postprocess.py` | 把原始输出转成结果表（Top-N 路线、每小时需求、车费/小费率） |
| `cluster/` | Dockerfile、docker-compose.yml、Hadoop/Spark 配置 |
| `scripts/prepare_data.py` | 下载 TLC parquet 文件，转成 CSV，并生成 S/M/L/XL 四档数据 |
| `scripts/cluster.sh` | `up N` / `load TIER` / `status` / `down` |
| `scripts/run_job.sh` | 在 master 容器里跑一次 job 并计时 |
| `scripts/run_benchmark.sh` | 跑全部实验，追加写入 `results/benchmark.csv` |
| `scripts/compare_outputs.py` | 检查各引擎的输出是否一致 |
| `scripts/plot_results.py` | 生成 `results/summary.csv`、`report/figures/*.pdf` 和 LaTeX 表格 |
| `report/` | LaTeX 报告（IEEEtran 双栏）。用 `\TODO{}` 标出待填内容 |

## 快速开始（Windows 11）

1. 安装 Docker Desktop（WSL 2 后端）。在 `%UserProfile%\.wslconfig` 里调大 WSL 的内存（默认只有主机内存的一半，不够跑 4 个 worker）：
   ```ini
   [wsl2]
   memory=26GB
   processors=16
   ```
   然后执行 `wsl --shutdown`，再重启 Docker Desktop。
2. 准备数据（需要 Python，并装有 pandas 和 pyarrow）：
   ```powershell
   python scripts/prepare_data.py --tiers S      # 先只准备 1 个月的数据
   ```
3. 冒烟测试（在 Git Bash 里运行）：
   ```bash
   scripts/cluster.sh up 2
   scripts/cluster.sh load S
   docker exec master /opt/scripts/run_job.sh mr routes S 2
   docker exec master /opt/scripts/run_job.sh spark_rdd routes S 2
   docker exec master /opt/scripts/run_job.sh serial routes S 1
   python scripts/compare_outputs.py results/outputs/serial-routes-S.tsv results/outputs/mr-routes-S.tsv results/outputs/spark_rdd-routes-S.tsv
   ```
   Web 界面：HDFS <http://localhost:9870>，YARN <http://localhost:8088>，JobHistory <http://localhost:19888>。
4. 正式实验：
   ```bash
   NODES="1 2 3 4" TIERS="S M L" REPS=3 scripts/run_benchmark.sh
   python scripts/plot_results.py
   ```
5. 编译报告：在 `report/` 目录下运行 `latexmk -pdf main.tex`。也可以把整个仓库上传到 Overleaf，主文件设为 `report/main.tex`。附录里的源码直接读自 `code/`。

## 实验设计要点

- **公平性**：每个 worker 都限制为 2 CPU + 5 GB 内存（`docker-compose.yml`），YARN 也只声明 2 vcores 和 3584 MB。这样 "1 个 worker" 才真的等于一台小机器。
- **自变量**：
  - worker 数：1/2/3/4；
  - 数据量：S=1 个月，M=6 个月，L=12 个月，XL=24 个月；
  - 引擎：`mr`、`mr_nocombiner`、`spark_rdd`、`spark_df`、`serial`。
- **指标**：
  - 墙钟时间：均值 ± 标准差，重复 3 次；
  - 相对加速比 T₁/Tₙ 和效率 S/N；
  - 相对串行基线的绝对加速比；
  - Karp–Flatt 串行比例。
- **数据规模（实测，24 个月已全部下载）**：S=2.96M 行/142 MiB，M=20.3M 行/974 MiB，L=41.2M 行/1.93 GiB，XL=79.5M 行/3.72 GiB；清洗丢弃约 3.2–3.6%。每月约 2 个 HDFS block，所以 map 任务数 S≈2、XL≈48。S 档串行约 6 s，可以拿来讨论“数据太小时分布式不划算”；加速效果看 L/XL 档。磁盘占用：data/raw 1.3 GB + data/csv 3.8 GB。
- **正确性**：所有引擎的输出都要用 `compare_outputs.py` 核对一致。
- **云上实验（Azure，koreacentral）**：1 台 master（D2_v4）+ 2 台 worker（D2s_v4），每台 2 vCPU / 8 GB，用同一个镜像、host 网络。
  - 脚本在 `cloud/`：`azure_create.sh` 建/删资源，`deploy.sh` 部署，`cluster-cloud.sh` 启动集群，`collect.sh` 收结果并停机。
  - 完整实验设计见 [docs/experiments.md](docs/experiments.md)。
  - 学生订阅每个区域最多 6 vCPU，所以只开了 3 台。
  - 在 Git Bash 里用 az 前，先执行 `export PATH="/c/Program Files/Microsoft SDKs/Azure/CLI2/wbin:$PATH"`。

## 分工（4 人示例）

| 成员 | 负责 | 报告章节 |
|---|---|---|
| A | 集群：Dockerfile、compose、配置、资源限制 | §2 安装、§4 环境 |
| B | 算法：mapper/reducer、Spark、正确性验证 | §3 算法 |
| C | 数据和实验：数据准备、benchmark、出图 | §5 数据、§6 结果 |
| D | 云部署、统稿、视频 | §4.2 云、§7 讨论、视频 |

## 时间线

| 时间 | 任务 |
|---|---|
| 11/23–11/29 | 装好 Docker，跑通 tier S 的冒烟测试 |
| 11/30–12/06 | 1–4 个 worker 都能稳定运行，全部引擎的结果一致 |
| 12/07–12/13 | 准备 M/L 档数据，搭云集群 |
| 12/14–12/20 | 跑完全部实验，出图 |
| 12/21–12/27 | 写报告、录视频 |
| 12/28–12/31 | 检查页数和 TODO（`grep -rn TODO report/sections`），提交 |

## 已验证 / 未验证

- 已验证（2026-11-23，Docker Desktop 4.100.0）：
  - 镜像能构建；`cluster.sh up 2` 约 2 分钟能起好集群（2 个 DataNode、2 个 NodeManager）。
  - 在真实 S 档数据、2 个 worker 上，5 个引擎 × 3 个 job 全部跑通，输出与串行基线完全一致（`compare_outputs.py` 全部 MATCH）。
  - 单次运行时间：串行约 5 s；MR、Spark 约 20–26 s。S 档里固定开销占了绝大部分。
  - Combiner 的效果（S 档，Reduce shuffle bytes）：`fare` 从 87 MB 降到 716 B，`demand` 从 31.6 MB 降到 110 KB，`routes` 从 34.4 MB 降到 491 KB。
- 已完成（2026-11-25）：
  - 本地 `experiments/local.plan` 561 次运行、Azure `experiments/cloud.plan` 225 次运行全部成功；所有档位、所有引擎的输出都与串行基线一致。
  - `scripts/plot_results.py --csv results/benchmark.csv,results/azure/benchmark.csv` 生成图和 `report/generated/*.tex`。
  - 报告用 MiKTeX 编译通过（`latexmk -pdf main.tex`），共 10 页（正文 7 页 + 源码附录 3 页）。
- 还需团队补充：成员名单、时间线、YARN 界面截图、仓库和视频链接（报告里的红色 TODO）。
- Windows 下的坑：
  - Git Bash 调 docker 时要设 `MSYS_NO_PATHCONV=1`，主机路径要用 `pwd -W`（脚本里已经处理）。
  - 刚装完 Docker 时，旧终端找不到 `docker` 命令，需要重开终端。

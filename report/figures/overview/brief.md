# Brief：系统总览图（FigGenie，systems / architecture）

## 1. 这张图是什么
替换报告第 IV 节现在那张简单的集群拓扑图（Fig. 2）。它是一张**单栏**总览图（约 240 × 170 pt），
画出从原始数据到计时结果的整条流水线，以及它在两种部署上怎么跑。

## 2. 组件（图上的英文标签 · 作用 · 标记）
- **左侧：数据准备**（在集群外）
  - **TLC Parquet (2023–24)**：纽约 TLC 的月度行程文件，标记为 external。
  - **prepare_data.py**：清洗数据，转成 CSV，再切分成 S/M/L/XL 和 W3/W9 各档，标记为 existing。
- **中间：Master 容器**（一个容器框）
  - **NameNode**
  - **ResourceManager**
  - **JobHistory**
  - **run_job.sh / spark-submit**：提交作业。
- **右侧：Worker ×N**（叠成一摞，标注 ×N）。每个 worker 里有：
  - **DataNode**：存 128 MB 的 HDFS 块。
  - **NodeManager**：管理该节点上的容器。
  - **Map/Reduce tasks or Spark executor**：任务或 executor 在这里运行。
  - 框旁注明资源上限：2 CPU · 5 GB。
- **Shared job code**：**mapper.py · reducer.py**，三个分析任务共用的一份 Python 代码。这是全图**唯一的强调色**（我们的贡献）。
  - 用细线连到五种执行方式：**Hadoop Streaming (±combiner)**、**Spark RDD**、**Spark DataFrame**、**Serial Python**。这五个画成一排小标签，不画成大框。
- **底部：两种部署**（两条窄带）
  - **Local: 1 host, Docker bridge, N = 1–4 containers**
  - **Azure: 3 VMs (1 master + 2 workers), N = 1–2**
  - 意思是：同一个 Docker 镜像、同样的配置，跑在两种环境上。
- **右下：结果**
  - **compare_outputs.py**：核对所有方式的输出是否一致。
  - **benchmark CSV → figures**：计时结果汇总成图表。

## 3. 数据流（主路径编号）
1. ① Parquet → prepare_data.py → CSV tiers
2. ② CSV → HDFS：用 `hdfs dfs -put` 上传，数据块分散到各个 DataNode
3. ③ run_job.sh → ResourceManager：提交作业
4. ④ ResourceManager → 各 worker 的 NodeManager：启动任务；map 读本节点上的块
5. ⑤ worker ↔ worker：shuffle（按 key 分发），再由 reduce 汇总
6. ⑥ 输出 → compare_outputs.py 和 benchmark CSV

次要的流（虚线，全图只表示一种含义：**控制 / 心跳**）：DataNode、NodeManager → Master 的注册和心跳。

## 4. 这张图要说明的一点
同一份 Python 代码，不加修改地跑在五种执行方式和两种部署上；唯一变化的是 worker 数量 N。
读者的视线从左边的数据开始，经过 Master，到右边那摞 ×N worker，最后落到结果。

## 5. 布局与风格
- 模板：layered + pipeline，整体从左到右。
- 参考的样例：nsdi26-086_fig2（Kubernetes 集群的分层画法）、nsdi23-047_fig4（数据 I/O 与 worker 分层）、osdi23-039_fig3（输入输出两端用面板收束，工具名作为小标签附在旁边）。
- 配色：白底；已有组件用灰色；只有共享代码用一个强调色（蓝，与数据图里的 Spark DF 蓝统一）。
- 不放图例：三种线型在图注里说明。
- 字体：Helvetica 风格，6.5–7 pt。

## 6. 需要你确认的假设
- (a) 画成**单栏**，直接替换现在的 Fig. 2，以保住 10 页。还是要做成更丰富的**通栏**图？通栏可能需要再删一些文字或附录才能放下。
- (b) 只把 **mapper.py · reducer.py**（一份代码，多种执行方式）作为强调色的“我们的贡献”，对吗？
- (c) Azure 作为底部的第二条部署带画进同一张图，而不是单独再画一张。对吗？
- (d) 不画缓存实验和 cgroup 探针脚本（放在正文里讲即可）。对吗？

## 7. 图注草稿
System overview. ① TLC Parquet files are cleaned into CSV tiers and ② loaded into HDFS,
whose 128 MB blocks are spread over the N workers. ③ run_job.sh submits a job to the
ResourceManager, which ④ starts map tasks (or Spark executors) next to the blocks;
⑤ intermediate pairs are shuffled to the reducers and ⑥ the merged output is checked
against the serial baseline and timed. The same image and the same mapper/reducer code
run on 1–4 containers on one host and on three Azure VMs.

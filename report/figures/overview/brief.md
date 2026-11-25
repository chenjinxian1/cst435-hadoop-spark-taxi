# Brief: system overview figure (FigGenie, systems / architecture)

## 1. What the figure is
It replaces the simple cluster topology figure of Section IV (Fig. 2). It is a **single-column**
overview (about 240 × 170 pt) that shows the whole pipeline from raw data to timed results,
and how it runs on the two deployments.

## 2. Components (English label · role · tag)
- **Left: data preparation** (outside the cluster)
  - **TLC Parquet (2023–24)**: the monthly NYC TLC trip files; external.
  - **prepare_data.py**: cleans the data, converts it to CSV and splits it into the tiers S/M/L/XL and W3/W9; existing.
- **Middle: master container** (one container box)
  - **NameNode**
  - **ResourceManager**
  - **JobHistory**
  - **run_job.sh / spark-submit**: submits the jobs.
- **Right: worker ×N** (drawn as a stack marked ×N). Each worker contains:
  - **DataNode**: stores 128 MB HDFS blocks.
  - **NodeManager**: manages the containers on this node.
  - **Map/Reduce tasks or Spark executor**: where tasks or the executor run.
  - Resource cap written next to the box: 2 CPU · 5 GB.
- **Shared job code**: **mapper.py · reducer.py**, the one Python code base shared by the three analytics jobs. This is the figure's **only accent colour** (our contribution).
  - Thin lines link it to the execution modes: **Hadoop Streaming (±combiner)**, **Spark RDD**, **Spark DataFrame**, **Serial Python**, drawn as a row of small labels, not as large boxes.
- **Bottom: two deployments** (two narrow strips)
  - **Local: 1 host, Docker bridge, N = 1–4 containers**
  - **Azure: 3 VMs (1 master + 2 workers), N = 1–2**
  - Meaning: the same Docker image and the same configuration run in both environments.
- **Bottom right: results**
  - **compare_outputs.py**: checks that all modes give the same output.
  - **benchmark CSV → figures**: the timings are summarised into figures and tables.

## 3. Data flow (numbered main path)
1. ① Parquet → prepare_data.py → CSV tiers
2. ② CSV → HDFS: uploaded with `hdfs dfs -put`; the blocks are spread over the DataNodes
3. ③ run_job.sh → ResourceManager: submit the job
4. ④ ResourceManager → each worker's NodeManager: start the tasks; map tasks read the local blocks
5. ⑤ worker ↔ worker: shuffle (distribution by key), then the reducers aggregate
6. ⑥ output → compare_outputs.py and the benchmark CSV

Secondary flow (dashed; one meaning only in the whole figure: **control / heartbeat**): DataNode and NodeManager register with and send heartbeats to the master.

## 4. The one point the figure makes
The same Python code runs unchanged in five execution modes and on two deployments; the only thing that changes is the number of workers N.
The reader's eye starts at the data on the left, passes through the master to the ×N stack of workers on the right, and ends at the results.

## 5. Layout and style
- Template: layered + pipeline, left to right overall.
- Reference exemplars: nsdi26-086_fig2 (layered drawing of a Kubernetes cluster), nsdi23-047_fig4 (data I/O and worker layers), osdi23-039_fig3 (input and output closed off by panels, tool names attached as small labels).
- Colours: white background; existing components grey; only the shared code in one accent colour (blue, the same as the Spark DF blue of the data figures).
- No legend: the three line styles are explained in the caption.
- Font: Helvetica style, 6.5–7 pt.

## 6. Assumptions to confirm
- (a) Draw it as a **single-column** figure that directly replaces the current Fig. 2, to keep the report at 10 pages. Or a richer **double-column** figure, which may require cutting some text or appendix?
- (b) Only **mapper.py · reducer.py** (one code base, many execution modes) is highlighted as "our contribution" in the accent colour. Correct?
- (c) Azure is drawn as a second deployment strip at the bottom of the same figure, not as a separate figure. Correct?
- (d) The cache experiment and the cgroup probe scripts are not drawn (they are covered in the text). Correct?

## 7. Caption draft
System overview. ① TLC Parquet files are cleaned into CSV tiers and ② loaded into HDFS,
whose 128 MB blocks are spread over the N workers. ③ run_job.sh submits a job to the
ResourceManager, which ④ starts map tasks (or Spark executors) next to the blocks;
⑤ intermediate pairs are shuffled to the reducers and ⑥ the merged output is checked
against the serial baseline and timed. The same image and the same mapper/reducer code
run on 1–4 containers on one host and on three Azure VMs.

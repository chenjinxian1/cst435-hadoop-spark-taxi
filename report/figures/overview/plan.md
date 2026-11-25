# Drawing plan: overview (246 × 190 pt, single column)

Canvas: 246 pt wide; 4 pt margin. Bands (y):
- 4–38: control row. `master` container x 4–174 (NameNode 7–48, ResourceManager 52–114,
  run_job.sh 128–166; boxes y 18–33). Job code (accent) x 182–242, y 8–34, two lines.
- 46–116: worker 1 (x 4–114) · ellipsis · worker N (x 132–242), mirrored so the tasks
  boxes face each other. Inside: DataNode (with 2×2 block cells), NodeManager, tasks.
- 122–128: routing channel (② bus at y 122, ⑥ bus at y 128).
- 134–154: data row. TLC Parquet (cylinder) 4–48 → prepare_data.py 58–114 → CSV tiers
  124–176; results 186–242 (two lines).
- 160–190: deployment strips (x 4–176, local / Azure), legend x 184–242.

Alignment: RM centre = worker-1 NodeManager centre (x 83) so ④ drops straight;
NameNode centre = worker-1 DataNode centre (x 27.5) so the dashed block-map line is
vertical. ② rises from the CSV centre (x 150) into worker-1 DataNode through the
channel; ⑥ leaves worker-N tasks (x 163) down to the results (x 214).

Encoding: our scripts light blue #dae8fc; Hadoop/Spark daemons grey #e8e8e8; the job
code is the only saturated fill (#0F4D92, white text, same blue as the data figures).
Solid black arrows = main path; dashed = block map (control); dotted grey = code shipped.
Steps ①–⑥ as filled black discs ⌀ 8 pt. Type: 6.5 pt labels, 6.5 bold titles, 6 pt legend.

Check list for the PNG:
1. No arrow crosses a label or another arrow.
2. ④ and the dashed line are straight verticals.
3. The accent box is the loudest thing in the figure.
4. Step numbers read ①→⑥ in order of the caption.
5. Card titles do not collide with the edges entering the cards.

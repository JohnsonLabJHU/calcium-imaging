# The scientist's workflow

What using the tool actually looks like, start to finish.

1. **Open the tool** from the lab dashboard and **pick the experiment** the
   analysis belongs to (a browse-all dropdown, filterable by title or id).

2. **Choose the preparation type:**
   - *In vitro* (culture) — no animal/eye; recording IDs come from the file or
     folder name, so bulk uploads need no per-file data entry.
   - *In vivo* (animal) — Animal ID is required and each movie is renamed to a
     canonical `animal_eye_region_timepoint_treatment_date_NN`.

3. **Add recordings** — either pick individual movie files (+ optional snap
   stills), or point at a whole **folder** (nested structure is fine; movies and
   their `*_snap` stills are paired automatically). TIFF only.

4. **Set the Suite2p options** — usually just confirm the frame rate `fs`; leave
   diameter blank to let Cellpose infer it.

5. **Set the analysis options** — pick the model pair that matches the
   acquisition (e.g. 15 Hz in-vitro), the sensor, and a neuron-grouping method.

6. **Submit.** The tool uploads the data to object storage, archives the movies,
   and creates a **Queued** run. The GPU job starts automatically (or is started
   by an operator), runs Suite2p → GCaMP-analysis, and writes results back.

7. **Get results.** Under *"Recent analyses on this experiment"*, each run shows
   its status (Queued → Running → Done). When Done, a **Files** button reveals an
   inline view/download panel — the per-recording metrics workbook, plots, and a
   portable results bundle — individually or all at once. The results are also
   attached to the experiment itself.

## Reusing already-uploaded movies

Because every uploaded movie is archived, the tool offers a second path: instead
of uploading, tick movies **already in this experiment** and analyze them again
(e.g. with different parameters) with no re-upload. Snaps are matched
automatically from the archive.

## Interpreting outputs

For each recording the workbook reports per-ROI event metrics (rate, amplitude,
kinetics) after the ROI classifier keeps active cells and the spike classifier
keeps real transients, plus neuron grouping / co-activity matrices and plots.
Treat detected events as *candidate transients*, interpret kinetics in an
indicator- and frame-rate-aware way, and always check the segmentation/QC overlay
first — good-looking metrics are meaningless if the ROIs landed on the wrong
structures.

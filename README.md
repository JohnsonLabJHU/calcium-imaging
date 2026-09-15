# Calcium Imaging (GCaMP) Analysis Workflow

A **self-service GCaMP calcium-imaging analysis workflow** that plugs into an
electronic lab notebook (ELN). A scientist uploads raw movies through a simple
web form; the platform runs the analysis on a cloud GPU and writes the results
back to the originating experiment — reproducibly and with a full audit trail.
No command line, no manual file wrangling.

This repository is released by the **[Johnson Lab](https://www.johnsonlabjhu.com)**
(Wilmer Eye Institute, Johns Hopkins University) so that other labs can adopt the
same pattern. It is the companion to our
[Signal Colocalization workflow](https://github.com/JohnsonLabJHU/signal-colocalization).

---

## What it does

The analysis chain is:

1. **Suite2p** registers each movie and detects ROIs — using **Cellpose** on a
   paired *snap* still when one is provided, or Suite2p's own detector when it
   is not.
2. Trained **ROI** and **spike** classifiers keep the real cells and real
   calcium transients.
3. **Event kinetics** and **neuron grouping / co-activity** are computed.
4. A per-recording **metrics workbook**, plots, and a portable results bundle
   are written back to the experiment.

The scientific pipeline itself lives in two packages we mirror for long-term
availability (see [Pipelines & models](#pipelines--models)):
`suite2p-johnsonlab` (registration + still-Cellpose) and `GCaMP-analysis`
(classifiers + grouping).

## Why an ELN-integrated workflow?

Most analysis code assumes a person at a workstation. This project is about the
*plumbing* that turns such code into a shared lab service:

- **One web form** captures the inputs and per-recording metadata.
- **Object storage** (any S3-compatible or Azure Blob store) holds the raw data
  so the ELN never handles large movies.
- **A GPU batch job** claims queued work, runs the pipeline, and uploads results.
- **The ELN** is the system of record: every run is an auditable entry linked to
  its experiment.

The reference implementation uses **eLabFTW** as the ELN and **Azure Container
Apps** for the GPU job, but the design is deliberately swappable — see
[`docs/adapting-to-your-lab.md`](docs/adapting-to-your-lab.md).

## Architecture at a glance

```
  Scientist ──> Submission tool (web form)
                    │  uploads movies+snaps to object storage
                    │  creates a "queued" run record in the ELN
                    ▼
              Object storage (Blob / S3)          ELN (eLabFTW)
                    ▲                                  ▲
                    │ stages inputs                    │ writes results + status
                    ▼                                  │
              GPU worker  ──> Suite2p ──> GCaMP-analysis ──> results
```

See [`docs/architecture.md`](docs/architecture.md) for the full picture and
[`docs/workflow.md`](docs/workflow.md) for the step-by-step user experience.

## Repository layout

| Path | What's inside |
|------|---------------|
| [`submission-tool/`](submission-tool/) | The web form scientists use (`gcamp.html`) + the results viewer. Configure the endpoints at the top and serve it from your ELN. |
| [`worker/`](worker/) | The GPU job: stages inputs, runs Suite2p → GCaMP-analysis, writes results back. Includes the container `Dockerfile`. |
| [`reference-deployment/`](reference-deployment/) | One worked example: Azure Container Apps job, a blob-upload relay, and a dispatcher that auto-starts the job. Adapt to your own infrastructure. |
| [`docs/`](docs/) | Architecture, workflow, the `gcamp-1` job schema, and a guide to adapting the workflow to your ELN / cloud. |

## Quick start

1. **Stand up the pieces** your lab needs: an ELN, an object store, and a place
   to run a GPU container. The [reference deployment](reference-deployment/)
   shows one concrete way (eLabFTW + Azure).
2. **Mirror the pipelines and model weights** into your own accounts
   ([Pipelines & models](#pipelines--models)).
3. **Build the worker image** — see [`worker/README.md`](worker/README.md).
4. **Configure and serve the submission tool** — edit the `CONFIG` block at the
   top of [`submission-tool/gcamp.html`](submission-tool/gcamp.html).
5. Upload a test movie and watch the results appear on the experiment.

Full instructions: [`docs/adapting-to-your-lab.md`](docs/adapting-to-your-lab.md).

## Pipelines & models

The analysis pipelines and trained models are maintained as separate packages so
they can be versioned and cited independently:

- **`suite2p-johnsonlab`** — Suite2p fork with the still-Cellpose path (GPL-3.0)
- **`GCaMP-analysis`** — ROI/spike classifiers, kinetics, neuron grouping
- **Model weights** — Cellpose retinal snap model + GCaMP ROI/spike classifier
  bundles

> **Availability note.** These are mirrored under `JohnsonLabJHU` so the workflow
> does not depend on any individual's personal account. **DINOv3** (used by the
> Cellpose snap model) is *not* redistributed here — it is installed at build
> time from Meta's repository under Meta's license.

## Credits

The scientific pipelines, trained models, and analysis methods were developed by
**Morgan Zinn**. The ELN-integration platform (submission tool, worker, and
reference deployment) was developed in the **Johnson Lab**. Built on
[Suite2p](https://github.com/MouseLand/suite2p),
[Cellpose](https://github.com/MouseLand/cellpose), and
[DINOv3](https://github.com/facebookresearch/dinov3).

If you use this workflow, please cite it via [`CITATION.cff`](CITATION.cff), **and
cite the underlying methods software** — Suite2p, Cellpose / Cellpose-SAM,
DINOv3, and scikit-learn. Full references are in
[`ACKNOWLEDGMENTS.md`](ACKNOWLEDGMENTS.md).

## License

Johnson Lab platform code: **MIT** (see [`LICENSE`](LICENSE)). Bundled and
dependency components keep their own licenses — notably Suite2p (GPL-3.0) and
DINOv3 (Meta's license). See the note in `LICENSE`.

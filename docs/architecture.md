# Architecture

The workflow has four moving parts. None of them is tied to a specific vendor —
the reference deployment happens to use eLabFTW and Azure, but each box below can
be swapped.

```
   ┌─────────────┐   1. upload movies+snaps      ┌──────────────────┐
   │  Scientist  │ ───────────────────────────▶  │  Object storage  │
   │  (browser)  │                                │  (Blob / S3)     │
   └──────┬──────┘                                └────────┬─────────┘
          │ 2. create "Queued" run record                  │
          ▼                                                 │ 4. stage inputs
   ┌─────────────┐   3. sees queued work          ┌─────────▼─────────┐
   │     ELN     │ ◀───────────────────────────── │    GPU worker     │
   │ (eLabFTW)   │ ─────────────────────────────▶ │  Suite2p +        │
   │  run record │   6. write results + status    │  GCaMP-analysis   │
   └─────────────┘                                └───────────────────┘
          ▲                                                 │
          │ 5. (optional) a dispatcher starts the           │
          │    GPU job when work is queued                  │
          └─────────────────────────────────────────────────┘
```

## The four parts

**1. Submission tool** (`submission-tool/gcamp.html`)
A single self-contained HTML page served from the ELN. It uploads each movie and
its snap to object storage through a small **upload relay** (so the browser never
holds cloud credentials), captures per-recording metadata, builds the
[`gcamp-1` job](job-schema.md), and creates a **Queued** run record in the ELN.

**2. Object storage**
Holds the raw movies and snaps. The reference deployment uses Azure Blob; any
S3-compatible store works. Keeping large files here means the ELN only ever
stores small result files and metadata. Compute reads the data in-region, so
there is no egress cost for the movies.

**3. GPU worker** (`worker/`)
A container that, for each queued run: reads the job JSON, **stages** the movies
and snaps from object storage into a working tree, runs **Suite2p** (registration
+ still-Cellpose or standard detection), runs **GCaMP-analysis** (`analyze`),
collects the metrics workbook + plots + bundle, **uploads** them back to the ELN
run record and experiment, and sets the run **Status** to Done/Failed with
provenance (tool version, models).

**4. Dispatcher** (optional; `reference-deployment/dispatcher/`)
So nobody has to start the GPU job by hand, a tiny always-on poller watches the
ELN for `Queued` runs and starts the container job when there is work (and the
job isn't already running). Without it, you simply start the job manually.

## Data model in the ELN

One **"Analysis runs"** record type holds every run, with fields grouped as:

- **Request** — Job type, Experiment ID/title, Submitted by, Date, the job JSON,
  input file names, source pointers.
- **Run** — Status (Queued → Running → Done/Failed), worker host, timestamps,
  tool version, models.
- **Results** — a short metrics summary, plus the attached result files.

Uploaded movies are additionally recorded as **"Data files"** entries (a
searchable, backed-up archive), which lets the tool offer *"reuse a movie already
uploaded to this experiment"* without re-uploading.

## Why this shape

- **The ELN is the system of record.** Every analysis is an auditable entry
  linked to its experiment — nothing lives only on someone's laptop.
- **Storage, compute, and notebook are decoupled.** Each can scale or be
  replaced independently.
- **The job JSON is the single contract.** As long as the tool emits it and the
  worker reads it, either side can be rewritten. See [job-schema.md](job-schema.md).

# Adapting this workflow to your lab

This project is a **reference implementation**, not a turnkey product. You will
wire it to your own ELN, object store, and compute. Here is what each piece
assumes and where to change it.

## 0. What you need

- An **ELN** with a REST API. The reference uses **eLabFTW** (v2 API). Any ELN
  works if you reimplement the small set of calls the tool/worker make (create a
  record, set fields, attach files, link to an experiment).
- An **object store** — Azure Blob or any S3-compatible service.
- Somewhere to run a **GPU container** — Azure Container Apps (reference), or
  AWS Batch, GKE, a SLURM cluster, or a single GPU box.

## 1. Mirror the pipelines and models (do this first)

So you don't depend on anyone's personal account:

- Fork/mirror `suite2p-johnsonlab`, `GCaMP-analysis` into your org.
- Copy the model weights (Cellpose retinal snap model; GCaMP ROI/spike bundles)
  into storage you control — your own Hugging Face org, or attach them to a
  GitHub Release, or bake them into the image from a private bucket.
- In `worker/bake_models.py` and `worker/gcamp_worker.py`, replace the
  `YOUR-ORG/...` model-repo placeholders with your locations.
- **DINOv3** is installed from Meta's GitHub at build time (see the
  `Dockerfile`). It is intentionally *not* redistributed here — review Meta's
  license and keep it as an install-time dependency.

## 2. Configure the submission tool

Open `submission-tool/gcamp.html` and edit the `CONFIG` block at the top:

```js
const CONFIG = {
  API:            '/api/v2',            // your ELN REST API base
  UPLOAD_URL:     '/blobapi/upload',    // your upload relay endpoint
  BLOB_CONTAINER: 'microscopy',         // object-store container/bucket
  RUNS_STORE:     'Analysis runs',      // ELN record type for runs
  DATA_STORE:     'Data files',         // ELN record type for the file archive
  TEAM_NAME:      'your lab',           // team/group allowed to use the tool
  RECORD_VIEW_URL:'/database.php?mode=view&id=' // ELN "open record" URL prefix
};
```

Serve the page from your ELN so it shares the same login session (the tool relies
on the browser's authenticated session, never on embedded credentials).

## 3. The upload relay

Browsers must not hold cloud keys. The relay
(`reference-deployment/blob-relay/eln_blob_upload.py`) is a tiny same-origin
service that validates the caller's ELN session, then streams the bytes to object
storage using a **managed identity** (no secrets in the browser or on disk). Set
`BLOB_ACCT` and the allowed containers via environment variables. If you use S3,
swap the Blob "put block / put block list" calls for a presigned-URL or
server-side upload.

## 4. Build and run the worker

See `worker/README.md`. In short: build the container (`Dockerfile`), which
installs Suite2p + Cellpose + DINOv3 + GCaMP-analysis and bakes the models, then
run it wherever you have a GPU. The worker reads these environment variables:

| Variable | Purpose |
|----------|---------|
| `ELAB_APIKEY` | ELN API key (as a secret) |
| `ELAB_BASE` | ELN API base URL |
| `BLOB_ACCT` | object-store account |
| `UAMI_CLIENT_ID` | managed-identity client id for storage reads (Azure) |
| `SUITE2P_DIR`, `GCAMP_DIR`, `GCAMP_MODELS_DIR` | in-image paths (defaults fine) |

## 5. (Optional) auto-start dispatcher

`reference-deployment/dispatcher/` polls the ELN for queued runs and starts the
GPU job so nobody runs a command by hand. On Azure it uses the VM's managed
identity to call the Container Apps management API; on other platforms, replace
that one call with your scheduler's "start job" API. Fill in `AZ_SUB`, `AZ_RG`,
and the job name via the env file. Without a dispatcher, just start the job
manually when work is queued.

## 6. ELN record types

Create two record types in your ELN (names must match the tool's `CONFIG`):

- **Analysis runs** — fields for Job type, Experiment ID/title, Submitted by,
  Date, Config (job JSON), Input uploads, Source pointers, Status, Worker host,
  timestamps, Tool version, Models, Metrics summary.
- **Data files** — fields for File name, Original file name, Experiment, Blob
  container, Blob path, plus optional provenance (animal, laterality, dates).

## Security notes

- Never commit real endpoints, account names, subscription/identity IDs, or keys.
  Everything lab-specific lives in env files (git-ignored) or the `CONFIG` block.
- The tool relies on the user's authenticated ELN session; gate it to your team.
- Build the public repo **fresh** — don't import git history from an internal
  repo, or scrubbed values may leak through old commits.

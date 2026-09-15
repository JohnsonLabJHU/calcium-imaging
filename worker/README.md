# Worker

The GPU job that runs a queued analysis end to end. For each `Queued` run in the
ELN it: reads the [`gcamp-1` job](../docs/job-schema.md), stages the movies and
snaps from object storage, runs **Suite2p** then **GCaMP-analysis**, uploads the
results back to the ELN, and sets the run status.

## Files

| File | Role |
|------|------|
| `gcamp_worker.py` | Entry point. Claims queued Calcium runs, orchestrates Suite2p → GCaMP-analysis, writes results back. |
| `s2p_standard.py` | Fallback Suite2p path for recordings with **no** snap still (uses Suite2p's own detector). |
| `bake_models.py` | Build-time: downloads the Cellpose snap model + GCaMP ROI/spike model bundles into the image so runtime is offline. |
| `elab_analysis_worker.py` | Shared helpers (ELN calls, blob staging, upload) reused across tools. |
| `sitecustomize.py` | Makes child processes trust a self-signed ELN certificate (only needed for on-prem ELNs with self-signed certs). |
| `Dockerfile` | Builds the CUDA image with Suite2p + Cellpose + DINOv3 + GCaMP-analysis and bakes the models. |

## Before you build

1. **Mirror the pipelines and models** and replace the `YOUR-ORG/...`
   placeholders in `bake_models.py` and `gcamp_worker.py` (see
   [../docs/adapting-to-your-lab.md](../docs/adapting-to-your-lab.md)).
2. Place the two pipeline packages next to the `worker/` folder so the Dockerfile
   can copy them:
   ```
   build-context/
     suite2p-johnsonlab/     # your mirror
     GCaMP-analysis/         # your mirror  (Dockerfile expects GCaMP-analysis-current/ — adjust COPY line)
     worker/                 # this folder
   ```

## Build

Any OCI builder works. Example with Azure Container Registry's cloud build (no
local Docker or GPU needed):

```
az acr build --registry YOUR-ACR --image calcium-worker:v1 \
  -f worker/Dockerfile --agent-pool YOUR-ACR-AGENTPOOL .
```

or plain Docker:

```
docker build -f worker/Dockerfile -t calcium-worker:v1 .
```

## Run

Run the image anywhere with an NVIDIA GPU. It expects these environment
variables:

| Variable | Purpose |
|----------|---------|
| `ELAB_APIKEY` | ELN API key (provide as a secret, never bake it in) |
| `ELAB_BASE` | ELN API base URL, e.g. `https://eln.example.org/api/v2` |
| `BLOB_ACCT` | object-store account name |
| `UAMI_CLIENT_ID` | managed-identity client id used to read storage (Azure) |
| `GCAMP_NJOBS` | (optional) parallelism for the analysis stage |
| `SUITE2P_DIR`, `GCAMP_DIR`, `GCAMP_MODELS_DIR` | in-image paths (defaults are set in the Dockerfile) |

The worker processes **all** currently-queued Calcium runs, then exits — so it
pairs naturally with a scale-to-zero job that is started on demand (see
[../reference-deployment/](../reference-deployment/)).

## Sizing

Suite2p registration memory scales with movie size and it writes a movie-sized
scratch binary to fast disk (freed after each recording). Cellpose inference
wants a GPU. A single mid-range GPU node (e.g. 8 vCPU / 56 GiB / one T4) handles
typical in-vitro recordings; give it more memory for large movies.

## Notes

- The Cellpose snap models use a **DINOv3** backbone, which the Dockerfile
  installs from Meta's repository at build time. It is not redistributed in this
  repo — review Meta's license.
- `scikit-learn` is pinned to the exact version the model bundles were trained
  with; the loader validates it. Don't bump it without re-exporting the models.

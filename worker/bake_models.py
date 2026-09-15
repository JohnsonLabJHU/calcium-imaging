#!/usr/bin/env python3
"""Build-time model bake for the gcamp-worker image (run with HF online; image then runs offline).

- GCaMP ROI+spike joblib classifier pairs -> /opt/gcamp-models/{roi,spike}/<pair>/  (worker points local paths)
- Cellpose retinal snap model -> HF cache (HF_HOME=/opt/hf-cache); Suite2p resolve_model reads it offline
"""
import os, sys

# Model sources — replace YOUR-ORG with your own mirror, or override via the env vars below, so the
# deployment does not depend on any individual's personal account (see docs/adapting-to-your-lab.md).
GCAMP_MODELS_REPO = os.environ.get("HF_GCAMP_MODELS_REPO", "YOUR-ORG/gcamp-analysis-models")
CELLPOSE_REPO     = os.environ.get("HF_CELLPOSE_REPO",     "YOUR-ORG/cellpose-retinal-models")

os.environ.pop("HF_HUB_OFFLINE", None)  # this step needs the network
from huggingface_hub import snapshot_download

snapshot_download(
    GCAMP_MODELS_REPO,
    allow_patterns=["roi/15hz_invitro_base/*", "spike/15hz_invitro_base/*",
                    "roi/3hz_invivo_base/*",  "spike/3hz_invivo_base/*"],
    local_dir="/opt/gcamp-models",
)
print("gcamp roi/spike model pairs baked from %s" % GCAMP_MODELS_REPO)

sys.path.insert(0, "/opt/suite2p-johnsonlab")
from suite2p.still_cellpose import StillProcessor
StillProcessor.resolve_model("cpdino_RGC-Snap", hf_repo_id=CELLPOSE_REPO)
print("cellpose cpdino_RGC-Snap baked into HF cache from %s" % CELLPOSE_REPO)

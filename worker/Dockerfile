# GCaMP / calcium-imaging worker — GPU image for Azure Container Apps (general-gpu profile).
# Build context = the pipelines/ folder:
#     az acr build --registry YOUR-ACR --image gcamp-worker:v1 -f worker/Dockerfile --agent-pool YOUR-ACR-AGENTPOOL .
# (so it can COPY suite2p-johnsonlab/, GCaMP-analysis-current/, and worker/)
#
# Chain: suite2p-johnsonlab (register + Cellpose-on-snap / standard run_s2p) -> gcamp_analysis analyze.
# NO Cascade / TensorFlow. scikit-learn is PINNED to 1.6.1 (the model bundle loader enforces it).

FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf-cache \
    HF_HUB_OFFLINE=1 \
    SUITE2P_DIR=/opt/suite2p-johnsonlab \
    GCAMP_DIR=/opt/GCaMP-analysis \
    GCAMP_MODELS_DIR=/opt/gcamp-models \
    PYTHONPATH=/opt/worker \
    PYTHONHTTPSVERIFY=0

# Python 3.11 (suite2p-recommended; sklearn 1.6.1 + cellpose>=4 wheels available) + git for provenance
RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common git curl ca-certificates && \
    add-apt-repository -y ppa:deadsnakes/ppa && apt-get update && \
    apt-get install -y --no-install-recommends python3.11 python3.11-venv python3.11-dev && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 && \
    ln -sf /usr/bin/python3.11 /usr/local/bin/python && \
    rm -rf /var/lib/apt/lists/*

# CUDA-enabled PyTorch first so Suite2p registration + Cellpose pick up the GPU build
RUN python -m pip install --upgrade pip && \
    python -m pip install torch --index-url https://download.pytorch.org/whl/cu124

# Suite2p (the Johnson-Lab still-Cellpose fork): brings cellpose>=4, numba, tifffile, scanimage-tiff-reader
COPY suite2p-johnsonlab/ /opt/suite2p-johnsonlab/
# The build context has no .git, so setuptools-scm can't derive a version — pin it explicitly.
RUN cd /opt/suite2p-johnsonlab && SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 python -m pip install --editable .

# GCaMP analysis package deps (run via `python -m gcamp_analysis` with cwd=$GCAMP_DIR — not pip-installed)
COPY GCaMP-analysis-current/ /opt/GCaMP-analysis/
RUN python -m pip install -r /opt/GCaMP-analysis/requirements.txt

# suite2p-johnsonlab's still_cellpose imports imageio at module load but doesn't declare it
RUN python -m pip install imageio

# The cpdino_* Cellpose snap models use a DINOv3 backbone; the package must be importable at
# inference (else NameError: name 'dinov3_vitl16' is not defined). Same pinned commit the coloc image uses.
RUN python -m pip install "dinov3 @ git+https://github.com/facebookresearch/dinov3.git@6876159a11b4df116f30f667f8c9888617df0751"

# Pin scikit-learn LAST — the gcamp model-bundle loader validates the exact version (1.6.1)
RUN python -m pip install "scikit-learn==1.6.1"

# Worker code: reuse the colocalization worker's helpers + the GCaMP worker + no-snap Suite2p helper
COPY worker/elab_analysis_worker.py /opt/worker/elab_analysis_worker.py
COPY worker/gcamp_worker.py         /opt/worker/gcamp_worker.py
COPY worker/s2p_standard.py         /opt/worker/s2p_standard.py
COPY worker/sitecustomize.py        /opt/worker/sitecustomize.py
COPY worker/bake_models.py          /opt/worker/bake_models.py

# Pre-bake models so runs never touch Hugging Face at run time (image runs HF_HUB_OFFLINE=1):
#  - Cellpose retinal snap model into the HF cache (Suite2p's resolve_model reads it offline)
#  - GCaMP ROI+spike joblib pairs into $GCAMP_MODELS_DIR/{roi,spike}/<pair>/ (worker points local paths)
RUN HF_HUB_OFFLINE=0 python /opt/worker/bake_models.py

# Container Apps runs non-root; make code + caches world-readable / traversable
RUN chmod -R a+rX /opt/suite2p-johnsonlab /opt/GCaMP-analysis /opt/gcamp-models /opt/worker /opt/hf-cache

WORKDIR /opt/GCaMP-analysis
ENTRYPOINT ["python", "/opt/worker/gcamp_worker.py"]

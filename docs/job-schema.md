# The `gcamp-1` job schema

The submission tool and the worker communicate through a single JSON document,
the **job**. The tool writes it into the ELN run record (as the "Config" field);
the worker reads it and runs the analysis. This is the contract — if you replace
either side, keep this shape.

## Example

```json
{
  "schema_version": "gcamp-1",
  "recordings": [
    {
      "id": "dish3_ctrl_20260915_01",
      "movie": "blob:microscopy/analysis/EXP0041/dish3_ctrl_20260915_01/movie.tif",
      "snap":  "blob:microscopy/analysis/EXP0041/dish3_ctrl_20260915_01/movie_snap.tif",
      "metadata": {
        "animal_id": "",
        "eye": "",
        "region": "GCL",
        "timepoint": "D14",
        "treatment": "control"
      }
    }
  ],
  "suite2p": {
    "settings_profile": "2D_invitro_olympus",
    "fs": 15,
    "cellpose_model": "cpdino_RGC-Snap",
    "diameter": null,
    "cellprob_threshold": 0.0,
    "flow_threshold": 0.4,
    "nchannels": 1,
    "functional_chan": 1
  },
  "analysis": {
    "model_pair": "15hz_invitro_base",
    "sensor": "gcamp6s",
    "grouping": "combined"
  },
  "execution": { "dry_run": false }
}
```

## Fields

### `recordings[]` — one entry per movie
| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Unique per job. Becomes the working-directory name and the label on all outputs. |
| `movie` | string | Pointer to the raw movie (TIFF). A `blob:<container>/<path>` pointer or any URI your worker's `download` step understands. |
| `snap` | string \| null | Pointer to the paired snap still (TIFF), or `null`. With a snap, Cellpose segments it; without, Suite2p uses its own detector. |
| `metadata` | object | Provenance carried onto the results: `animal_id`, `eye`, `region`, `timepoint`, `treatment`. All optional; empty strings are fine (e.g. in-vitro has no `animal_id`/`eye`). |

### `suite2p` — registration + ROI detection
| Field | Type | Notes |
|-------|------|-------|
| `settings_profile` | string | Name of a validated Suite2p settings bundle shipped with `suite2p-johnsonlab` (e.g. `2D_invitro_olympus`). |
| `fs` | number | Acquisition frame rate (Hz). |
| `cellpose_model` | string | Cellpose snap-segmentation model (e.g. `cpdino_RGC-Snap`). |
| `diameter` | number \| **null** | Expected cell diameter in px. **`null` = Cellpose infers it** (recommended default). Must be a scalar, never a list. |
| `cellprob_threshold` | number | Lower → more/larger ROIs. |
| `flow_threshold` | number | Higher → more, looser masks. |
| `nchannels` | integer | Acquisition channel count. |
| `functional_chan` | integer | Which channel carries the GCaMP signal. |

### `analysis` — classifiers + grouping
| Field | Type | Notes |
|-------|------|-------|
| `model_pair` | string | Trained ROI+spike classifier set matching the acquisition context, e.g. `15hz_invitro_base` or `3hz_invivo_base`. **Never mix contexts.** |
| `sensor` | string | GCaMP variant (`gcamp6s`, `gcamp8s`, …). |
| `grouping` | string | Neuron co-activity clustering: `corr`, `wcorr`, `sttc`, `combined` (STTC + correlation), or `none`. |

### `execution`
| Field | Type | Notes |
|-------|------|-------|
| `dry_run` | boolean | Validate inputs and config without running the full analysis. |

## Versioning

`schema_version` is a string (`gcamp-1`). If you make a breaking change to the
shape, bump it (`gcamp-2`) and have the worker branch on it, so old queued runs
still parse.

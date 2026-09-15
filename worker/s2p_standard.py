#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standard Suite2p run (built-in ROI detection) for recordings that have NO snap still.

The suite2p-johnsonlab batch runner only handles recordings paired with a `*_snap` still
(it segments the snap with Cellpose and disables Suite2p's own detector). Some lab recordings
have no snap, so for those we run vanilla Suite2p — registration + built-in detection +
extraction + deconvolution + classification — which produces the SAME `suite2p/plane0/`
outputs (`F.npy`, `iscell.npy`, ...) that gcamp_analysis consumes downstream.

Called once per no-snap recording by gcamp_worker.py:
  python s2p_standard.py --recdir <dir> --movie <movie.tif> --settings <profile.npy> --fs 15
"""
import argparse
from pathlib import Path

import numpy as np

# suite2p-johnsonlab is installed in the image; SUITE2P_DIR is also on sys.path via the worker env.
from suite2p.parameters import default_db, default_settings
from suite2p.still_cellpose_batch import deep_merge
from suite2p.run_s2p import run_s2p


def main() -> int:
    ap = argparse.ArgumentParser(description="Standard Suite2p (built-in detection) for a no-snap recording.")
    ap.add_argument("--recdir", required=True, help="Recording folder containing the movie TIFF.")
    ap.add_argument("--movie", required=True, help="Movie filename (relative to --recdir) or absolute path.")
    ap.add_argument("--settings", required=True, help="Path to a settings-profile .npy (overrides merged onto defaults).")
    ap.add_argument("--fs", type=float, default=15.0)
    ap.add_argument("--nchannels", type=int, default=1)
    ap.add_argument("--functional_chan", type=int, default=1)
    a = ap.parse_args()

    recdir = Path(a.recdir).resolve()
    movie = Path(a.movie)
    movie_name = movie.name

    # Build settings the same way the still-path does, but KEEP built-in detection on.
    settings = default_settings()
    try:
        overrides = np.load(a.settings, allow_pickle=True).item()
        if isinstance(overrides, dict):
            deep_merge(settings, overrides)
    except Exception as e:
        print("s2p_standard: could not load settings profile (%s); using defaults" % e)

    settings["run"]["do_registration"] = 2          # full registration
    settings["run"]["do_detection"] = True          # <-- the difference vs the still path
    settings.setdefault("io", {})["delete_bin"] = True
    # frame rate / channels
    settings.setdefault("main", settings.get("main", {}))
    for group in ("main", "output"):
        settings.setdefault(group, {})
    # fs / nchannels / functional_chan live in the flat compat layer used by run_s2p; set in a few
    # likely locations so whichever the version reads picks it up.
    for k, v in (("fs", a.fs), ("nchannels", a.nchannels), ("functional_chan", a.functional_chan), ("nplanes", 1)):
        settings[k] = v
        if isinstance(settings.get("main"), dict):
            settings["main"][k] = v

    db = default_db()
    db["data_path"] = [str(recdir)]
    db["file_list"] = [movie_name]
    db["save_path0"] = str(recdir)
    db["save_folder"] = "suite2p"
    db["fast_disk"] = str(recdir)
    db["input_format"] = "tif"
    db["look_one_level_down"] = False
    db["subfolders"] = None

    print("s2p_standard: %s (fs=%s) -> %s/suite2p/plane0/" % (movie_name, a.fs, recdir))
    run_s2p(db=db, settings=settings)

    plane0 = recdir / "suite2p" / "plane0"
    ok = (plane0 / "F.npy").is_file() and (plane0 / "iscell.npy").is_file()
    print("s2p_standard: %s" % ("OK" if ok else "MISSING OUTPUTS"))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

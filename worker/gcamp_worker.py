#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GCaMP (calcium-imaging) worker — sibling of elab_analysis_worker.py for Job type "Calcium (GCaMP)".

One-shot: claims every Queued "Calcium (GCaMP)" run in the Analysis-runs store, runs the chain, writes
results back, then exits (fits the scale-to-zero Container Apps job).

Chain per run:
  stage movies (+ optional *_snap stills) from blob into a recording tree
    -> Suite2p (suite2p-johnsonlab): still-Cellpose path when a snap exists, else standard run_s2p
    -> gcamp_analysis analyze  (trained ROI + spike joblib classifiers -> per-video metrics + bundle)
    -> [experiment_analysis: only when the job supplies comparisons — deferred in v1]
    -> upload metrics/plots/bundle to the experiment + the run record; set Status Done/Failed.

Reuses the low-level helpers (eLab API, blob staging via managed identity, uploads) from
elab_analysis_worker.py so the live colocalization worker file is untouched.

Env: ELAB_APIKEY, ELAB_BASE, SUITE2P_DIR (/opt/suite2p-johnsonlab), GCAMP_DIR (/opt/GCaMP-analysis),
     GCAMP_MODELS_DIR (/opt/gcamp-models: roi/<pair>/, spike/<pair>/, cellpose/<model>/), GCAMP_NJOBS.
"""
import os, sys, json, re, subprocess, tempfile, zipfile, time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import elab_analysis_worker as w   # api, upload_file, download_blob, set_fields, fields_of, fv, now_iso, analysis_runs_category

JOB_TYPE    = os.environ.get("JOB_TYPE", "Calcium (GCaMP)")
SUITE2P_DIR = os.environ.get("SUITE2P_DIR", "/opt/suite2p-johnsonlab")
GCAMP_DIR   = os.environ.get("GCAMP_DIR", "/opt/GCaMP-analysis")
MODELS_DIR  = os.environ.get("GCAMP_MODELS_DIR", "/opt/gcamp-models")
NJOBS       = int(os.environ.get("GCAMP_NJOBS", "4"))
S2P_STD     = str(Path(__file__).resolve().parent / "s2p_standard.py")
TIMEOUT     = int(os.environ.get("GCAMP_TIMEOUT", str(60 * 60 * 6)))   # 6h wall for the whole chain
HOSTNAME    = w.HOSTNAME


def git_short(d):
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=d,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout.strip() or "?"
    except Exception:
        return "?"


def safe(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(s)).strip("_")[:60] or "rec"


PROGRESS_SECS = int(os.environ.get("GCAMP_PROGRESS_SECS", "45"))  # push a log tail this often while a stage runs


def _tail(path, n=3500):
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()[-n:]
    except Exception:
        return ""


def _run_streamed(cmd, cwd, env, run_id, label, timeout, header, logpath):
    """Run a long child process, streaming its stdout to a file, and push the tail to the
    run record every PROGRESS_SECS so a multi-hour Suite2p/GCaMP stage shows live progress
    on the Analysis-runs tracker. Returns (returncode, full_output_text)."""
    with open(logpath, "w") as f:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, text=True)
        start = time.time()
        while True:
            try:
                proc.wait(timeout=PROGRESS_SECS)
            except subprocess.TimeoutExpired:
                pass
            elapsed = int(time.time() - start)
            try:
                w.set_fields(run_id, {"Status": "Running — %s" % label,
                                      "Message / log": ("%s\n[%s | %dm elapsed]\n%s"
                                                        % (header, label, elapsed // 60, _tail(logpath)))[-6000:]})
            except Exception:
                pass
            if proc.poll() is not None:
                break
            if timeout and (time.time() - start) > timeout:
                proc.kill()
                break
    rc = proc.returncode if proc.returncode is not None else -1
    try:
        out = open(logpath, "r", errors="replace").read()
    except Exception:
        out = ""
    return rc, out


def queued_gcamp():
    cat = w.analysis_runs_category()
    if not cat:
        print("!! Analysis-runs store not found."); return []
    st, items, _ = w.api("GET", "/items?cat=%d&extended=1&limit=9999" % cat)
    out = []
    if st == 200 and isinstance(items, list):
        for it in items:
            ef = w.fields_of(it)
            if w.fv(ef, "Status") == "Queued" and w.fv(ef, "Job type") == JOB_TYPE:
                out.append((it, ef))
    out.sort(key=lambda p: p[0].get("id", 0))
    return out


def _recordings_from_job(job, pointers):
    """Return [{'id','movie','snap','metadata'}]. Prefer job['recordings']; else treat each flat
    Source pointer as a movie with no snap (manual-test convenience)."""
    recs = job.get("recordings")
    if isinstance(recs, list) and recs:
        norm = []
        for i, r in enumerate(recs):
            if not isinstance(r, dict) or not r.get("movie"):
                continue
            norm.append({"id": r.get("id") or ("rec%02d" % (i + 1)),
                         "movie": str(r["movie"]).strip(),
                         "snap": (str(r["snap"]).strip() if r.get("snap") else None),
                         "metadata": r.get("metadata") or {}})
        return norm
    flat = [p.strip() for p in (pointers or "").replace(",", "\n").splitlines() if p.strip()]
    return [{"id": "rec%02d" % (i + 1), "movie": p, "snap": None, "metadata": {}} for i, p in enumerate(flat)]


def _write_batch_yaml(path, s2p, dry):
    profile = s2p.get("settings_profile") or "2D_invitro_olympus"
    model = s2p.get("cellpose_model") or "cpdino_RGC-Snap"
    local_cp = Path(MODELS_DIR) / "cellpose" / model
    if local_cp.exists():
        model_ref, hf = str(local_cp), "null"
    else:
        model_ref, hf = model, (s2p.get("cellpose_hf_repo") or os.environ.get("HF_CELLPOSE_REPO","YOUR-ORG/cellpose-retinal-models"))
    dv = s2p.get("diameter", None)
    # Cellpose wants a scalar diameter or None (auto) — a list triggers "'>' not supported: list vs int".
    diam_field = "null" if dv in (None, "",) else ("%s" % float(dv))
    Path(path).write_text(
        "cellpose:\n"
        "  model_name_or_path: %s\n"
        "  hf_repo_id: %s\n"
        "  diameter: %s\n"
        "  cellprob_threshold: %s\n"
        "  flow_threshold: %s\n"
        "channels:\n"
        "  still_channel: %d\n"
        "  alignment_channel: %d\n"
        "  channel_axis: null\n"
        "alignment:\n"
        "  mode: auto\n  auto_align: true\n  min_response: 0.1\n  min_ecc: 0.5\n  max_abs_shift: 50.0\n  dy: 0\n  dx: 0\n"
        "settings_file: %s\n"
        "acquisition:\n"
        "  nchannels: %d\n  functional_chan: %d\n"
        "batch:\n"
        "  output_folder: suite2p\n  skip_completed: true\n  save_qc: true\n"
        "  delete_binary_after: true\n  stop_on_error: false\n  dry_run: %s\n  device: null\n"
        % (model_ref, hf, diam_field,
           float(s2p.get("cellprob_threshold", 0.0)), float(s2p.get("flow_threshold", 0.4)),
           int(s2p.get("still_channel", 1)), int(s2p.get("still_channel", 1)),
           profile, int(s2p.get("nchannels", 1)), int(s2p.get("functional_chan", 1)),
           "true" if dry else "false"),
        encoding="utf-8")
    return profile


def _resolve_model_pair(pair):
    """Find the baked .joblib + *_results.json for the roi and spike halves of a model pair."""
    out = {}
    for kind in ("roi", "spike"):
        folder = Path(MODELS_DIR) / kind / pair
        joblibs = sorted(folder.glob("*.joblib"))
        results = sorted(folder.glob("*_results.json"))
        if not joblibs or not results:
            raise FileNotFoundError("model pair %r missing %s artifacts in %s" % (pair, kind, folder))
        out[kind] = (str(joblibs[0]), str(results[0]))
    return out


# Per-strategy grouping config bodies (indented 4 spaces, sit under `  <name>:`).
# Values mirror GCaMP-analysis config/notebook_config.yaml. "combined" = STTC + correlation.
_GROUP_BODY = {
    "corr": ("    enabled: true\n    trace: \"norm_sm_f\"\n    method: \"pearson\"\n"
             "    cluster: \"hierarchical\"\n    linkage_method: \"complete\"\n"
             "    remove_global: false\n    use_diff: false\n    diff_order: 2\n"
             "    zscore_each: true\n    clip_negatives: true\n    distance_threshold: 0.15\n"
             "    min_group_size: 2\n    window: 10\n    polyorder: 2\n"),
    "wcorr": ("    enabled: true\n    trace: \"norm_sm_f\"\n    method: \"weighted_pearson\"\n"
              "    cluster: \"hierarchical\"\n    linkage_method: \"average\"\n"
              "    remove_global: true\n    use_diff: false\n    diff_order: 2\n"
              "    zscore_each: true\n    clip_negatives: true\n    distance_threshold: 0.15\n"
              "    min_group_size: 2\n    window: 10\n    polyorder: 2\n"),
    "sttc": ("    enabled: true\n    time_window: 0.4\n    correlation_threshold: 0.1\n"
             "    linkage_method: \"average\"\n    distance_threshold: 0.2\n    min_group_size: 2\n"),
    "combined": ("    enabled: true\n    corr:\n      max_lag: 5\n    sttc:\n      dt: 1.75\n"
                 "    cluster:\n      linkage_method: \"average\"\n      cluster_criterion: \"distance\"\n"
                 "      cluster_param: 0.5\n      min_group_size: 2\n"),
}


def _grouping_yaml(grp):
    grp = (grp or "corr").strip().lower()
    if grp in ("none", "", None) or grp not in _GROUP_BODY:
        if grp == "none":
            return "grouping:\n  strategies: []\n"
        grp = "corr"
    return "grouping:\n  strategies: [\"%s\"]\n  %s:\n%s" % (grp, grp, _GROUP_BODY[grp])


def _write_pipeline_yaml(path, analysis, settings_profile):
    sensor = analysis.get("sensor") or "gcamp6s"
    pair = analysis.get("model_pair") or "15hz_invitro_base"
    m = _resolve_model_pair(pair)
    Path(path).write_text(
        "traces:\n  smooth_sigma: 1\n  sensor_type: \"%s\"\n"
        "parallel:\n  n_jobs: %d\n"
        "models:\n  source: local\n"
        "  roi_model_path: %s\n  roi_config_path: %s\n"
        "  spike_model_path: %s\n  spike_config_path: %s\n"
        "%s"
        % (sensor, NJOBS, m["roi"][0], m["roi"][1], m["spike"][0], m["spike"][1],
           _grouping_yaml(analysis.get("grouping"))),
        encoding="utf-8")
    return pair


def process(run_item, ef):
    run_id = run_item["id"]
    exp_id = w.fv(ef, "Experiment ID")
    config_json = w.fv(ef, "Config (job JSON)")
    pointers = w.fv(ef, "Source pointers")
    print("[run %s] claiming GCaMP (experiment %s)" % (run_id, exp_id or "?"))
    s2p_ver, gc_ver = git_short(SUITE2P_DIR), git_short(GCAMP_DIR)
    w.set_fields(run_id, {"Status": "Running", "Worker host": HOSTNAME, "Started at": w.now_iso(),
                          "Tool version": "suite2p %s / gcamp %s" % (s2p_ver, gc_ver),
                          "Message / log": "Started on %s" % HOSTNAME})
    try:
        job = json.loads(config_json or "{}")
    except Exception:
        job = {}
    s2p_cfg = job.get("suite2p") or {}
    analysis = job.get("analysis") or {}
    dry = bool((job.get("execution") or {}).get("dry_run"))
    recs = _recordings_from_job(job, pointers)
    if not recs:
        w.set_fields(run_id, {"Status": "Failed", "Finished at": w.now_iso(),
                              "Error": "No recordings/movies in the job."}); return

    with tempfile.TemporaryDirectory(prefix="gcamp_run_") as tmp:
        tmp = Path(tmp)
        root = tmp / "recordings"; root.mkdir()
        log = []

        # 1) stage each recording: movie (+ snap renamed to <movie_stem>_snap.<ext>)
        staged = 0
        for r in recs:
            recdir = root / safe(r["id"]); recdir.mkdir(parents=True, exist_ok=True)
            movie_local = Path(w.download_blob(r["movie"], recdir)) if r["movie"].lower().startswith("blob:") else Path(r["movie"])
            r["_recdir"] = recdir; r["_movie"] = movie_local; r["_has_snap"] = False
            if r.get("snap"):
                snap_local = Path(w.download_blob(r["snap"], recdir)) if r["snap"].lower().startswith("blob:") else Path(r["snap"])
                target = recdir / (movie_local.stem + "_snap" + snap_local.suffix)
                if snap_local.resolve() != target.resolve():
                    snap_local.replace(target)
                r["_has_snap"] = True
            staged += 1
        n_snap = sum(1 for r in recs if r["_has_snap"])
        print("[run %s] staged %d recording(s): %d with snap, %d without" % (run_id, staged, n_snap, staged - n_snap))
        log.append("Staged %d recordings (%d snap / %d no-snap)." % (staged, n_snap, staged - n_snap))

        env = dict(os.environ, PYTHONUNBUFFERED="1")

        # 2) Suite2p — still-Cellpose batch handles the snap recordings
        if n_snap:
            batch_yaml = tmp / "batch_processing.yaml"
            _write_batch_yaml(batch_yaml, s2p_cfg, dry)
            cmd = [sys.executable, "scripts/run_batch.py", "--root", str(root), "--config", str(batch_yaml)]
            if dry: cmd.append("--dry-run")
            print("[run %s] suite2p (still): %s" % (run_id, " ".join(cmd)))
            rc, out = _run_streamed(cmd, SUITE2P_DIR, env, run_id,
                                    "Suite2p registration + Cellpose (%d recording(s))" % n_snap,
                                    TIMEOUT, "\n".join(log), tmp / "suite2p_still.log")
            log.append("[suite2p still] rc=%s\n%s" % (rc, out[-2500:]))

        # 3) no-snap recordings -> standard run_s2p
        profile_npy = str(Path(SUITE2P_DIR) / "config" / "settings_defaults" /
                          ((s2p_cfg.get("settings_profile") or "2D_invitro_olympus") + ".npy"))
        for r in recs:
            if r["_has_snap"] or dry:
                continue
            cmd = [sys.executable, S2P_STD, "--recdir", str(r["_recdir"]), "--movie", str(r["_movie"]),
                   "--settings", profile_npy, "--fs", str(s2p_cfg.get("fs", 15)),
                   "--nchannels", str(s2p_cfg.get("nchannels", 1)),
                   "--functional_chan", str(s2p_cfg.get("functional_chan", 1))]
            envp = dict(env, PYTHONPATH=SUITE2P_DIR + os.pathsep + env.get("PYTHONPATH", ""))
            print("[run %s] suite2p (standard, no snap): %s" % (run_id, r["id"]))
            rc, out = _run_streamed(cmd, SUITE2P_DIR, envp, run_id,
                                    "Suite2p (no snap): %s" % r["id"], TIMEOUT,
                                    "\n".join(log), tmp / ("suite2p_std_%s.log" % safe(r["id"])))
            log.append("[suite2p std %s] rc=%s\n%s" % (r["id"], rc, out[-1200:]))

        # verify suite2p outputs
        have = [r for r in recs if (r["_recdir"] / "suite2p" / "plane0" / "F.npy").is_file()]
        print("[run %s] suite2p produced outputs for %d/%d recording(s)" % (run_id, len(have), len(recs)))
        if not have and not dry:
            w.set_fields(run_id, {"Status": "Failed", "Finished at": w.now_iso(),
                                  "Error": "Suite2p produced no plane0 outputs.",
                                  "Message / log": "\n".join(log)[-6000:]}); return

        # 4) gcamp_analysis analyze
        pair = "n/a"
        if not dry:
            pipe_yaml = tmp / "pipeline_config.yaml"
            pair = _write_pipeline_yaml(pipe_yaml, analysis, s2p_cfg.get("settings_profile"))
            cmd = [sys.executable, "-m", "gcamp_analysis", "analyze", str(root), "--config", str(pipe_yaml)]
            if analysis.get("sensor"): cmd += ["--sensor", str(analysis["sensor"])]
            print("[run %s] gcamp analyze: %s" % (run_id, " ".join(cmd)))
            rc, out = _run_streamed(cmd, GCAMP_DIR, env, run_id, "GCaMP analysis (ROI/spike + grouping)",
                                    TIMEOUT, "\n".join(log), tmp / "gcamp_analyze.log")
            p = type("P", (), {"returncode": rc, "stdout": out})()
            log.append("[gcamp analyze] rc=%s\n%s" % (p.returncode, (p.stdout or "")[-3000:]))
            if p.returncode != 0:
                w.set_fields(run_id, {"Status": "Failed", "Finished at": w.now_iso(),
                                      "Error": "gcamp_analysis exited %s" % p.returncode,
                                      "Message / log": "\n".join(log)[-6000:]}); return

        # 5) collect + upload results
        prefix = "run%s_%s_" % (run_id, w.now_iso()[:10])
        targets = [("items", run_id)]
        if exp_id and str(exp_id).strip().isdigit():
            targets.insert(0, ("experiments", int(exp_id)))
        uploaded, total_xlsx = [], 0
        results_zip = tmp / ("gcamp_run%s_results.zip" % run_id)
        zf = zipfile.ZipFile(results_zip, "w", zipfile.ZIP_DEFLATED)
        for r in recs:
            mdir = r["_recdir"] / "metrics"
            if not mdir.exists():
                continue
            for f in sorted(mdir.glob("*.xlsx")):
                total_xlsx += 1
                oname = prefix + safe(r["id"]) + "_" + f.name
                for entity, eid in targets:
                    w.upload_file(entity, eid, f, comment="GCaMP metrics (run %s, %s)" % (run_id, r["id"]), name=oname)
                uploaded.append(oname)
            for f in sorted(mdir.glob("*_corr_heatmap.png")) + sorted(mdir.glob("*_corr_groups.png")):
                w.upload_file("items", run_id, f, comment="GCaMP QC (run %s)" % run_id, name=prefix + safe(r["id"]) + "_" + f.name)
            # everything (metrics + portable bundle) into the results zip
            for sub in ("metrics", "analysis_results"):
                d = r["_recdir"] / sub
                if d.exists():
                    for f in d.rglob("*"):
                        if f.is_file():
                            zf.write(f, arcname="%s/%s/%s" % (safe(r["id"]), sub, f.relative_to(d)))
        zf.close()
        if total_xlsx:
            w.upload_file("items", run_id, results_zip, comment="All GCaMP results (run %s)" % run_id, name=results_zip.name)
            uploaded.append(results_zip.name)
        # attach the full Suite2p / GCaMP stage logs (the live "Message / log" only holds the tail)
        for lf in sorted(tmp.glob("*.log")):
            try:
                w.upload_file("items", run_id, lf, comment="Run log (run %s)" % run_id, name=prefix + lf.name)
            except Exception:
                pass

        summary = "%d recording(s) analyzed (%d snap / %d no-snap); %d metrics workbook(s). Model pair: %s." % (
            len(have), n_snap, len(have) - n_snap, total_xlsx, pair)
        models = "gcamp %s (roi+spike joblib, pair %s); cellpose %s" % (
            gc_ver, pair, s2p_cfg.get("cellpose_model") or "cpdino_RGC-Snap")
        w.set_fields(run_id, {"Status": ("Done" if not dry else "Done"), "Finished at": w.now_iso(),
                              "Result files": ", ".join(uploaded) or ("(dry run)" if dry else "(none)"),
                              "Metrics summary": ("DRY RUN — " + summary) if dry else summary,
                              "Models + versions": models, "Message / log": "\n".join(log)[-6000:]})
        print("[run %s] DONE — %d file(s) uploaded" % (run_id, len(uploaded)))


def main():
    if not w.ELAB_KEY:
        print("!! ELAB_APIKEY not set."); return 1
    w.preflight()
    runs = queued_gcamp()
    print("Queued %s job(s): %d" % (JOB_TYPE, len(runs)))
    for it, ef in runs:
        try:
            process(it, ef)
        except Exception as e:
            print("[run %s] EXCEPTION: %s" % (it.get("id"), e))
            try:
                w.set_fields(it["id"], {"Status": "Failed", "Finished at": w.now_iso(), "Error": str(e)[:900]})
            except Exception:
                pass
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

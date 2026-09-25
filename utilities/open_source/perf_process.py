# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

'''
perf_process.py - Analyze per-trace screen recording clips using a run's trace manifest.

Takes a single HOBL run directory.  Everything needed lives inside it:
  trace_manifest.json          Written by core/app_scenario.py, one entry per recorded clip.
                               Each entry carries the clip folder name, the resolved capture
                               settings, and its "traceProcess" measurement settings.
  perf_screenshots/<clip>/     Per-clip folder (named by the manifest's "clip" field) holding
                               the recorded "capture.mp4" (and a "frame_times.csv").

For each manifest entry the entry's "traceProcess" measure is applied to its clip and a result
is recorded.  A summary CSV and a details JSON are written to the run directory.

Each manifest entry carries the measurement settings directly:
  traceProcess : "settle" | "pixel_change" | "template"  - which measurement to run.
  threshold    : mean abs diff (0-255) for settle/pixel_change; match confidence (0-1) for template.
  template     : template image path for "template" (resolved relative to the run directory).

Measurements always run against the full captured region using the first frame as the baseline.

Usage:
  python utilities/open_source/perf_process.py <run_dir>
'''

import argparse
import csv
import json
import logging
import os
import sys

import cv2 as cv
import numpy as np

# Ensure the repo root is importable so "core" resolves when run directly.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.template_match import TemplateMatcher


# Default pixel-difference threshold (mean absolute difference, 0-255) when an entry
# does not specify one.
DEFAULT_PIXEL_THRESHOLD = 10.0
# Default template-match confidence threshold when an entry does not specify one.
DEFAULT_TEMPLATE_THRESHOLD = 0.70
# Measure used when an entry's traceProcess omits one (mirrors app_scenario's default).
DEFAULT_MEASURE = "settle"

# The manifest that core/app_scenario.py writes into the run directory.
MANIFEST_FILENAME = "trace_manifest.json"
# Clips are copied back from the DUT into this subfolder of the run directory.
CLIPS_SUBDIR = "perf_screenshots"
# Each recorded clip lives in its own folder (named by the manifest "clip" field) and the video
# file inside is always named this.
CLIP_FILENAME = "capture.mp4"


def build_matcher(run_dir):
    '''
    Build a TemplateMatcher for offline analysis of recorded clips.

    Templates are matched against the clip's native pixels, so DPI standardization is disabled
    (device scale 1.0) and no debug images are written.  Template paths in a traceProcess are
    resolved relative to the run directory.
    '''
    return TemplateMatcher(
        json_parent_dir=run_dir,
        device_scale=1.0,
        standardize_dpi=False,
        debug_dir=None,
    )


def load_manifest(run_dir):
    '''Load the trace manifest (list of clip entries) from the run directory.'''
    manifest_path = os.path.join(run_dir, MANIFEST_FILENAME)
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f"No {MANIFEST_FILENAME} found in run directory: {run_dir}")
    with open(manifest_path, 'r') as file:
        return json.load(file)


def resolve_clips_dir(run_dir):
    '''
    Locate the folder that holds the per-clip subfolders.  Clips are copied back from the DUT
    into "<run_dir>/perf_screenshots", but fall back to the run directory itself if that
    subfolder is absent.
    '''
    clips_dir = os.path.join(run_dir, CLIPS_SUBDIR)
    if os.path.isdir(clips_dir):
        return clips_dir
    logging.warning("Clips subfolder '%s' not found under %s; using run directory.",
                    CLIPS_SUBDIR, run_dir)
    return run_dir


def get_fps(cap, entry):
    '''
    Determine frames-per-second: prefer the video metadata, fall back to the capture framerate
    recorded in the manifest entry.
    '''
    fps = cap.get(cv.CAP_PROP_FPS)
    if fps and fps > 0:
        return fps
    framerate = entry.get("capture", {}).get("framerate", 0)
    try:
        framerate = float(framerate)
    except (TypeError, ValueError):
        framerate = 0
    if framerate > 0:
        return framerate
    return None


def open_clip(clip_path):
    '''Open a video clip, raising if it cannot be read.'''
    cap = cv.VideoCapture(clip_path)
    if not cap.isOpened():
        cap.release()
        raise IOError(f"Unable to open video clip: {clip_path}")
    return cap


def frame_gray(frame):
    '''Grayscale a full frame for difference math.'''
    return cv.cvtColor(frame, cv.COLOR_BGR2GRAY)


# A clip may start before the first keyframe is received, in which case the leading frames are
# completely black.  These frames must stay in the clip (they carry timing information), but
# they have to be ignored for detection and pixel-change baselines - otherwise the arrival of
# the first keyframe is falsely reported as the first change.
BLACK_FRAME_MAX = 1.0  # Max mean pixel value (0-255) for a frame to be considered black.


def is_black_frame(gray):
    '''Return True if a grayscale frame is (essentially) all black.'''
    return float(np.mean(gray)) <= BLACK_FRAME_MAX


def measure_pixel_change(cap, threshold):
    '''
    Find the first frame that differs from the first (baseline) frame by more than the threshold.
    Returns (frame_index, diff_value) or (None, None) if no change is detected.

    Leading black frames (recorded before the first keyframe) are counted for timing but never
    used as a baseline or reported as a change.
    '''
    baseline = None
    index = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        current = frame_gray(frame)
        # Ignore black frames for matching, but keep counting so timing stays correct.
        if is_black_frame(current):
            index += 1
            continue
        if baseline is None:
            baseline = current
            index += 1
            continue
        diff = float(np.mean(cv.absdiff(current, baseline)))
        if diff > threshold:
            return index, diff
        index += 1
    return None, None


def measure_settle(cap, threshold):
    '''
    Find when the captured region settled into the state it holds at the end of the clip.

    Working backwards from the final frame, this locates the last frame that still differed
    from the end frame by more than the threshold; the settle point is the frame immediately
    after it (the first frame that matches the final state and never changes again).  Returns
    (settle_frame_index, last_change_diff) or (None, None).

    Leading black frames (recorded before the first keyframe) are counted for timing but treated
    as no-change and never used as the end-state reference.
    '''
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        current = frame_gray(frame)
        # Keep black frames as placeholders so timing (frame index) stays correct, but mark
        # them so they are never used as the end-state reference.
        frames.append(None if is_black_frame(current) else current)

    if not frames:
        return None, None

    # The end state is the last non-black frame.
    end_index = None
    for i in range(len(frames) - 1, -1, -1):
        if frames[i] is not None:
            end_index = i
            break
    if end_index is None:
        # Entire clip was black - nothing to measure.
        return None, None

    end_frame = frames[end_index]

    # Scan backwards to find the last frame that still differed from the final state.
    for i in range(end_index, -1, -1):
        if frames[i] is None:
            continue
        diff = float(np.mean(cv.absdiff(frames[i], end_frame)))
        if diff > threshold:
            # Frame i was the last change; it settled into its final state on the next frame.
            return i + 1, diff

    # Never differed from the end state - settled from the first non-black frame.
    for i in range(len(frames)):
        if frames[i] is not None:
            return i, 0.0
    return None, None


def measure_template(cap, template, threshold, matcher):
    '''
    Find the first frame in which the template image is located above the confidence threshold.
    Returns (frame_index, confidence) or (None, None).
    '''
    if not template:
        raise ValueError("traceProcess measure 'template' requires a template image path")

    index = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        # Ignore black frames (recorded before the first keyframe) but keep counting for timing.
        if is_black_frame(frame_gray(frame)):
            index += 1
            continue
        point, confidence, _next_best = matcher.get_point(template, frame, threshold=threshold)
        if point is not False and point is not None:
            return index, confidence
        index += 1
    return None, None


def process_entry(entry, clips_dir, matcher):
    '''Run a manifest entry's traceProcess measurement against its clip.  Returns a result dict.'''
    clip_name = entry.get("clip", "")
    measure = entry.get("traceProcess") or DEFAULT_MEASURE

    result = {
        "clip": clip_name,
        "label": entry.get("label", ""),
        "action_id": entry.get("action_id", ""),
        "instance": entry.get("instance", ""),
        "scenario_time_s": entry.get("scenario_time_s", ""),
        "measure": measure,
        "frame_index": None,
        "time_ms": None,
        "value": None,
        "status": "ok",
    }

    clip_path = os.path.join(clips_dir, clip_name, CLIP_FILENAME)
    if not os.path.isfile(clip_path):
        result["status"] = "missing_clip"
        return result

    threshold = entry.get("threshold")
    if threshold is None or threshold == "":
        threshold = DEFAULT_TEMPLATE_THRESHOLD if measure == "template" else DEFAULT_PIXEL_THRESHOLD
    threshold = float(threshold)

    cap = open_clip(clip_path)
    try:
        fps = get_fps(cap, entry)

        if measure == "pixel_change":
            frame_index, value = measure_pixel_change(cap, threshold)
        elif measure == "settle":
            frame_index, value = measure_settle(cap, threshold)
        elif measure == "template":
            frame_index, value = measure_template(cap, entry.get("template"), threshold, matcher)
        else:
            raise ValueError(f"Unknown traceProcess measure: {measure!r}")
    finally:
        cap.release()

    result["value"] = value
    if frame_index is None:
        result["status"] = "not_detected"
    else:
        result["frame_index"] = frame_index
        if fps:
            result["time_ms"] = round(frame_index * 1000.0 / fps, 2)
    return result


def write_outputs(results, out_dir):
    '''Write a summary CSV and a details JSON for all processed clips.'''
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "perf_process_results.csv")
    json_path = os.path.join(out_dir, "perf_process_results.json")

    fieldnames = ["clip", "label", "action_id", "instance", "scenario_time_s", "measure",
                  "frame_index", "time_ms", "value", "status"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    return csv_path, json_path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Analyze per-trace screen recording clips using a run's trace manifest.")
    parser.add_argument("run_dir", help="HOBL run directory containing trace_manifest.json and the recorded clips.")
    parser.add_argument("--out", default=None,
                        help="Output folder for the results CSV and JSON (default: the run directory).")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not os.path.isdir(args.run_dir):
        parser.error(f"run_dir does not exist: {args.run_dir}")

    manifest = load_manifest(args.run_dir)
    logging.info("Loaded %d manifest entr(y/ies) from %s",
                 len(manifest), os.path.join(args.run_dir, MANIFEST_FILENAME))

    clips_dir = resolve_clips_dir(args.run_dir)
    matcher = build_matcher(args.run_dir)

    results = []
    for entry in manifest:
        clip_name = entry.get("clip", "")
        try:
            result = process_entry(entry, clips_dir, matcher)
        except Exception as exp:
            logging.error("Failed to process clip '%s': %s", clip_name, exp)
            result = {
                "clip": clip_name,
                "label": entry.get("label", ""),
                "action_id": entry.get("action_id", ""),
                "instance": entry.get("instance", ""),
                "scenario_time_s": entry.get("scenario_time_s", ""),
                "measure": entry.get("traceProcess") or DEFAULT_MEASURE,
                "frame_index": None,
                "time_ms": None,
                "value": None,
                "status": f"error: {exp}",
            }
        results.append(result)
        logging.info("%s [%s#%s] -> frame=%s time_ms=%s value=%s (%s)",
                     result["clip"], result["action_id"], result["instance"],
                     result["frame_index"], result["time_ms"], result["value"], result["status"])

    if not results:
        logging.warning("No clips referenced by the manifest were processed.")

    out_dir = args.out or args.run_dir
    csv_path, json_path = write_outputs(results, out_dir)
    logging.info("Wrote %d result(s) to:\n  %s\n  %s", len(results), csv_path, json_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

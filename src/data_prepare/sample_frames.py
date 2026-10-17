"""Кадры для разметки детектора: чистые видео → data/frames/<round>/images + manifest.csv.

Видео декодируется с шагом 1/fps; бюджет кадров делится между видео пропорционально длительности.
Внутри видео кадры берутся равномерно по времени: отрезок делится на квоту интервалов, в каждом —
кадр с наибольшим движением (средняя разница с предыдущим кадром). Так в выборку попадают
и все сцены, и моменты, когда что-то происходит с руками, деньгами, сейфом.
Split — по видео: val-видео целиком в val, дубли (duplicate_of) пропускаются.
"""

import argparse
import csv
import os
import subprocess
from pathlib import Path

import numpy as np

# По одному видео из сцен A, B, D, E (docs/norm.md); сцена C (X-31) одна — остаётся в train
VAL_VIDEOS = {"X-19", "X-27", "X-37", "X-45"}
THUMB_W, THUMB_H = 58, 106


def motion_scores(video: Path, fps: float) -> np.ndarray:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale={THUMB_W}:{THUMB_H},format=gray",
         "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    ).stdout
    frames = np.frombuffer(out, dtype=np.uint8).reshape(-1, THUMB_H, THUMB_W).astype(np.float32)
    diffs = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
    return np.concatenate([[diffs[0] if len(diffs) else 0.0], diffs])


def pick(scores: np.ndarray, quota: int) -> list[int]:
    bins = np.array_split(np.arange(len(scores)), min(quota, len(scores)))
    return [int(b[np.argmax(scores[b])]) for b in bins if len(b)]


def extract(video: Path, times: list[float], out_dir: Path) -> list[Path]:
    paths = []
    for t in times:
        path = out_dir / f"{video.stem}_{round(t * 1000):06d}.jpg"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-q:v", "2",
             str(path)],
            check=True,
        )
        paths.append(path)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("DATA_DIR", "/data")))
    ap.add_argument("--round", default="r1", help="подкаталог data/frames/<round>")
    ap.add_argument("--verdict", choices=["violation", "no_violation"], default="no_violation")
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--budget", type=int, default=800, help="сколько кадров всего")
    ap.add_argument("--min-per-video", type=int, default=10)
    ap.add_argument("--episodes", nargs="*", help="вместо отбора по движению: окна вокруг секунд, например X-4:57,68 X-38:33")
    ap.add_argument("--window", type=float, default=6.0, help="полуширина окна вокруг эпизода, с")
    ap.add_argument("--full", nargs="*", default=[], help="видео, которые дополнительно берутся целиком 1 кадр/с")
    args = ap.parse_args()

    with (args.data / "labels.csv").open() as f:
        labels = {r["video"]: r for r in csv.DictReader(f)}
    out_dir = args.data / "frames" / args.round / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []

    if args.episodes:
        # раунд по эпизодам (например, видео с нарушениями для редких классов): всё идёт в train
        for spec in args.episodes:
            name, _, seconds = spec.partition(":")
            duration = float(labels[name]["duration_sec"])
            times = set()
            for t in (float(s) for s in seconds.split(",") if s):
                times.update(np.arange(max(0.0, t - args.window), min(duration, t + args.window) + 1e-6, 1 / args.fps))
            if name in args.full:
                times.update(np.arange(0.0, duration, 1.0))
            times = sorted({round(float(t), 2) for t in times if t < duration})
            for t, path in zip(times, extract(args.data / "videos" / f"{name}.mov", times, out_dir)):
                manifest.append({"file": path.name, "video": name, "t_sec": t, "split": "train"})
            print(f"{name}: {len(times)} кадров (train)")
    rows = [] if args.episodes else [r for r in labels.values() if r["verdict"] == args.verdict and not r["duplicate_of"]]
    total = sum(float(r["duration_sec"]) for r in rows)

    for r in rows:
        video = args.data / "videos" / f"{r['video']}.mov"
        scores = motion_scores(video, args.fps)
        quota = max(args.min_per_video, round(args.budget * float(r["duration_sec"]) / total))
        times = [i / args.fps for i in pick(scores, quota)]
        split = "val" if r["video"] in VAL_VIDEOS else "train"
        for t, path in zip(times, extract(video, times, out_dir)):
            manifest.append({"file": path.name, "video": r["video"], "t_sec": round(t, 3), "split": split})
        print(f"{r['video']}: {len(times)} кадров ({split})")

    with (args.data / "frames" / args.round / "manifest.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "video", "t_sec", "split"])
        writer.writeheader()
        writer.writerows(manifest)
    n_val = sum(m["split"] == "val" for m in manifest)
    print(f"→ {len(manifest)} кадров: train {len(manifest) - n_val}, val {n_val}")

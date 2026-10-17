"""Раскадровки видео с таймкодами: data/videos/X-<n>.mov → data/sheets/<video>_<page>.jpg.

Нужны, чтобы глазами разобрать сценарии на видео: что делает кассир, где лежат предметы,
где в стекле отражаются люди. Кроп (--crop x:y:w:h в пикселях исходника) — для мелочи в руках.
"""

import argparse
import csv
import os
import subprocess
from pathlib import Path


def render(video: Path, out_dir: Path, fps: float, cols: int, rows: int, width: int,
           crop: str | None, suffix: str) -> list[Path]:
    filters = [f"fps={fps}"]
    if crop:
        filters.append(f"crop={crop}")
    filters += [
        f"scale={width}:-2",
        f"drawtext=text='{video.stem} %{{pts\\:hms}}':x=4:y=4:fontsize=14:fontcolor=yellow:box=1:boxcolor=black@0.6",
        f"tile={cols}x{rows}:padding=2:color=white",
    ]
    pattern = out_dir / f"{video.stem}{suffix}_%02d.jpg"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", ",".join(filters),
         "-q:v", "3", "-start_number", "1", str(pattern)],
        check=True,
    )
    return sorted(out_dir.glob(f"{video.stem}{suffix}_*.jpg"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("DATA_DIR", "/data")))
    ap.add_argument("--verdict", choices=["violation", "no_violation"], help="только видео с этим вердиктом")
    ap.add_argument("--videos", nargs="*", help="конкретные видео, например X-3 X-5")
    ap.add_argument("--fps", type=float, default=1.0)
    ap.add_argument("--cols", type=int, default=8)
    ap.add_argument("--rows", type=int, default=4)
    ap.add_argument("--width", type=int, default=232, help="ширина одного кадра в раскадровке")
    ap.add_argument("--crop", help="x:y:w:h в пикселях исходного кадра")
    ap.add_argument("--suffix", default="", help="добавка к имени файла, например _desk")
    args = ap.parse_args()

    with (args.data / "labels.csv").open() as f:
        rows = [r for r in csv.DictReader(f) if not r["duplicate_of"]]
    if args.verdict:
        rows = [r for r in rows if r["verdict"] == args.verdict]
    if args.videos:
        rows = [r for r in rows if r["video"] in set(args.videos)]

    out_dir = args.data / "sheets"
    out_dir.mkdir(parents=True, exist_ok=True)
    for r in rows:
        pages = render(args.data / "videos" / f"{r['video']}.mov", out_dir, args.fps, args.cols, args.rows,
                       args.width, args.crop, args.suffix)
        print(f"{r['video']}: {len(pages)} стр.")

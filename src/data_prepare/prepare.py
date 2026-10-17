"""open.zip → data/videos/X-<n>.mov + data/labels.csv.

Особенности исходника:
- имена X-1, X-2 с латинской X, остальные с кириллической Х → приводим к ASCII X-<n>;
- побайтные дубли (Х-4 = Х-47, Х-5 = Х-48) → колонка duplicate_of, в split дубли держать вместе;
- таймкод строкой: «22 секунда», «1минута 8 секунда» → секунды.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

import openpyxl

NAME_RE = re.compile(r"^[XХ]-(\d+)$")  # латинская и кириллическая X
TIME_RE = re.compile(r"(?:(\d+)\s*минут\w*)?\s*(?:(\d+)\s*секунд\w*)?")


def normalize_name(raw: str) -> str:
    m = NAME_RE.match(raw.strip())
    if not m:
        raise ValueError(f"unexpected video name: {raw!r}")
    return f"X-{int(m.group(1))}"


def parse_timecode(raw: str | None) -> int | None:
    if not raw:
        return None
    m = TIME_RE.fullmatch(raw.strip())
    if not m or not any(m.groups()):
        raise ValueError(f"unexpected timecode: {raw!r}")
    minutes, seconds = (int(g) if g else 0 for g in m.groups())
    return minutes * 60 + seconds


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(out.stdout)
    stream = info["streams"][0]
    num, den = stream["r_frame_rate"].split("/")
    return {
        "duration_sec": round(float(info["format"]["duration"]), 3),
        "fps": round(int(num) / int(den), 3),
        "width": stream["width"],
        "height": stream["height"],
    }


def read_labels(xlsx: bytes) -> dict[str, tuple[str, int | None]]:
    ws = openpyxl.load_workbook(BytesIO(xlsx), read_only=True).active
    labels = {}
    for name, timecode, label in ws.iter_rows(min_row=2, values_only=True):
        if not name:
            continue
        verdict = "violation" if label.strip() == "нарушение" else "no_violation"
        labels[normalize_name(name)] = (verdict, parse_timecode(timecode))
    return labels


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zip", type=Path, help="путь к open.zip")
    ap.add_argument("--out", type=Path, default=Path(os.environ.get("DATA_DIR", "/data")))
    args = ap.parse_args()

    videos_dir = args.out / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(args.zip) as zf:
        labels = read_labels(zf.read("open/open_labels.xlsx"))
        rows, first_by_hash = [], {}
        for entry in zf.infolist():
            path = Path(entry.filename)
            if path.suffix.lower() != ".mov":
                continue
            name = normalize_name(path.stem)
            data = zf.read(entry)
            target = videos_dir / f"{name}.mov"
            target.write_bytes(data)

            sha = hashlib.sha256(data).hexdigest()
            verdict, timecode = labels[name]
            rows.append({
                "video": name,
                "n": int(name.split("-")[1]),
                "source_name": path.name,
                "verdict": verdict,
                "timecode_sec": timecode,
                "sha256": sha,
                "duplicate_of": first_by_hash.get(sha, ""),
                **probe(target),
            })
            first_by_hash.setdefault(sha, name)

    missing = sorted(set(labels) - {r["video"] for r in rows})
    if missing:
        raise SystemExit(f"labels without video: {missing}")

    rows.sort(key=lambda r: r["n"])
    with (args.out / "labels.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    unique = [r for r in rows if not r["duplicate_of"]]
    print(f"videos: {len(rows)}, unique: {len(unique)}, "
          f"violation: {sum(r['verdict'] == 'violation' for r in unique)}, "
          f"no_violation: {sum(r['verdict'] == 'no_violation' for r in unique)}")
    for r in rows:
        if r["duplicate_of"]:
            orig = next(o for o in rows if o["video"] == r["duplicate_of"])
            note = "" if (orig["verdict"], orig["timecode_sec"]) == (r["verdict"], r["timecode_sec"]) else "  <-- разметка расходится"
            print(f"duplicate: {r['video']} = {orig['video']} "
                  f"({r['verdict']} {r['timecode_sec']} vs {orig['verdict']} {orig['timecode_sec']}){note}")
    print(f"→ {args.out / 'labels.csv'}")

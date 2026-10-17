"""Разметка кадров → датасеты для обучения детекторов.

Источник: выгрузка CVAT (data/frames/<round>/cvat_export/*.zip, COCO 1.0) или, для дым-теста до конца
валидации, сырая предразметка (--from-prelabels). Раундов можно несколько (--round r1 r1b), имена кадров
не пересекаются. Классы — в порядке cvat/labels.json; split — из manifest.csv каждого раунда.
Результат в data/datasets/<name>/:
  yolo/  images/{train,val}, labels/{train,val}, data.yaml — для Ultralytics
  coco/  {train,valid,test}/ + _annotations.coco.json    — для RF-DETR (test = valid)
Картинки — жёсткие ссылки на data/frames/<round>/images.
Известные ошибки разметки правятся при сборке (data_prepare.label_fixes, --no-fixes — без правки): список правок —
<датасет>/fixes.csv, задание команде на правку в CVAT — data/cvat/label_fixes-<раунды>.md.
"""

import argparse
import csv
import json
import os
import shutil
import zipfile
from pathlib import Path

from data_prepare.label_fixes import fix_video, report, static_boxes

LABELS = Path(__file__).resolve().parents[2] / "cvat" / "labels.json"


def load_cvat_exports(export_dir: Path) -> list[dict]:
    """COCO каждой задачи; имя задачи — имя архива (cvat-io export)."""
    cocos = []
    for zip_path in sorted(export_dir.glob("*.zip")):
        with zipfile.ZipFile(zip_path) as zf:
            name = next(n for n in zf.namelist() if n.endswith(".json"))
            cocos.append({**json.loads(zf.read(name)), "task": zip_path.stem})
    if not cocos:
        raise SystemExit(f"нет выгрузок CVAT в {export_dir}")
    return cocos


def merge(cocos: list[dict], class_names: list[str]) -> tuple[dict[str, list[dict]], dict[str, tuple]]:
    """file_name → [{cls, bbox(xywh px), attributes}] с классами по имени; file_name → (задача, кадр, w, h)."""
    by_file: dict[str, list[dict]] = {}
    where: dict[str, tuple] = {}
    for coco in cocos:
        for im in coco["images"]:  # id картинки в выгрузке CVAT — номер кадра задачи + 1
            where[im["file_name"].rsplit("/", 1)[-1]] = (coco.get("task", "prelabels"), im["id"] - 1, im["width"], im["height"])
        names = {c["id"]: c["name"] for c in coco["categories"]}
        files = {im["id"]: (im["file_name"].rsplit("/", 1)[-1], im["width"], im["height"]) for im in coco["images"]}
        for file_name, _, _ in files.values():
            by_file.setdefault(file_name, [])
        for ann in coco["annotations"]:
            name = names[ann["category_id"]]
            if name not in class_names:
                continue
            file_name, w, h = files[ann["image_id"]]
            by_file[file_name].append({"cls": class_names.index(name), "bbox": ann["bbox"], "w": w, "h": h,
                                       "attributes": ann.get("attributes", {})})
    return by_file, where


def apply_fixes(by_file: dict[str, list[dict]], where: dict[str, tuple], video_of: dict[str, str],
                class_names: list[str]) -> list[dict]:
    """Правка по видео (data_prepare.label_fixes) на месте; возвращает список правок с задачей и кадром CVAT."""
    static = static_boxes()
    files_of: dict[str, list[str]] = {}
    for file_name in by_file:
        if file_name in video_of:
            files_of.setdefault(video_of[file_name], []).append(file_name)
    actions = []
    for video, files in files_of.items():
        frames = {}
        for f in files:
            _, _, w, h = where[f]
            frames[f] = [{**a, "cls": class_names[a["cls"]],
                          "box": [a["bbox"][0] / w, a["bbox"][1] / h, (a["bbox"][0] + a["bbox"][2]) / w,
                                  (a["bbox"][1] + a["bbox"][3]) / h]} for a in by_file[f]]
        fixed, done = fix_video(frames, static.get(video))
        for f, anns in fixed.items():
            _, _, w, h = where[f]
            by_file[f] = [{"cls": class_names.index(a["cls"]), "w": w, "h": h, "attributes": a.get("attributes", {}),
                           "bbox": [a["box"][0] * w, a["box"][1] * h, (a["box"][2] - a["box"][0]) * w,
                                    (a["box"][3] - a["box"][1]) * h]} for a in anns]
        for a in done:
            task, frame, _, _ = where[a["file"]]
            actions.append({"video": video, "task": task, "frame": frame, **a})
    return actions


def link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        os.link(src, dst)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("DATA_DIR", "/data")))
    ap.add_argument("--round", nargs="+", default=["r1"])
    ap.add_argument("--name", default="det_r1")
    ap.add_argument("--from-prelabels", action="store_true", help="сырая предразметка вместо выгрузки CVAT (дым-тест)")
    ap.add_argument("--no-fixes", action="store_true", help="без правки известных ошибок разметки (label_fixes)")
    args = ap.parse_args()

    # классы детектора — только рамки; тег event (система событий в CVAT) классом не является
    class_names = [label["name"] for label in json.loads(LABELS.read_text()) if label.get("type", "rectangle") != "tag"]
    split_of, root_of, video_of, cocos = {}, {}, {}, []
    for rnd in args.round:
        root = args.data / "frames" / rnd
        with (root / "manifest.csv").open() as f:
            for m in csv.DictReader(f):
                split_of[m["file"]], root_of[m["file"]], video_of[m["file"]] = m["split"], root, m["video"]
        if args.from_prelabels:
            cocos.append(json.loads((root / "prelabels.coco.json").read_text()))
        else:
            cocos += load_cvat_exports(root / "cvat_export")
    by_file, where = merge(cocos, class_names)
    fixes = [] if args.no_fixes else apply_fixes(by_file, where, video_of, class_names)

    out = args.data / "datasets" / args.name
    if out.exists():
        shutil.rmtree(out)
    if fixes:
        out.mkdir(parents=True)
        with (out / "fixes.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["file", "task", "frame", "video", "action", "rule", "from", "to", "box"])
            w.writeheader()
            w.writerows({**a, "box": json.dumps(a["box"])} for a in fixes)
        if not args.from_prelabels:
            md = args.data / "cvat" / f"label_fixes-{'+'.join(args.round)}.md"
            md.write_text(report(fixes, args.round))
    coco_out = {s: {"images": [], "annotations": [], "categories": [{"id": i, "name": n} for i, n in enumerate(class_names)]}
                for s in ("train", "valid")}
    counts = {s: [0] * len(class_names) for s in ("train", "val")}
    for file_name, anns in sorted(by_file.items()):
        split = split_of.get(file_name)
        if split is None:
            continue
        src = root_of[file_name] / "images" / file_name
        stem = Path(file_name).stem

        link(src, out / "yolo" / "images" / split / file_name)
        lines = []
        for a in anns:
            x, y, bw, bh = a["bbox"]
            lines.append(f"{a['cls']} {(x + bw / 2) / a['w']:.6f} {(y + bh / 2) / a['h']:.6f} {bw / a['w']:.6f} {bh / a['h']:.6f}")
            counts[split][a["cls"]] += 1
        label_path = out / "yolo" / "labels" / split / f"{stem}.txt"
        label_path.parent.mkdir(parents=True, exist_ok=True)
        label_path.write_text("\n".join(lines) + ("\n" if lines else ""))

        coco_split = "train" if split == "train" else "valid"
        link(src, out / "coco" / coco_split / file_name)
        c = coco_out[coco_split]
        img_id = len(c["images"]) + 1
        w, h = (anns[0]["w"], anns[0]["h"]) if anns else (464, 848)
        c["images"].append({"id": img_id, "file_name": file_name, "width": w, "height": h})
        for a in anns:
            c["annotations"].append({"id": len(c["annotations"]) + 1, "image_id": img_id, "category_id": a["cls"],
                                     "bbox": a["bbox"], "area": a["bbox"][2] * a["bbox"][3], "iscrowd": 0,
                                     "attributes": a["attributes"]})

    for coco_split, c in coco_out.items():
        (out / "coco" / coco_split / "_annotations.coco.json").write_text(json.dumps(c))
    # RF-DETR ждёт test/ — кладём туда копию valid
    (out / "coco" / "test").mkdir(parents=True, exist_ok=True)
    for f in (out / "coco" / "valid").iterdir():
        if f.suffix == ".jpg":
            link(f, out / "coco" / "test" / f.name)
        else:
            shutil.copy(f, out / "coco" / "test" / f.name)

    (out / "yolo" / "data.yaml").write_text(
        f"path: {out / 'yolo'}\ntrain: images/train\nval: images/val\nnames:\n"
        + "".join(f"  {i}: {n}\n" for i, n in enumerate(class_names))
    )
    print(f"→ {out} ({'предразметка' if args.from_prelabels else 'CVAT'}: {' + '.join(args.round)})")
    if fixes:
        from collections import Counter
        print("правки разметки:", ", ".join(f"{rule} {action} ×{n}" for (rule, action), n in
                                            Counter((a["rule"], a["action"]) for a in fixes).most_common()))
    print(f"{'класс':<14}{'train':>7}{'val':>7}")
    for i, n in enumerate(class_names):
        print(f"{n:<14}{counts['train'][i]:>7}{counts['val'][i]:>7}")

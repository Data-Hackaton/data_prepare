"""Разметка кадров → датасеты для обучения детекторов.

Источник: выгрузка CVAT (data/frames/<round>/cvat_export/*.zip, COCO 1.0) или, для дым-теста до конца
валидации, сырая предразметка (--from-prelabels). Раундов можно несколько (--round r1 r1b), имена кадров
не пересекаются. Классы — в порядке cvat/labels.json; split — из manifest.csv каждого раунда.
Результат в data/datasets/<name>/:
  yolo/  images/{train,val}, labels/{train,val}, data.yaml — для Ultralytics
  coco/  {train,valid,test}/ + _annotations.coco.json    — для RF-DETR (test = valid)
Картинки — жёсткие ссылки на data/frames/<round>/images.
"""

import argparse
import csv
import json
import os
import shutil
import zipfile
from pathlib import Path

LABELS = Path(__file__).resolve().parents[2] / "cvat" / "labels.json"


def load_cvat_exports(export_dir: Path) -> list[dict]:
    cocos = []
    for zip_path in sorted(export_dir.glob("*.zip")):
        with zipfile.ZipFile(zip_path) as zf:
            name = next(n for n in zf.namelist() if n.endswith(".json"))
            cocos.append(json.loads(zf.read(name)))
    if not cocos:
        raise SystemExit(f"нет выгрузок CVAT в {export_dir}")
    return cocos


def merge(cocos: list[dict], class_names: list[str]) -> dict[str, list[dict]]:
    """file_name → [{cls, bbox(xywh px), attributes}] с классами по имени."""
    by_file: dict[str, list[dict]] = {}
    for coco in cocos:
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
    return by_file


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
    args = ap.parse_args()

    class_names = [label["name"] for label in json.loads(LABELS.read_text())]
    split_of, root_of, cocos = {}, {}, []
    for rnd in args.round:
        root = args.data / "frames" / rnd
        with (root / "manifest.csv").open() as f:
            for m in csv.DictReader(f):
                split_of[m["file"]], root_of[m["file"]] = m["split"], root
        if args.from_prelabels:
            cocos.append(json.loads((root / "prelabels.coco.json").read_text()))
        else:
            cocos += load_cvat_exports(root / "cvat_export")
    by_file = merge(cocos, class_names)

    out = args.data / "datasets" / args.name
    if out.exists():
        shutil.rmtree(out)
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
    print(f"{'класс':<14}{'train':>7}{'val':>7}")
    for i, n in enumerate(class_names):
        print(f"{n:<14}{counts['train'][i]:>7}{counts['val'][i]:>7}")

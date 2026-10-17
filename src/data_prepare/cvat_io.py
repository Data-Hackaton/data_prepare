"""Обмен с CVAT: кадры и предразметка туда, проверенная разметка обратно.

upload   — проект с метками из cvat/labels.json, задачи по --task-size кадров отдельно для train и val
         (jobs по --job-size, чтобы делить работу), импорт предразметки COCO по каждой задаче;
labels   — добавить в проект новые метки из cvat/labels.json;
reimport — заменить предразметку в задачах, которые ещё никто не правил;
export   — выгрузка COCO 1.0 из всех задач раунда в data/frames/<round>/cvat_export/<task>.zip;
backup   — полный бэкап проекта раунда (кадры + разметка) в data/cvat/<проект>.zip.
Адрес и учётка: CVAT_URL, CVAT_USER, CVAT_PASSWORD (compose берёт их из ~/cvat/admin.env).
"""

import argparse
import csv
import json
import os
import tempfile
from pathlib import Path

from cvat_sdk import make_client
from cvat_sdk.core.proxies.tasks import ResourceType

LABELS = Path(__file__).resolve().parents[2] / "cvat" / "labels.json"


def client_from_env():
    return make_client(
        host=os.environ.get("CVAT_URL", "http://cvat-server:8080"),
        credentials=(os.environ["CVAT_USER"], os.environ["CVAT_PASSWORD"]),
    )


def coco_subset(coco: dict, names: set[str]) -> dict:
    images = [im for im in coco["images"] if im["file_name"] in names]
    ids = {im["id"] for im in images}
    return {
        "images": images,
        "annotations": [a for a in coco["annotations"] if a["image_id"] in ids],
        "categories": coco["categories"],
    }


def upload(args) -> None:
    root = args.data / "frames" / args.round
    with (root / "manifest.csv").open() as f:
        manifest = list(csv.DictReader(f))
    coco = json.loads((root / "prelabels.coco.json").read_text()) if (root / "prelabels.coco.json").exists() else None
    labels = json.loads(LABELS.read_text())

    with client_from_env() as client:
        project = client.projects.create(spec={"name": f"{args.project}-{args.round}", "labels": labels})
        print(f"проект {project.id}: {project.name}")
        for split in ("train", "val"):
            rows = sorted((m for m in manifest if m["split"] == split), key=lambda m: (int(m["video"][2:]), float(m["t_sec"])))
            for n, start in enumerate(range(0, len(rows), args.task_size), start=1):
                chunk = rows[start:start + args.task_size]
                task = client.tasks.create_from_data(
                    spec={"name": f"{args.round}-{split}-{n:02d}", "project_id": project.id, "segment_size": args.job_size},
                    resource_type=ResourceType.LOCAL,
                    resources=[str(root / "images" / m["file"]) for m in chunk],
                    data_params={"image_quality": 95, "sorting_method": "predefined"},
                )
                if coco:
                    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
                        json.dump(coco_subset(coco, {m["file"] for m in chunk}), tmp)
                    task.import_annotations(format_name="COCO 1.0", filename=tmp.name)
                    os.unlink(tmp.name)
                print(f"  задача {task.id} {task.name}: {len(chunk)} кадров")


def sync_labels(args) -> None:
    """Добавить в проект раунда метки из cvat/labels.json, которых в нём ещё нет (задачи не пересоздаются)."""
    labels = json.loads(LABELS.read_text())
    with client_from_env() as client:
        project = next(p for p in client.projects.list() if p.name == f"{args.project}-{args.round}")
        existing = {label.name for label in project.get_labels()}
        missing = [label for label in labels if label["name"] not in existing]
        if missing:
            project.update({"labels": missing})
        print(f"  {project.name}: добавлено {[label['name'] for label in missing] or 'ничего'}")


def reimport(args) -> None:
    """Заменить предразметку в задачах раунда, которые ещё никто не правил.

    Нетронутая задача — все jobs в состоянии new и все боксы из импорта (source=file). Время изменения jobs
    не годится: CVAT сдвигает его у всех jobs, когда в проект добавляют метки.
    Задачи, где уже есть правки человека, пропускаются: их разметку не трогаем.
    """
    root = args.data / "frames" / args.round
    coco = json.loads((root / "prelabels.coco.json").read_text())
    with client_from_env() as client:
        project = next(p for p in client.projects.list() if p.name == f"{args.project}-{args.round}")
        for task in sorted(client.tasks.list(), key=lambda t: t.id):
            if task.project_id != project.id:
                continue
            touched = [j.id for j in task.get_jobs() if j.state != "new"]
            manual = sum(1 for s in task.get_annotations().shapes if str(s.source) != "file")
            if touched or manual:
                print(f"  {task.name}: пропущена — jobs не в new: {touched}, ручных боксов: {manual}")
                continue
            names = {Path(f.name).name for f in task.get_frames_info()}
            subset = coco_subset(coco, names)
            task.remove_annotations()
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
                json.dump(subset, tmp)
            task.import_annotations(format_name="COCO 1.0", filename=tmp.name)
            os.unlink(tmp.name)
            print(f"  {task.name}: {len(subset['annotations'])} боксов")


def backup(args) -> None:
    """Полный бэкап проекта раунда (кадры + разметка) в data/cvat/<проект>.zip — восстанавливается в другом
    CVAT через Projects → Create from backup."""
    out_dir = args.data / "cvat"
    out_dir.mkdir(parents=True, exist_ok=True)
    with client_from_env() as client:
        project = next(p for p in client.projects.list() if p.name == f"{args.project}-{args.round}")
        path = out_dir / f"{project.name}.zip"
        project.download_backup(str(path))
        print(f"  {project.name} → {path} ({path.stat().st_size / 1e6:.1f} МБ)")


def export(args) -> None:
    out_dir = args.data / "frames" / args.round / "cvat_export"
    out_dir.mkdir(parents=True, exist_ok=True)
    with client_from_env() as client:
        project = next(p for p in client.projects.list() if p.name == f"{args.project}-{args.round}")
        for task in client.tasks.list():
            if task.project_id != project.id:
                continue
            zip_path = out_dir / f"{task.name}.zip"
            task.export_dataset(format_name="COCO 1.0", filename=str(zip_path), include_images=False)
            print(f"  {task.name} → {zip_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["upload", "labels", "reimport", "export", "backup"])
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("DATA_DIR", "/data")))
    ap.add_argument("--round", default="r1")
    ap.add_argument("--project", default="datathon-l1")
    ap.add_argument("--task-size", type=int, default=200)
    ap.add_argument("--job-size", type=int, default=100)
    args = ap.parse_args()
    {"upload": upload, "labels": sync_labels, "reimport": reimport, "export": export, "backup": backup}[args.command](args)

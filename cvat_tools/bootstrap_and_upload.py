"""Bootstrap this local CVAT and idempotently load one task per source video."""
from __future__ import annotations

import argparse
import csv
import json
import secrets
import subprocess
from collections import defaultdict
from pathlib import Path

from cvat_sdk import make_client
from cvat_sdk.core.proxies.tasks import ResourceType

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
ROUND = WORKSPACE / "data" / "frames" / "all-videos"
HOST = "http://localhost:48080"
PROJECT = "Datathon — все 42 видео"


def credentials():
    path = ROOT / "admin.env"
    if not path.exists():
        with path.open("x", encoding="utf-8") as handle:
            handle.write(f"CVAT_URL={HOST}\nCVAT_USER=admin\nCVAT_PASSWORD={secrets.token_urlsafe(24)}\n")
    values = dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line)
    assert values["CVAT_URL"] == HOST
    return values["CVAT_USER"], values["CVAT_PASSWORD"]


def bootstrap(user, password):
    code = (
        "from django.contrib.auth import get_user_model\n"
        f"username = {user!r}\npassword = {password!r}\n"
        "User = get_user_model()\n"
        "existing = User.objects.filter(username=username).first()\n"
        "if existing is None:\n"
        "    User.objects.create_superuser(username=username, password=password, email='')\n"
        "    print('Local CVAT admin created')\n"
        "elif existing.check_password(password):\n"
        "    print('Existing local CVAT admin verified')\n"
        "else:\n"
        "    raise RuntimeError('An admin already exists with different credentials; no password was changed')\n"
    )
    subprocess.run(["docker", "exec", "-i", "hackalem-cvat-server", "python", "manage.py", "shell"],
                   input=code, text=True, check=True, encoding="utf-8")


def upload(user, password):
    with (ROUND / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    groups = defaultdict(list)
    for row in rows:
        groups[row["video"]].append(row)
    schema = json.loads((WORKSPACE / "data_prepare" / "cvat" / "labels.json").read_text(encoding="utf-8"))
    preparation = json.loads((ROUND / "preparation.json").read_text(encoding="utf-8"))
    provenance = {video["video"]: video for video in preparation["items"]}
    with make_client(HOST, credentials=(user, password)) as client:
        projects = [p for p in client.projects.list() if p.name == PROJECT]
        if len(projects) > 1:
            raise RuntimeError("More than one matching project; refusing ambiguous upload")
        project = projects[0] if projects else client.projects.create({"name": PROJECT, "labels": schema})
        assert {label.name for label in project.get_labels()} == {label["name"] for label in schema}
        existing = {task.name: task for task in client.tasks.list() if task.project_id == project.id}
        report = {"url": HOST, "project_id": project.id, "project_url": f"{HOST}/projects/{project.id}",
                  "project_name": PROJECT, "sampling": preparation["sampling"], "tasks": []}
        for name in sorted(groups, key=lambda name: int(name[2:])):
            chunk = sorted(groups[name], key=lambda row: float(row["t_sec"]))
            task = existing.get(name)
            if task is None:
                task = client.tasks.create_from_data(
                    spec={"name": name, "project_id": project.id, "subset": chunk[0]["split"], "segment_size": 200},
                    resource_type=ResourceType.SHARE,
                    resources=[f"frames/all-videos/images/{row['file']}" for row in chunk],
                    data_params={"image_quality": 100, "sorting_method": "lexicographical", "copy_data": True},
                )
            info = task.get_frames_info()
            actual = [Path(frame.name).name for frame in info]
            expected = [row["file"] for row in chunk]
            if actual != expected:
                raise RuntimeError(f"Frame order/count mismatch in task {task.id} ({name})")
            if any(frame.width != 464 or frame.height != 848 for frame in info):
                raise RuntimeError(f"Unexpected frame dimensions: {name}")
            jobs = task.get_jobs()
            report["tasks"].append({"video": name, "task_id": task.id, "frames": len(chunk),
                "subset": chunk[0]["split"], "duplicate_of": provenance[name]["duplicate_of"],
                "job_ids": [job.id for job in jobs],
                "job_urls": [f"{HOST}/tasks/{task.id}/jobs/{job.id}" for job in jobs]})
            (ROOT / "cvat-project.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"video": name, "task_id": task.id, "frames": len(chunk), "verified": True}), flush=True)
        report["total_tasks"] = len(report["tasks"])
        report["total_frames"] = sum(task["frames"] for task in report["tasks"])
        assert report["total_tasks"] == 42 and report["total_frames"] == 1501
        (ROOT / "cvat-project.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({key: val for key, val in report.items() if key != "tasks"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()
    user, password = credentials()
    if args.bootstrap:
        bootstrap(user, password)
    if args.upload:
        upload(user, password)

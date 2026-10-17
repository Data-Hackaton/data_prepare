"""Import every original video frame into CVAT, one task per video, without sampling."""
import json
from pathlib import Path

from cvat_sdk import make_client
from cvat_sdk.core.proxies.tasks import ResourceType

from bootstrap_and_upload import HOST, ROOT, WORKSPACE, credentials

PROJECT = "Datathon — 42 полных видео, все кадры"
VAL = {"X-19", "X-27", "X-37", "X-45"}


def main():
    manifest = json.loads((WORKSPACE / "data" / "video_frame_manifest.json").read_text(encoding="utf-8"))
    schema = json.loads((WORKSPACE / "data_prepare" / "cvat" / "labels.json").read_text(encoding="utf-8"))
    with make_client(HOST, credentials=credentials()) as client:
        projects = [p for p in client.projects.list() if p.name == PROJECT]
        if len(projects) > 1:
            raise RuntimeError("Ambiguous project name")
        project = projects[0] if projects else client.projects.create({"name": PROJECT, "labels": schema})
        assert {label.name for label in project.get_labels()} == {label["name"] for label in schema}
        existing = {task.name: task for task in client.tasks.list() if task.project_id == project.id}
        report = {"url": HOST, "project_id": project.id, "project_name": PROJECT,
                  "project_url": f"{HOST}/projects/{project.id}", "frame_step": 1,
                  "annotation_status": "not_started", "tasks": []}
        for video in manifest["items"]:
            name = video["video"]
            canonical = video["duplicate_of"] or name
            split = "val" if canonical in VAL else "train"
            task = existing.get(name)
            if task is None:
                task = client.tasks.create_from_data(
                    spec={"name": name, "project_id": project.id, "subset": split, "segment_size": 10000},
                    resource_type=ResourceType.SHARE,
                    resources=[f"videos/{name}.mov"],
                    data_params={"image_quality": 100, "copy_data": True, "use_cache": True, "frame_step": 1},
                )
            meta = task.get_meta()
            if meta.size != video["frame_count"] or meta.start_frame != 0 or meta.stop_frame != video["frame_count"] - 1:
                raise RuntimeError(f"Frame coverage mismatch for {name}: got {meta.size}, expected {video['frame_count']}")
            if meta.frame_filter not in ("", "step=1") or meta.deleted_frames:
                raise RuntimeError(f"Frames skipped or deleted in {name}")
            if meta.included_frames is not None and len(meta.included_frames) != video["frame_count"]:
                raise RuntimeError(f"Incomplete included_frames for {name}")
            jobs = task.get_jobs()
            report["tasks"].append({"video": name, "task_id": task.id, "frames": meta.size,
                "start_frame": meta.start_frame, "stop_frame": meta.stop_frame,
                "frame_filter": meta.frame_filter, "subset": split, "duplicate_of": video["duplicate_of"] or None,
                "source_sha256": video["sha256"], "job_ids": [job.id for job in jobs],
                "job_urls": [f"{HOST}/tasks/{task.id}/jobs/{job.id}" for job in jobs]})
            (ROOT / "cvat-full-project.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"video": name, "task_id": task.id, "frames": meta.size,
                              "verified_all_original_frames": True}), flush=True)
        report["total_tasks"] = len(report["tasks"])
        report["total_frames"] = sum(task["frames"] for task in report["tasks"])
        assert report["total_tasks"] == manifest["videos"] and report["total_frames"] == manifest["frames"]
        (ROOT / "cvat-full-project.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k != "tasks"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

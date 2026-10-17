"""Read-only audit: full frame coverage and annotation state are reported separately."""
import argparse
import hashlib
import json
from datetime import datetime, timezone

from cvat_sdk import make_client
from bootstrap_and_upload import HOST, ROOT, WORKSPACE, credentials


def main(exact_readback=False):
    imported = json.loads((ROOT / "cvat-full-project.json").read_text(encoding="utf-8"))
    source = json.loads((WORKSPACE / "data" / "video_frame_manifest.json").read_text(encoding="utf-8"))
    expected = {item["video"]: item for item in source["items"]}
    audit = {"checked_at": datetime.now(timezone.utc).isoformat(), "project_url": imported["project_url"],
             "tasks": [], "errors": [], "annotation_review": "No manual review completion is inferred from object counts."}
    readbacks=[]
    with make_client(HOST, credentials=credentials()) as client:
        project = client.projects.retrieve(imported["project_id"])
        schema_path = ROOT / "labels-annotation.json"
        if not schema_path.exists():
            schema_path = WORKSPACE / "data_prepare" / "cvat" / "labels.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        actual_labels = {label.name: label for label in project.get_labels()}
        if set(actual_labels) != {item["name"] for item in schema}:
            audit["errors"].append("Project label set differs from the source schema")
        for item in schema:
            actual = actual_labels.get(item["name"])
            if actual is None:
                continue
            attributes = {attr.name: attr for attr in actual.attributes}
            if set(attributes) != {attr["name"] for attr in item["attributes"]}:
                audit["errors"].append(f"Attribute set mismatch: {item['name']}")
            for attr in item["attributes"]:
                observed = attributes.get(attr["name"])
                if observed and any(observed.to_dict()[key] != attr[key]
                    for key in ("input_type", "mutable", "values", "default_value")):
                    audit["errors"].append(f"Attribute mismatch: {item['name']}.{attr['name']}")
        for item in imported["tasks"]:
            task = client.tasks.retrieve(item["task_id"])
            meta, annotations, jobs = task.get_meta(), task.get_annotations(), task.get_jobs()
            if exact_readback:
                from import_annotations import payload_for
                from revise_own_annotations import fingerprints
                path=ROOT/'assembled'/f"{item['video']}.json"
                assembled=json.loads(path.read_text(encoding='utf-8'))
                ledger=json.loads((ROOT/'imports'/f"{item['video']}.json").read_text(encoding='utf-8'))
                labels={name:label.to_dict() for name,label in actual_labels.items()}
                actual=annotations.to_dict()['tracks'];ids=set(ledger['track_ids'])
                owned=[track for track in actual if track['id'] in ids]
                assert fingerprints(owned)==fingerprints(payload_for(assembled,labels)['tracks']),item['video']
                readbacks.append(dict(video=item['video'],task_id=task.id,readback_exact=True,
                    tracks=len(owned),assembled_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    other_tracks_preserved=len(actual)-len(owned)))
                print('READBACK_EXACT',item['video'],flush=True)
            original = expected[item["video"]]
            coverage = (meta.size == original["frame_count"] and meta.start_frame == 0
                        and meta.stop_frame == original["frame_count"]-1
                        and meta.frame_filter in ("", "step=1") and not meta.deleted_frames)
            if not coverage:
                audit["errors"].append(f"Frame coverage mismatch: {item['video']}")
            frame_coverage = {s.frame for t in annotations.tracks for s in t.shapes if not s.outside}
            frame_coverage.update(s.frame for s in annotations.shapes)
            imported_path = ROOT / "imports" / f"{item['video']}.json"
            if imported_path.exists() and frame_coverage != set(range(meta.size)):
                audit["errors"].append(f"Explicit annotation coverage mismatch: {item['video']}")
            audit["tasks"].append({"video": item["video"], "task_id": task.id, "frames": meta.size,
                "all_original_frames": coverage, "shapes": len(annotations.shapes),
                "tracks": len(annotations.tracks), "tags": len(annotations.tags),
                "tracked_shapes": sum(len(t.shapes) for t in annotations.tracks),
                "frames_with_explicit_annotations": len(frame_coverage),
                "human_review_complete": False,
                "jobs": [{"id": job.id, "stage": str(job.stage), "state": str(job.state)} for job in jobs]})
    audit["total_tasks"] = len(audit["tasks"])
    audit["total_frames"] = sum(item["frames"] for item in audit["tasks"])
    audit["tasks_with_annotations"] = sum(bool(item["shapes"] or item["tracks"] or item["tags"]) for item in audit["tasks"])
    audit["frames_with_explicit_annotations"] = sum(item["frames_with_explicit_annotations"] for item in audit["tasks"])
    if audit["total_tasks"] != len(expected) or audit["total_frames"] != source["frames"]:
        audit["errors"].append("Video or frame totals differ from the source manifest")
    (ROOT / "verification.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if exact_readback and not audit['errors']:
        report=dict(checked_at=audit['checked_at'],videos=len(readbacks),all_readbacks_exact=True,
            corrections_sha256=hashlib.sha256((ROOT/'manual/dense_corrections.json').read_bytes()).hexdigest(),
            per_video=readbacks)
        assert report['videos']==42
        (ROOT/'qa_20261017/readback-step5-final.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({key: value for key, value in audit.items() if key != "tasks"}, ensure_ascii=False))
    if audit["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument('--exact-readback',action='store_true')
    main(exact_readback=parser.parse_args().exact_readback)

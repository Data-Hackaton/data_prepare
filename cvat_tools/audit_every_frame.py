"""Decode and audit every source frame; never equate this with visual review.

The snapshot is read-only against CVAT. Risk flags are review candidates, not
automatic reasons to remove annotations. Per-frame evidence is saved as JSONL.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / 'data'
QA = ROOT / 'qa_20261017'


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def snapshot():
    from cvat_sdk import make_client
    from bootstrap_and_upload import HOST, credentials
    from import_annotations import payload_for
    from revise_own_annotations import fingerprints
    manifest = json.loads((ROOT / 'cvat-full-project.json').read_text(encoding='utf-8'))
    target = QA / 'baseline'
    target.mkdir(parents=True, exist_ok=True)
    report = {'created_at': utc(), 'tasks': [], 'errors': []}
    with make_client(HOST, credentials=credentials()) as client:
        for item in manifest['tasks']:
            name = item['video']
            task = client.tasks.retrieve(item['task_id'])
            live = task.get_annotations().to_dict()
            labels = {label.name: label.to_dict() for label in task.get_labels()}
            ledger = json.loads((ROOT / 'imports' / f'{name}.json').read_text(encoding='utf-8'))
            source = ROOT / 'assembled' / f'{name}.json'
            assembled = json.loads(source.read_text(encoding='utf-8'))
            own = [t for t in live['tracks'] if t['id'] in set(ledger['track_ids'])]
            same = fingerprints(own) == fingerprints(payload_for(assembled, labels)['tracks'])
            if not same:
                report['errors'].append(f'{name}: live objects differ from published baseline; merge required')
            output = target / f'{name}.cvat.json.gz'
            # Refuse to replace the original snapshot if a run is resumed.
            if not output.exists():
                with gzip.open(output, 'wt', encoding='utf-8') as stream:
                    json.dump(live, stream, ensure_ascii=False, separators=(',', ':'))
            local = target / f'{name}.assembled.json'
            if not local.exists():
                local.write_bytes(source.read_bytes())
            row = {'video': name, 'task_id': task.id, 'tracks': len(live['tracks']),
                   'own_tracks': len(own), 'published_baseline_matches_live': same,
                   'source_sha256': assembled['source_sha256'],
                   'assembled_sha256': sha(local), 'snapshot_sha256': sha(output)}
            report['tasks'].append(row)
            save(QA / 'baseline.json', report)
            print(json.dumps({'snapshot': row}), flush=True)
    report['completed_at'] = utc()
    save(QA / 'baseline.json', report)
    if report['errors']:
        raise SystemExit(1)


def overlap(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    aa, ab = (a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1])
    return intersection / max(1e-6, aa+ab-intersection), intersection / max(1e-6, min(aa, ab))


def intervals(frames):
    result = []
    for frame in sorted(set(frames)):
        if result and result[-1][1] == frame-1:
            result[-1][1] = frame
        else:
            result.append([frame, frame])
    return result


def audit(item):
    name = item['video']
    source = DATA / 'videos' / f'{name}.mov'
    expected_n = item['frame_count']
    data = json.loads((QA / 'baseline' / f'{name}.assembled.json').read_text(encoding='utf-8'))
    times = json.loads((DATA / 'frame_times' / f'{name}.json').read_text(encoding='utf-8'))
    report = {'video': name, 'started_at': utc(), 'source_sha256': sha(source),
              'expected_frames': expected_n, 'decoded_frames': 0, 'errors': [],
              'visually_reviewed_frames': 0, 'review_method': 'programmatic_full_frame_audit'}
    if report['source_sha256'] != item['sha256']:
        report['errors'].append('source_hash_mismatch')
    if len(times) != expected_n or data['frame_count'] != expected_n:
        report['errors'].append('frame_count_mismatch')
    frames = [[] for _ in range(expected_n)]
    issues = defaultdict(list)
    short = set()
    for ti, track in enumerate(data['tracks']):
        samples = track['samples']
        sf = [sample['frame'] for sample in samples]
        if sf != sorted(set(sf)):
            report['errors'].append(f'unsorted_or_duplicate_frames_track_{ti}')
        visible = [s for s in samples if not s['outside']]
        if track['label'] in ('hand', 'person', 'reflection') and len(visible) < 5:
            short.add(ti)
        for sample in visible:
            f = sample['frame']
            if not 0 <= f < expected_n:
                report['errors'].append(f'frame_out_of_range_track_{ti}_{f}')
                continue
            frames[f].append((ti, track['label'], sample))
    cap = cv2.VideoCapture(str(source))
    previous_gray = None
    previous_boxes = {}
    counts = Counter()
    frame_file = QA / 'frame_audit' / f'{name}.jsonl.gz'
    frame_file.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(frame_file, 'wt', encoding='utf-8') as stream:
        for f in range(expected_n):
            ok, bgr = cap.read()
            if not ok:
                report['errors'].append(f'decode_failed_at_{f}')
                break
            report['decoded_frames'] += 1
            if bgr.shape[:2] != (848, 464):
                report['errors'].append(f'wrong_dimensions_at_{f}')
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            mean_delta = float(np.mean(cv2.absdiff(gray, previous_gray))) if previous_gray is not None else 0.0
            local_flags = []
            visible = frames[f]
            if not visible:
                report['errors'].append(f'no_explicit_annotations_at_{f}')
            present = Counter(label for _, label, _ in visible)
            for ti, label, sample in visible:
                box = sample['box']
                x1, y1, x2, y2 = box
                flags = []
                if not all(np.isfinite(box)) or not (0 <= x1 < x2 <= 464 and 0 <= y1 < y2 <= 848):
                    report['errors'].append(f'invalid_box_track_{ti}_frame_{f}')
                if sample.get('method') == 'hold_uncertain':
                    flags.append('held_without_motion_evidence')
                if ti in short:
                    flags.append('brief_track')
                if label == 'hand' and ((x2-x1)*(y2-y1) > 3500 or max(x2-x1, y2-y1) > 85):
                    flags.append('large_hand_box')
                if label in ('person', 'reflection') and x2-x1 > 220:
                    flags.append('wide_person_box')
                if any(v == 'unknown' for v in sample.get('attributes', {}).values()):
                    flags.append('unknown_state')
                if ti in previous_boxes and previous_boxes[ti][0] == f-1:
                    old = previous_boxes[ti][1]
                    center_jump = float(np.linalg.norm((np.asarray(box[:2])+box[2:]-np.asarray(old[:2])-old[2:])/2))
                    area = (x2-x1)*(y2-y1)
                    old_area = (old[2]-old[0])*(old[3]-old[1])
                    ratio = max(area, old_area) / max(1, min(area, old_area))
                    if center_jump > (18 if label == 'hand' else 30):
                        flags.append('center_jump')
                    if ratio > 1.7:
                        flags.append('area_jump')
                previous_boxes[ti] = (f, box)
                for flag in flags:
                    issues[(flag, (ti,))].append(f)
                    local_flags.append([flag, ti])
                    counts[flag] += 1
            dynamic = [(ti, label, sample) for ti, label, sample in visible if label in ('hand', 'person', 'reflection')]
            for ai, (ti, label, sample) in enumerate(dynamic):
                for tj, other_label, other in dynamic[ai+1:]:
                    if label != other_label:
                        continue
                    iou, containment = overlap(sample['box'], other['box'])
                    if iou >= 0.72 or (label == 'hand' and containment >= 0.94):
                        flag = 'possible_duplicate'
                        issues[(flag, tuple(sorted((ti, tj))))].append(f)
                        local_flags.append([flag, ti, tj])
                        counts[flag] += 1
            row = {'frame': f, 'time_sec': times[f], 'decoded_pixel_sha256': hashlib.sha256(bgr.tobytes()).hexdigest(),
                   'annotations': len(visible), 'labels': dict(present), 'image_mean_delta': round(mean_delta, 4),
                   'flags': local_flags, 'visual_reviewed': False}
            stream.write(json.dumps(row, separators=(',', ':'))+'\n')
            previous_gray = gray
    extra, _ = cap.read()
    cap.release()
    if extra:
        report['errors'].append('extra_source_frames')
    report.update(completed_at=utc(), flags=dict(counts), frame_report_sha256=sha(frame_file),
                  issues=[{'kind': kind, 'track_indices': list(tracks), 'frames': intervals(fs), 'count': len(fs)}
                          for (kind, tracks), fs in sorted(issues.items())])
    save(QA / 'audit' / f'{name}.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'issues'}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', action='store_true')
    parser.add_argument('--videos', nargs='*')
    args = parser.parse_args()
    if args.snapshot:
        snapshot()
        return
    cv2.setNumThreads(2)
    items = json.loads((DATA / 'video_frame_manifest.json').read_text(encoding='utf-8'))['items']
    reports = []
    for item in items:
        if args.videos and item['video'] not in args.videos:
            continue
        reports.append(audit(item))
        summary = {'updated_at': utc(), 'videos_audited': len(reports),
                   'frames_audited': sum(r['decoded_frames'] for r in reports),
                   'visual_review_complete': False,
                   'errors': [f"{r['video']}: {e}" for r in reports for e in r['errors']],
                   'per_video': [{k: v for k, v in r.items() if k != 'issues'} for r in reports]}
        save(QA / 'audit_summary.json', summary)


if __name__ == '__main__':
    main()

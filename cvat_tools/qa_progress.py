"""Summarize recorded visual evidence separately from automated frame checks."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QA = ROOT / 'qa_20261017'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def frames(values):
    result = set()
    for value in values:
        if isinstance(value, int):
            result.add(value)
        else:
            assert len(value) == 2 and value[0] <= value[1], value
            result.update(range(value[0], value[1] + 1))
    return result


def intervals(values):
    result = []
    for value in sorted(values):
        if result and result[-1][1] == value - 1:
            result[-1][1] = value
        else:
            result.append([value, value])
    return result


def build():
    items = read(ROOT.parent / 'data/video_frame_manifest.json')['items']
    evidence = {}
    for folder in ['scene_a', 'scene_b', 'scene_c', 'parent']:
        ledger = read(QA / folder / 'review.json')
        entries = ledger['videos']
        if isinstance(entries, list):
            entries = {v['video']: v for v in entries}
        for name, entry in entries.items():
            full = set()
            if folder == 'scene_a':
                any_scope = frames(entry['visually_reviewed_frames'])
                for session in entry.get('inspection_sessions', []):
                    if session.get('crop') == [0, 0, 464, 848] or (
                        session.get('crop') is None and 'full-frame' in session.get('scope', '').lower()
                    ):
                        full.update(frames(session['frames']))
            elif folder == 'scene_b':
                full = frames(entry.get('visual_reviewed_intervals', []))
                any_scope = full.copy()
            elif folder == 'scene_c':
                full = frames(entry.get('full_frame_reviewed_frames', []))
                any_scope = frames(entry.get('reviewed_frames', []))
            else:
                full = frames(entry['reviewed_frames'])
                any_scope = full.copy()
            assert full <= any_scope, (folder, name)
            evidence[name] = dict(full=full, any_scope=any_scope,
                                  ledger=f'{folder}/review.json',
                                  unresolved=entry.get('unresolved', entry.get('notes', [])))
    extra_path = QA / 'scene_b/c_extra_review.json'
    if extra_path.exists():
        entries = read(extra_path)['videos']
        if isinstance(entries, list):
            entries = {v['video']: v for v in entries}
        for name, entry in entries.items():
            ev = evidence[name]
            full = frames(entry.get('full_frame_reviewed_frames', []))
            any_scope = frames(entry.get('reviewed_frames', []))
            assert full <= any_scope, name
            ev['full'].update(full)
            ev['any_scope'].update(any_scope)
            ev['ledger'] = [ev['ledger'], 'scene_b/c_extra_review.json']
            ev['unresolved'] = entry.get('unresolved', ev['unresolved'])
    by_name = {item['video']: item for item in items}
    videos = []
    for item in items:
        source = item.get('duplicate_of') or item['video']
        if source != item['video']:
            assert item['sha256'] == by_name[source]['sha256']
            assert item['frame_count'] == by_name[source]['frame_count']
        ev = evidence[source]
        n = item['frame_count']
        all_frames = set(range(n))
        assert ev['any_scope'] <= all_frames, source
        videos.append(dict(video=item['video'], source_video=source, frame_count=n,
            duplicate_evidence_inherited=source != item['video'],
            source_sha256=item['sha256'], ledger=ev['ledger'],
            full_frame_screened=len(ev['full']), any_region_screened=len(ev['any_scope']),
            full_frame_screened_intervals=intervals(ev['full']),
            full_frame_remaining_intervals=intervals(all_frames-ev['full']),
            full_frame_screening_complete=ev['full'] == all_frames,
            all_object_geometry_validated=False, unresolved=ev['unresolved']))
    audit = read(QA / 'audit_summary.json')
    spec = read(ROOT / 'manual/dense_corrections.json')
    unique = [v for v in videos if not v['duplicate_evidence_inherited']]
    return dict(updated_at=datetime.now(timezone.utc).isoformat(),
        full_frame_screening_is_not_all_object_geometry_validation=True,
        visual_review_complete=False, total_videos=len(videos),
        total_source_frames=sum(v['frame_count'] for v in videos),
        full_frame_screened=sum(v['full_frame_screened'] for v in videos),
        any_region_screened=sum(v['any_region_screened'] for v in videos),
        unique_source_frames=sum(v['frame_count'] for v in unique),
        unique_full_frame_screened=sum(v['full_frame_screened'] for v in unique),
        source_frame_step=1, automated_audit_errors=audit['errors'],
        staged_correction_count=sum(len(v['patches']) for v in spec['videos'].values()),
        videos=videos)


if __name__ == '__main__':
    result = build()
    (QA / 'progress.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'videos'}, ensure_ascii=False))

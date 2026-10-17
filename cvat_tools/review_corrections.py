"""Apply evidence-backed frame corrections without changing unrelated objects."""
from __future__ import annotations
import bisect
import copy
import hashlib
import json


def tracks_checksum(tracks):
    return hashlib.sha256(json.dumps(tracks, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_box(box):
    assert len(box) == 4
    x1, y1, x2, y2 = map(float, box)
    assert 0 <= x1 < x2 <= 464 and 0 <= y1 < y2 <= 848, box
    return [round(v, 2) for v in (x1, y1, x2, y2)]


def interpolated_box(patch, frame, times):
    if 'box' in patch:
        return validate_box(patch['box'])
    keys = patch['keyframes']
    indices = [k['frame'] for k in keys]
    assert indices == sorted(set(indices)) and indices[0] <= frame <= indices[-1]
    i = bisect.bisect_right(indices, frame)-1
    left = keys[i]
    if i+1 == len(keys) or indices[i] == frame:
        return validate_box(left['box'])
    right = keys[i+1]
    fraction = (times[frame]-times[left['frame']])/(times[right['frame']]-times[left['frame']])
    return validate_box([a+(b-a)*fraction for a, b in zip(left['box'], right['box'])])


def segments(track, n):
    """Represent corrected gaps/label changes explicitly; never bridge a gap."""
    output = []
    part = None
    for sample in track['samples']:
        if sample['outside']:
            continue
        label = sample.pop('_corrected_label', track['label'])
        if part is None or part['label'] != label or part['samples'][-1]['frame'] != sample['frame']-1:
            if part is not None:
                last = part['samples'][-1]
                if last['frame'] < n-1:
                    part['samples'].append(dict(last, frame=last['frame']+1, outside=True))
            part = {k: copy.deepcopy(v) for k, v in track.items() if k not in ('samples', 'label')}
            part.update(label=label, samples=[])
            if label == 'reflection':
                part['attributes'].pop('role', None)
            output.append(part)
        if label == 'reflection':
            sample.get('attributes', {}).pop('role', None)
        part['samples'].append(sample)
    if part is not None and part['samples'][-1]['frame'] < n-1:
        last = part['samples'][-1]
        part['samples'].append(dict(last, frame=last['frame']+1, outside=True))
    return output


def apply(tracks, specification, times):
    assert tracks_checksum(tracks) == specification['baseline_tracks_sha256'], 'Correction baseline changed; review required'
    corrected = copy.deepcopy(tracks)
    changed = set()
    touched = set()
    applied = []
    for index, patch in enumerate(specification['patches']):
        operation = patch['operation']
        assert patch.get('reason') and patch.get('evidence_frames'), 'Correction needs visual evidence'
        if operation == 'add_track':
            track = copy.deepcopy(patch['track'])
            assert track['samples']
            track.setdefault('attributes', {})
            sample_frames = [sample['frame'] for sample in track['samples']]
            assert sample_frames == sorted(set(sample_frames))
            for sample in track['samples']:
                validate_box(sample['box'])
                assert 0 <= sample['frame'] < len(times)
                sample.setdefault('attributes', {})
                if not sample['outside']:
                    touched.add((len(corrected), sample['frame']))
            corrected.append(track)
            changed.add(len(corrected)-1)
            applied.append({'patch': index, 'operation': operation, 'samples_changed': len(track['samples'])})
            continue
        ti = patch['track_index']
        assert 0 <= ti < len(tracks)
        start, end = patch['frames']
        assert 0 <= start <= end < len(times)
        selected = set(patch.get('frame_list', range(start, end+1)))
        assert selected <= set(range(start, end+1))
        track = corrected[ti]
        affected = []
        for sample in track['samples']:
            f = sample['frame']
            if f not in selected or sample['outside']:
                continue
            before = copy.deepcopy(sample)
            if operation == 'outside':
                sample['outside'] = True
            elif operation == 'replace_box':
                sample['box'] = interpolated_box(patch, f, times)
            elif operation == 'attributes':
                sample.setdefault('attributes', {}).update(patch['attributes'])
            elif operation == 'relabel':
                sample['_corrected_label'] = patch['label']
            else:
                raise ValueError(f'Unknown correction operation {operation}')
            if sample != before:
                sample['method'] = 'visual_review_correction' if f in patch['evidence_frames'] else 'review_correction_propagation'
                affected.append(f)
                touched.add((ti, f))
        assert affected, f'Patch {index} does not change a visible sample'
        changed.add(ti)
        applied.append({'patch': index, 'track_index': ti, 'operation': operation,
                        'samples_changed': len(affected), 'first_frame': min(affected), 'last_frame': max(affected)})
    result = []
    for ti, track in enumerate(corrected):
        result.extend(segments(track, len(times)) if ti in changed else [track])
    return result, {'patches_applied': len(applied), 'distinct_object_frames_changed': len(touched),
                    'affected_source_tracks': len(changed), 'patch_details': applied}

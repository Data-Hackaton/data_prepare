"""Safety checks for frame-indexed corrections, gaps and preserved tracks."""
import copy
from review_corrections import apply, tracks_checksum


def main():
    samples = [{'frame': f, 'box': [10,20,30,50], 'outside': False,
                'occluded': False, 'attributes': {}} for f in range(8)]
    original = [{'label': 'person', 'attributes': {}, 'samples': samples},
                {'label': 'table', 'attributes': {}, 'samples': copy.deepcopy(samples)}]
    pristine = copy.deepcopy(original)
    def spec(patches):
        return {'baseline_tracks_sha256': tracks_checksum(original), 'patches': patches}
    base = {'track_index': 0, 'reason': 'Fixture: real reviewed disappearance', 'evidence_frames': [3,4]}
    result, stats = apply(original, spec([dict(base, operation='outside', frames=[3,4])]), list(range(8)))
    assert original == pristine and result[-1] == original[1]
    assert [[s['frame'] for s in t['samples'] if not s['outside']] for t in result[:-1]] == [[0,1,2],[5,6,7]]
    assert result[0]['samples'][-1]['outside'] and result[0]['samples'][-1]['frame'] == 3
    assert stats['distinct_object_frames_changed'] == 2
    result, _ = apply(original, spec([dict(base, operation='relabel', frames=[3,5], label='reflection')]), list(range(8)))
    assert [t['label'] for t in result] == ['person','reflection','person','table']
    assert result[1]['samples'][-1]['outside'] and result[1]['samples'][-1]['frame'] == 6
    result, _ = apply(original, spec([dict(base, operation='replace_box', frames=[1,3], keyframes=[
        {'frame':1,'box':[10,20,40,50]}, {'frame':3,'box':[20,30,50,60]}])]), [0,1,2,4,5,6,7,8])
    assert result[0]['samples'][2]['box'] == [13.33,23.33,43.33,53.33]
    assert result[0]['samples'][0]['box'] == original[0]['samples'][0]['box']
    result, _ = apply(original, spec([dict(base, operation='outside', frames=[0,7])]), list(range(8)))
    assert result == original[1:]
    bad = spec([]); bad['baseline_tracks_sha256'] = 'changed'
    try:
        apply(original, bad, list(range(8)))
    except AssertionError:
        pass
    else:
        raise AssertionError('Changed baseline was not rejected')
    addition={'label':'person','samples':[{'frame':3,'box':[12,22,32,52],'outside':False}]}
    result,_=apply(original,spec([dict(operation='add_track',track=addition,
        reason='Fixture: a visually confirmed missing object',evidence_frames=[3])]),list(range(8)))
    assert result[-1]['samples'][0].get('occluded') is False, 'New reviewed tracks need the CVAT occlusion field'
    assert 'occluded' not in addition['samples'][0], 'Do not mutate the patch input'
    from import_annotations import payload_for
    payload=payload_for({'tracks':result},{
        'person':{'id':1,'name':'person','attributes':[]},
        'table':{'id':2,'name':'table','attributes':[]}})
    assert payload['tracks'][-1]['shapes'][0]['occluded'] is False
    print('PASS: gaps, relabel splits, VFR interpolation, preserved objects, immutable input, empty tracks, stale-baseline rejection')


if __name__ == '__main__':
    main()

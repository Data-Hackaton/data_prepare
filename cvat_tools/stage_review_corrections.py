"""Stage reviewed patch files against immutable published annotation baselines."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from review_corrections import apply, tracks_checksum

ROOT=Path(__file__).resolve().parent
QA=ROOT/'qa_20261017'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('files',nargs='+',type=Path)
    parser.add_argument('--videos',nargs='*')
    args=parser.parse_args()
    path=ROOT/'manual/dense_corrections.json'
    bundle=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema_version':1,'videos':{}}
    grouped=defaultdict(list)
    for file in args.files:
        patches=json.loads(file.read_text(encoding='utf-8'))
        if isinstance(patches,dict):patches=patches['patches']
        for patch in patches:
            if not args.videos or patch['video'] in args.videos:
                grouped[patch['video']].append(patch)
    reports=[]
    for name,patches in grouped.items():
        before=json.loads((QA/'baseline'/f'{name}.assembled.json').read_text(encoding='utf-8'))
        times=json.loads((ROOT.parent/'data/frame_times'/f'{name}.json').read_text(encoding='utf-8'))
        spec={'source_sha256':before['source_sha256'],
              'baseline_tracks_sha256':tracks_checksum(before['tracks']),'patches':patches}
        result,stats=apply(before['tracks'],spec,times)
        assert any(t['label']=='table' for t in result)
        assert {s['frame'] for t in result for s in t['samples'] if not s['outside']}==set(range(before['frame_count']))
        bundle['videos'][name]=spec
        reports.append({'video':name,**stats})
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)
    report=QA/'staged_corrections.json'
    report.write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'staged_videos':len(grouped),'patches':sum(len(x) for x in grouped.values()),
                      'object_frames_changed':sum(x['distinct_object_frames_changed'] for x in reports)}))


if __name__=='__main__':main()

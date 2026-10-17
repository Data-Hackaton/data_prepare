"""Check exported labels and visible rectangles against the assembled snapshot."""
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def check(name):
    assembled=json.loads((ROOT/'assembled'/f'{name}.json').read_text(encoding='utf-8'))
    expected=Counter((track['label'],s['frame'],tuple(round(float(v),2) for v in s['box']),
                      bool(s.get('occluded',False)))
                     for track in assembled['tracks'] for s in track['samples'] if not s['outside'])
    actual=Counter()
    for event,track in ET.iterparse(ROOT/'exports/per-video'/f'{name}.xml',events=('end',)):
        if track.tag!='track':continue
        for box in track.findall('box'):
            if box.get('outside','0')=='1':continue
            coords=tuple(round(float(box.get(key)),2) for key in ('xtl','ytl','xbr','ybr'))
            actual[(track.get('label'),int(box.get('frame')),coords,box.get('occluded','0')=='1')]+=1
        track.clear()
    missing=expected-actual
    assert not missing, (name,'Export differs from assembled visible geometry',list(missing.items())[:3])
    return dict(video=name,visible_object_frames=sum(expected.values()),
        geometry_labels_occlusion_match=True,additional_export_object_frames=sum((actual-expected).values()))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('videos',nargs='*');args=parser.parse_args()
    names=args.videos or [i['video'] for i in json.loads((ROOT.parent/'data/video_frame_manifest.json').read_text(encoding='utf-8'))['items']]
    result=[check(name) for name in names]
    report=dict(checked_at=datetime.now(timezone.utc).isoformat(),videos=len(result),
        all_exported_geometry_matches=True,per_video=result,
        archive_sha256=hashlib.sha256((ROOT/'exports/datathon-42-videos-cvat.zip').read_bytes()).hexdigest())
    if not args.videos:
        (ROOT/'exports/geometry-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(videos=len(result),all_exported_geometry_matches=True,
        visible_object_frames=sum(r['visible_object_frames'] for r in result))))

if __name__=='__main__':main()

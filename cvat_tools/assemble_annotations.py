"""Combine reviewed scene keyframes with dense automatic motion tracks.

Every source frame is explicit. This does not assert exhaustive visual review.
"""
from __future__ import annotations
import argparse
import bisect
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import cv2
import numpy as np
from deduplicate_people import deduplicate_people

ROOT=Path(__file__).resolve().parent
DATA=ROOT.parent/'data'
OUT=ROOT/'assembled'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def nearest(times,t):
    i=bisect.bisect_left(times,float(t))
    if i==0:return 0
    if i==len(times):return i-1
    return i-1 if abs(times[i-1]-t)<=abs(times[i]-t) else i

def densify(track,times):
    keys={nearest(times,k['time_sec']):dict(k) for k in track['keyframes']}
    indices=sorted(keys)
    assert indices
    n=len(times)
    assert indices[-1]==n-1 or keys[indices[-1]].get('outside',False), 'Track must terminate or reach final source frame'
    base=dict(track.get('attributes',{}))
    # Carry attributes forward before interpolation and uncertainty handling.
    current=base.copy()
    for i in indices:
        current.update(keys[i].get('attributes',{}))
        keys[i]['attributes']=current.copy()
    samples=[]
    j=0
    for f in range(indices[0],n):
        while j+1<len(indices) and indices[j+1]<=f:j+=1
        left=keys[indices[j]]
        right=keys[indices[j+1]] if j+1<len(indices) else left
        outside=bool(left.get('outside',False))
        # Outside stretches need just the first terminating shape.
        if outside and (f!=indices[j] or (samples and samples[-1]['outside'])):continue
        box=np.array(left['box'],dtype=float)
        if not outside and not right.get('outside',False) and j+1<len(indices):
            fraction=(times[f]-times[indices[j]])/(times[indices[j+1]]-times[indices[j]])
            box=box*(1-fraction)+np.array(right['box'])*fraction
        attrs=left['attributes'].copy()
        if f!=indices[j] and j+1<len(indices):
            for name in ('state','screen'):
                if name in attrs and attrs[name]!=right['attributes'].get(name,attrs[name]):
                    attrs[name]='unknown'
        samples.append({'frame':f,'box':[round(float(x),2) for x in box],
                        'outside':outside,'occluded':bool(left.get('occluded',False)),
                        'attributes':attrs,'method':'reviewed_keyframe' if f in keys else 'interpolation'})
    return {'label':track['label'],'attributes':base,'samples':samples,'origin':'scene_keyframes'}

def region_kind(region,index):
    explicit=region.get('kind',region.get('type','')).lower()
    description=str(region.get('condition','')).lower()
    if explicit in ('door','closed_door') or ('door' in description and 'closed' in description):
        return 'closed_door'
    return 'fixed_glass'

def reflection(box,frame,manual,door_states,in_room_identity=False):
    limit=manual.get('room_entry_boundary',{}).get('conservative_glass_person_max_bottom_y',320)
    center=((box[0]+box[2])/2,(box[1]+box[3])/2)
    for i,region in enumerate(manual.get('reflection_regions',[])):
        if box[3]>region.get('max_bottom_y',region.get('max_person_bottom_y',limit)):continue
        if center[0]>region.get('max_center_x',float('inf')):continue
        points=region.get('polygon')
        if not points:
            b=region.get('box',region.get('bbox'))
            if b:points=[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]]]
        if not points:continue
        if region_kind(region,i)=='closed_door' and (door_states.get(frame)!='closed' or in_room_identity):continue
        if cv2.pointPolygonTest(np.asarray(points,dtype=np.float32),center,False)>=0:return True
    return False

def split_dense(labelled,original_id,origin):
    """Split at label changes; close tracks explicitly at missing frames."""
    result=[];segment=None
    for label,sample in labelled:
        if segment is None or label!=segment['label'] or sample['frame']!=segment['samples'][-1]['frame']+1:
            if segment:
                end=dict(segment['samples'][-1],frame=segment['samples'][-1]['frame']+1,outside=True)
                segment['samples'].append(end)
            segment={'label':label,'attributes':{},'samples':[],'origin':origin,'original_id':original_id}
            result.append(segment)
        segment['samples'].append(sample)
    return result

def make_dynamic(auto,manual,scene,n):
    door_states={s['frame']:s['attributes'].get('state','unknown')
                 for t in scene if t['label']=='door' for s in t['samples'] if not s['outside']}
    people=[];hands=[];uncertain=0
    times=json.loads((DATA/'frame_times'/f"{manual['video']}.json").read_text())
    empty_intervals=[(nearest(times,a),nearest(times,b)) for a,b in manual.get('empty_room_intervals_sec',[])]
    doorway_intervals=[(nearest(times,a),nearest(times,b)) for a,b in manual.get('doorway_person_intervals_sec',[])]
    for t in auto['tracks']:
        visible=[s for s in t['samples'] if not s[5]]
        if not visible:continue
        if len(visible)<5 and max(s[7] for s in visible)<.4:continue
        fully_in_room=[s[0] for s in visible if s[4]>450]
        labelled=[]
        for s in visible:
            f=s[0]
            sample={'frame':f,'box':s[1:5],'outside':False,'occluded':False,
                    'attributes':{},'method':s[8],'score':s[7]}
            if s[6]:uncertain+=1
            label=t['label']
            nearby=bisect.bisect_left(fully_in_room,f-60)
            in_room_identity=(nearby<len(fully_in_room) and fully_in_room[nearby]<=f+60) or any(a<=f<=b for a,b in doorway_intervals)
            if label=='person' and reflection(sample['box'],f,manual,door_states,in_room_identity):label='reflection'
            if label=='person' and any(a<=f<=b for a,b in empty_intervals):label='reflection'
            labelled.append((label,sample))
        result=split_dense(labelled,t['id'],'dynamic_tracking')
        # Last outside sample prevents the last box persisting beyond its evidence.
        if result and result[-1]['samples'][-1]['frame']<n-1:
            last=result[-1]['samples'][-1]
            result[-1]['samples'].append(dict(last,frame=last['frame']+1,outside=True))
        if t['label']=='hand':hands.extend(result)
        else:people.extend(result)
    deduplicated,dedup_stats=deduplicate_people(people)
    people=[]
    for t in deduplicated:
        labelled=[(t['label'],s) for s in t['samples'] if not s['outside']]
        parts=split_dense(labelled,t['original_id'],'dynamic_tracking')
        if parts and parts[-1]['samples'][-1]['frame']<n-1:
            last=parts[-1]['samples'][-1]
            parts[-1]['samples'].append(dict(last,frame=last['frame']+1,outside=True))
        people.extend(parts)
    real=defaultdict(list)
    for t in people:
        if t['label']=='person':
            for s in t['samples']:
                if not s['outside']:real[s['frame']].append(s['box'])
    filtered=[];removed=0
    for t in hands:
        samples=[]
        for s in t['samples']:
            if s['outside']:continue
            b=s['box'];x=(b[0]+b[2])/2;y=(b[1]+b[3])/2
            # Keep hand candidates supported by a real in-room person's extent.
            supported=any(p[0]-35<=x<=p[2]+35 and p[1]-12<=y<=p[3]+20 for p in real[s['frame']])
            if supported:samples.append(('hand',s))
            else:removed+=1
        parts=split_dense(samples,t['original_id'],'dynamic_tracking')
        if parts and parts[-1]['samples'][-1]['frame']<n-1:
            last=parts[-1]['samples'][-1]
            parts[-1]['samples'].append(dict(last,frame=last['frame']+1,outside=True))
        filtered.extend(parts)
    return people+filtered,{'uncertain_dynamic_samples':uncertain,'unsupported_hand_samples_removed':removed,**dedup_stats}

def load_manual():
    found={}
    for path in sorted((ROOT/'manual').glob('scene_*.json')):
        data=json.loads(path.read_text(encoding='utf-8'))
        for video in data['videos']:
            assert video['video'] not in found
            found[video['video']]=(video,path)
    for path in sorted((ROOT/'manual/overrides').glob('*.json')):
        data=json.loads(path.read_text(encoding='utf-8'))
        for video in data['videos']:
            assert video['video'] in found, 'Override requires an existing source video'
            found[video['video']]=(video,path)
    reflection_path=ROOT/'manual/reflection_overrides.json'
    if reflection_path.exists():
        for name,metadata in json.loads(reflection_path.read_text(encoding='utf-8')).items():
            if name in found:found[name][0].update(metadata)
    return found

def assemble(name,manual_index=None):
    manifest=json.loads((DATA/'video_frame_manifest.json').read_text(encoding='utf-8'))
    items={i['video']:i for i in manifest['items']}
    item=items[name];source=item['duplicate_of'] or name
    index=manual_index or load_manual()
    manual,path=index[source]
    times=json.loads((DATA/'frame_times'/f'{name}.json').read_text())
    auto_path=ROOT/'automatic'/f'{source}.json'
    auto=json.loads(auto_path.read_text())
    assert auto['source_sha256']==item['sha256'] and auto['frame_count']==len(times)==item['frame_count']
    assert auto['all_frames_decoded']
    scene=[densify(t,times) for t in manual['tracks']]
    dynamic,stats=make_dynamic(auto,manual,scene,len(times))
    tracks=scene+dynamic
    coverage=set();counts=Counter();unknown=Counter()
    for track in tracks:
        frames=[s['frame'] for s in track['samples']]
        assert frames==sorted(set(frames))
        for s in track['samples']:
            assert 0<=s['frame']<len(times)
            x1,y1,x2,y2=s['box']
            assert 0<=x1<x2<=464 and 0<=y1<y2<=848,(name,track['label'],s)
            if not s['outside']:
                coverage.add(s['frame']);counts[track['label']]+=1
                for key,value in s['attributes'].items():
                    if value=='unknown':unknown[f"{track['label']}.{key}"]+=1
    assert coverage==set(range(len(times)))
    result={'video':name,'source_video':source,'frame_count':len(times),'source_sha256':item['sha256'],
            'all_source_frames_decoded':True,'frames_with_annotations':len(coverage),
            'review_status':'assisted_annotation_requires_visual_review','tracks':tracks,
            'provenance':{'scene_file':str(path),'scene_sha256':digest(path),
                          'dynamic_sha256':digest(auto_path),'scene_reviewed_samples':manual.get('reviewed_samples',[])},
            'quality':{**stats,'unknown_attribute_samples':dict(unknown),'visible_shapes_by_label':dict(counts),
                       'notes':manual.get('notes',[]),'unresolved':manual.get('unresolved',[])}}
    OUT.mkdir(exist_ok=True)
    reflection_path=ROOT/'manual/reflection_overrides.json'
    if reflection_path.exists():result['provenance']['reflection_metadata_sha256']=digest(reflection_path)
    target=OUT/f'{name}.json'
    target.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'assembled':name,'frames':len(times),'tracks':len(tracks),'shapes':sum(counts.values()),'quality':stats}),flush=True)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('videos',nargs='+')
    args=parser.parse_args()
    index=load_manual()
    for video in args.videos:assemble(video,index)

if __name__=='__main__':main()

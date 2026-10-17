"""Append assisted annotations to CVAT, preserving existing user objects.

The import journal prevents duplicate uploads. Jobs stay open for visual review.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from cvat_sdk import make_client
from bootstrap_and_upload import ROOT, HOST, credentials

OUT=ROOT/'imports'

def utc():return datetime.now(timezone.utc).isoformat()
def checksum(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def save(path,data):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)

def attribute_values(label,values,mutable):
    result=[]
    for attr in label['attributes']:
        if attr['mutable']!=mutable:continue
        value=values.get(attr['name'],attr['default_value'])
        assert value in attr['values'],(label['name'],attr['name'],value)
        result.append({'spec_id':attr['id'],'value':value})
    return result

def payload_for(assembled,labels):
    payload={'tags':[],'shapes':[],'tracks':[]}
    for track in assembled['tracks']:
        label=labels[track['label']]
        shapes=[]
        for sample in track['samples']:
            attrs={**track.get('attributes',{}),**sample.get('attributes',{})}
            shapes.append({'type':'rectangle','frame':sample['frame'],
                           'points':list(map(float,sample['box'])),'outside':sample['outside'],
                           'occluded':sample['occluded'],'z_order':0,'rotation':0.0,
                           'attributes':attribute_values(label,attrs,True)})
        payload['tracks'].append({'label_id':label['id'],'frame':shapes[0]['frame'],'group':0,
                                  'source':'auto','shapes':shapes,
                                  'attributes':attribute_values(label,track.get('attributes',{}),False)})
    return payload

def normalize_track(track):
    shapes=sorted(track['shapes'],key=lambda s:s['frame'])
    # CVAT removes leading outside shapes and starts at the first visible frame.
    while shapes and shapes[0].get('outside',False):shapes=shapes[1:]
    return {'label_id':track['label_id'],'frame':shapes[0]['frame'] if shapes else track['frame'],'group':track.get('group',0),
            'source':track.get('source','manual'),
            'attributes':sorted(track.get('attributes',[]),key=lambda a:a['spec_id']),
            'shapes':[{'frame':s['frame'],'type':str(s['type']),
                       'points':[round(float(v),2) for v in s['points']],
                       'outside':s.get('outside',False),'occluded':s.get('occluded',False),
                       'attributes':sorted(s.get('attributes',[]),key=lambda a:a['spec_id'])}
                      for s in shapes]}

def import_video(client,name):
    OUT.mkdir(exist_ok=True)
    target=OUT/f'{name}.json'
    local_path=ROOT/'assembled'/f'{name}.json'
    assembled=json.loads(local_path.read_text(encoding='utf-8'))
    manifest=json.loads((ROOT/'cvat-full-project.json').read_text(encoding='utf-8'))
    item=next(t for t in manifest['tasks'] if t['video']==name)
    assert assembled['frame_count']==item['frames'] and assembled['source_sha256']==item['source_sha256']
    task=client.tasks.retrieve(item['task_id'])
    labels={label.name:label.to_dict() for label in task.get_labels()}
    payload=payload_for(assembled,labels)
    payload_hash=checksum(payload)
    if target.exists():
        previous=json.loads(target.read_text(encoding='utf-8'))
        if previous['payload_sha256']!=payload_hash:
            raise RuntimeError(f'{name}: local annotations changed after import; reconcile explicitly without overwriting user edits')
        print(json.dumps({'video':name,'status':'already_imported','frames':item['frames']}),flush=True)
        return previous
    pending=OUT/f'{name}.pending.json'
    live=task.get_annotations().to_dict()
    backup=OUT/f'{name}.before.json'
    uploaded=False
    if pending.exists():
        previous=json.loads(pending.read_text(encoding='utf-8'))
        assert previous['payload_sha256']==payload_hash, 'Pending payload changed'
        before=json.loads(backup.read_text(encoding='utf-8'))
        previous_ids={t['id'] for t in before['tracks']}
        created=[t for t in live['tracks'] if t['id'] not in previous_ids]
        if Counter(checksum(normalize_track(t)) for t in created)==Counter(checksum(normalize_track(t)) for t in payload['tracks']):
            uploaded=True
        elif live!=before:
            raise RuntimeError(f'{name}: pending upload has ambiguous server changes; inspect before retrying')
    else:
        if backup.exists():raise RuntimeError(f'{name}: existing backup without journal requires inspection')
        before=live
        save(backup,before)
    before_ids={track['id'] for track in before['tracks']}
    save(pending,{'video':name,'task_id':task.id,'started_at':utc(),'payload_sha256':payload_hash,
                  'before_track_ids':sorted(before_ids),'expected_tracks':len(payload['tracks'])})
    if not uploaded:
        client.api_client.tasks_api.partial_update_annotations(
            action='create',id=task.id,patched_labeled_data_request=payload,
            _content_type='application/json',_validate_outputs=False,_request_timeout=300)
    after=task.get_annotations().to_dict()
    actual=[t for t in after['tracks'] if t['id'] not in before_ids]
    expected_hashes=Counter(checksum(normalize_track(t)) for t in payload['tracks'])
    actual_hashes=Counter(checksum(normalize_track(t)) for t in actual)
    if actual_hashes!=expected_hashes:
        save(OUT/f'{name}.readback.json',after)
        raise RuntimeError(f'{name}: read-back differs from submitted annotation data')
    after_ids={t['id'] for t in after['tracks']}
    assert before_ids<=after_ids, 'An existing user track disappeared'
    coverage={s['frame'] for t in actual for s in t['shapes'] if not s.get('outside',False)}
    assert coverage==set(range(item['frames']))
    summary={'video':name,'task_id':task.id,'job_urls':item['job_urls'],'imported_at':utc(),
             'status':'assisted_annotations_imported','payload_sha256':payload_hash,
             'assembled_sha256':hashlib.sha256(local_path.read_bytes()).hexdigest(),
             'tracks':len(actual),'track_ids':sorted(t['id'] for t in actual),
             'tracked_shapes':sum(len(t['shapes']) for t in actual),
             'frames':item['frames'],'frames_with_explicit_annotations':len(coverage),
             'readback_exact':True,'existing_tracks_preserved':len(before_ids),
             'review_status':'requires_visual_review','quality':assembled['quality']}
    for job in task.get_jobs():
        if str(job.state)=='new':job.update({'state':'in progress'})
    archive=OUT/f'{name}.assembled.json'
    if not archive.exists():save(archive,assembled)
    save(target,summary)
    pending.unlink()
    print(json.dumps({k:summary[k] for k in ('video','status','tracks','tracked_shapes','frames','readback_exact')},ensure_ascii=False),flush=True)
    return summary

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('videos',nargs='+')
    args=parser.parse_args()
    with make_client(HOST,credentials=credentials()) as client:
        for name in args.videos:import_video(client,name)

if __name__=='__main__':main()

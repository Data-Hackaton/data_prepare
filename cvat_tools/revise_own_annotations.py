"""Revise only this run's unchanged objects; preserve all other CVAT objects."""
import argparse,json
from collections import Counter
from datetime import datetime,timezone
from cvat_sdk import make_client
from bootstrap_and_upload import ROOT,HOST,credentials
from import_annotations import OUT,payload_for,normalize_track,checksum,save,utc

def fingerprints(tracks):return Counter(checksum(normalize_track(t)) for t in tracks)

def revise(client,name):
    ledger_path=OUT/f'{name}.json'
    ledger=json.loads(ledger_path.read_text(encoding='utf-8'))
    task=client.tasks.retrieve(ledger['task_id'])
    labels={l.name:l.to_dict() for l in task.get_labels()}
    old_data=json.loads((OUT/f'{name}.assembled.json').read_text(encoding='utf-8'))
    new_path=ROOT/'assembled'/f'{name}.json'
    new_data=json.loads(new_path.read_text(encoding='utf-8'))
    old_payload=payload_for(old_data,labels)
    new_payload=payload_for(new_data,labels)
    if fingerprints(old_payload['tracks'])==fingerprints(new_payload['tracks']):
        print(json.dumps({'video':name,'revision':'no_annotation_changes'}),flush=True)
        return
    current=task.get_annotations().to_dict()
    old_ids=set(ledger['track_ids'])
    own=[t for t in current['tracks'] if t['id'] in old_ids]
    if fingerprints(own)!=fingerprints(old_payload['tracks']):
        raise RuntimeError(f'{name}: user edits detected; automated replacement refused')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    backup=OUT/'revisions'/f'{name}-{stamp}'
    backup.mkdir(parents=True)
    save(backup/'before.json',current);save(backup/'ledger.json',ledger);save(backup/'assembled.json',old_data)
    before_ids={t['id'] for t in current['tracks']}
    client.api_client.tasks_api.partial_update_annotations(action='create',id=task.id,
        patched_labeled_data_request=new_payload,_request_timeout=300)
    uploaded=task.get_annotations().to_dict()
    added=[t for t in uploaded['tracks'] if t['id'] not in before_ids]
    assert fingerprints(added)==fingerprints(new_payload['tracks'])
    # Recheck after uploading, before deleting only our previously imported IDs.
    still_own=[t for t in uploaded['tracks'] if t['id'] in old_ids]
    if fingerprints(still_own)!=fingerprints(old_payload['tracks']):
        save(backup/'conflict.json',uploaded)
        raise RuntimeError(f'{name}: concurrent edit detected; old objects preserved')
    client.api_client.tasks_api.partial_update_annotations(action='delete',id=task.id,
        patched_labeled_data_request={'tracks':still_own,'shapes':[],'tags':[]},_request_timeout=300)
    final=task.get_annotations().to_dict()
    added_ids={t['id'] for t in added}
    assert not old_ids & {t['id'] for t in final['tracks']}
    assert fingerprints([t for t in final['tracks'] if t['id'] in added_ids])==fingerprints(new_payload['tracks'])
    others_before=[t for t in current['tracks'] if t['id'] not in old_ids]
    others_after=[t for t in final['tracks'] if t['id'] not in added_ids]
    assert fingerprints(others_before)==fingerprints(others_after)
    coverage={s['frame'] for t in added for s in t['shapes'] if not s['outside']}
    assert coverage==set(range(new_data['frame_count']))
    ledger.update({'imported_at':utc(),'payload_sha256':checksum(new_payload),'tracks':len(added),
                   'track_ids':sorted(added_ids),'tracked_shapes':sum(len(t['shapes']) for t in added),
                   'quality':new_data['quality'],'revision_backup':str(backup),'readback_exact':True})
    import hashlib
    ledger['assembled_sha256']=hashlib.sha256(new_path.read_bytes()).hexdigest()
    save(OUT/f'{name}.assembled.json',new_data);save(ledger_path,ledger)
    for job in task.get_jobs():
        if str(job.state)=='new':job.update({'state':'in progress'})
    print(json.dumps({'video':name,'revision':'verified','tracks':len(added),'frames':len(coverage),'other_tracks_preserved':len(others_before)}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('videos',nargs='+');args=parser.parse_args()
    with make_client(HOST,credentials=credentials()) as client:
        for name in args.videos:revise(client,name)

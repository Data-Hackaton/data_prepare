"""Replace only changed owned tracks, with backups and exact full readback."""
import argparse
import hashlib
import json
from collections import Counter,defaultdict,deque
from datetime import datetime,timezone
from cvat_sdk import make_client
from bootstrap_and_upload import ROOT,HOST,credentials
from import_annotations import OUT,payload_for,normalize_track,checksum,save,utc
from revise_own_annotations import fingerprints

def select_delta(old,desired):
    available=defaultdict(deque)
    for track in old:
        available[checksum(normalize_track(track))].append(track['id'])
    kept=[];added=[]
    for track in desired:
        bucket=available[checksum(normalize_track(track))]
        if bucket:kept.append(bucket.popleft())
        else:added.append(track)
    keep_set=set(kept)
    return kept,added,[t for t in old if t['id'] not in keep_set]

def revise(client,name):
    ledger_path=OUT/f'{name}.json';ledger=json.loads(ledger_path.read_text(encoding='utf-8'))
    task=client.tasks.retrieve(ledger['task_id'])
    labels={l.name:l.to_dict() for l in task.get_labels()}
    old_data=json.loads((OUT/f'{name}.assembled.json').read_text(encoding='utf-8'))
    new_path=ROOT/'assembled'/f'{name}.json';new_data=json.loads(new_path.read_text(encoding='utf-8'))
    old_payload=payload_for(old_data,labels);new_payload=payload_for(new_data,labels)
    before=task.get_annotations().to_dict();old_ids=set(ledger['track_ids'])
    owned=[t for t in before['tracks'] if t['id'] in old_ids]
    assert fingerprints(owned)==fingerprints(old_payload['tracks']),f'{name}: existing user edits detected'
    kept,create,remove=select_delta(owned,new_payload['tracks'])
    if not create and not remove:
        print(json.dumps(dict(video=name,revision='no_annotation_changes',readback_exact=True)),flush=True)
        return dict(video=name,task_id=task.id,readback_exact=True,tracks=len(owned),
            assembled_sha256=hashlib.sha256(new_path.read_bytes()).hexdigest(),other_tracks_preserved=len(before['tracks'])-len(owned))
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    backup=OUT/'revisions'/f'{name}-{stamp}';backup.mkdir(parents=True)
    save(backup/'before.json',before);save(backup/'ledger.json',ledger);save(backup/'assembled.json',old_data)
    before_ids={t['id'] for t in before['tracks']}
    if create:
        client.api_client.tasks_api.partial_update_annotations(action='create',id=task.id,
            patched_labeled_data_request=dict(tracks=create,shapes=[],tags=[]),_request_timeout=300)
    uploaded=task.get_annotations().to_dict()
    added=[t for t in uploaded['tracks'] if t['id'] not in before_ids]
    assert fingerprints(added)==fingerprints(create),f'{name}: new track readback mismatch; originals retained'
    still_owned=[t for t in uploaded['tracks'] if t['id'] in old_ids]
    assert fingerprints(still_owned)==fingerprints(owned),f'{name}: concurrent edit detected; originals retained'
    if remove:
        client.api_client.tasks_api.partial_update_annotations(action='delete',id=task.id,
            patched_labeled_data_request=dict(tracks=remove,shapes=[],tags=[]),_request_timeout=300)
    final=task.get_annotations().to_dict()
    new_ids=set(kept)|{t['id'] for t in added}
    final_owned=[t for t in final['tracks'] if t['id'] in new_ids]
    assert fingerprints(final_owned)==fingerprints(new_payload['tracks']),f'{name}: full final readback mismatch'
    assert not {t['id'] for t in remove}&{t['id'] for t in final['tracks']}
    assert fingerprints([t for t in before['tracks'] if t['id'] not in old_ids])==fingerprints([t for t in final['tracks'] if t['id'] not in new_ids])
    coverage={s['frame'] for t in final_owned for s in t['shapes'] if not s['outside']}
    assert coverage==set(range(new_data['frame_count']))
    ledger.update(imported_at=utc(),payload_sha256=checksum(new_payload),tracks=len(final_owned),
        track_ids=sorted(new_ids),tracked_shapes=sum(len(t['shapes']) for t in final_owned),
        quality=new_data['quality'],revision_backup=str(backup),readback_exact=True,
        assembled_sha256=hashlib.sha256(new_path.read_bytes()).hexdigest())
    save(OUT/f'{name}.assembled.json',new_data);save(ledger_path,ledger)
    print(json.dumps(dict(video=name,revision='verified_incremental',reused_tracks=len(kept),
        created_tracks=len(added),removed_tracks=len(remove),frames=len(coverage))),flush=True)
    return dict(video=name,task_id=task.id,readback_exact=True,tracks=len(final_owned),
        assembled_sha256=ledger['assembled_sha256'],other_tracks_preserved=len(final['tracks'])-len(final_owned))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('videos',nargs='*');args=parser.parse_args()
    names=args.videos or [i['video'] for i in json.loads((ROOT.parent/'data/video_frame_manifest.json').read_text(encoding='utf-8'))['items']]
    checks=[]
    with make_client(HOST,credentials=credentials()) as client:
        for name in names:checks.append(revise(client,name))
    if not args.videos:
        report=dict(checked_at=utc(),videos=len(checks),all_readbacks_exact=True,
            corrections_sha256=hashlib.sha256((ROOT/'manual/dense_corrections.json').read_bytes()).hexdigest(),per_video=checks)
        save(ROOT/'qa_20261017/readback-step5-final.json',report)
    print('ALL_READBACKS_EXACT',len(checks),flush=True)

if __name__=='__main__':main()

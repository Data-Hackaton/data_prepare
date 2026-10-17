"""Import finished videos as the local tracking batch produces them."""
import json,time
from datetime import datetime,timezone
from cvat_sdk import make_client
from bootstrap_and_upload import ROOT,HOST,credentials
from assemble_annotations import load_manual,assemble
from import_annotations import import_video,save,OUT

def status(tasks):
    completed=[]
    for item in tasks:
        path=OUT/f"{item['video']}.json"
        if path.exists():completed.append(json.loads(path.read_text(encoding='utf-8')))
    calculated=[]
    for path in (ROOT/'automatic').glob('X-*.json'):
        data=json.loads(path.read_text())
        calculated.append({'video':data['video'],'frames':data['frame_count']})
    report={'updated_at':datetime.now(timezone.utc).isoformat(),
            'project_url':f'{HOST}/projects/1','total_videos':len(tasks),'total_frames':sum(t['frames'] for t in tasks),
            'imported_videos':len(completed),'imported_frames':sum(t['frames'] for t in completed),
            'calculated_unique_videos':len(calculated),'calculated_unique_frames':sum(t['frames'] for t in calculated),
            'imported_video_names':[t['video'] for t in completed],
            'review_status':'assisted_annotations_require_visual_review'}
    report['imported_frame_percent']=round(report['imported_frames']/report['total_frames']*100,2)
    save(ROOT/'annotation-status.json',report)
    return report

def main():
    tasks=json.loads((ROOT/'cvat-full-project.json').read_text(encoding='utf-8'))['tasks']
    with make_client(HOST,credentials=credentials()) as client:
        last=None
        while True:
            manual=load_manual()
            ready_path=ROOT/'manual/ready_videos.json'
            ready=set(json.loads(ready_path.read_text()) if ready_path.exists() else [])
            for task in tasks:
                name=task['video'];source=task.get('duplicate_of') or name
                if (OUT/f'{name}.json').exists():continue
                if source not in manual:continue
                if source not in ready and not manual[source][0].get('annotation_ready'):continue
                if not (ROOT/'automatic'/f'{source}.json').exists():continue
                assemble(name,manual)
                import_video(client,name)
                current=status(tasks)
                print(json.dumps(current,ensure_ascii=False),flush=True)
            current=status(tasks)
            key=(current['imported_videos'],current['calculated_unique_videos'])
            if key!=last:
                print(json.dumps(current,ensure_ascii=False),flush=True);last=key
            if current['imported_videos']==len(tasks):break
            time.sleep(15)

if __name__=='__main__':main()

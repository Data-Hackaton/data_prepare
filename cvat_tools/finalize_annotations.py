"""Apply reviewed fixes, verify full project coverage, and export annotations."""
import contextlib
import io
import json
import traceback
import time
from datetime import datetime,timezone
from cvat_sdk import make_client
from bootstrap_and_upload import ROOT,HOST,credentials
from assemble_annotations import assemble,load_manual
from import_annotations import import_video
from revise_own_annotations import revise
import verify_cvat
import export_annotations

status_path=ROOT/'finalization-status.json'
state={'phase':'starting','completed_videos':[],'errors':[]}
def status(**changes):
    state.update(changes,updated_at=datetime.now(timezone.utc).isoformat())
    temporary=status_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    # Windows readers/antivirus can briefly hold the destination without
    # FILE_SHARE_DELETE. A progress-file collision must not stop CVAT work.
    for attempt in range(20):
        try:
            temporary.replace(status_path)
            break
        except PermissionError:
            if attempt==19:
                print('Progress file temporarily locked; continuing.',flush=True)
            else:time.sleep(.1)
    print(json.dumps({k:state[k] for k in ('phase','updated_at','errors')}
        |{'completed':len(state['completed_videos']),'video':state.get('video')},ensure_ascii=False),flush=True)

def main():
    tasks=json.loads((ROOT/'cvat-full-project.json').read_text(encoding='utf-8'))['tasks']
    index=load_manual()
    diagnostics=[]
    with make_client(HOST,credentials=credentials()) as client:
        for item in tasks:
            name=item['video']
            status(phase='applying_reviewed_fixes',video=name)
            with contextlib.redirect_stdout(io.StringIO()):
                assembled=assemble(name,index)
            diagnostics.append({'video':name,**{k:v for k,v in assembled['quality'].items() if k.startswith('duplicate_people')}})
            if (ROOT/'imports'/f'{name}.json').exists():revise(client,name)
            else:import_video(client,name)
            state['completed_videos'].append(name)
            status()
    (ROOT/'people-dedup-audit.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),encoding='utf-8')
    status(phase='verifying_project',video=None)
    verify_cvat.main()
    status(phase='exporting_annotations')
    export_annotations.main()
    status(phase='complete')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        status(phase='failed',errors=[str(exc)])
        traceback.print_exc()
        raise

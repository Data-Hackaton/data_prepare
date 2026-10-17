"""Export the annotated local project and verify the archive is readable."""
import argparse,copy,json,hashlib,zipfile
from collections import Counter,defaultdict
import xml.etree.ElementTree as ET
from cvat_sdk import make_client
from bootstrap_and_upload import ROOT,HOST,credentials

def main(download=True):
    report=json.loads((ROOT/'verification.json').read_text(encoding='utf-8'))
    assert not report['errors']
    assert report['total_tasks']==report['tasks_with_annotations']==42
    assert report['total_frames']==report['frames_with_explicit_annotations']==43230
    destination=ROOT/'exports'
    destination.mkdir(exist_ok=True)
    archive=destination/'datathon-42-videos-cvat.zip'
    if download:
        with make_client(HOST,credentials=credentials()) as client:
            project=client.projects.retrieve(1)
            project.export_dataset('CVAT for video 1.1',archive,include_images=False,status_check_period=5)
    per_video=destination/'per-video';per_video.mkdir(exist_ok=True)
    handles={};task_names={};offsets={}
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        entries=z.namelist()
        assert any(name.endswith('.xml') for name in entries)
        source=json.loads((ROOT/'cvat-full-project.json').read_text(encoding='utf-8'))
        expected={t['task_id']:t['frames'] for t in source['tasks']}
        exported_frames=defaultdict(set);exported_tracks=Counter()
        for name in entries:
            if not name.endswith('.xml'):continue
            with z.open(name) as stream:
                for event,node in ET.iterparse(stream,events=('end',)):
                    if node.tag=='meta':
                        project=node.find('project')
                        cursor=0;previous_subset=None
                        for task in project.findall('./tasks/task'):
                            task_id=int(task.findtext('id'));name=task.findtext('name')
                            subset=task.findtext('subset')
                            if subset!=previous_subset:cursor=0;previous_subset=subset
                            assert int(task.findtext('size'))==expected[task_id]
                            assert task.findtext('frame_filter') in ('','step=1',None)
                            assert int(task.findtext('start_frame'))==0
                            offsets[task_id]=cursor;cursor+=expected[task_id];task_names[task_id]=name
                            single_meta=ET.Element('meta');single_task=copy.deepcopy(task)
                            single_task.append(copy.deepcopy(project.find('labels')));single_meta.append(single_task)
                            handle=(per_video/f'{name}.xml').open('wb');handles[task_id]=handle
                            handle.write(b'<?xml version="1.0" encoding="utf-8"?>\n<annotations>\n<version>1.1</version>\n')
                            handle.write(ET.tostring(single_meta,encoding='utf-8'))
                        continue
                    if node.tag!='track':continue
                    task_id=int(node.attrib['task_id'])
                    assert task_id in expected
                    exported_tracks[task_id]+=1
                    for shape in node:
                        if shape.tag=='attribute':continue
                        # CVAT project XML uses cumulative frames within each
                        # subset (ProjectData._init_task_frame_offsets).
                        frame=int(shape.attrib['frame'])-offsets[task_id]
                        assert 0<=frame<expected[task_id],(task_id,frame,expected[task_id])
                        if shape.attrib.get('outside','0')=='0':exported_frames[task_id].add(frame)
                        shape.attrib['frame']=str(frame)
                    node.attrib.pop('task_id');node.attrib.pop('subset',None)
                    node.attrib['id']=str(exported_tracks[task_id]-1)
                    handles[task_id].write(ET.tostring(node,encoding='utf-8'))
                    node.clear()
        assert set(exported_frames)==set(expected)
        assert all(exported_frames[k]==set(range(n)) for k,n in expected.items())
    individual=[]
    for task_id,handle in handles.items():
        handle.write(b'\n</annotations>\n');handle.close()
        name=task_names[task_id];xml=per_video/f'{name}.xml';target=per_video/f'{name}.zip'
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:z.write(xml,'annotations.xml')
        with zipfile.ZipFile(target) as z:assert z.testzip() is None
        individual.append({'video':name,'file':f'per-video/{name}.zip','frames':expected[task_id],
                           'tracks':exported_tracks[task_id],'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    # Compress the unchanged official project XML, which CVAT stores verbatim.
    compressed=archive.with_suffix('.compressed.zip')
    with zipfile.ZipFile(archive) as src,zipfile.ZipFile(compressed,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as dst:
        for name in src.namelist():dst.writestr(name,src.read(name))
    with zipfile.ZipFile(compressed) as z:assert z.testzip() is None
    compressed.replace(archive)
    output={'archive':str(archive),'bytes':archive.stat().st_size,
            'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'entries':entries,
            'all_frames':43230,'videos':42,'exported_tracks':sum(exported_tracks.values()),
            'export_frame_coverage_verified':True,'per_video':individual,
            'review_status':'assisted_annotations_require_visual_review'}
    (destination/'manifest.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in output.items() if k!='per_video'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify-existing',action='store_true')
    main(download=not parser.parse_args().verify_existing)

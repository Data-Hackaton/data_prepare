"""Decode every frame, detect periodically, and track motion on intervening frames.

These are automatic annotations. Frame coverage is not a claim of exhaustive human review.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from scipy.optimize import linear_sum_assignment
from detect_onnx import Detector, iou

ROOT=Path(__file__).resolve().parent
DATA=ROOT.parent/'data'
OUT=ROOT/'automatic'
CROP=(0,240,464,660)
CONFIG={'people_step':15, 'hands_step':10, 'people_threshold':.25, 'hands_threshold':.22,
        'method':'Grounding DINO FP32 + per-frame Lucas-Kanade optical flow', 'crop':list(CROP)}


@dataclass
class Track:
    id: int
    label: str
    box: np.ndarray
    last_detection: int
    score: float
    history: list=field(default_factory=list)
    points: np.ndarray | None=None
    flow_good: bool=False
    missed: bool=False
    closed: bool=False


def corners(gray, box):
    x1,y1,x2,y2=np.round(box).astype(int)
    x1,y1=max(0,x1),max(0,y1)
    x2,y2=min(gray.shape[1]-1,x2),min(gray.shape[0]-1,y2)
    if x2-x1<3 or y2-y1<3:return None
    pts=cv2.goodFeaturesToTrack(gray[y1:y2+1,x1:x2+1],maxCorners=35,qualityLevel=.012,minDistance=3,blockSize=3)
    if pts is not None: pts += np.float32([x1,y1])
    return pts


def flow_tracks(active, old, gray):
    for track in active:
        track.flow_good=False
        pts=track.points
        if pts is None or len(pts)<3:pts=corners(old,track.box)
        if pts is None or len(pts)<3:continue
        new,status,error=cv2.calcOpticalFlowPyrLK(old,gray,pts,None,winSize=(19,19),maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,20,.02))
        if new is None:continue
        valid=(status.ravel()==1)&(error.ravel()<35)
        before,after=pts.reshape(-1,2)[valid],new.reshape(-1,2)[valid]
        if len(after)<3:continue
        back,bs,be=cv2.calcOpticalFlowPyrLK(gray,old,after[:,None,:],None,winSize=(19,19),maxLevel=3)
        valid_back=(bs.ravel()==1)&(np.linalg.norm(back.reshape(-1,2)-before,axis=1)<2.5)
        before,after=before[valid_back],after[valid_back]
        if len(after)<3:continue
        delta=np.median(after-before,axis=0)
        if np.linalg.norm(delta)>55:continue
        track.box += np.tile(delta,2)
        track.box[[0,2]]=np.clip(track.box[[0,2]],0,463.99)
        track.box[[1,3]]=np.clip(track.box[[1,3]],0,847.99)
        track.flow_good=True
        track.points=after[:,None,:].astype(np.float32)


def cost(a,b,label):
    ac=(a[:2]+a[2:])/2;bc=(b[:2]+b[2:])/2
    scale=max(10.,float(np.linalg.norm(a[2:]-a[:2])))
    distance=float(np.linalg.norm(ac-bc))/scale
    overlap=iou(a,b)
    ratio=max(float(np.prod(a[2:]-a[:2])),1)/max(float(np.prod(b[2:]-b[:2])),1)
    if (overlap<.1 and distance>(.8 if label=='hand' else .5)) or not .18<ratio<5.5:return 100.
    return 1-overlap+.3*distance


def update(active, tracks, rows, label, frame, gray, step):
    candidates=[t for t in active if t.label==label]
    matches=[]
    if candidates and rows:
        matrix=np.array([[cost(t.box,np.array(row['box']),label) for row in rows] for t in candidates])
        ti,di=linear_sum_assignment(matrix)
        matches=[(int(a),int(b)) for a,b in zip(ti,di) if matrix[a,b]<1.5]
    matched_t={a for a,b in matches};matched_d={b for a,b in matches}
    for a,b in matches:
        track,row=candidates[a],rows[b]
        track.box=np.array(row['box'],dtype=np.float32)
        track.last_detection=frame;track.score=row['score'];track.missed=False
        track.points=corners(gray,track.box)
    for a,track in enumerate(candidates):
        if a in matched_t:continue
        track.missed=True
        if frame-track.last_detection>=step*(2 if label=='person' else 1):
            track.closed=True
            track.history.append([frame,*map(float,track.box),True,True,round(track.score,4),'outside'])
    for b,row in enumerate(rows):
        if b in matched_d:continue
        track=Track(len(tracks),label,np.array(row['box'],dtype=np.float32),frame,row['score'])
        track.points=corners(gray,track.box)
        tracks.append(track);active.append(track)
    active[:]=[t for t in active if not t.closed]


def annotate(detector,item,force=False):
    name=item['video']
    target=OUT/f'{name}.json'
    if target.exists() and not force:
        previous=json.loads(target.read_text(encoding='utf-8'))
        if previous.get('frame_count')==item['frame_count'] and previous.get('config')==CONFIG:
            print(json.dumps({'video':name,'status':'reused','frames':item['frame_count']}),flush=True)
            return
    times=json.loads((DATA/'frame_times'/f'{name}.json').read_text())
    cap=cv2.VideoCapture(str(DATA/'videos'/f'{name}.mov'))
    if not cap.isOpened():raise RuntimeError(f'Cannot decode {name}')
    active=[];tracks=[];previous=None;coverage=[]
    start=time.perf_counter()
    for frame,pts in enumerate(times):
        ok,bgr=cap.read()
        if not ok:raise RuntimeError(f'Missing decoded frame {frame} in {name}')
        if bgr.shape[:2]!=(848,464):raise RuntimeError(f'Unexpected dimensions {name}')
        gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
        if previous is not None:flow_tracks(active,previous,gray)
        detect_people=frame%CONFIG['people_step']==0 or frame==len(times)-1
        detect_hands=frame%CONFIG['hands_step']==0 or frame==len(times)-1
        if detect_people or detect_hands:
            rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
            pil=Image.fromarray(rgb)
        if detect_people:
            rows=detector.detect(pil,queries=[('person','person')],threshold=CONFIG['people_threshold'])
            rows=[r for r in rows if r['box'][2]-r['box'][0]>12 and r['box'][3]-r['box'][1]>25]
            update(active,tracks,rows,'person',frame,gray,CONFIG['people_step'])
        if detect_hands:
            rows=detector.detect(pil.crop(CROP),queries=[('hand','hand')],threshold=CONFIG['hands_threshold'])
            filtered=[]
            for row in rows:
                x1,y1,x2,y2=row['box']
                row['box']=[x1+CROP[0],y1+CROP[1],x2+CROP[0],y2+CROP[1]]
                if 3<x2-x1<75 and 3<y2-y1<90 and (x2-x1)*(y2-y1)<4000:filtered.append(row)
            update(active,tracks,filtered,'hand',frame,gray,CONFIG['hands_step'])
        for track in active:
            detected=frame==track.last_detection
            track.history.append([frame,*[round(float(v),2) for v in track.box],False,
                                  bool(track.missed or (not detected and not track.flow_good)),
                                  round(track.score,4),'detector' if detected else 'optical_flow' if track.flow_good else 'hold_uncertain'])
        coverage.append(frame)
        previous=gray
        if frame%150==0 or frame==len(times)-1:
            status={'video':name,'frame':frame,'total':len(times),'elapsed_sec':round(time.perf_counter()-start,1),
                    'active_tracks':len(active),'all_decoded_so_far':len(coverage)==frame+1}
            (OUT/'progress.json').write_text(json.dumps(status),encoding='utf-8')
            print(json.dumps(status),flush=True)
    extra,unused=cap.read();cap.release()
    if extra:raise RuntimeError(f'Extra decoded frames in {name}')
    assert coverage==list(range(item['frame_count']))
    result={'video':name,'frame_count':len(times),'source_sha256':item['sha256'],'config':CONFIG,
            'all_frames_decoded':True,'frame_start':0,'frame_stop':len(times)-1,
            'human_review':'not_exhaustive','tracks':[{'id':t.id,'label':t.label,'samples':t.history} for t in tracks],
            'elapsed_sec':time.perf_counter()-start}
    temporary=target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
    temporary.replace(target)
    print(json.dumps({'video':name,'status':'complete','frames':len(times),'tracks':len(tracks),'elapsed_sec':result['elapsed_sec']}),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--videos',nargs='*')
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    cv2.setNumThreads(2)
    items=json.loads((DATA/'video_frame_manifest.json').read_text(encoding='utf-8'))['items']
    detector=Detector(0,verbose=False)
    if 'CUDAExecutionProvider' not in detector.session.get_providers():raise RuntimeError('CUDA unavailable; refusing an unexpectedly slow batch')
    for item in items:
        if item['duplicate_of'] or (args.videos and item['video'] not in args.videos):continue
        annotate(detector,item,args.force)


if __name__=='__main__':main()

"""Validate TF32 only for the person/hand queries used by the tracking batch."""
import json,time
from PIL import Image
from scipy.optimize import linear_sum_assignment
import numpy as np
from detect_onnx import Detector,ROOT,iou

reference=json.loads((ROOT/'probe/dynamic/report.json').read_text())
d=Detector(0,verbose=False,use_tf32=True)
results=[]
for row in reference:
    if row['mode'] not in ('people','hands'):continue
    query='person' if row['mode']=='people' else 'hand'
    threshold=.25 if query=='person' else .2
    image=Image.open(ROOT.parent/'data/frames/all-videos/images'/row['file']).convert('RGB').crop(row['region'])
    t=time.perf_counter(); actual=d.detect(image,[(query,query)],threshold); elapsed=time.perf_counter()-t
    expected=row['detections']
    matrix=np.array([[1-iou(a['box'],b['box']) for b in actual] for a in expected])
    matched=[]
    if expected and actual:
        aa,bb=linear_sum_assignment(matrix)
        matched=[{'iou':1-matrix[a,b],'score_error':abs(expected[a]['score']-actual[b]['score'])} for a,b in zip(aa,bb)]
    passed=len(expected)==len(actual) and all(m['iou']>.95 and m['score_error']<.03 for m in matched)
    results.append({'file':row['file'],'mode':row['mode'],'elapsed_sec':elapsed,'passed':bool(passed),'matches':matched,
                    'expected_count':len(expected),'actual_count':len(actual)})
    print(json.dumps(results[-1]),flush=True)
(ROOT/'probe/parity/tf32-dynamic.json').write_text(json.dumps(results,indent=2))
assert all(r['passed'] for r in results)

"""Check tensor-core mode against the previously measured CPU reference."""
import json,time
from PIL import Image
from scipy.optimize import linear_sum_assignment
import numpy as np
from detect_onnx import Detector,ROOT,iou

reference=json.loads((ROOT/'probe/parity/report.json').read_text())
d=Detector(0,verbose=False,use_tf32=True)
results=[]
for row in reference:
    image=Image.open(ROOT.parent/'data/frames/all-videos/images'/row['file']).convert('RGB').crop((0,270,464,600))
    t=time.perf_counter(); actual=d.detect(image); elapsed=time.perf_counter()-t
    expected=row['cpu_detections']
    matrix=np.array([[1-iou(a['box'],b['box']) for b in actual] for a in expected])
    aa,bb=linear_sum_assignment(matrix)
    matched=[{'iou':1-matrix[a,b],'score_error':abs(expected[a]['score']-actual[b]['score']),
              'label_equal':expected[a]['label']==actual[b]['label'],
              'uncertain':min(expected[a]['score'],actual[b]['score'])<.22} for a,b in zip(aa,bb)]
    passed=len(expected)==len(actual) and all(m['iou']>.95 and m['score_error']<.03 and (m['label_equal'] or m['uncertain']) for m in matched)
    results.append({'file':row['file'],'elapsed_sec':elapsed,'passed':bool(passed),'matches':matched,'actual':actual})
(ROOT/'probe/parity/tf32.json').write_text(json.dumps(results,indent=2))
print(json.dumps([{'file':r['file'],'sec':r['elapsed_sec'],'passed':r['passed']} for r in results]),flush=True)
assert all(r['passed'] for r in results)

"""Compare the actual detector outputs on CPU and GPU before bulk annotation."""
import gc
import json
import time
from pathlib import Path
import numpy as np
from PIL import Image
from detect_onnx import Detector, preview, iou
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parent
FILES = ['X-1_007000.jpg', 'X-35_010033.jpg']
OUT = ROOT / 'probe' / 'parity'
OUT.mkdir(parents=True, exist_ok=True)


def main():
    cpu = Detector(-1, verbose=False)
    baseline = []
    images = [Image.open(ROOT.parent / 'data/frames/all-videos/images' / name).convert('RGB').crop((0, 270, 464, 600)) for name in FILES]
    for name, image in zip(FILES, images):
        started = time.perf_counter()
        rows = cpu.detect(image)
        baseline.append((cpu.last_logits.copy(), cpu.last_boxes.copy(), rows))
        print(json.dumps({'file':name, 'cpu_sec':time.perf_counter()-started, 'objects':len(rows)}), flush=True)
    del cpu
    gc.collect()
    gpu = Detector(0, verbose=False)
    report = []
    for name, image, (logits, boxes, expected) in zip(FILES, images, baseline):
        started = time.perf_counter()
        rows = gpu.detect(image)
        delta_logits = np.abs(gpu.last_logits-logits)
        finite = np.isfinite(delta_logits)
        delta_boxes = np.abs(gpu.last_boxes-boxes)
        item = {'file':name, 'gpu_sec':time.perf_counter()-started,
                'max_logit_error':float(delta_logits[finite].max()), 'mean_logit_error':float(delta_logits[finite].mean()),
                'max_box_error':float(delta_boxes.max()), 'mean_box_error':float(delta_boxes.mean()),
                'cpu_detections':expected, 'gpu_detections':rows}
        # DETR proposal order can change at top-k ties; match final detections by geometry.
        costs = np.array([[1-iou(a['box'], b['box']) for b in rows] for a in expected])
        ai, bi = linear_sum_assignment(costs)
        matches = [{'iou':1-float(costs[a,b]), 'score_error':abs(expected[a]['score']-rows[b]['score']),
                    'class_equal':expected[a]['label']==rows[b]['label'], 'cpu_score':expected[a]['score']}
                   for a,b in zip(ai,bi)]
        item['matched_detections'] = matches
        item['parity_pass'] = (len(expected)==len(rows) and all(m['iou']>.95 and m['score_error']<.03
            and (m['class_equal'] or m['cpu_score']<.22) for m in matches))
        report.append(item)
        preview(image, rows, OUT / name)
        print(json.dumps({k:v for k,v in item.items() if 'detections' not in k}), flush=True)
    (OUT / 'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if not all(item['parity_pass'] for item in report):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

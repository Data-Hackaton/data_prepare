import json
import time
from pathlib import Path
from PIL import Image
from detect_onnx import Detector, preview

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'probe'/'dynamic'
OUT.mkdir(parents=True,exist_ok=True)
detector=Detector(0, verbose=False)
names=['X-1_007000.jpg','X-8_000000.jpg','X-35_010033.jpg','X-40_015000.jpg']
report=[]
for name in names:
    path=ROOT.parent/'data/frames/all-videos/images'/name
    if not path.exists():
        path=next(path.parent.glob(name.split('_')[0]+'_'+name.split('_')[1][:3]+'*.jpg'))
    image=Image.open(path).convert('RGB')
    for mode,region,queries,threshold in [
        ('people',(0,0,464,848), [('person','person')],.25),
        ('hands',(0,260,464,650), [('hand','hand')],.20),
        ('small',(0,300,464,540), [('banknotes','banknotes'),('id_card','identity card'),('phone','mobile phone')],.23),
    ]:
        crop=image.crop(region)
        start=time.perf_counter()
        rows=detector.detect(crop, queries=queries, threshold=threshold)
        item={'file':path.name,'mode':mode,'sec':time.perf_counter()-start,'region':region,'detections':rows}
        report.append(item)
        preview(crop,rows,OUT/f'{path.stem}_{mode}.jpg')
        print(json.dumps({'file':path.name,'mode':mode,'sec':item['sec'],'objects':len(rows)}),flush=True)
(OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

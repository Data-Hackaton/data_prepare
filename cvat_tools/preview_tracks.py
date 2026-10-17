"""Render selected source frames with dynamic tracking candidates for visual QA."""
import argparse
import json
from pathlib import Path
import cv2
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('video')
    parser.add_argument('--assembled',action='store_true')
    parser.add_argument('--manual',action='store_true')
    parser.add_argument('--count',type=int,default=15)
    args=parser.parse_args()
    if args.manual:
        from assemble_annotations import load_manual,densify
        times=json.loads((ROOT.parent/'data/frame_times'/f'{args.video}.json').read_text())
        scene=load_manual()[args.video][0]
        data={'frame_count':len(times),'tracks':[densify(t,times) for t in scene['tracks']]}
        args.assembled=True
    else:
        data=json.loads((ROOT/('assembled' if args.assembled else 'automatic')/f'{args.video}.json').read_text(encoding='utf-8'))
    n=data['frame_count']
    selected=sorted({round(i*(n-1)/max(1,args.count-1)) for i in range(args.count)})
    cap=cv2.VideoCapture(str(ROOT.parent/'data/videos'/f'{args.video}.mov'))
    tiles=[]
    for f in selected:
        cap.set(cv2.CAP_PROP_POS_FRAMES,f)
        ok,bgr=cap.read()
        assert ok
        image=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))
        draw=ImageDraw.Draw(image)
        colors={'hand':'#43ff55','person':'#ff445d','reflection':'#888888','banknotes':'#fff12b',
                'cash_machine':'#ff982b','safe':'#d739ff','door':'#30e8ff','table':'#d29144',
                'computer':'#10bfa1','id_card':'#317aff','foreign_object':'#ffaad6','phone':'#e03acb','bag':'#a9ff26'}
        for idx,t in enumerate(data['tracks']):
            samples=([s for s in t['samples'] if s['frame']==f and not s['outside']] if args.assembled
                     else [s for s in t['samples'] if s[0]==f and not s[5]])
            for s in samples:
                b=s['box'] if args.assembled else s[1:5]
                color=colors.get(t['label'],'white')
                draw.rectangle(b,outline=color,width=2)
                draw.text((b[0],max(0,b[1]-12)),f"{t['label']} {idx}",fill=color,stroke_width=1,stroke_fill='black')
        image.thumbnail((232,424))
        tile=Image.new('RGB',(232,447),'white')
        tile.paste(image,(0,23))
        ImageDraw.Draw(tile).text((5,5),f'{args.video} frame {f}',fill='black')
        tiles.append(tile)
    sheet=Image.new('RGB',(232*5,447*((len(tiles)+4)//5)),'#cccccc')
    for i,tile in enumerate(tiles):sheet.paste(tile,((i%5)*232,(i//5)*447))
    target=ROOT/'probe'/f'{args.video}-{"manual" if args.manual else "assembled" if args.assembled else "tracking"}.jpg'
    sheet.save(target,quality=92)
    print(target)

if __name__=='__main__':main()

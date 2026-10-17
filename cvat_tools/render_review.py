"""Create numbered, auditable annotation review contact sheets."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
COLORS = {'person': '#ff445d', 'hand': '#43ff55', 'reflection': '#aaaaaa',
          'banknotes': '#fff12b', 'id_card': '#317aff', 'cash_machine': '#ff982b',
          'safe': '#d739ff', 'door': '#30e8ff', 'table': '#d29144',
          'computer': '#10bfa1', 'phone': '#e03acb', 'bag': '#a9ff26'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('videos', nargs='+')
    p.add_argument('--frames', default='first,last')
    p.add_argument('--labels', default='all')
    p.add_argument('--source', default='qa_20261017/baseline')
    p.add_argument('--out', required=True)
    p.add_argument('--cols', type=int, default=4)
    p.add_argument('--per-page', type=int, default=8)
    p.add_argument('--scale', type=float, default=1)
    p.add_argument('--crop', help='Optional source-coordinate x1,y1,x2,y2 region')
    a = p.parse_args()
    tiles, evidence, pages = [], [], []
    prefix = ROOT / a.out
    prefix.parent.mkdir(parents=True, exist_ok=True)
    def flush():
        if not tiles:
            return
        w, h = tiles[0].size
        sheet = Image.new('RGB', (w*a.cols, h*((len(tiles)+a.cols-1)//a.cols)), '#dddddd')
        for index, tile in enumerate(tiles):
            sheet.paste(tile, ((index % a.cols)*w, (index // a.cols)*h))
        target = prefix.parent / f'{prefix.name}-{len(pages):04d}.jpg'
        sheet.save(target, quality=94)
        pages.append({'file': str(target), 'frames': evidence[-len(tiles):], 'viewed': False})
        tiles.clear()
    for name in a.videos:
        source = ROOT / a.source / f'{name}.assembled.json'
        if not source.exists():
            source = ROOT / a.source / f'{name}.json'
        data = json.loads(source.read_text(encoding='utf-8'))
        n = data['frame_count']
        selected = set()
        for part in a.frames.split(','):
            if part == 'first':
                selected.add(0)
            elif part == 'last':
                selected.add(n-1)
            elif ':' in part:
                values = [int(v) for v in part.split(':')]
                selected.update(range(values[0], min(values[1]+1, n), values[2] if len(values)>2 else 1))
            else:
                selected.add(int(part))
        by_frame = {}
        for ti, track in enumerate(data['tracks']):
            if a.labels != 'all' and track['label'] not in a.labels.split(','):
                continue
            for s in track['samples']:
                if s['frame'] in selected and not s['outside']:
                    by_frame.setdefault(s['frame'], []).append((ti, track, s))
        cap = cv2.VideoCapture(str(ROOT.parent / 'data/videos' / f'{name}.mov'))
        decoded = -1
        for f in sorted(selected):
            assert 0 <= f < n
            # MOV/VFR seeking can return the wrong frame or miss the final one.
            # Sequential decoding keeps these numbers identical to the audit.
            while decoded < f:
                ok, bgr = cap.read()
                assert ok, (name, decoded+1, f)
                decoded += 1
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(rgb)
            draw = ImageDraw.Draw(im)
            for ti, track, s in by_frame.get(f, []):
                label = track['label']
                box = s['box']
                color = COLORS.get(label, 'white')
                draw.rectangle(box, outline=color, width=1)
                draw.text((box[0]+1, max(0, box[1]-12)), f'{label}:{ti}', fill=color, stroke_width=1, stroke_fill='black')
            if a.crop:
                im = im.crop(tuple(int(v) for v in a.crop.split(',')))
            w, h = round(im.width*a.scale), round(im.height*a.scale)
            if a.scale != 1:
                im = im.resize((w, h), Image.Resampling.LANCZOS)
            tile = Image.new('RGB', (w, h+24), 'white')
            tile.paste(im, (0,24))
            ImageDraw.Draw(tile).text((5,5), f'{name} frame {f} / {n-1}', fill='black')
            evidence.append({'video': name, 'frame': f, 'source_pixel_sha256': hashlib.sha256(bgr.tobytes()).hexdigest()})
            tiles.append(tile)
            if len(tiles) == a.per_page:
                flush()
        cap.release()
    flush()
    prefix.with_suffix('.json').write_text(json.dumps({'pages': pages, 'note': 'Rendering is not visual review.'}, indent=2), encoding='utf-8')
    print(json.dumps({'pages': len(pages), 'frames': len(evidence), 'manifest': str(prefix.with_suffix('.json'))}))


if __name__ == '__main__':
    main()

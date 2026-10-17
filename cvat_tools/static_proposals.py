"""Draft geometry for stationary objects. Requires visual validation before import."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data"
TEMPLATES = {
    "A": {"cash_machine": [32, 402, 114, 488], "table": [21, 390, 300, 495]},
    "B": {"cash_machine": [46, 368, 122, 451], "table": [44, 379, 320, 490]},
    "C": {"cash_machine": [208, 318, 274, 387], "table": [41, 367, 303, 460]},
    "D": {"cash_machine": [257, 336, 333, 415], "table": [47, 367, 336, 446]},
    "E": {"cash_machine": [208, 335, 279, 405], "table": [34, 385, 308, 470]},
}


def scene(number):
    if number <= 5 or 15 <= number <= 19 or number in [47, 48]: return "A"
    if number <= 29: return "B"
    if number <= 31: return "C"
    if number <= 40: return "D"
    return "E"


if __name__ == "__main__":
    videos = json.loads((DATA / "video_frame_manifest.json").read_text(encoding="utf-8"))["items"]
    unique = [video for video in videos if not video["duplicate_of"]]
    out = ROOT / "static-review"
    out.mkdir(exist_ok=True)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
    proposals = []
    for page in range(0, len(unique), 10):
        canvas = Image.new("RGB", (464*5, 380*2), "#151515")
        for n, video in enumerate(unique[page:page+10]):
            name = video["video"]
            image = Image.open(DATA / "frames" / "all-videos" / "images" / f"{name}_000000.jpg").convert("RGB")
            draw = ImageDraw.Draw(image)
            boxes = TEMPLATES[scene(int(video["n"]))]
            for label, box in boxes.items():
                color = "#ff8800" if label == "cash_machine" else "#00ff88"
                draw.rectangle(box, outline=color, width=2)
                draw.text((box[0]+2, box[1]+2), label, fill=color, stroke_width=1, stroke_fill="black")
            tile = image.crop((0, 270, 464, 620))
            x, y = (n % 5) * 464, (n // 5) * 380
            canvas.paste(tile, (x, y))
            ImageDraw.Draw(canvas).text((x+6, y+352), name, font=font, fill="white")
            proposals.append({"video": name, "boxes": boxes, "status": "unreviewed_template"})
        canvas.save(out / f"first-frames-{page//10+1}.jpg", quality=95)
    (out / "proposals.json").write_text(json.dumps(proposals, indent=2), encoding="utf-8")
    print(json.dumps({"videos": len(proposals), "preview_pages": 4, "status": "unreviewed_template"}))

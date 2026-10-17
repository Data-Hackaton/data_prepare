"""Local Grounding DINO inference; results are proposals, never reviewed truth."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "models" / "grounding-dino-tiny"
QUERIES = [
    ("person", "person"), ("hand", "hand"),
    ("banknotes", "banknotes"), ("id_card", "identity card"),
    ("cash_machine", "money counting machine"), ("safe", "safe"),
    ("door", "door"), ("phone", "smartphone"),
    ("bag", "green bag"), ("table", "desk"),
    ("foreign_object", "jacket"), ("foreign_object", "handbag"),
    ("foreign_object", "cup"), ("computer", "laptop"),
]


def iou(a, b):
    w, h = max(0, min(a[2], b[2]) - max(a[0], b[0])), max(0, min(a[3], b[3]) - max(a[1], b[1]))
    overlap = w * h
    return overlap / max(1e-6, (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - overlap)


def nms(rows, threshold=0.45):
    kept = []
    for row in sorted(rows, key=lambda r: r["score"], reverse=True):
        if not any(row["label"] == old["label"] and iou(row["box"], old["box"]) > threshold for old in kept):
            kept.append(row)
    return kept


class Detector:
    def __init__(self, device=-1, model_path=None, verbose=True, use_tf32=False):
        ort.set_default_logger_severity(3)
        options = ort.SessionOptions()
        options.enable_mem_pattern = False
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.intra_op_num_threads = 4
        options.log_severity_level = 3
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        options.add_free_dimension_override_by_name("sequence_length", 128)
        if device >= 0 and "CUDAExecutionProvider" in ort.get_available_providers():
            # cuDNN loads additional engine DLLs after ORT preloads its main library.
            bins = list((Path(sys.prefix) / "Lib" / "site-packages" / "nvidia").glob("*/bin"))
            self.dll_handles = [os.add_dll_directory(str(path)) for path in bins] if os.name == "nt" else []
            os.environ["PATH"] = os.pathsep.join(map(str, bins)) + os.pathsep + os.environ.get("PATH", "")
            ort.preload_dlls(directory="")
            providers = [("CUDAExecutionProvider", {"device_id": 0, "cudnn_conv_algo_search": "HEURISTIC", "use_tf32": int(use_tf32)}), "CPUExecutionProvider"]
            model_path = model_path or MODEL / 'onnx' / 'model_promoted_fp32.onnx'
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        elif device >= 0:
            providers = [("DmlExecutionProvider", {"device_id": device}), "CPUExecutionProvider"]
        else:
            providers = ["CPUExecutionProvider"]
        model_path = model_path or MODEL / 'onnx' / 'model_fp16.onnx'
        self.session = ort.InferenceSession(str(model_path), options, providers=providers)
        self.tokenizer = Tokenizer.from_file(str(MODEL / "tokenizer.json"))
        self.tokenizer.enable_padding(length=128)
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        if verbose:
            print(json.dumps({"providers": self.session.get_providers(),
                          "inputs": [(i.name, i.type, i.shape) for i in self.session.get_inputs()],
                          "outputs": [(o.name, o.type, o.shape) for o in self.session.get_outputs()]}), flush=True)

    def detect(self, image: Image.Image, queries=QUERIES, threshold=0.20):
        caption, intervals = "", []
        for label, phrase in queries:
            start = len(caption)
            caption += phrase + ". "
            intervals.append((label, phrase, start, start + len(phrase)))
        encoded = self.tokenizer.encode(caption.strip())
        indices = [[idx for idx, (a, b) in enumerate(encoded.offsets) if b > a and a >= start and b <= end]
                   for _, _, start, end in intervals]
        pixels = np.asarray(image.convert("RGB").resize((800, 800), Image.Resampling.BILINEAR), dtype=np.float32) / 255
        pixels = ((pixels - self.mean) / self.std).transpose(2, 0, 1)[None]
        values = {"pixel_values": pixels, "pixel_mask": np.ones((1, 800, 800), dtype=np.int64),
                  "input_ids": np.array([encoded.ids], dtype=np.int64),
                  "attention_mask": np.array([encoded.attention_mask], dtype=np.int64),
                  "token_type_ids": np.array([encoded.type_ids], dtype=np.int64)}
        types = {"tensor(float)": np.float32, "tensor(float16)": np.float16,
                 "tensor(int64)": np.int64, "tensor(bool)": np.bool_, "tensor(int32)": np.int32}
        feed = {i.name: values[i.name].astype(types[i.type], copy=False) for i in self.session.get_inputs()}
        result = dict(zip([o.name for o in self.session.get_outputs()], self.session.run(None, feed)))
        logits = result["logits"][0].astype(np.float32)
        self.last_logits = logits
        scores = 1 / (1 + np.exp(-np.clip(logits, -40, 40)))
        proposals = result["pred_boxes"][0].astype(np.float32)
        self.last_boxes = proposals
        width, height = image.size
        detections = []
        for logit_row, (cx, cy, bw, bh) in zip(scores, proposals):
            class_scores = [float(logit_row[index].max()) if index else 0 for index in indices]
            winner = int(np.argmax(class_scores))
            score = class_scores[winner]
            if score < threshold:
                continue
            box = [max(0, (cx-bw/2)*width), max(0, (cy-bh/2)*height),
                   min(width, (cx+bw/2)*width), min(height, (cy+bh/2)*height)]
            if box[2] - box[0] < 2 or box[3] - box[1] < 2:
                continue
            label, phrase, _, _ = intervals[winner]
            detections.append({"label": label, "query": phrase, "score": round(score, 4),
                               "box": [round(float(v), 2) for v in box], "source": "auto"})
        return nms(detections)


def preview(image, rows, path):
    canvas = image.convert("RGB").resize((image.width * 2, image.height * 2))
    draw = ImageDraw.Draw(canvas)
    colors = {"person": "red", "hand": "lime", "banknotes": "yellow", "safe": "magenta",
              "door": "cyan", "computer": "orange", "cash_machine": "#ff8040"}
    for row in rows:
        box = [v * 2 for v in row["box"]]
        color = colors.get(row["label"], "#8080ff")
        draw.rectangle(box, outline=color, width=2)
        draw.text((box[0]+2, max(0, box[1]-12)), f"{row['label']} {row['score']:.2f}", fill=color,
                  stroke_width=1, stroke_fill="black")
    canvas.save(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--device", type=int, default=-1, help="CPU by default; GPU outputs require parity validation")
    parser.add_argument("--crop", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    detector = Detector(args.device)
    loaded = time.perf_counter()
    image = Image.open(args.image).convert("RGB")
    if args.crop:
        image = image.crop((0, 270, 464, 600))
    results = detector.detect(image)
    output = ROOT / "probe"
    output.mkdir(exist_ok=True)
    (output / f"{args.image.stem}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    preview(image, results, output / f"{args.image.stem}.jpg")
    print(json.dumps({"load_sec": loaded-started, "inference_sec": time.perf_counter()-loaded,
                      "detections": len(results), "preview": str(output / f"{args.image.stem}.jpg")}), flush=True)

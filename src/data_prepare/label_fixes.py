"""Правка известных ошибок разметки до обучения: computer на сейфе, счётной машинке и стуле; пропущенный сейф.

Ошибки нашли 17.10 по det_l1 (раунды r1 + r1b): в ракурсе X-34…X-39 сейф размечен как computer, в X-8…X-19
машинка — как computer, в X-27, X-29 стул на переднем плане — как computer; в X-10, X-34, X-38, X-40, X-43, X-45
сейфа нет почти ни в одном кадре. YOLO выучил это один в один. Правила по порядку, координаты нормированы:
  1. computer с центром ниже 0,8 высоты кадра — стул → удалить;
  2. computer на машинке (IoU > 0,3 с cash_machine кадра или с медианной машинкой видео) → удалить, если
     машинка в кадре размечена, иначе переименовать в cash_machine;
  3. computer площадью от 0,03 кадра — сейф (ноутбук ~0,011) → safe; если safe рядом уже есть — дубль, удалить;
  4. эталон сейфа видео: ручной из cvat/label_fixes.yaml, иначе медиана safe видео после шагов 1–3;
  5. safe с IoU < 0,1 к эталону — рамка не на сейфе (на стекле) → удалить;
  6. кадр без safe → эталон, если люди закрывают его не больше чем наполовину (камера в видео неподвижна).
Остальные рамки не трогаются; повторное применение ничего не меняет. Разметку в CVAT правит команда по отчёту.
"""

from pathlib import Path

import yaml

FIXES = Path(__file__).resolve().parents[2] / "cvat" / "label_fixes.yaml"
CHAIR_CY = 0.8
MACHINE_IOU = 0.3
SAFE_AREA = 0.03
SAFE_DUP_IOU = 0.3
SAFE_FAR_IOU = 0.1
OCCLUDED = 0.5
PEOPLE = ("person", "reflection")


def area(b: list[float]) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def inter(a: list[float], b: list[float]) -> float:
    return area([max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])])


def iou(a: list[float], b: list[float]) -> float:
    i = inter(a, b)
    return i / (area(a) + area(b) - i + 1e-9)


def median_box(boxes: list[list[float]]) -> list[float] | None:
    if not boxes:
        return None
    return [sorted(b[i] for b in boxes)[len(boxes) // 2] for i in range(4)]


def static_boxes(path: Path = FIXES) -> dict[str, list[float]]:
    """Ручные рамки сейфа по видео (xyxy, нормированные)."""
    if not path.exists():
        return {}
    return {video: entry["safe"] for video, entry in (yaml.safe_load(path.read_text()) or {}).items()}


def fix_video(frames: dict[str, list[dict]], static_safe: list[float] | None = None) -> tuple[dict, list[dict]]:
    """frames: файл → [{cls: имя, box: xyxy нормированный, …}] одного видео. Возвращает исправленные кадры и
    список правок {file, action: delete/relabel/add, rule, from, to, box}."""
    out, actions = {}, []

    def log(file, action, rule, box, src=None, dst=None):
        actions.append({"file": file, "action": action, "rule": rule, "from": src, "to": dst,
                        "box": [round(v, 4) for v in box]})

    machine = median_box([b["box"] for anns in frames.values() for b in anns if b["cls"] == "cash_machine"])
    for file, anns in frames.items():
        kept = []
        machines = [b["box"] for b in anns if b["cls"] == "cash_machine"]
        safes = [b["box"] for b in anns if b["cls"] == "safe"]
        for b in anns:
            if b["cls"] != "computer":
                kept.append(b)
                continue
            box = b["box"]
            if (box[1] + box[3]) / 2 > CHAIR_CY:
                log(file, "delete", "chair", box, "computer")
            elif any(iou(box, m) > MACHINE_IOU for m in machines):
                log(file, "delete", "cash_machine", box, "computer")
            elif machine and iou(box, machine) > MACHINE_IOU:
                log(file, "relabel", "cash_machine", box, "computer", "cash_machine")
                kept.append({**b, "cls": "cash_machine"})
            elif area(box) >= SAFE_AREA:
                if any(iou(box, s) > SAFE_DUP_IOU for s in safes):
                    log(file, "delete", "duplicate_safe", box, "computer")
                else:
                    log(file, "relabel", "safe", box, "computer", "safe")
                    kept.append({**b, "cls": "safe"})
            else:
                kept.append(b)
        out[file] = kept

    ref = static_safe or median_box([b["box"] for anns in out.values() for b in anns if b["cls"] == "safe"])
    if ref is None:
        return out, actions
    for file, anns in out.items():
        kept = []
        for b in anns:
            if b["cls"] == "safe" and iou(b["box"], ref) < SAFE_FAR_IOU:
                log(file, "delete", "safe_elsewhere", b["box"], "safe")
            else:
                kept.append(b)
        if not any(b["cls"] == "safe" for b in kept):
            covered = sum(inter(ref, b["box"]) for b in kept if b["cls"] in PEOPLE) / area(ref)
            if covered <= OCCLUDED:
                log(file, "add", "missing_safe", ref, None, "safe")
                kept.append({"cls": "safe", "box": list(ref), "added": True})
        out[file] = kept
    return out, actions


RULE_RU = {
    "chair": "удалить computer на стуле (передний план)",
    "cash_machine": "computer на счётной машинке → cash_machine (или удалить, если машинка уже обведена)",
    "safe": "computer на сейфе → safe",
    "duplicate_safe": "удалить computer поверх рамки safe",
    "safe_elsewhere": "удалить safe не на сейфе",
    "missing_safe": "дорисовать safe",
}


def frame_ranges(frames: list[int]) -> str:
    """[3, 4, 5, 9] → «3–5, 9»."""
    out, start, prev = [], None, None
    for f in sorted(set(frames)):
        if start is None:
            start = prev = f
        elif f == prev + 1:
            prev = f
        else:
            out.append(f"{start}–{prev}" if prev > start else f"{start}")
            start = prev = f
    if start is not None:
        out.append(f"{start}–{prev}" if prev > start else f"{start}")
    return ", ".join(out)


def report(actions: list[dict], rounds: list[str]) -> str:
    """Список правок для команды: задача CVAT → видео → что исправить, номера кадров задачи."""
    lines = [f"# Правка разметки CVAT: раунды {' + '.join(rounds)}", "",
             "Автоматически исправлено при сборке датасета (`build-datasets`, `data_prepare/label_fixes.py`); "
             "в CVAT эти рамки ещё ошибочны. Номер кадра — как в задаче CVAT (с 0), файл — в `fixes.csv`.", ""]
    by_task: dict[str, dict[tuple[str, str], list[int]]] = {}
    for a in actions:
        by_task.setdefault(a["task"], {}).setdefault((a["video"], a["rule"]), []).append(a["frame"])
    for task in sorted(by_task):
        lines += [f"## {task}", "", "| Видео | Что исправить | Кадры |", "|---|---|---|"]
        for (video, rule), frames in sorted(by_task[task].items(), key=lambda kv: (int(kv[0][0][2:]), kv[0][1])):
            lines.append(f"| {video} | {RULE_RU[rule]} | {frame_ranges(frames)} |")
        lines.append("")
    return "\n".join(lines)

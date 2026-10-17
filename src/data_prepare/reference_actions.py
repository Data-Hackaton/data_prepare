"""Эталонный порядок действий → feature store.

Берёт reference/scenarios.yaml (шаблоны сценариев) и reference/actions.yaml (журнал действий по чистым видео):
1. проверяет словарь, что видео есть в labels.csv и без нарушений, таймкоды в пределах длительности,
   порядок шагов по шаблону, обязательные шаги и инварианты;
2. если ошибок нет, пишет в feature store (DATA_DIR/features):
   <sha256>/actions.parquet      журнал действий видео, source=reference_r0
   reference/scenarios.parquet   шаги шаблонов по порядку
   reference/invariants.parquet  инварианты и что по ним видно в эталоне
   reference/summary.json        покрытие шагов и длительности открытого сейфа
   index.parquet                 какие видео и источники лежат в store
"""

import argparse
import csv
import json
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

SOURCE = "reference_r0"

ACTIONS_SCHEMA = pa.schema([
    ("video", pa.string()),
    ("sha256", pa.string()),
    ("scene", pa.string()),
    ("scenario", pa.string()),
    ("instance", pa.int32()),
    ("step", pa.int32()),
    ("t_start", pa.float32()),
    ("t_end", pa.float32()),
    ("action", pa.string()),
    ("actor", pa.string()),
    ("object", pa.string()),
    ("target", pa.string()),
    ("certain", pa.bool_()),
    ("source", pa.string()),
])


def as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def step_matches(step: dict, a: dict) -> bool:
    if step["action"] != a["action"]:
        return False
    if "actor" in step and step["actor"] != a.get("actor"):
        return False
    objects = as_list(step.get("object"))
    if objects and a.get("object") not in objects:
        return False
    return "target" not in step or step["target"] == a.get("target")


def selector_matches(sel, a: dict) -> bool:
    sel = {"action": sel} if isinstance(sel, str) else sel
    return all(a.get(k) == v for k, v in sel.items())


def check_instance(where: str, scenario: dict, actions: list[dict], errors: list, warnings: list,
                   safe_durations: list) -> list[int | None]:
    """Возвращает номер шага шаблона для каждого действия (None — вне шаблона)."""
    steps = scenario["steps"]
    pointer, assigned = 0, []
    for a in actions:
        candidates = [i for i, s in enumerate(steps) if step_matches(s, a)]
        if not candidates:
            warnings.append(f"{where}: {a['action']} {a.get('object') or ''} на {a['t']} с — вне шаблона")
            assigned.append(None)
            continue
        forward = [i for i in candidates if i >= pointer]
        if not forward:
            errors.append(f"{where}: {a['action']} на {a['t']} с идёт раньше по шаблону, чем предыдущие шаги")
            assigned.append(candidates[0])
            continue
        pointer = forward[0]
        assigned.append(pointer)

    for i, s in enumerate(steps):
        if s.get("required") and i not in assigned:
            errors.append(f"{where}: нет обязательного шага {s['action']} ({s.get('actor', '')})")

    for inv in scenario.get("invariants", []):
        if inv["kind"] == "max_duration":
            for a in (x for x in actions if selector_matches(inv["from"], x)):
                close = next((b for b in actions if selector_matches(inv["to"], b) and b["t"] >= a["t"]), None)
                if close is None:
                    errors.append(f"{where}: {inv['from']} на {a['t']} с без {inv['to']}")
                    continue
                duration = close["t"] - a["t"]
                safe_durations.append(duration)
                if duration > inv["sec"]:
                    errors.append(f"{where}: {inv['from']}→{inv['to']} {duration} с > {inv['sec']} с")
        elif inv["kind"] == "before":
            if "if_present" in inv and not any(selector_matches(inv["if_present"], x) for x in actions):
                continue
            firsts = [x["t"] for x in actions if selector_matches(inv["first"], x)]
            for then in (x for x in actions if selector_matches(inv["then"], x)):
                if not firsts:
                    if "if_present" in inv:
                        errors.append(f"{where}: {then['action']} на {then['t']} с без предшествующего {inv['first']}")
                elif min(firsts) > then["t"]:
                    errors.append(f"{where}: {inv['first']} после {then['action']} ({min(firsts)} с > {then['t']} с)")
    return assigned


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("DATA_DIR", "/data")))
    ap.add_argument("--reference", type=Path, default=Path(os.environ.get("REFERENCE_DIR", "/app/reference")))
    ap.add_argument("--check-only", action="store_true", help="только проверить, ничего не писать")
    args = ap.parse_args()

    spec = yaml.safe_load((args.reference / "scenarios.yaml").read_text())
    journal = yaml.safe_load((args.reference / "actions.yaml").read_text())
    vocab = spec["vocabulary"]
    scenarios = spec["scenarios"]
    with (args.data / "labels.csv").open() as f:
        labels = {r["video"]: r for r in csv.DictReader(f)}

    errors, warnings, safe_durations = [], [], []
    rows_by_video: dict[str, list[dict]] = {}
    coverage: dict[str, Counter] = defaultdict(Counter)
    n_instances: Counter = Counter()

    for video, entry in journal.items():
        label = labels.get(video)
        if label is None:
            errors.append(f"{video}: нет в labels.csv")
            continue
        if label["verdict"] != "no_violation" or label["duplicate_of"]:
            errors.append(f"{video}: эталон берётся только из уникальных видео без нарушений")
        duration = float(label["duration_sec"])
        rows = []
        for idx, inst in enumerate(entry["instances"], start=1):
            name = inst["scenario"]
            where = f"{video}#{idx} {name}"
            if name not in scenarios:
                errors.append(f"{where}: неизвестный сценарий")
                continue
            actions = sorted(inst["actions"], key=lambda a: a["t"])
            for a in actions:
                if a["action"] not in vocab["actions"]:
                    errors.append(f"{where}: действие {a['action']} не из словаря")
                for field, allowed in (("actor", "actors"), ("object", "objects"), ("target", "targets")):
                    if a.get(field) is not None and a[field] not in vocab[allowed]:
                        errors.append(f"{where}: {field}={a[field]} не из словаря")
                if max(a["t"], a.get("t_end", a["t"])) > duration + 1:
                    errors.append(f"{where}: {a['action']} на {a['t']} с за пределами видео ({duration:.1f} с)")
            steps = check_instance(where, scenarios[name], actions, errors, warnings, safe_durations)
            n_instances[name] += 1
            coverage[name].update({s for s in steps if s is not None})
            for a, step in zip(actions, steps):
                rows.append({
                    "video": video, "sha256": label["sha256"], "scene": entry.get("scene"),
                    "scenario": name, "instance": idx, "step": step,
                    "t_start": float(a["t"]), "t_end": float(a.get("t_end", a["t"])),
                    "action": a["action"], "actor": a.get("actor"), "object": a.get("object"),
                    "target": a.get("target"), "certain": a.get("certain", True), "source": SOURCE,
                })
        rows_by_video[video] = rows

    summary = {"source": SOURCE, "videos": len(rows_by_video), "scenarios": {}}
    for name, scenario in scenarios.items():
        total = n_instances[name]
        summary["scenarios"][name] = {
            "title": scenario["title"],
            "instances": total,
            "steps": [
                {"step": i, "action": s["action"], "actor": s.get("actor"), "object": s.get("object"),
                 "target": s.get("target"), "required": s.get("required", False),
                 "seen_in": f"{coverage[name][i]}/{total}"}
                for i, s in enumerate(scenario["steps"])
            ],
        }
    if safe_durations:
        summary["safe_open_sec"] = {"n": len(safe_durations), "min": min(safe_durations),
                                    "median": statistics.median(safe_durations), "max": max(safe_durations)}

    for name, s in summary["scenarios"].items():
        print(f"\n{name} — {s['title']}: {s['instances']} экз.")
        for st in s["steps"]:
            mark = "*" if st["required"] else " "
            objects = "|".join(as_list(st["object"]))
            print(f"  {st['step']:>2}{mark} {st['action']:<15} {st['actor'] or '':<10} "
                  f"{objects:<30} {st['target'] or '':<13} {st['seen_in']}")
    if safe_durations:
        print(f"\nсейф открыт, с: {summary['safe_open_sec']}")
    for w in warnings:
        print(f"[вне шаблона] {w}")
    for e in errors:
        print(f"[ошибка] {e}")
    if errors:
        raise SystemExit(f"{len(errors)} ошибок — feature store не записан")
    if args.check_only:
        return

    store = args.data / "features"
    (store / "reference").mkdir(parents=True, exist_ok=True)
    index = []
    for video, rows in rows_by_video.items():
        sha = labels[video]["sha256"]
        (store / sha).mkdir(exist_ok=True)
        pq.write_table(pa.Table.from_pylist(rows, schema=ACTIONS_SCHEMA), store / sha / "actions.parquet")
        index.append({"sha256": sha, "video": video, "verdict": labels[video]["verdict"],
                      "scene": journal[video].get("scene"), "table": "actions", "source": SOURCE,
                      "rows": len(rows)})
    pq.write_table(pa.Table.from_pylist(index), store / "index.parquet")

    pq.write_table(pa.Table.from_pylist([
        {"scenario": name, "title": sc["title"], "step": i, "action": s["action"], "actor": s.get("actor"),
         "objects": as_list(s.get("object")), "target": s.get("target"), "required": s.get("required", False)}
        for name, sc in scenarios.items() for i, s in enumerate(sc["steps"])
    ]), store / "reference" / "scenarios.parquet")
    pq.write_table(pa.Table.from_pylist([
        {"scenario": name, "kind": inv["kind"], "params": json.dumps({k: v for k, v in inv.items()
                                                                       if k not in ("kind", "why")}, ensure_ascii=False),
         "why": inv.get("why")}
        for name, sc in scenarios.items() for inv in sc.get("invariants", [])
    ]), store / "reference" / "invariants.parquet")
    (store / "reference" / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n→ {store}: {len(index)} видео, {sum(r['rows'] for r in index)} действий")

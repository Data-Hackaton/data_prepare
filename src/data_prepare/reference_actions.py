"""Эталонный порядок действий → feature store.

Берёт reference/scenarios.yaml (шаблоны сценариев) и reference/actions.yaml (журнал действий по чистым видео):
1. проверяет словарь, что видео есть в labels.csv и без нарушений, таймкоды в пределах длительности,
   порядок шагов по шаблону, обязательные шаги и инварианты;
2. если ошибок нет, пишет в feature store (DATA_DIR/features):
   <sha256>/actions.parquet      журнал действий видео, source=reference_r0
   reference/scenarios.parquet   шаги шаблонов по порядку
   reference/invariants.parquet  инварианты шаблонов и видео, с нормативом
   reference/norms.parquet       нормативы (документ, пункт, URL, цитата)
   reference/violations.parquet  каталог нарушений: чем пойманы, норматив
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
CATCH_WINDOW_SEC = 3  # отклонение должно сработать не дальше, чем в 3 с от размеченной секунды

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
                   safe_durations: list, hits: list | None = None) -> list[int | None]:
    """Возвращает номер шага шаблона для каждого действия (None — вне шаблона).

    Каждое отклонение от нормы пишется в errors (или warnings для действий вне шаблона)
    и, если передан hits, — туда же с временем и правилом: по hits видно, чем поймано нарушение.
    """
    def flag(t: float, rule: str, message: str, target: list, norm: str | None = None) -> None:
        target.append(f"{where}: {message}")
        if hits is not None:
            hits.append({"t": t, "rule": rule, "message": message, "norm": norm})

    steps = scenario["steps"]
    pointer, assigned = 0, []
    for a in actions:
        candidates = [i for i, s in enumerate(steps) if step_matches(s, a)]
        if not candidates:
            flag(a["t"], "out_of_template", f"{a['action']} {a.get('object') or ''} на {a['t']} с — вне шаблона", warnings)
            assigned.append(None)
            continue
        forward = [i for i in candidates if i >= pointer]
        if not forward:
            flag(a["t"], "order", f"{a['action']} на {a['t']} с идёт раньше по шаблону, чем предыдущие шаги", errors)
            assigned.append(candidates[0])
            continue
        pointer = forward[0]
        assigned.append(pointer)

    for i, s in enumerate(steps):
        if s.get("required") and i not in assigned:
            flag(actions[0]["t"] if actions else 0, "required", f"нет обязательного шага {s['action']} ({s.get('actor', '')})", errors)

    for inv in scenario.get("invariants", []):
        norm = inv.get("norm")
        if inv["kind"] == "max_duration":
            for a in (x for x in actions if selector_matches(inv["from"], x)):
                close = next((b for b in actions if selector_matches(inv["to"], b) and b["t"] >= a["t"]), None)
                if close is None:
                    flag(a["t"], "max_duration", f"{inv['from']} на {a['t']} с без {inv['to']}", errors, norm)
                    continue
                duration = close["t"] - a["t"]
                safe_durations.append(duration)
                if duration > inv["sec"]:
                    flag(a["t"], "max_duration", f"{inv['from']}→{inv['to']} {duration} с > {inv['sec']} с", errors, norm)
        elif inv["kind"] == "before":
            if "if_present" in inv and not any(selector_matches(inv["if_present"], x) for x in actions):
                continue
            firsts = [x["t"] for x in actions if selector_matches(inv["first"], x)]
            for then in (x for x in actions if selector_matches(inv["then"], x)):
                if not firsts:
                    if "if_present" in inv:
                        flag(then["t"], "before", f"{then['action']} на {then['t']} с без предшествующего {inv['first']}", errors, norm)
                elif min(firsts) > then["t"]:
                    flag(then["t"], "before", f"{inv['first']} после {then['action']} ({min(firsts)} с > {then['t']} с)", errors, norm)
        elif inv["kind"] == "forbidden":
            for a in (x for x in actions if selector_matches(inv["action"], x)):
                flag(a["t"], f"forbidden:{a['action']}", f"{a['action']} {a.get('object') or ''} на {a['t']} с запрещено: {inv.get('why', '')}",
                     errors, norm)
        elif inv["kind"] == "forbidden_after":
            starts = [x["t"] for x in actions if selector_matches(inv["after"], x)]
            if not starts:
                continue
            for a in (x for x in actions if selector_matches(inv["action"], x) and x["t"] >= min(starts)):
                flag(a["t"], f"forbidden_after:{a['action']}",
                     f"{a['action']} на {a['t']} с после {inv['after']} ({min(starts)} с): {inv.get('why', '')}", errors, norm)
    return assigned


def check_video(where: str, instances: list[list[dict]], video_invariants: list[dict], errors: list,
                hits: list | None = None) -> None:
    """Проверки через все экземпляры видео подряд; instances — действия экземпляров в порядке журнала."""
    timeline = sorted(((a["t"], k, a) for k, actions in enumerate(instances) for a in actions), key=lambda x: x[:2])
    for inv in video_invariants:
        if inv["kind"] != "desk_carryover":
            continue
        on_desk: list[tuple[int, float]] = []  # (экземпляр, когда положили) для предметов inv["object"]
        for t, k, a in timeline:
            if any(selector_matches(trig, a) for trig in inv["triggers"]):
                stale = [(k0, t0) for k0, t0 in on_desk if k0 < k]
                if stale:
                    message = (f"{a['action']} на {t} с, а на столе {inv['object']} предыдущего клиента "
                               f"(положены на {stale[0][1]} с): {inv.get('why', '')}")
                    errors.append(f"{where}: {message}")
                    if hits is not None:
                        hits.append({"t": t, "rule": f"desk_carryover:{inv['object']}", "message": message,
                                     "norm": inv.get("norm")})
            if a.get("object") == inv["object"] and a.get("target") == "desk":
                if a["action"] == "put":
                    on_desk.append((k, t))
                elif a["action"] == "take" and on_desk:
                    on_desk.pop(0)


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

    violations_path = args.reference / "violations.yaml"
    catalog = yaml.safe_load(violations_path.read_text()) if violations_path.exists() else {}
    norms_path = args.reference / "norms.yaml"
    norms = yaml.safe_load(norms_path.read_text()) if norms_path.exists() else {}

    errors, warnings, safe_durations = [], [], []
    rows_by_video: dict[str, list[dict]] = {}
    coverage: dict[str, Counter] = defaultdict(Counter)
    n_instances: Counter = Counter()

    def journal_rows(video: str, entry: dict, verdict: str, check_errors: list, check_warnings: list,
                     hits: list | None = None) -> list[dict] | None:
        """Проверка словаря и таймкодов (ошибки — общие) и порядка по шаблону (ошибки — в check_*)."""
        label = labels.get(video)
        if label is None:
            errors.append(f"{video}: нет в labels.csv")
            return None
        if label["verdict"] != verdict or label["duplicate_of"]:
            errors.append(f"{video}: ожидалось уникальное видео с вердиктом {verdict}")
        duration = float(label["duration_sec"])
        rows, instance_actions = [], []
        for idx, inst in enumerate(entry["instances"], start=1):
            name = inst["scenario"]
            where = f"{video}#{idx} {name}"
            if name not in scenarios:
                errors.append(f"{where}: неизвестный сценарий")
                continue
            actions = sorted(inst["actions"], key=lambda a: a["t"])
            instance_actions.append(actions)
            for a in actions:
                if a["action"] not in vocab["actions"]:
                    errors.append(f"{where}: действие {a['action']} не из словаря")
                for field, allowed in (("actor", "actors"), ("object", "objects"), ("target", "targets")):
                    if a.get(field) is not None and a[field] not in vocab[allowed]:
                        errors.append(f"{where}: {field}={a[field]} не из словаря")
                if max(a["t"], a.get("t_end", a["t"])) > duration + 1:
                    errors.append(f"{where}: {a['action']} на {a['t']} с за пределами видео ({duration:.1f} с)")
            steps = check_instance(where, scenarios[name], actions, check_errors, check_warnings,
                                   safe_durations if verdict == "no_violation" else [], hits)
            if verdict == "no_violation":
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
        check_video(video, instance_actions, spec.get("video_invariants", []), check_errors, hits)
        return rows

    # эталон нормы: любое отклонение от шаблона — ошибка
    for video, entry in journal.items():
        rows = journal_rows(video, entry, "no_violation", errors, warnings)
        if rows is not None:
            rows_by_video[video] = rows

    # каталог нарушений: отклонение обязано сработать рядом с каждой размеченной секундой
    violation_rows = []
    for video, entry in catalog.items():
        hits: list[dict] = []
        rows = journal_rows(video, entry, "violation", [], [], hits)
        if rows is None:
            continue
        rows_by_video[video] = rows
        for label_t in as_list(entry["label_t"]):
            near = [h for h in hits if abs(h["t"] - label_t) <= CATCH_WINDOW_SEC]
            if not near:
                errors.append(f"{video}: шаблоны не ловят нарушение «{entry['type']}» около {label_t} с — дополнить scenarios.yaml")
            # норматив из каталога (его дал человек) важнее норматива сработавшего правила
            norm_id = entry.get("norm") or next((h["norm"] for h in near if h.get("norm")), None)
            if norm_id is not None and norm_id not in norms:
                errors.append(f"{video}: норматив {norm_id} не найден в norms.yaml")
            norm = norms.get(norm_id, {})
            violation_rows.append({
                "video": video, "sha256": labels[video]["sha256"], "label_t": float(label_t),
                "type": entry["type"], "description": entry["description"], "confirmed": bool(entry.get("confirmed")),
                "norm": norm_id, "act": norm.get("act"), "clause": norm.get("clause"), "url": norm.get("url"),
                "quote": norm.get("quote"),
                "evidence": json.dumps(entry.get("evidence", {})), "caught_by": json.dumps(near, ensure_ascii=False),
            })

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
    for v in violation_rows:
        caught = json.loads(v["caught_by"])
        rules = ", ".join(sorted({h["rule"] for h in caught})) or "НЕ ПОЙМАНО"
        print(f"\n[нарушение] {v['video']} {v['label_t']:.0f} с — {v['type']}: {rules}")
        for h in caught:
            print(f"    {h['t']} с: {h['message']}")
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
                      "scene": (journal.get(video) or catalog.get(video)).get("scene"), "table": "actions",
                      "source": SOURCE, "rows": len(rows)})
    pq.write_table(pa.Table.from_pylist(index), store / "index.parquet")
    if violation_rows:
        pq.write_table(pa.Table.from_pylist(violation_rows), store / "reference" / "violations.parquet")

    pq.write_table(pa.Table.from_pylist([
        {"scenario": name, "title": sc["title"], "step": i, "action": s["action"], "actor": s.get("actor"),
         "objects": as_list(s.get("object")), "target": s.get("target"), "required": s.get("required", False)}
        for name, sc in scenarios.items() for i, s in enumerate(sc["steps"])
    ]), store / "reference" / "scenarios.parquet")
    all_invariants = [(name, inv) for name, sc in scenarios.items() for inv in sc.get("invariants", [])]
    all_invariants += [("*video*", inv) for inv in spec.get("video_invariants", [])]
    pq.write_table(pa.Table.from_pylist([
        {"scenario": name, "kind": inv["kind"], "norm": inv.get("norm"),
         "params": json.dumps({k: v for k, v in inv.items() if k not in ("kind", "why", "norm")}, ensure_ascii=False),
         "why": inv.get("why")}
        for name, inv in all_invariants
    ]), store / "reference" / "invariants.parquet")
    if norms:
        pq.write_table(pa.Table.from_pylist([{"norm": k, **v} for k, v in norms.items()]),
                       store / "reference" / "norms.parquet")
    (store / "reference" / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n→ {store}: {len(index)} видео, {sum(r['rows'] for r in index)} действий")

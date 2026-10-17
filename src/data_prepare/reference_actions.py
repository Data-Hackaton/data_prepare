"""Эталонный порядок действий → feature store.

Берёт reference/scenarios.yaml (шаблоны сценариев) и reference/actions.yaml (журнал действий по чистым видео):
1. проверяет словарь, что видео есть в labels.csv и без нарушений, таймкоды в пределах длительности,
   порядок шагов по шаблону, обязательные шаги и инварианты;
2. если ошибок нет, пишет в feature store (DATA_DIR/features):
   <sha256>/actions.parquet      журнал действий видео, source=reference_r0
   <sha256>/events.parquet       события со статусами expected / warning / violation (sop_events.py)
   reference/scenarios.parquet   шаги шаблонов по порядку
   reference/invariants.parquet  инварианты шаблонов и видео, с нормативом
   reference/norms.parquet       нормативы (документ, пункт, URL, цитата)
   reference/violations.parquet  каталог нарушений: чем пойманы, норматив
   reference/summary.json        покрытие шагов и длительности открытого сейфа
   reference/events_report.md    таймлайн событий по каждому видео
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

from data_prepare.sop_events import STATUS_RU, STATUSES, build_events, render_report, rule_severity, worst

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

EVENTS_SCHEMA = pa.schema([
    ("video", pa.string()),
    ("sha256", pa.string()),
    ("scene", pa.string()),
    ("scenario", pa.string()),
    ("instance", pa.int32()),
    ("step", pa.int32()),  # номер шага процедуры с 1, как в NVIDIA actions.json; null — вне процедуры
    ("t_start", pa.float32()),
    ("t_end", pa.float32()),
    ("event", pa.string()),
    ("actor", pa.string()),
    ("object", pa.string()),
    ("target", pa.string()),
    ("status", pa.string()),  # expected / warning / violation
    ("rules", pa.list_(pa.string())),
    ("norm", pa.string()),
    ("title", pa.string()),  # тип нарушения для ответа жюри и интерфейса
    ("message", pa.string()),
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


# Эталон для tests/test_sop_fsm.py. Проверка журналов и сервис работают на автоматах (sop_fsm): тот же результат.
def check_instance(where: str, scenario: dict, actions: list[dict], errors: list, warnings: list,
                   safe_durations: list, hits: list | None = None, partial: bool = False) -> list[int | None]:
    """Возвращает номер шага шаблона для каждого действия (None — вне шаблона).

    Каждое отклонение от нормы пишется в errors (или warnings для действий вне шаблона)
    и, если передан hits, — туда же с временем, правилом, статусом (sop_events.STATUSES) и ссылкой на действие:
    по hits видно, чем поймано нарушение, и из них собираются события. partial — экземпляр в журнале
    записан не с начала, пропущенные обязательные шаги не считаются.
    """
    def flag(t: float, rule: str, message: str, target: list, action: dict | None = None,
             severity: str = "warning", norm: str | None = None, title: str | None = None) -> None:
        target.append(f"{where}: {message}")
        if hits is not None:
            hits.append({"t": t, "rule": rule, "message": message, "norm": norm, "severity": severity,
                         "title": title, "ref": None if action is None else id(action)})

    steps = scenario["steps"]
    pointer, assigned = 0, []
    for a in actions:
        candidates = [i for i, s in enumerate(steps) if step_matches(s, a)]
        if not candidates:
            flag(a["t"], "out_of_template", f"{a['action']} {a.get('object') or ''} на {a['t']} с — вне шаблона", warnings, a)
            assigned.append(None)
            continue
        forward = [i for i in candidates if i >= pointer]
        if not forward:
            flag(a["t"], "order", f"{a['action']} на {a['t']} с идёт раньше по шаблону, чем предыдущие шаги", errors, a)
            assigned.append(candidates[0])
            continue
        pointer = forward[0]
        assigned.append(pointer)

    for i, s in enumerate(steps):
        if s.get("required") and i not in assigned and not partial:
            flag(actions[0]["t"] if actions else 0, "required", f"нет обязательного шага {s['action']} ({s.get('actor', '')})", errors)

    for inv in scenario.get("invariants", []):
        norm, severity, title = inv.get("norm"), rule_severity(inv), inv.get("title")
        if inv["kind"] == "max_duration":
            for a in (x for x in actions if selector_matches(inv["from"], x)):
                close = next((b for b in actions if selector_matches(inv["to"], b) and b["t"] >= a["t"]), None)
                if close is None:
                    flag(a["t"], "max_duration", f"{inv['from']} на {a['t']} с без {inv['to']}", errors, a, severity, norm, title)
                    continue
                duration = close["t"] - a["t"]
                safe_durations.append(duration)
                if duration > inv["sec"]:
                    flag(a["t"], "max_duration", f"{inv['from']}→{inv['to']} {duration} с > {inv['sec']} с", errors, a, severity, norm, title)
        elif inv["kind"] == "before":
            if "if_present" in inv and not any(selector_matches(inv["if_present"], x) for x in actions):
                continue
            firsts = [x["t"] for x in actions if selector_matches(inv["first"], x)]
            for then in (x for x in actions if selector_matches(inv["then"], x)):
                if not firsts:
                    if "if_present" in inv:
                        flag(then["t"], "before", f"{then['action']} на {then['t']} с без предшествующего {inv['first']}",
                             errors, then, severity, norm, title)
                elif min(firsts) > then["t"]:
                    flag(then["t"], "before", f"{inv['first']} после {then['action']} ({min(firsts)} с > {then['t']} с)",
                         errors, then, severity, norm, title)
        elif inv["kind"] == "forbidden":
            for a in (x for x in actions if selector_matches(inv["action"], x)):
                flag(a["t"], f"forbidden:{a['action']}", f"{a['action']} {a.get('object') or ''} на {a['t']} с запрещено: {inv.get('why', '')}",
                     errors, a, severity, norm, title)
        elif inv["kind"] == "forbidden_after":
            starts = [x["t"] for x in actions if selector_matches(inv["after"], x)]
            if not starts:
                continue
            for a in (x for x in actions if selector_matches(inv["action"], x) and x["t"] >= min(starts)):
                flag(a["t"], f"forbidden_after:{a['action']}",
                     f"{a['action']} на {a['t']} с после {inv['after']} ({min(starts)} с): {inv.get('why', '')}",
                     errors, a, severity, norm, title)
    return assigned


def check_video(where: str, instances: list[list[dict]], video_invariants: list[dict], errors: list,
                hits: list | None = None) -> None:
    """Проверки через все экземпляры видео подряд; instances — действия экземпляров в порядке журнала."""
    timeline = sorted(((a["t"], k, a) for k, actions in enumerate(instances) for a in actions), key=lambda x: x[:2])
    for inv in video_invariants:
        if inv["kind"] != "desk_carryover":
            continue
        # object — предмет или список; target — куда положили (по умолчанию стол); any_instance — срабатывать и на
        # положенном в этом же экземпляре (уход кассира), иначе только на оставшемся от предыдущего клиента
        objects, target = as_list(inv["object"]), inv.get("target", "desk")
        rule = f"desk_carryover:{'/'.join(objects)}" + (f"@{target}" if target != "desk" else "")
        on_desk: list[tuple[int, float]] = []  # (экземпляр, когда положили) для предметов objects
        for t, k, a in timeline:
            if any(selector_matches(trig, a) for trig in inv["triggers"]):
                # min_age_sec — сколько предмет должен пролежать до триггера: деньги, положенные за секунду до
                # прихода клиента, принёс он сам (X-39)
                stale = [(k0, t0) for k0, t0 in on_desk
                         if (k0 < k or inv.get("any_instance")) and t - t0 >= inv.get("min_age_sec", 0)]
                if stale:
                    whose = "" if inv.get("any_instance") else " предыдущего клиента"
                    message = (f"{a['action']} на {t} с, а на месте «{target}» {'/'.join(objects)}{whose} "
                               f"(положены на {stale[0][1]} с): {inv.get('why', '')}")
                    errors.append(f"{where}: {message}")
                    if hits is not None:
                        hits.append({"t": t, "rule": rule, "message": message,
                                     "norm": inv.get("norm"), "severity": rule_severity(inv), "title": inv.get("title"),
                                     "ref": id(a)})
            if a.get("object") in objects and a.get("target") == target:
                if a["action"] == "put":
                    on_desk.append((k, t))
                elif a["action"] == "take" and on_desk:
                    on_desk.pop(0)


def main() -> None:
    from data_prepare.sop_fsm import check_instance_fsm, check_video_fsm  # sop_fsm импортирует этот модуль

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
    known_norms = set(norms)
    for name in ("norms_review.yaml", "norms_corpus.yaml"):  # аудит пакета проверки и нормативный корпус
        path = args.reference / name
        known_norms |= set(yaml.safe_load(path.read_text()) or {}) if path.exists() else set()
    topics_path = args.reference / "topics.yaml"
    topics = yaml.safe_load(topics_path.read_text()) if topics_path.exists() else {}

    errors, warnings, safe_durations = [], [], []
    for inv in [i for sc in scenarios.values() for i in sc.get("invariants", [])] + spec.get("video_invariants", []):
        for b in inv.get("basis", []):  # косвенные основания — из аудита норм, корпуса или выверенных вручную
            if b["norm"] not in known_norms:
                errors.append(f"scenarios.yaml: основание {b['norm']} правила «{inv.get('title')}» нет в norms*.yaml")
        for t in inv.get("topics", []):  # процедуры проверки из нормативного корпуса
            if t not in topics:
                errors.append(f"scenarios.yaml: темы {t} правила «{inv.get('title')}» нет в topics.yaml")
        topic_norms = {n for t in inv.get("topics", []) for n in topics.get(t, {}).get("norms", [])}
        for b in inv.get("basis", []):
            if inv.get("topics") and b["norm"] not in topic_norms:
                print(f"[основание] {b['norm']} правила «{inv.get('title')}» не из норм его тем {inv['topics']}")
    rows_by_video: dict[str, list[dict]] = {}
    coverage: dict[str, Counter] = defaultdict(Counter)
    n_instances: Counter = Counter()

    def journal_rows(video: str, entry: dict, verdict: str, check_errors: list, check_warnings: list
                     ) -> tuple[list[dict], list[dict], list[dict]] | None:
        """Проверка словаря и таймкодов (ошибки — общие) и порядка по шаблону (ошибки — в check_*).

        Возвращает строки журнала для actions.parquet, события со статусами и все сработавшие правила.
        """
        label = labels.get(video)
        if label is None:
            errors.append(f"{video}: нет в labels.csv")
            return None
        if label["verdict"] != verdict or label["duplicate_of"]:
            errors.append(f"{video}: ожидалось уникальное видео с вердиктом {verdict}")
        duration = float(label["duration_sec"])
        rows, instance_actions, instances, hits = [], [], [], []
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
            first_hit = len(hits)
            steps = check_instance_fsm(where, scenarios[name], actions, check_errors, check_warnings,
                                   safe_durations if verdict == "no_violation" else [], hits, inst.get("partial", False))
            for h in hits[first_hit:]:
                h.update(instance=idx, scenario=name)
            instances.append((name, actions, steps))
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
        check_video_fsm(video, instance_actions, spec.get("video_invariants", []), check_errors, hits)
        for e in (events := build_events(video, instances, hits)):
            e.update(sha256=label["sha256"], scene=entry.get("scene"), source=SOURCE)
        return rows, events, hits

    events_by_video: dict[str, list[dict]] = {}

    # эталон нормы: любое отклонение от шаблона — ошибка
    for video, entry in journal.items():
        result = journal_rows(video, entry, "no_violation", errors, warnings)
        if result is not None:
            rows_by_video[video], events_by_video[video], _ = result

    # каталог нарушений: отклонение обязано сработать рядом с каждой размеченной секундой
    violation_rows = []
    for video, entry in catalog.items():
        result = journal_rows(video, entry, "violation", [], [])
        if result is None:
            continue
        rows_by_video[video], events_by_video[video], hits = result
        for label_t in as_list(entry["label_t"]):
            near = [{k: v for k, v in h.items() if k != "ref"} for h in hits if abs(h["t"] - label_t) <= CATCH_WINDOW_SEC]
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

    # сверка итогов событий с разметкой организаторов
    for video, events in events_by_video.items():
        status = worst(e["status"] for e in events)
        if labels[video]["verdict"] == "no_violation" and status == "violation":
            errors.append(f"{video}: видео без нарушения, а в событиях есть нарушение")
        if labels[video]["verdict"] == "violation" and status != "violation":
            errors.append(f"{video}: видео с нарушением, а итог событий — {STATUS_RU[status]}")

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
    print("\nсобытия по видео (ожидаемое / предупреждение / нарушение):")
    for video, events in sorted(events_by_video.items(), key=lambda kv: int(kv[0][2:])):
        counts = [sum(e["status"] == s for e in events) for s in STATUSES]
        print(f"  {video:<5} {labels[video]['verdict']:<13} → {STATUS_RU[worst(e['status'] for e in events)]:<15} {counts}")
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
        pq.write_table(pa.Table.from_pylist(events_by_video[video], schema=EVENTS_SCHEMA), store / sha / "events.parquet")
        scene = (journal.get(video) or catalog.get(video)).get("scene")
        for table, n in (("actions", len(rows)), ("events", len(events_by_video[video]))):
            index.append({"sha256": sha, "video": video, "verdict": labels[video]["verdict"], "scene": scene,
                          "table": table, "source": SOURCE, "rows": n})
    pq.write_table(pa.Table.from_pylist(index), store / "index.parquet")

    report_videos = [
        {"video": v, "scene": (journal.get(v) or catalog.get(v)).get("scene"), "label_verdict": labels[v]["verdict"],
         "label_t": as_list(catalog.get(v, {}).get("label_t")), "events": events_by_video[v]}
        for v in sorted(events_by_video, key=lambda v: int(v[2:]))
    ]
    (store / "reference" / "events_report.md").write_text(render_report(report_videos, norms))
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
    actions_index = [r for r in index if r["table"] == "actions"]
    n_events = sum(r["rows"] for r in index if r["table"] == "events")
    print(f"\n→ {store}: {len(actions_index)} видео, {sum(r['rows'] for r in actions_index)} действий, {n_events} событий")

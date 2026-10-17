"""События видео со статусами: сверка действий с эталонной процедурой (SOP).

Подход как в NVIDIA SOP Monitoring Blueprints: процедура — упорядоченные шаги, часть шагов можно пропускать;
сверка ловит пропущенные обязательные шаги, шаги не по порядку и действия вне процедуры. Сверху — правила
с нормативами (scenarios.yaml). Каждое действие журнала становится событием с одним из статусов:

  expected  — ожидаемое: шаг процедуры на своём месте, ни одно правило не сработало;
  warning   — предупреждение: отклонение без подтверждённого норматива (не по порядку, вне процедуры,
              пропущен обязательный шаг, правило без нормы);
  violation — нарушение: сработало правило с нормативом или правило, подтверждённое как нарушение.

Статус события — самый тяжёлый из сработавших на нём правил; статус видео — самый тяжёлый из статусов событий.
"""

from collections import defaultdict

STATUSES = ("expected", "warning", "violation")
STATUS_RU = {"expected": "ожидаемое", "warning": "предупреждение", "violation": "нарушение"}


def rule_severity(inv: dict) -> str:
    """Явный severity из шаблона; иначе нарушение, если у правила есть норматив, и предупреждение, если нет."""
    return inv.get("severity") or ("violation" if inv.get("norm") else "warning")


def worst(statuses) -> str:
    return max(statuses, key=STATUSES.index, default="expected")


def build_events(video: str, instances: list[tuple[str, list[dict], list[int | None]]], hits: list[dict]) -> list[dict]:
    """instances — (сценарий, действия, номера шагов) в порядке журнала; hits — сработавшие правила.

    Hit с ref = id(действия) относится к этому действию; hit без ref (пропущенный шаг) становится
    отдельным событием в начале своего экземпляра.
    """
    by_ref: dict[int, list[dict]] = defaultdict(list)
    synthetic = []
    for h in hits:
        (by_ref[h["ref"]] if h.get("ref") is not None else synthetic).append(h)

    events = []
    for k, (scenario, actions, steps) in enumerate(instances, start=1):
        for a, step in zip(actions, steps):
            hs = by_ref.get(id(a), [])
            status = worst(h["severity"] for h in hs)
            events.append({
                "video": video, "t_start": float(a["t"]), "t_end": float(a.get("t_end", a["t"])),
                "event": a["action"], "actor": a.get("actor"), "object": a.get("object"), "target": a.get("target"),
                "scenario": scenario, "instance": k, "step": None if step is None else step + 1,
                "status": status, "rules": sorted({h["rule"] for h in hs}),
                "norm": next((h["norm"] for h in hs if h.get("norm") and h["severity"] == status), None),
                "message": "; ".join(h["message"] for h in hs) or None,
                "certain": a.get("certain", True),
            })
    for h in synthetic:
        events.append({
            "video": video, "t_start": float(h["t"]), "t_end": float(h["t"]),
            "event": "missing_step", "actor": None, "object": None, "target": None,
            "scenario": h.get("scenario"), "instance": h.get("instance"), "step": None,
            "status": h["severity"], "rules": [h["rule"]], "norm": h.get("norm"), "message": h["message"],
            "certain": True,
        })
    return sorted(events, key=lambda e: (e["t_start"], e["instance"] or 0))


def fmt_t(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def describe(e: dict) -> str:
    who = {"cashier": "кассир", "client": "клиент", "collector": "инкассатор"}.get(e["actor"] or "", e["actor"] or "")
    what = e["event"] + (f" {e['object']}" if e["object"] else "") + (f" → {e['target']}" if e["target"] else "")
    return f"{who}: {what}" if who else what


def render_report(videos: list[dict], norms: dict) -> str:
    """videos — {video, scene, label_verdict, label_t, events}; markdown с таймлайном событий по каждому видео."""
    lines = [
        "# События по видео: сверка с эталонной процедурой",
        "",
        "Статусы: **ожидаемое** — шаг процедуры на своём месте; **предупреждение** — отклонение без подтверждённого "
        "норматива; **нарушение** — сработало правило с нормативом или подтверждённое как нарушение. "
        "Источник событий — эталонный журнал (`reference_r0`); `?` — наблюдение под вопросом.",
        "",
        "| Видео | Разметка | Итог сверки | Ожидаемых | Предупреждений | Нарушений |",
        "|---|---|---|---|---|---|",
    ]
    for v in videos:
        counts = {s: sum(e["status"] == s for e in v["events"]) for s in STATUSES}
        label = "нарушение" if v["label_verdict"] == "violation" else "норма"
        if v["label_t"]:
            label += " (" + ", ".join(f"{t:g} с" for t in v["label_t"]) + ")"
        lines.append(f"| {v['video']} | {label} | {STATUS_RU[worst(e['status'] for e in v['events'])]} | "
                     f"{counts['expected']} | {counts['warning']} | {counts['violation']} |")
    for v in videos:
        lines += ["", f"## {v['video']} — {STATUS_RU[worst(e['status'] for e in v['events'])]} (сцена {v['scene']})", "",
                  "| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |", "|---|---|---|---|---|"]
        for e in v["events"]:
            span = fmt_t(e["t_start"]) + (f"–{fmt_t(e['t_end'])}" if e["t_end"] > e["t_start"] else "")
            where = f"{e['scenario']} #{e['instance']}" + (f" · шаг {e['step']}" if e["step"] else "")
            norm = norms.get(e["norm"], {}).get("short", e["norm"]) if e["norm"] else None
            rule = ", ".join(e["rules"]) + (f" · {norm}" if norm else "")
            status = STATUS_RU[e["status"]] if e["status"] == "expected" else f"**{STATUS_RU[e['status']]}**"
            lines.append(f"| {span} | {describe(e)}{'' if e['certain'] else ' ?'} | {status} | {where} | {rule} |")
    return "\n".join(lines) + "\n"

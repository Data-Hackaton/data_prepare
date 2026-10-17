"""L3 на конечных автоматах (pytransitions): процедура экземпляра и инварианты как автоматы.

ProcedureMachine — экземпляр сценария: состояние = указатель по шагам шаблона scenarios.yaml (s0…sN), триггер
observe(action). Переход вперёд — на первый подходящий шаг не раньше указателя; внутренние переходы фиксируют
«не по порядку» (подходит только шаг раньше указателя) и «вне шаблона». Инварианты — свои автоматы на тех же
действиях: Forbidden (watch), ForbiddenAfter (idle → armed), Before (no_first → first_seen), MaxDuration
(closed ↔ open); desk_carryover — DeskCarryover на всё видео (empty ↔ occupied).

Время — видео, не часы: встроенный Timeout библиотеки здесь не годится. Часть правил смотрит на экземпляр
целиком (before: самое раннее first, даже если оно позже then; max_duration: закрытие где угодно позже;
обязательные шаги) — они ждут finalize(), который вызывается при закрытии экземпляра (в потоке — когда пришёл
следующий клиент или кончилась запись). Выход совпадает со старыми check_instance / check_video до каждого
срабатывания, включая порядок (tests/test_sop_fsm.py сверяет на всех журналах эталона).
"""

from functools import partial

from transitions import Machine

from data_prepare.reference_actions import as_list, selector_matches, step_matches
from data_prepare.sop_events import rule_severity


class _Channel:
    """Срабатывания одного правила: hits и строки errors/warnings в том порядке, в каком их даёт старый код."""

    def __init__(self, where: str) -> None:
        self.where, self.items = where, []

    def flag(self, t: float, rule: str, message: str, kind: str = "errors", action: dict | None = None,
             severity: str = "warning", norm: str | None = None, title: str | None = None) -> None:
        self.items.append((kind, f"{self.where}: {message}", {
            "t": t, "rule": rule, "message": message, "norm": norm, "severity": severity, "title": title,
            "ref": None if action is None else id(action)}))


class ProcedureMachine:
    """Указатель по шагам шаблона. assigned — номер шага для каждого действия (None — вне шаблона)."""

    def __init__(self, where: str, steps: list[dict]) -> None:
        self.steps, self.assigned, self.channel = steps, [], _Channel(where)
        n = max(1, len(steps))
        self.machine = Machine(model=self, states=[f"s{i}" for i in range(n)], initial="s0", auto_transitions=False,
                               send_event=True)
        anytime = [j for j, s in enumerate(steps) if s.get("anytime")]
        for p in range(len(steps)):
            for j in anytime:  # шаг без места в порядке: засчитывается, указатель на месте
                self.machine.add_transition("observe", f"s{p}", None, conditions=[partial(self._fits, j)],
                                            after=partial(self._assign, j))
            for j in range(p, len(steps)):  # вперёд: первый подходящий шаг не раньше указателя
                if j in anytime:
                    continue
                self.machine.add_transition("observe", f"s{p}", f"s{j}", conditions=[partial(self._fits, j)],
                                            after=partial(self._assign, j))
            self.machine.add_transition("observe", f"s{p}", None, conditions=[self._fits_earlier], after=self._order)
            self.machine.add_transition("observe", f"s{p}", None, after=self._outside)

    def _action(self, event):
        return event.kwargs["action"]

    def _fits(self, j: int, event) -> bool:
        return step_matches(self.steps[j], self._action(event))

    def _fits_earlier(self, event) -> bool:
        return any(step_matches(s, self._action(event)) for s in self.steps)

    def _assign(self, j: int, event) -> None:
        self.assigned.append(j)

    def _order(self, event) -> None:
        a = self._action(event)
        self.channel.flag(a["t"], "order", f"{a['action']} на {a['t']} с идёт раньше по шаблону, чем предыдущие шаги",
                          action=a)
        self.assigned.append(next(i for i, s in enumerate(self.steps) if step_matches(s, a)))

    def _outside(self, event) -> None:
        a = self._action(event)
        self.channel.flag(a["t"], "out_of_template", f"{a['action']} {a.get('object') or ''} на {a['t']} с — вне шаблона",
                          kind="warnings", action=a)
        self.assigned.append(None)


class _Invariant:
    """Общее у инвариантов: канал срабатываний, статус и норматив правила."""

    def __init__(self, where: str, inv: dict) -> None:
        self.inv, self.channel = inv, _Channel(where)
        self.norm, self.severity, self.title = inv.get("norm"), rule_severity(inv), inv.get("title")

    def hit(self, t: float, rule: str, message: str, action: dict | None) -> None:
        self.channel.flag(t, rule, message, action=action, severity=self.severity, norm=self.norm, title=self.title)

    def finalize(self, actions: list[dict], safe_durations: list) -> None:
        pass


class Forbidden(_Invariant):
    """watch: каждое подходящее действие — нарушение."""

    def __init__(self, where: str, inv: dict) -> None:
        super().__init__(where, inv)
        self.machine = Machine(model=self, states=["watch"], initial="watch", auto_transitions=False, send_event=True)
        self.machine.add_transition("observe", "watch", None,
                                    conditions=[lambda e: selector_matches(self.inv["action"], e.kwargs["action"])],
                                    after=self._hit)
        self.machine.add_transition("observe", "watch", None)

    def _hit(self, event) -> None:
        a = event.kwargs["action"]
        self.hit(a["t"], f"forbidden:{a['action']}",
                 f"{a['action']} {a.get('object') or ''} на {a['t']} с запрещено: {self.inv.get('why', '')}", a)


class ForbiddenAfter(_Invariant):
    """idle → armed на первом after; в armed подходящее действие — нарушение. Подходящие действия с тем же
    временем, что и after, но раньше в журнале, тоже считаются (старое правило: t ≥ min(after))."""

    def __init__(self, where: str, inv: dict) -> None:
        super().__init__(where, inv)
        self.start, self.waiting = None, []
        self.machine = Machine(model=self, states=["idle", "armed"], initial="idle", auto_transitions=False,
                               send_event=True)
        self.machine.add_transition("observe", "idle", "armed", conditions=[self._is_after], after=self._arm)
        self.machine.add_transition("observe", "idle", None, conditions=[self._is_target], after=self._wait)
        self.machine.add_transition("observe", "idle", None)
        self.machine.add_transition("observe", "armed", None, conditions=[self._is_target], after=self._hit)
        self.machine.add_transition("observe", "armed", None)

    def _is_after(self, event) -> bool:
        return selector_matches(self.inv["after"], event.kwargs["action"])

    def _is_target(self, event) -> bool:
        return selector_matches(self.inv["action"], event.kwargs["action"])

    def _wait(self, event) -> None:
        self.waiting.append(event.kwargs["action"])

    def _arm(self, event) -> None:
        a = event.kwargs["action"]
        self.start = a["t"]
        for w in (w for w in self.waiting if w["t"] >= self.start):
            self._flag(w)
        if self._is_target(event):  # само after тоже может быть запрещённым действием
            self._flag(a)

    def _hit(self, event) -> None:
        self._flag(event.kwargs["action"])

    def _flag(self, a: dict) -> None:
        self.hit(a["t"], f"forbidden_after:{a['action']}",
                 f"{a['action']} на {a['t']} с после {self.inv['after']} ({self.start} с): {self.inv.get('why', '')}", a)


class Before(_Invariant):
    """no_first → first_seen. then копятся; решение — в finalize: first позже then (или нет вовсе при if_present)."""

    def __init__(self, where: str, inv: dict) -> None:
        super().__init__(where, inv)
        self.firsts, self.thens, self.present = [], [], False
        self.machine = Machine(model=self, states=["no_first", "first_seen"], initial="no_first", auto_transitions=False,
                               send_event=True)
        for state in ("no_first", "first_seen"):
            self.machine.add_transition("observe", state, "first_seen", conditions=[self._is_first], after=self._record)
            self.machine.add_transition("observe", state, None, after=self._record)

    def _is_first(self, event) -> bool:
        return selector_matches(self.inv["first"], event.kwargs["action"])

    def _record(self, event) -> None:
        a = event.kwargs["action"]
        if self._is_first(event):
            self.firsts.append(a["t"])
        if selector_matches(self.inv["then"], a):
            self.thens.append(a)
        if "if_present" in self.inv and selector_matches(self.inv["if_present"], a):
            self.present = True

    def finalize(self, actions: list[dict], safe_durations: list) -> None:
        if "if_present" in self.inv and not self.present:
            return
        for then in self.thens:
            if not self.firsts:
                if "if_present" in self.inv:
                    self.hit(then["t"], "before", f"{then['action']} на {then['t']} с без предшествующего {self.inv['first']}",
                             then)
            elif min(self.firsts) > then["t"]:
                self.hit(then["t"], "before", f"{self.inv['first']} после {then['action']} ({min(self.firsts)} с > {then['t']} с)",
                         then)


class MaxDuration(_Invariant):
    """closed ↔ open по видео-времени. Итог — в finalize: для каждого from — ближайшее to не раньше него."""

    def __init__(self, where: str, inv: dict) -> None:
        super().__init__(where, inv)
        self.froms, self.tos = [], []
        self.machine = Machine(model=self, states=["closed", "open"], initial="closed", auto_transitions=False,
                               send_event=True)
        for state in ("closed", "open"):
            self.machine.add_transition("observe", state, "open", conditions=[self._is_from], after=self._record)
            self.machine.add_transition("observe", state, "closed", conditions=[self._is_to], after=self._record)
            self.machine.add_transition("observe", state, None)

    def _is_from(self, event) -> bool:
        return selector_matches(self.inv["from"], event.kwargs["action"])

    def _is_to(self, event) -> bool:
        return selector_matches(self.inv["to"], event.kwargs["action"])

    def _record(self, event) -> None:
        a = event.kwargs["action"]
        if self._is_from(event):
            self.froms.append(a)
        if self._is_to(event):
            self.tos.append(a)

    def finalize(self, actions: list[dict], safe_durations: list) -> None:
        for a in self.froms:
            close = next((b for b in self.tos if b["t"] >= a["t"]), None)
            if close is None:
                self.hit(a["t"], "max_duration", f"{self.inv['from']} на {a['t']} с без {self.inv['to']}", a)
                continue
            duration = close["t"] - a["t"]
            safe_durations.append(duration)
            if duration > self.inv["sec"]:
                self.hit(a["t"], "max_duration", f"{self.inv['from']}→{self.inv['to']} {duration} с > {self.inv['sec']} с", a)


INVARIANTS = {"forbidden": Forbidden, "forbidden_after": ForbiddenAfter, "before": Before, "max_duration": MaxDuration}


class Instance:
    """Экземпляр процедуры: автомат шаблона + автоматы инвариантов на одних действиях; finalize — при закрытии."""

    def __init__(self, where: str, scenario: dict, partial_instance: bool = False) -> None:
        self.where, self.scenario, self.partial = where, scenario, partial_instance
        self.procedure = ProcedureMachine(where, scenario["steps"])
        self.invariants = [INVARIANTS[inv["kind"]](where, inv) for inv in scenario.get("invariants", [])
                           if inv["kind"] in INVARIANTS]
        self.actions, self.required = [], _Channel(where)

    def observe(self, action: dict) -> None:
        self.actions.append(action)
        self.procedure.observe(action=action)
        for inv in self.invariants:
            inv.observe(action=action)

    def finalize(self, safe_durations: list) -> list[tuple[str, str, dict]]:
        for i, s in enumerate(self.scenario["steps"]):
            if s.get("required") and i not in self.procedure.assigned and not self.partial:
                t = self.actions[0]["t"] if self.actions else 0
                self.required.flag(t, "required", f"нет обязательного шага {s['action']} ({s.get('actor', '')})")
        for inv in self.invariants:
            inv.finalize(self.actions, safe_durations)
        return self.procedure.channel.items + self.required.items + [x for inv in self.invariants for x in inv.channel.items]


def _emit(items, errors: list, warnings: list, hits: list | None) -> None:
    for kind, line, hit in items:
        (warnings if kind == "warnings" else errors).append(line)
        if hits is not None:
            hits.append(hit)


def check_instance_fsm(where: str, scenario: dict, actions: list[dict], errors: list, warnings: list,
                       safe_durations: list, hits: list | None = None, partial: bool = False) -> list[int | None]:
    """То же, что reference_actions.check_instance, на автоматах: номер шага для каждого действия + срабатывания."""
    inst = Instance(where, scenario, partial)
    for a in actions:
        inst.observe(a)
    _emit(inst.finalize(safe_durations), errors, warnings, hits)
    return inst.procedure.assigned


class DeskCarryover:
    """empty ↔ occupied на всё видео: что положено на место target и не убрано. Триггер (приход клиента, уход
    кассира…) при «устаревшем» предмете — нарушение: из прошлого экземпляра (или любого при any_instance) и
    пролежавшем не меньше min_age_sec."""

    def __init__(self, where: str, inv: dict) -> None:
        self.inv, self.where = inv, where
        self.objects, self.target = as_list(inv["object"]), inv.get("target", "desk")
        self.rule = f"desk_carryover:{'/'.join(self.objects)}" + (f"@{self.target}" if self.target != "desk" else "")
        self.on_desk: list[tuple[int, float]] = []
        self.items: list[tuple[str, str, dict]] = []
        self.machine = Machine(model=self, states=["empty", "occupied"], initial="empty", auto_transitions=False,
                               send_event=True)
        for state in ("empty", "occupied"):
            self.machine.add_transition("observe", state, None, conditions=[self._is_trigger], after=self._check)
        self.machine.add_transition("observe", "empty", "occupied", conditions=[self._is_put], after=self._put)
        self.machine.add_transition("observe", "occupied", None, conditions=[self._is_put], after=self._put)
        self.machine.add_transition("observe", "occupied", "empty", conditions=[self._is_take, self._last], after=self._take)
        self.machine.add_transition("observe", "occupied", None, conditions=[self._is_take], after=self._take)
        for state in ("empty", "occupied"):
            self.machine.add_transition("observe", state, None)

    def observe(self, t: float, k: int, a: dict) -> None:
        # проверка триггера и учёт предмета — два шага на одном действии, как в старом коде
        self.machine.events["observe"].trigger(self, t=t, k=k, action=a, phase="trigger")
        self.machine.events["observe"].trigger(self, t=t, k=k, action=a, phase="place")

    def _is_trigger(self, e) -> bool:
        return e.kwargs["phase"] == "trigger" and any(selector_matches(trig, e.kwargs["action"]) for trig in self.inv["triggers"])

    def _placed(self, e) -> bool:
        a = e.kwargs["action"]
        return e.kwargs["phase"] == "place" and a.get("object") in self.objects and a.get("target") == self.target

    def _is_put(self, e) -> bool:
        return self._placed(e) and e.kwargs["action"]["action"] == "put"

    def _is_take(self, e) -> bool:
        return self._placed(e) and e.kwargs["action"]["action"] == "take" and bool(self.on_desk)

    def _last(self, e) -> bool:
        return len(self.on_desk) == 1

    def _put(self, e) -> None:
        self.on_desk.append((e.kwargs["k"], e.kwargs["t"]))

    def _take(self, e) -> None:
        self.on_desk.pop(0)

    def _check(self, e) -> None:
        t, k, a = e.kwargs["t"], e.kwargs["k"], e.kwargs["action"]
        stale = [(k0, t0) for k0, t0 in self.on_desk
                 if (k0 < k or self.inv.get("any_instance")) and t - t0 >= self.inv.get("min_age_sec", 0)]
        if not stale:
            return
        whose = "" if self.inv.get("any_instance") else " предыдущего клиента"
        message = (f"{a['action']} на {t} с, а на месте «{self.target}» {'/'.join(self.objects)}{whose} "
                   f"(положены на {stale[0][1]} с): {self.inv.get('why', '')}")
        self.items.append(("errors", f"{self.where}: {message}", {
            "t": t, "rule": self.rule, "message": message, "norm": self.inv.get("norm"),
            "severity": rule_severity(self.inv), "title": self.inv.get("title"), "ref": id(a)}))


def check_video_fsm(where: str, instances: list[list[dict]], video_invariants: list[dict], errors: list,
                    hits: list | None = None) -> None:
    """То же, что reference_actions.check_video, на автоматах DeskCarryover."""
    timeline = sorted(((a["t"], k, a) for k, actions in enumerate(instances) for a in actions), key=lambda x: x[:2])
    for inv in video_invariants:
        if inv["kind"] != "desk_carryover":
            continue
        machine = DeskCarryover(where, inv)
        for t, k, a in timeline:
            machine.observe(t, k, a)
        _emit(machine.items, errors, [], hits)

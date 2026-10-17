"""L3 на автоматах (sop_fsm) совпадает со старыми check_instance / check_video до каждого срабатывания."""

from pathlib import Path

import pytest
import yaml

from data_prepare.reference_actions import check_instance, check_video
from data_prepare.sop_fsm import check_instance_fsm, check_video_fsm

REFERENCE = Path(__file__).resolve().parents[1] / "reference"
SPEC = yaml.safe_load((REFERENCE / "scenarios.yaml").read_text())
JOURNALS = {**yaml.safe_load((REFERENCE / "actions.yaml").read_text()),
            **yaml.safe_load((REFERENCE / "violations.yaml").read_text())}


def run_old(scenario, actions, partial=False):
    errors, warnings, durations, hits = [], [], [], []
    assigned = check_instance("v", scenario, actions, errors, warnings, durations, hits, partial)
    return assigned, errors, warnings, durations, hits


def run_new(scenario, actions, partial=False):
    errors, warnings, durations, hits = [], [], [], []
    assigned = check_instance_fsm("v", scenario, actions, errors, warnings, durations, hits, partial)
    return assigned, errors, warnings, durations, hits


@pytest.mark.parametrize("video", sorted(JOURNALS, key=lambda v: int(v[2:])))
def test_reference_journals_equal(video):
    instances = []
    for inst in JOURNALS[video]["instances"]:
        actions = sorted(inst["actions"], key=lambda a: a["t"])
        instances.append(actions)
        scenario = SPEC["scenarios"][inst["scenario"]]
        assert run_new(scenario, actions, inst.get("partial", False)) == run_old(scenario, actions, inst.get("partial", False))
    old_errors, old_hits, new_errors, new_hits = [], [], [], []
    check_video(video, instances, SPEC.get("video_invariants", []), old_errors, old_hits)
    check_video_fsm(video, instances, SPEC.get("video_invariants", []), new_errors, new_hits)
    assert (new_errors, new_hits) == (old_errors, old_hits)


def act(t, action, actor=None, obj=None, target=None):
    return {k: v for k, v in {"t": t, "action": action, "actor": actor, "object": obj, "target": target}.items() if v is not None}


def test_tricky_cases_equal():
    sc = SPEC["scenarios"]
    cases = [
        # before: first (safe_close) позже then (уход кассира); if_present без first
        (sc["leave_workplace"], [act(1, "safe_open", "cashier"), act(3, "person_leave", "cashier"), act(5, "safe_close", "cashier")]),
        (sc["leave_workplace"], [act(1, "use_laptop", "cashier"), act(4, "person_leave", "cashier")]),
        # max_duration без закрытия и дольше нормы
        (sc["client_service"], [act(0, "person_enter", "client"), act(2, "safe_open", "cashier")]),
        (sc["client_service"], [act(0, "person_enter", "client"), act(2, "safe_open", "cashier"), act(40, "safe_close", "cashier")]),
        # forbidden_after: запрещённое действие в ту же секунду, что и after, но раньше в журнале
        (sc["client_service"], [act(0, "person_enter", "client"), act(5, "put", "cashier", "banknotes", "cash_machine"),
                                act(5, "person_leave", "client"), act(6, "put", "cashier", "banknotes", "cash_machine")]),
        # порядок и вне шаблона, повтор шага
        (sc["client_service"], [act(0, "person_enter", "client"), act(3, "person_leave", "client"),
                                act(4, "give", "client", "id_card", "cashier"), act(5, "lights_off", "cashier"),
                                act(6, "person_leave", "client")]),
        (sc["client_service"], []),
    ]
    for scenario, actions in cases:
        for partial in (False, True):
            assert run_new(scenario, actions, partial) == run_old(scenario, actions, partial)


def test_anytime_step_keeps_order():
    """Работа за компьютером в начале (экран включён с первого кадра) не делает остальные шаги «не по порядку»."""
    actions = [act(0, "person_enter", "client"), act(0, "use_laptop", "cashier"), act(7, "give", "client", "id_card", "cashier"),
               act(9, "inspect", "cashier", "id_card"), act(12, "give", "client", "banknotes", "cashier"),
               act(13, "put", "cashier", "banknotes", "desk"), act(14, "paperwork", "cashier"), act(16, "take", "cashier", "banknotes", "desk")]
    scenario = SPEC["scenarios"]["client_service"]
    new = run_new(scenario, actions)
    assert new == run_old(scenario, actions)
    assert not [h for h in new[4] if h["rule"] in ("order", "out_of_template")]


def test_video_carryover_equal():
    inst = [[act(0, "person_enter", "client"), act(2, "put", "cashier", "banknotes", "desk")],
            [act(9, "person_enter", "client"), act(10, "take", "cashier", "banknotes", "desk"),
             act(11, "put", "cashier", "bag", "desk"), act(12, "person_leave", "cashier")]]
    old_e, old_h, new_e, new_h = [], [], [], []
    check_video("v", inst, SPEC["video_invariants"], old_e, old_h)
    check_video_fsm("v", inst, SPEC["video_invariants"], new_e, new_h)
    assert old_h and (new_e, new_h) == (old_e, old_h)

from data_prepare.reference_actions import check_instance, check_video

SCENARIO = {
    "steps": [
        {"action": "person_enter", "actor": "client", "required": True},
        {"action": "put", "actor": "cashier", "object": "banknotes", "target": "cash_machine"},
        {"action": "safe_open", "actor": "cashier"},
        {"action": "put", "actor": "cashier", "object": "banknotes", "target": "safe"},
        {"action": "safe_close", "actor": "cashier"},
        {"action": "person_leave", "actor": "client"},
    ],
    "invariants": [
        {"kind": "max_duration", "from": "safe_open", "to": "safe_close", "sec": 20},
        {"kind": "before", "first": "safe_close", "then": {"action": "person_leave", "actor": "client"}},
    ],
}


def run(actions):
    errors, warnings, durations = [], [], []
    steps = check_instance("t", SCENARIO, actions, errors, warnings, durations)
    return steps, errors, warnings, durations


def a(t, action, actor="cashier", **kw):
    return {"t": t, "action": action, "actor": actor, **kw}


def test_reference_order_passes():
    steps, errors, warnings, durations = run([
        a(1, "person_enter", "client"),
        a(5, "put", object="banknotes", target="cash_machine"),
        a(10, "safe_open"),
        a(11, "put", object="banknotes", target="safe"),
        a(14, "safe_close"),
        a(16, "person_leave", "client"),
    ])
    assert errors == [] and warnings == []
    assert steps == [0, 1, 2, 3, 4, 5]
    assert durations == [4]


def test_step_out_of_order_is_error():
    _, errors, _, _ = run([
        a(1, "person_enter", "client"),
        a(5, "safe_open"),
        a(6, "put", object="banknotes", target="cash_machine"),
        a(8, "safe_close"),
    ])
    assert any("раньше по шаблону" in e for e in errors)


def test_missing_required_and_unknown_action():
    steps, errors, warnings, _ = run([a(3, "phone_call")])
    assert steps == [None]
    assert any("обязательного шага person_enter" in e for e in errors)
    assert len(warnings) == 1


def test_safe_left_open_too_long_and_leave_before_close():
    _, errors, _, _ = run([
        a(1, "person_enter", "client"),
        a(10, "safe_open"),
        a(25, "person_leave", "client"),
        a(40, "safe_close"),
    ])
    assert any("30 с > 20 с" in e for e in errors)
    assert any("safe_close после person_leave" in e for e in errors)


def test_forbidden_after_counting_once_client_left():
    scenario = {"steps": SCENARIO["steps"], "invariants": [
        {"kind": "forbidden_after", "after": {"action": "person_leave", "actor": "client"},
         "action": {"action": "put", "object": "banknotes", "target": "cash_machine"}, "norm": "n231_p20"},
    ]}
    errors, hits = [], []
    check_instance("t", scenario, [
        a(1, "person_enter", "client"),
        a(5, "put", object="banknotes", target="cash_machine"),  # при клиенте — можно
        a(12, "person_leave", "client"),
        a(12.5, "put", object="banknotes", target="cash_machine"),  # после ухода — нельзя
    ], errors, [], [], hits)
    rules = [h for h in hits if h["rule"].startswith("forbidden_after")]
    assert [h["t"] for h in rules] == [12.5]
    assert rules[0]["norm"] == "n231_p20"


def test_forbidden_selector_with_object():
    scenario = {"steps": SCENARIO["steps"], "invariants": [
        {"kind": "forbidden", "action": {"action": "put", "object": "foreign_object", "target": "desk"}, "norm": "n231_p12"},
    ]}
    errors, hits = [], []
    check_instance("t", scenario, [
        a(1, "person_enter", "client"),
        a(2, "put", object="banknotes", target="desk"),
        a(3, "put", object="foreign_object", target="desk"),
    ], errors, [], [], hits)
    assert [h["t"] for h in hits if h["rule"].startswith("forbidden")] == [3]


CARRYOVER = [{"kind": "desk_carryover", "object": "banknotes", "norm": "n231_p20", "triggers": [
    {"action": "person_enter", "actor": "client"},
    {"action": "put", "object": "banknotes", "target": "desk"},
]}]


def test_desk_carryover_previous_client_money():
    errors, hits = [], []
    check_video("v", [
        [a(1, "person_enter", "client"), a(5, "put", object="banknotes", target="desk"), a(8, "person_leave", "client")],
        [a(12, "person_enter", "client"), a(15, "put", object="banknotes", target="desk")],
    ], CARRYOVER, errors, hits)
    assert [h["t"] for h in hits] == [12, 15]
    assert all(h["norm"] == "n231_p20" for h in hits)


def test_desk_carryover_cleared_before_next_client():
    errors = []
    check_video("v", [
        [a(1, "person_enter", "client"), a(5, "put", object="banknotes", target="desk"),
         a(7, "take", object="banknotes", target="desk"), a(8, "person_leave", "client")],
        [a(12, "person_enter", "client")],
    ], CARRYOVER, errors)
    assert errors == []

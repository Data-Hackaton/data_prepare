from data_prepare.reference_actions import check_instance

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

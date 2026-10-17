from data_prepare.reference_actions import check_instance
from data_prepare.sop_events import build_events, rule_severity, worst

SCENARIO = {
    "steps": [
        {"action": "person_enter", "actor": "client", "required": True},
        {"action": "put", "actor": "cashier", "object": "banknotes", "target": "cash_machine"},
        {"action": "person_leave", "actor": "client"},
    ],
    "invariants": [
        {"kind": "forbidden", "action": "keep", "norm": None, "severity": "violation"},
        {"kind": "forbidden_after", "after": {"action": "person_leave", "actor": "client"},
         "action": {"action": "put", "object": "banknotes", "target": "cash_machine"}, "norm": "n231_p20"},
    ],
}


def a(t, action, actor="cashier", **kw):
    return {"t": t, "action": action, "actor": actor, **kw}


def events_for(actions, partial=False):
    hits = []
    steps = check_instance("t", SCENARIO, actions, [], [], [], hits, partial)
    for h in hits:
        h.update(instance=1, scenario="client_service")
    return build_events("V", [("client_service", actions, steps)], hits)


def test_rule_severity_defaults():
    assert rule_severity({"norm": "n231_p20"}) == "violation"
    assert rule_severity({"norm": None}) == "warning"
    assert rule_severity({"norm": None, "severity": "violation"}) == "violation"


def test_reference_order_is_all_expected():
    events = events_for([a(1, "person_enter", "client"), a(5, "put", object="banknotes", target="cash_machine"),
                         a(9, "person_leave", "client")])
    assert [e["status"] for e in events] == ["expected"] * 3
    assert [e["step"] for e in events] == [1, 2, 3]
    assert worst(e["status"] for e in events) == "expected"


def test_out_of_procedure_action_is_warning():
    events = events_for([a(1, "person_enter", "client"), a(3, "phone_call")])
    phone = next(e for e in events if e["event"] == "phone_call")
    assert phone["status"] == "warning" and phone["step"] is None


def test_rule_with_norm_is_violation_on_its_action():
    events = events_for([a(1, "person_enter", "client"), a(9, "person_leave", "client"),
                         a(10, "put", object="banknotes", target="cash_machine")])
    late = next(e for e in events if e["t_start"] == 10)
    assert late["status"] == "violation" and late["norm"] == "n231_p20"
    assert "forbidden_after:put" in late["rules"]


def test_confirmed_rule_without_norm_is_violation():
    events = events_for([a(1, "person_enter", "client"), a(4, "keep", object="banknotes")])
    keep = next(e for e in events if e["event"] == "keep")
    assert keep["status"] == "violation" and keep["norm"] is None


def test_missing_required_step_is_warning_event_unless_partial():
    events = events_for([a(5, "put", object="banknotes", target="cash_machine")])
    missing = [e for e in events if e["event"] == "missing_step"]
    assert len(missing) == 1 and missing[0]["status"] == "warning"
    assert not [e for e in events_for([a(5, "put", object="banknotes", target="cash_machine")], partial=True)
                if e["event"] == "missing_step"]

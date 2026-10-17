"""Правка разметки: каждое правило по отдельности, повторное применение и сейф, закрытый человеком."""

from data_prepare.label_fixes import fix_video, frame_ranges

LAPTOP = [0.50, 0.42, 0.62, 0.51]
MACHINE = [0.10, 0.43, 0.25, 0.53]
SAFE = [0.66, 0.40, 0.90, 0.58]


def box(cls, b):
    return {"cls": cls, "box": list(b)}


def rules(actions):
    return sorted((a["rule"], a["action"]) for a in actions)


def test_chair_machine_safe():
    frames = {"f1": [box("computer", LAPTOP), box("computer", [0.2, 0.82, 0.45, 0.99]),
                     box("cash_machine", MACHINE), box("computer", MACHINE), box("computer", SAFE)],
              "f2": [box("computer", MACHINE)]}  # машинка в кадре не обведена — её computer становится cash_machine
    out, actions = fix_video(frames)
    assert rules(actions) == [("cash_machine", "delete"), ("cash_machine", "relabel"), ("chair", "delete"),
                              ("missing_safe", "add"), ("safe", "relabel")]
    assert sorted(b["cls"] for b in out["f1"]) == ["cash_machine", "computer", "safe"]
    assert sorted(b["cls"] for b in out["f2"]) == ["cash_machine", "safe"]


def test_duplicate_and_elsewhere_safe():
    frames = {"f1": [box("safe", SAFE), box("computer", [0.67, 0.41, 0.89, 0.57])],
              "f2": [box("safe", SAFE), box("safe", [0.30, 0.20, 0.40, 0.25])]}
    out, actions = fix_video(frames)
    assert rules(actions) == [("duplicate_safe", "delete"), ("safe_elsewhere", "delete")]
    assert [b["cls"] for b in out["f1"]] == ["safe"] and [b["cls"] for b in out["f2"]] == ["safe"]


def test_static_safe_and_occlusion():
    frames = {"open": [box("computer", LAPTOP)], "hidden": [box("person", [0.6, 0.3, 0.95, 0.7])]}
    out, actions = fix_video(frames, static_safe=SAFE)
    assert [(a["file"], a["rule"]) for a in actions] == [("open", "missing_safe")]
    assert not any(b["cls"] == "safe" for b in out["hidden"])


def test_idempotent():
    frames = {"f1": [box("computer", SAFE), box("computer", [0.2, 0.82, 0.45, 0.99])], "f2": []}
    once, _ = fix_video(frames)
    twice, actions = fix_video(once)
    assert actions == [] and twice == once


def test_frame_ranges():
    assert frame_ranges([5, 3, 4, 9, 11, 12]) == "3–5, 9, 11–12"

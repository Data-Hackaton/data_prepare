"""Нормативный корпус: ключи норм, справочники topics/norms_corpus и связь правил L3 с темами."""

from pathlib import Path

import pytest
import yaml

from data_prepare.corpus_import import WORKFLOWS, import_norms, import_topics
from data_prepare.norm_keys import norm_key

REFERENCE = Path(__file__).resolve().parents[1] / "reference"


def load(name):
    return yaml.safe_load((REFERENCE / name).read_text())


def test_norm_keys():
    assert norm_key("V1900019680:20") == "n231_p20"
    assert norm_key("V1500012534:12/1") == "n927_p12_1"
    assert norm_key("K1500000414:181.2/1") == "tk_p181_2_1"
    assert norm_key("K1500000414:23.2/25-1") == "tk_p23_2_25_1"
    assert norm_key("V2000020075:16@transition_until_2027") == "n14_p16_transition_until_2027"
    assert norm_key("B-ONLINE2025") == "forte_online2025_p35_4"


def test_topics_and_norms_consistent():
    topics, norms = load("topics.yaml"), load("norms_corpus.yaml")
    assert len(topics) == 80 and len(norms) == 187
    for tid, t in topics.items():
        assert t["steps"] and t["check"], tid
        assert set(t["norms"]) <= set(norms), tid
        assert all(set(s["norms"]) <= set(norms) for s in t["steps"]), tid


def test_rules_link_existing_topics():
    topics, spec = load("topics.yaml"), load("scenarios.yaml")
    rules = [inv for sc in spec["scenarios"].values() for inv in sc.get("invariants", [])] + spec["video_invariants"]
    linked = [inv for inv in rules if inv.get("topics")]
    assert linked and all(t in topics for inv in linked for t in inv["topics"])
    assert all(inv.get("topics") for inv in rules if inv["title"] != "Присвоение части наличных")


@pytest.mark.skipif(not WORKFLOWS.exists(), reason="нет reference/normative_coverage (корпус)")
def test_import_matches_reference():
    import json

    wf = json.loads(WORKFLOWS.read_text())
    assert import_norms(wf).keys() == load("norms_corpus.yaml").keys()
    assert import_topics(wf) == load("topics.yaml")

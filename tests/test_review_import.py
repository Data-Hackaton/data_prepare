"""Импорт «Полной проверки ForteBank»: ключи норм и повторяемая правка каталога без потери комментариев."""

import shutil
from pathlib import Path

import yaml

from data_prepare.review_import import norm_key, update_unreviewed

REFERENCE = Path(__file__).resolve().parents[1] / "reference"


def test_norm_keys():
    assert norm_key("V1900019680:20") == "n231_p20"
    assert norm_key("V1900019680:10-1") == "n231_p10_1"
    assert norm_key("V2000020075:8") == "n14_p8"
    assert norm_key("V2600038336:71") == "n53_p71"
    assert norm_key("B-ONLINE2025") == "forte_online2025_p35_4"


def test_update_unreviewed_idempotent(tmp_path):
    shutil.copy(REFERENCE / "violations_unreviewed.yaml", tmp_path)
    videos = {"X-11": {"status": "insufficient", "scenario": "Оставление оборудования, включённого", "norms": ["n53_p71"]},
              "X-13": {"status": "probable", "scenario": "Пропуск пересчёта", "norms": ["n231_p41"]}}
    update_unreviewed(videos, tmp_path)
    once = (tmp_path / "violations_unreviewed.yaml").read_text()
    update_unreviewed(videos, tmp_path)
    assert (tmp_path / "violations_unreviewed.yaml").read_text() == once
    catalog = yaml.safe_load(once)
    assert catalog["X-11"]["type"] == "неясно" and catalog["X-11"]["review"]["norms"] == ["n53_p71"]
    assert catalog["X-13"]["type"] == "Пропуск пересчёта" and catalog["X-13"]["prev_type"]
    assert once.count("# при выключенном свете") == 1  # комментарий к rule не потерян

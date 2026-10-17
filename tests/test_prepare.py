import pytest

from data_prepare.prepare import normalize_name, parse_timecode


@pytest.mark.parametrize("raw", ["X-1", "Х-1"])  # латинская и кириллическая
def test_normalize_name_to_ascii(raw):
    assert normalize_name(raw) == "X-1"


@pytest.mark.parametrize(
    ("raw", "sec"),
    [("22 секунда", 22), ("1минута 8 секунда", 68), ("2 минуты", 120), (None, None), ("", None)],
)
def test_parse_timecode(raw, sec):
    assert parse_timecode(raw) == sec


def test_parse_timecode_rejects_garbage():
    with pytest.raises(ValueError):
        parse_timecode("примерно середина")

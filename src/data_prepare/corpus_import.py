"""Импорт нормативного корпуса (reference/normative_coverage, коммит 191bfd87) в справочники правил.

  python -m data_prepare.corpus_import [--workflows …/reference_workflows/workflows.json] [--reference /refw]

Пишет:
  reference/norms_corpus.yaml — 187 пунктов из 16 официальных источников: полный текст (quote), якорь adilet (url),
                                контрольная сумма источника; ключи — data_prepare.norm_keys (n231_p20, n14_p8 …).
                                Поверх него — norms_review.yaml (требование, границы применимости) и norms.yaml;
  reference/topics.yaml       — 80 процедур проверки: шаги с наблюдаемостью по видео, исключения и допустимые
                                варианты, что проверить человеку (check), нормы шагов (ключи norms_corpus).
Правила L3 ссылаются на темы полем topics в scenarios.yaml; на статус события это не влияет.
"""

import argparse
import json
from pathlib import Path

import yaml

from data_prepare.norm_keys import norm_key

REFERENCE = Path(__file__).resolve().parents[2] / "reference"
WORKFLOWS = REFERENCE / "normative_coverage" / "reference_workflows" / "workflows.json"
OBSERVABILITY_RU = {"partly_observable": "видно частично", "context_required": "нужен контекст",
                    "not_visually_verifiable": "по видео не проверяется"}


def keys(specs: list[str]) -> list[str]:
    return list(dict.fromkeys(norm_key(s) for s in specs))


def import_norms(wf: dict) -> dict:
    out = {}
    for spec, ref in wf["references"].items():
        key = norm_key(spec)
        if key in out:
            raise SystemExit(f"{spec}: ключ {key} уже занят {out[key]['spec']}")
        meta = wf["source_metadata"].get(ref["document_id"], {})
        out[key] = {
            "short": f"{ref['document']}, {ref['locator']}",
            "document": meta.get("title"),
            "act": meta.get("official_name"),
            "clause": ref["locator"],
            "url": ref["url"],
            "quote": ref["text"],
            "heading": ref.get("heading"),
            "spec": spec,
            "source_sha256": ref.get("source_sha256"),
            "source": "corpus 2026-10-17",
        }
    return out


def import_topics(wf: dict) -> dict:
    out = {}
    for t in wf["topic_procedures"]:
        out[t["rule_id"]] = {
            "title": t["title"],
            "domain": t.get("domain"),
            "procedure_type": t.get("procedure_type"),
            "actor": t.get("actor"),
            "applicability": t.get("applicability"),
            "expected_outcome": t.get("expected_outcome"),
            "steps": [{"action": s["action"], "kind": s.get("kind"), "observability": s.get("video_verification"),
                       "norms": keys(s.get("source_specs", []))} for s in t["steps"]],
            "exceptions": [{"kind": e.get("kind"), "condition": e.get("condition"), "behavior": e.get("behavior"),
                            "norms": keys(e.get("source_specs", []))} for e in t.get("exceptions", [])],
            "check": t.get("evidence", []),
            "limits": t.get("catalog_limits_and_exceptions"),
            "norms": keys(t.get("source_specs", [])),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workflows", type=Path, default=WORKFLOWS)
    ap.add_argument("--reference", type=Path, default=REFERENCE, help="куда писать (в compose reference/ только на чтение)")
    args = ap.parse_args()
    wf = json.loads(args.workflows.read_text())
    norms, topics = import_norms(wf), import_topics(wf)
    missing = sorted({k for t in topics.values() for k in t["norms"]} - set(norms))
    if missing:
        raise SystemExit(f"нормы тем без текста в корпусе: {missing}")
    header = ("# Сгенерировано python -m data_prepare.corpus_import из reference/normative_coverage — не править вручную.\n"
              f"# Корпус: {wf.get('title', '')}, {wf.get('review_date', '')}. {wf['global_limits'][0]}\n")
    (args.reference / "norms_corpus.yaml").write_text(
        header + "# Пункты с полным текстом и якорем; требование и границы применимости — norms_review.yaml, ручные — norms.yaml.\n"
        + yaml.safe_dump(norms, allow_unicode=True, sort_keys=False, width=120))
    (args.reference / "topics.yaml").write_text(
        header + "# Процедуры проверки по темам. observability шага: " + ", ".join(f"{k} — {v}" for k, v in OBSERVABILITY_RU.items())
        + ".\n# check — что установить человеку; limits — исключения и границы вывода.\n"
        + yaml.safe_dump(topics, allow_unicode=True, sort_keys=False, width=120))
    print(f"нормы: {len(norms)}, темы: {len(topics)} → {args.reference}")


if __name__ == "__main__":
    main()

"""Импорт пакета «Полная проверка ForteBank» (data/review/<пакет>/) в справочники reference/.

  python -m data_prepare.review_import [--package /data/review/forte-full-check-2026-10-17] [--reference /refw]

Пишет:
  reference/norms_review.yaml   — пункты из аудита норм (точный текст, требование, границы применимости, URL);
                                  ключи как в norms.yaml (n231_p20, n14_p8, n53_p71, forte_online2025_p35_4…).
                                  Вручную выверенные norms.yaml (n231_p12, n231_p20, n231_p22) не трогает;
  reference/video_review.yaml   — итог проверки по каждому из 42 файлов: статус доказанности, сценарий, что видно,
                                  хронология, ограничения, нормы (ключи norms_review), метка организаторов;
  reference/violations_unreviewed.yaml — блок review у 16 видео; type из проверки при supported / probable,
                                  при insufficient — «неясно», прежний — в prev_type; комментарии файла остаются.
Сам пакет — данные команды; он проверяет упаковку и согласованность, а не удостоверяет нарушения.
"""

import argparse
import json
import os
import re
from pathlib import Path

import yaml

REFERENCE = Path(__file__).resolve().parents[2] / "reference"
DEFAULT_PACKAGE = "review/forte-full-check-2026-10-17"
ACTS = {"V1900019680": ("n231", "Правила №231"), "V2000020075": ("n14", "Правила №14 (охрана и устройство помещений)"),
        "V2200026867": ("n55", "Правила пожарной безопасности №55"),
        "V2600038336": ("n53", "Требования к информационной безопасности банков №53")}
FORTE = {"B-ONLINE2025": "forte_online2025_p35_4", "B-ONLINE2024": "forte_online2024_p35_3", "B-REMOTE": "forte_remote",
         "B-EBU19": "forte_ebu19", "B-EBU21": "forte_ebu21", "B-ETHICS": "forte_ethics", "B-CA": "forte_ca",
         "B-INSIDER": "forte_insider", "B-ACCOUNTS-CASH": "forte_accounts_cash",
         "B-ACCOUNTS-COLLECTION": "forte_accounts_collection", "B-ANNUAL2024": "forte_annual2024",
         "B-GENERAL63": "forte_general63"}
STATUS_RU = {"supported": "подтверждено", "probable": "вероятно", "insufficient": "недостаточно данных",
             "conditional_issue": "условный кандидат", "no_supported_violation": "нарушение не подтверждено"}


def norm_key(rule_id: str) -> str:
    """V1900019680:20 → n231_p20; V1900019680:10-1 → n231_p10_1; B-ONLINE2025 → forte_online2025_p35_4."""
    if rule_id in FORTE:
        return FORTE[rule_id]
    act, _, point = rule_id.partition(":")
    return f"{ACTS[act][0]}_p{point.replace('-', '_')}"


def video_name(name: str) -> str:
    return re.sub(r"^Х", "X", name)  # в пакете у части файлов кириллическая Х


def import_norms(audit: dict) -> dict:
    out = {}
    for r in audit["rules"]:
        act = r["id"].partition(":")[0]
        point = r["point_exact"]
        short = (f"{ACTS[act][1]}, п.{r['id'].partition(':')[2]}" if act in ACTS
                 else f"ForteBank: {r['document_title']}, " + re.sub(r"\s*\(редакция[^)]*\)", "", point.split(";")[0]))
        out[norm_key(r["id"])] = {
            "short": short,
            "document": " ".join((r.get("document_title") or "").split()),
            "act": (f"№{r['document_number']} от {r['document_date']}" if r.get("document_number") else None),
            "clause": point,
            "url": r.get("official_url"),
            "quote": r.get("exact_text"),
            "requirement": r.get("plain_requirement"),
            "limits": r.get("applicability_limits"),
            "kind": r.get("source_kind"),
            "quote_verified": r.get("quote_verified_against_local_source"),
            "source": "review 2026-10-17",
        }
    return out


def import_videos(table: dict) -> dict:
    out = {}
    for r in table["rows"]:
        out[video_name(r["video_id"])] = {
            "label": r["original_label"], "label_t": r.get("original_timestamp_sec"), "status": r["status"],
            "status_ru": STATUS_RU.get(r["status"], r["status"]), "scenario": r["scenario"], "observed": r["observed"],
            "timeline": r["timeline"], "limitations": r["limitations"],
            "norms": [norm_key(x) for x in r["rule_ids"]], "window_sec": r.get("reviewed_window_sec"),
            "evidence": [e["path"] for e in r.get("evidence", [])],
        }
    return out


NOTE = ("\n# review — итог «Полной проверки ForteBank 2026-10-17» (подробно — video_review.yaml). type берётся из неё при"
        "\n# статусе supported / probable, при insufficient — «неясно»; прежний тип — в prev_type.\n")


def update_unreviewed(videos: dict, reference: Path) -> None:
    """Правка построчно: комментарии и пояснения к rule в файле остаются; повторный импорт заменяет прежний."""
    path = reference / "violations_unreviewed.yaml"
    head, *entries = re.split(r"(?m)^(?=X-\d+:$)", path.read_text())
    out = [head if NOTE.strip() in head else head.rstrip("\n") + "\n" + NOTE + "\n"]
    for block in entries:
        review = videos.get(block.split(":", 1)[0])
        block = re.sub(r"(?m)^  review:.*\n(?:    .*\n)*", "", block)
        prev = re.search(r"(?m)^  prev_type: (.*)\n", block)
        block = re.sub(r"(?m)^  prev_type: .*\n", "", block)
        if review:
            original = yaml.safe_load(prev.group(1)) if prev else yaml.safe_load(re.search(r"(?m)^  type: (.*)$", block).group(1))
            new = review["scenario"] if review["status"] in ("supported", "probable") else "неясно"
            q = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731 — строка JSON — это строка YAML в кавычках
            typed = f"  type: {q(new)}\n" + (f"  prev_type: {q(original)}\n" if new != original else "")
            block = re.sub(r"(?m)^  type: .*\n", lambda m: typed, block, count=1)
            core = block.rstrip("\n")
            block = (core + f"\n  review:\n    status: {review['status']}\n    scenario: {q(review['scenario'])}\n"
                     f"    norms: [{', '.join(review['norms'])}]" + (block[len(core):] or "\n"))
        out.append(block)
    path.write_text("".join(out))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", type=Path, default=Path(os.environ.get("DATA_DIR", "/data")) / DEFAULT_PACKAGE)
    ap.add_argument("--reference", type=Path, default=REFERENCE, help="куда писать (в compose reference/ только на чтение)")
    args = ap.parse_args()
    audit = json.loads((args.package / "data" / "norms_audit.json").read_text())
    table = json.loads((args.package / "data" / "full_table.json").read_text())
    norms, videos = import_norms(audit), import_videos(table)
    header = (f"# Сгенерировано python -m data_prepare.review_import из {args.package.name} — не править вручную.\n")
    (args.reference / "norms_review.yaml").write_text(
        header + "# Пункты из аудита норм: точный текст (quote) сверен с локальным источником пакета; limits — границы\n"
        "# применимости. Это основания для правил; вывод о нарушении они не заменяют.\n"
        + yaml.safe_dump(norms, allow_unicode=True, sort_keys=False, width=120))
    (args.reference / "video_review.yaml").write_text(
        header + "# Итог проверки по каждому файлу. status: supported / probable / insufficient / conditional_issue /\n"
        "# no_supported_violation. Метка организаторов (label) остаётся истиной для оценки.\n"
        + yaml.safe_dump(videos, allow_unicode=True, sort_keys=False, width=120))
    update_unreviewed(videos, args.reference)
    print(f"нормы: {len(norms)}, видео: {len(videos)} → {args.reference}")


if __name__ == "__main__":
    main()

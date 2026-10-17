"""Collect the public documents linked by ForteBank, without touching video work."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
HOST = "https://prod-one-strapi.s3.eu-north-1.amazonaws.com/"
DOCS = [
    ("forte_online_procedure_2025", "Процедура предоставления электронных банковских услуг на Онлайн-платформе, 2025", "Proczedura_EBU_11_2025_final_docx_2e559bb913.pdf", "https://business.forte.kz/ru/documents"),
    ("forte_ethics_2024", "Кодекс корпоративной этики ForteBank (извлечение), 2024", "Kodeks_korp_etiki_izvlechenie_na_razmeshhenie_148494258d_8850aeb114.pdf", "https://forte.kz/ru/documents"),
    ("forte_general_operations_2026", "Правила об общих условиях банковских и иных операций, изменения от 16.09.2026", "Pravila_ob_obshhih_usloviyah_bankovskih_i_inyh_operaczijs_Izm_SD_36_z_ot160926_dc368384cd.pdf", "https://forte.kz/ru/documents"),
    ("forte_remote_terms", "Общие условия дистанционного обслуживания", "Obshhie_usloviya_distanczionnogo_obsluzhivaniya_IBMIB_b2d3e86193.pdf", "https://business.forte.kz/ru/documents"),
    ("forte_ebu_rules", "Правила предоставления электронных банковских услуг для юридических лиц и ИП", "Pravila_preostavleniya_EBU_dlya_Yu_L_i_IP_v_sisteme_IB_i_MIB_Utv_UL_13d9f445d4.pdf", "https://business.forte.kz/ru/documents"),
    ("forte_business_manual", "Руководство пользователя системы ForteBusiness", "Rukovodstvo_polzovatelya_Sistemy_Forte_Business_27e882066b_ee0cfa0a37.pdf", "https://business.forte.kz/ru/documents"),
]


def main():
    # Preserve the expanded registry when the original entry point is reused.
    if (ROOT / 'source_catalog.json').exists():
        from expand_forte_public import fetch, parse
        fetch()
        parse()
        return
    entries = []
    for doc_id, title, remote_file, landing_url in DOCS:
        destination = ROOT / (doc_id + ".pdf")
        url = HOST + remote_file
        if not destination.exists():
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=40) as response:
                data = response.read()
            if not data.startswith(b"%PDF-"):
                raise ValueError("Unexpected content for " + doc_id)
            destination.write_bytes(data)
        data = destination.read_bytes()
        reader = PdfReader(destination)
        pages = [{"page": index + 1, "text": page.extract_text() or ""}
                 for index, page in enumerate(reader.pages)]
        entry = {"id": doc_id, "title": title, "url": url,
                 "landing_url": landing_url,
                 "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                 "sha256": hashlib.sha256(data).hexdigest(),
                 "bytes": len(data), "page_count": len(pages),
                 "characters": sum(len(p["text"]) for p in pages),
                 "pages_without_text": [p["page"] for p in pages if not p["text"].strip()],
                 "extraction_method": "pypdf; every page processed; visual verification of cited pages required",
                 "full_legal_applicability_confirmed": False}
        (ROOT / (doc_id + ".json")).write_text(
            json.dumps({"metadata": entry, "pages": pages}, ensure_ascii=False, indent=2), encoding="utf-8")
        entries.append(entry)
        print(json.dumps({"id": doc_id, "pages": len(pages), "characters": entry["characters"],
                          "empty_pages": entry["pages_without_text"]}, ensure_ascii=False), flush=True)
    (ROOT / "source_manifest.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

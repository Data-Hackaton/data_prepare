"""Download and index public comparative security references for the Forte case."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
EARLIER_CANDIDATES = [
    {"id": "muslim_cooperative_bank_isms_2022", "title": "The Muslim Co-Operative Bank Ltd. — Information Security Management System Policy, PL-01 v2.0",
     "url": "https://muslimcooperativebank.com/images/notice/PL%2001-%20ISMS%20Policy.pdf",
     "version": "2.0; release date 18.10.2022 on cover; current internal status not independently established",
     "source_type": "other_bank_internal_policy_public_copy", "jurisdiction": "India",
     "scope": "Users of this bank's information assets, including staff and contractors; head and branch offices. Not ForteBank.",
     "locator": "7.21 Clean and Clear Desk, PDF/printed page 23; scope pp. 6–7", "pdf_page": 23,
     "check": "Screens must be locked", "render_pages": [1, 7, 23]},
    {"id": "bangladesh_bank_ict_v4_2023", "title": "Bangladesh Bank — Guideline on ICT Security, Version 4.0, 2023",
     "url": "https://www.bb.org.bd/mediaroom/circulars/brpd/jun192023brpd10.pdf",
     "version": "Version 4.0; BRPD Circular No. 10, 19.06.2023; downloaded published version, not a claim of exhaustive subsequent-amendment review",
     "source_type": "foreign_financial_regulator_guideline", "jurisdiction": "Bangladesh",
     "scope": "Institutions regulated by Bangladesh Bank, as defined in section 1.2. Not a Kazakhstan regulation.",
     "locator": "5.12.1.2, PDF 44 / printed 33; scope 1.2, PDF 13 / printed 2", "pdf_page": 44,
     "check": "5.12.1.2", "render_pages": [2, 13, 44]},
    {"id": "nist_sp800_53r5_2020", "title": "NIST SP 800-53 Rev. 5 — Security and Privacy Controls for Information Systems and Organizations",
     "url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf",
     "version": "September 2020, updates 10.12.2020; official landing page announces release 5.2.0 on 27.08.2025; see separate changes file",
     "source_type": "security_control_catalog", "jurisdiction": "United States; comparative methodological reference",
     "scope": "Configurable controls adopted through an organization's risk management; selection is needed for AC-11a. No evidence of adoption by ForteBank.",
     "locator": "AC-11 and AC-11(1), PDF 69 / printed 42; discussion continues PDF 70", "pdf_page": 69,
     "check": "AC-11", "render_pages": [69]},
    {"id": "nist_sp800_53_release_520_changes", "title": "NIST — Summary of Changes: SP 800-53 Release 5.2.0",
     "url": "https://csrc.nist.gov/files/projects/Risk-Management/800-53%20Comment%20Site/SP800-53-r5.2.0-changes.pdf",
     "version": "Release 5.2.0, announced 27.08.2025",
     "source_type": "version_change_record", "jurisdiction": "United States",
     "scope": "Version record; not a separate screen-lock rule. AC-11 is not listed as changed in this release.",
     "locator": "Table 1, pp. 1–2", "pdf_page": 1,
     "check": "5.2.0", "render_pages": []},
    {"id": "moex_code_ethics_2024", "title": "Кодекс профессиональной этики ПАО Московская Биржа",
     "url": "https://www.moex.com/files/4m8te7k9fcc54z7ekd68bfbhx4",
     "version": "Утвержден 11.12.2024, протокол №13; опубликованная копия",
     "source_type": "financial_market_organization_employee_code", "jurisdiction": "Russia",
     "scope": "Работники и члены органов управления ПАО Московская Биржа; не банковский регламент ForteBank и не обязательное правило для всех компаний группы.",
     "locator": "11.3, PDF/печатная 7; область действия — раздел 1 и сноски, PDF 2", "pdf_page": 7,
     "check": "блокируем компьютер", "render_pages": [1, 7]},
]
SOURCES = [s for s in EARLIER_CANDIDATES if s["id"].startswith("nist_")] + [
    {"id": "bank_of_england_our_code_2024", "title": "Bank of England — Our Code, January 2024",
     "web_review_only": True, "web_review_path": "bank_of_england_our_code_2024_web_review.json",
     "url": "https://beta.bankofengland.co.uk/-/media/boe/files/about/human-resources/our-code-2024.pdf",
     "version": "January 2024; historical published edition. Current January 2026 web code differs and does not reproduce this specific sentence.",
     "source_type": "central_bank_employee_code_historical", "jurisdiction": "United Kingdom",
     "scope": "Staff of the Bank of England; a published historical employee rule, not a rule for every UK bank or ForteBank.",
     "locator": "Safety and security at the Bank’s premises, PDF 35 / printed 34; staff scope PDF 2–3",
     "pdf_page": 35, "check": "lock your computer screen", "render_pages": [1, 2, 35]},
    {"id": "fdic_cybersecurity_privacy_training", "title": "FDIC — Cybersecurity and Privacy Awareness Training",
     "url": "https://www.fdic.gov/formsdocuments/it-security-privacy-awareness.pdf",
     "version": "No edition date on cover. PDF metadata: created 24.10.2025, modified 14.11.2025; metadata dates are not an approval date. Public copy retrieved 17.10.2026.",
     "source_type": "financial_regulator_staff_training", "jurisdiction": "United States",
     "scope": "FDIC employees, contractors and authorized visitors using FDIC systems. Not a general rule for all banks supervised by FDIC.",
     "locator": "Protecting Information Throughout the Lifecycle / Acceptable Use Policy for FDIC Information, PDF/printed 25–26; direct screen rule page 26",
     "pdf_page": 26, "check": "Always lock your screen", "render_pages": [1, 25, 26]},
    {"id": "enisa_ncsa_transatlantic_checklist_2020", "title": "ENISA / NCSA — 2020 Transatlantic Cybersecurity Checklist for Small Businesses",
     "url": "https://www.enisa.europa.eu/sites/default/files/2024-10/transatlantic-cybersecurity-checklist.pdf",
     "version": "November 2020; year in storage directory is not the document edition.",
     "source_type": "joint_eu_us_awareness_guidance", "jurisdiction": "European Union and United States",
     "scope": "Baseline guidance for small businesses and employee cyber hygiene; not banking regulation.",
     "locator": "Educate employees on cyber hygiene basics, first bullet, PDF/printed page 2; joint authorship page 1",
     "pdf_page": 2, "check": "always lock your device", "render_pages": [1, 2]},
    {"id": "pci_ssc_faq_1147", "title": "PCI SSC — FAQ 1147: Purpose of PCI DSS Requirement 8.2.8",
     "url": "https://www.pcisecuritystandards.org/faqs/1147/", "format": "html",
     "version": "November 2025 on official FAQ",
     "source_type": "payment_industry_standard_official_explanation", "jurisdiction": "International payment card industry",
     "scope": "PCI DSS scoped systems. Exception for POS accounts accessing only one card number at a time for one transaction. Scope of the X-28 device is unknown.",
     "locator": "FAQ 1147, requirement 8.2.8 and applicability note",
     "check": "15 minutes", "render_pages": []},
    {"id": "cnil_workstation_security_2024", "title": "CNIL — Sécurité : Sécuriser les postes de travail",
     "url": "https://www.cnil.fr/fr/securite-securiser-les-postes-de-travail", "format": "html",
     "version": "14 March 2024 on official page",
     "source_type": "data_protection_authority_guidance", "jurisdiction": "France / European Union",
     "scope": "Guidance for securing workstations processing personal data; does not establish a universal immediate-lock rule or a Kazakhstan employee duty.",
     "locator": "Les précautions élémentaires, first bullet",
     "check": "verrouillage automatique", "render_pages": []},
    {"id": "bank_of_england_our_code_2026", "title": "Bank of England — Our Code, January 2026 (version context)",
     "url": "https://www.bankofengland.co.uk/about/governance-and-funding/staff-codes-and-policies/our-code", "format": "html",
     "version": "January 2026; page last updated 30 January 2026",
     "source_type": "version_context", "jurisdiction": "United Kingdom",
     "scope": "Current public overview; staff duties and reference to separate Security conduct policy. Does not reproduce the 2024 immediate-lock sentence.",
     "locator": "3: Demonstrating openness and accountability / Security conduct",
     "check": "Security conduct", "render_pages": []},
]
HOSTS = {urlsplit(s["url"]).hostname for s in SOURCES} | {"bankofengland.co.uk", "www.bankofengland.co.uk"}


def save(name, data):
    (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch():
    receipts_file = ROOT / "download_receipts.json"
    receipts = json.loads(receipts_file.read_text(encoding="utf-8")) if receipts_file.exists() else {}
    save("source_catalog.json", SOURCES)
    save("earlier_candidates.json", {"selection_note": "User requested United States, Europe and international sources. Bangladesh, India and Russia are excluded from the principal evidence set; earlier files and receipts are retained for provenance.", "candidates": [s for s in EARLIER_CANDIDATES if not s["id"].startswith("nist_")]})
    for source in SOURCES:
        sid = source["id"]
        if source.get("web_review_only"):
            continue
        kind = source.get("format", "pdf")
        target = ROOT / (sid + "." + kind)
        if target.exists() and receipts.get(sid, {}).get("status") == "downloaded":
            continue
        record = {"url": source["url"], "retrieved_at_utc": datetime.now(timezone.utc).isoformat()}
        try:
            with urlopen(Request(source["url"], headers={"User-Agent": "Mozilla/5.0"}), timeout=40) as response:
                if urlsplit(response.url).hostname not in HOSTS:
                    raise ValueError("Unexpected redirect host")
                raw = response.read(40_000_001)
                record.update(final_url=response.url, content_type=response.headers.get("Content-Type"))
            if len(raw) > 40_000_000:
                raise ValueError("Response is too large")
            if kind == "pdf" and not raw.startswith(b"%PDF-"):
                raise ValueError("Response is not a PDF")
            if kind == "html" and "text/html" not in (record.get("content_type") or ""):
                raise ValueError("Response is not HTML")
            target.write_bytes(raw)
            record.update(status="downloaded", bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        except Exception as exc:
            record.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        if sid in receipts:
            record["previous_attempts"] = receipts[sid].get("previous_attempts", []) + [{k: v for k, v in receipts[sid].items() if k != "previous_attempts"}]
        receipts[sid] = record
        save("download_receipts.json", receipts)
        print(json.dumps({"id": sid, **record}, ensure_ascii=False), flush=True)


def parse():
    from pypdf import PdfReader
    import pypdfium2 as pdfium
    manifest, errors = [], []
    receipts = json.loads((ROOT / "download_receipts.json").read_text(encoding="utf-8"))
    renders = ROOT / "verified_pages"
    renders.mkdir(exist_ok=True)
    for source in SOURCES:
        sid = source["id"]
        if source.get("web_review_only"):
            review_path = ROOT / source["web_review_path"]
            review = json.loads(review_path.read_text(encoding="utf-8"))
            if source["check"] not in review["short_excerpt"] or review["source_url"] != source["url"]:
                errors.append({"id": sid, "error": "Web review reference mismatch"})
            manifest.append({**source, "format": "web_review", "page_count": 0,
                             "source_document_pages": 60, "parsed_path": review_path.name,
                             "original_pdf_downloaded": False,
                             "direct_forte_employee_obligation": False})
            print(json.dumps({"id": sid, "format": "web_review", "original_pdf_downloaded": False}), flush=True)
            continue
        kind = source.get("format", "pdf")
        path = ROOT / (sid + "." + kind)
        if not path.exists():
            errors.append({"id": sid, "error": "Source file was not downloaded"})
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != receipts[sid]["sha256"]:
            errors.append({"id": sid, "error": "Receipt hash mismatch"})
            continue
        if kind == "html":
            from html.parser import HTMLParser
            class TextParser(HTMLParser):
                def __init__(self):
                    super().__init__(); self.parts = []; self.skip = 0
                def handle_starttag(self, tag, attrs):
                    if tag in {"script", "style"}: self.skip += 1
                def handle_endtag(self, tag):
                    if tag in {"script", "style"}: self.skip = max(0, self.skip - 1)
                def handle_data(self, data):
                    if not self.skip and data.strip(): self.parts.append(data.strip())
            parser = TextParser(); parser.feed(path.read_text(encoding="utf-8", errors="replace"))
            content = "\n".join(parser.parts)
            if source["check"] not in content:
                errors.append({"id": sid, "error": "HTML key phrase missing"})
            meta = {**source, "sha256": digest, "page_count": 0, "bytes": path.stat().st_size,
                    "retrieved_at_utc": receipts[sid]["retrieved_at_utc"], "source_path": path.name,
                    "parsed_path": sid + ".json", "direct_forte_employee_obligation": False}
            save(sid + ".json", {"metadata": meta, "text": content})
            manifest.append(meta)
            print(json.dumps({"id": sid, "format": "html", "key_phrase_found": source["check"] in content}), flush=True)
            continue
        reader = PdfReader(path)
        pages = [{"page": i + 1, "text": p.extract_text() or ""} for i, p in enumerate(reader.pages)]
        matches = [p["page"] for p in pages if source["check"] in " ".join(p["text"].split())]
        key_page = source.get("pdf_page") or (matches[0] if matches else 1)
        key_text = " ".join(pages[key_page - 1]["text"].split())
        if source["check"] not in key_text:
            errors.append({"id": sid, "error": "Key phrase not found on expected page"})
        meta = {**source, "pdf_page": key_page, "matching_pages": matches, "sha256": digest, "page_count": len(pages), "bytes": path.stat().st_size,
                "retrieved_at_utc": receipts[sid]["retrieved_at_utc"],
                "parsed_at_utc": datetime.now(timezone.utc).isoformat(),
                "pdf_path": path.name, "parsed_path": sid + ".json",
                "direct_forte_employee_obligation": False,
                "pages_without_extracted_text": [p["page"] for p in pages if not p["text"].strip()],
                "extraction_note": "pypdf text from every page; not a full OCR transcription. Key pages rendered separately."}
        save(sid + ".json", {"metadata": meta, "pages": pages})
        manifest.append(meta)
        pdf = pdfium.PdfDocument(path)
        for page in sorted(set(source["render_pages"] + [key_page])):
            pdf[page - 1].render(scale=1.3).to_pil().save(renders / f"{sid}_p{page}.png")
        print(json.dumps({"id": sid, "pages": len(pages), "key_page": key_page, "key_phrase_found": source["check"] in key_text}, ensure_ascii=False), flush=True)
    save("source_catalog.json", SOURCES)
    save("source_manifest.json", manifest)
    save("validation.json", {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
                             "documents": len(manifest), "pages": sum(s["page_count"] for s in manifest),
                             "downloaded_originals": sum(s.get("format") != "web_review" for s in manifest),
                             "web_review_only": sum(s.get("format") == "web_review" for s in manifest),
                             "passed": not errors and len(manifest) == len(SOURCES), "errors": errors})
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["fetch", "parse"])
    args = parser.parse_args()
    fetch() if args.mode == "fetch" else parse()

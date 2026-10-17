"""Reproducible, resumable collection of public ForteBank documents.

Build the catalog locally, fetch only its allowlisted URLs, then extract all PDF
pages. Download/extraction is not a finding of legal applicability.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
ALLOWED_HOSTS = {'prod-one-strapi.s3.eu-north-1.amazonaws.com',
                 'main.storage-object.pscloud.io', 'kase.kz', 'old.kase.kz'}
BASELINE = ['forte_online_procedure_2025', 'forte_ethics_2024',
            'forte_general_operations_2026', 'forte_remote_terms', 'forte_ebu_rules']

# Link matches are resolved from saved official indexes, never invented paths.
SELECTIONS = [
    ('forte_business_manual', 'business_documents', 'Rukovodstvo_polzovatelya_Sistemy', 'client_manual'),
    ('forte_insider_access', 'forte_documents', 'Pravila_vnutr_kontrolya', 'bank_policy_special_scope'),
    ('forte_governance_2025', 'forte_documents', 'Kodeks_korporativnogo_upravleniya', 'corporate_governance'),
    ('forte_personal_data_inventory', 'forte_documents', 'Perechen_personalnyh', 'personal_data_scope'),
    ('forte_payment_acceptance_contract', 'forte_documents', 'Dogovor_ob_okazanii_uslug_po_priemu', 'client_contract'),
    ('forte_personal_data_consent_2026', 'forte_documents', 'Soglasie_na_sbor_i_obrabotku', 'client_consent'),
    ('forte_web_user_agreement', 'forte_documents', 'Polzovatelskoe_soglashenie_dlya_internet', 'client_contract'),
    ('forte_anticorruption', 'forte_documents', 'Politika_po_protivodejstviyu', 'bank_employee_policy'),
    ('forte_business_accounts_2026', 'business_documents', 'Obshhie_usloviya_po_schetam', 'client_contract'),
    ('forte_account_docs_legal', 'business_documents', 'Perechen_dokumentov_dlya_otkrytiya_bankovskogo_scheta_Yu_L', 'client_procedure'),
    ('forte_account_docs_llp', 'business_documents', 'Perechen_dokumentov_dlya_otkrytiya_bankovskogo_scheta_TOO', 'client_procedure'),
    ('forte_account_docs_entrepreneur', 'business_documents', 'Perechen_dokumentov_dlya_otkrytiya_bankovskogo_scheta_IP', 'client_procedure'),
    ('forte_business_card_contract', 'business_documents', 'Dogovor_o_vydache_i_obsluzhivanii_korporativnyh', 'client_contract'),
    ('forte_registration_rules', 'business_documents', 'Pravila_registraczii_84', 'client_procedure'),
    ('forte_business_registration_rules', 'business_documents', 'Pravila_registraczii_dlya_Forte', 'client_procedure'),
    ('forte_otp_manual', 'business_documents', 'Forte_OTP_v3', 'client_manual'),
    ('forte_ca_regulation', 'certification', 'Reglament_deyatelnosti', 'certification_participants'),
    ('forte_ca_certificate_policy', 'certification', 'Politika_primeneniya', 'certification_participants'),
    ('forte_antifraud_response', 'business_service', 'Kak_dejstvovat', 'client_guidance'),
    ('forte_online_safety', 'business_service', 'Zashhitite_sebya', 'client_guidance'),
    ('forte_antifraud_memo', 'business_service', 'Pamyatka_dlya_klienta', 'client_guidance'),
    ('forte_cash_tariff_limits_2025', 'forte_documents', '03_Prilozhenie_3_Predelnye', 'tariff_annex'),
]


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def catalog():
    docs = []
    for ident in BASELINE:
        old = read_json(ROOT / (ident + '.json'))['metadata']
        doc = {k: old[k] for k in ['id', 'title', 'url', 'landing_url']}
        doc['source_role'] = ('bank_employee_policy' if ident == 'forte_ethics_2024'
                              else 'bank_general_operations' if ident == 'forte_general_operations_2026'
                              else 'client_contract')
        docs.append(doc)
    for ident, index, needle, role in SELECTIONS:
        source = read_json(ROOT / 'discovery' / (index + '.links.json'))
        matches = {r['url']: r for r in source['links'] if needle in r['url']}
        if len(matches) != 1:
            raise ValueError(f'{ident}: expected one official link, found {len(matches)}')
        row = next(iter(matches.values()))
        docs.append({'id': ident, 'title': row['text'].replace(' (PDF)', ''),
                     'url': row['url'], 'landing_url': source['url'],
                     'discovery_snapshot': 'discovery/' + index + '.html',
                     'source_role': role})
    # This annual report is embedded in the official site's serialized page data.
    html = (ROOT / 'discovery/reporting.html').read_text(encoding='utf-8')
    urls = set(re.findall(r'https[^\s"<>]+?\.pdf', html))
    annual = [u for u in urls if 'Forte_Bank_AR_2023_rus' in u]
    if len(annual) != 1:
        raise ValueError('Cannot resolve annual report from the official reporting page')
    docs.append({'id': 'forte_annual_report_2023', 'title': 'Годовой отчет ForteBank за 2023 год',
                 'url': annual[0], 'landing_url': 'https://forte.kz/ru/reporting',
                 'discovery_snapshot': 'discovery/reporting.html', 'source_role': 'annual_report'})
    docs.extend([
        {'id': 'forte_annual_report_2024', 'title': 'Годовой отчет ForteBank за 2024 год',
         'url': 'https://kase.kz/files/emitters/ASBN/asbnp_2024_rus.pdf.pdf',
         'landing_url': 'https://kase.kz/ru/issuers/ASBN',
         'discovery_method': 'Issuer disclosure PDF indexed on the official Kazakhstan Stock Exchange',
         'source_role': 'annual_report'},
        {'id': 'forte_online_procedure_2024', 'title': 'Процедура ЭБУ на Онлайн-платформе, редакция 11.10.2024',
         'url': 'https://main.storage-object.pscloud.io/Proczedura_predostavleniya_EBU_na_Onlajn_platforme_111024_3e3be56ce8.pdf',
         'landing_url': 'https://business.forte.kz/ru/documents',
         'discovery_method': 'Search-indexed prior edition on the bank document storage; not asserted to be the current link',
         'source_role': 'historical_client_contract'},
        {'id': 'forte_business_ebu_rules', 'title': 'Правила ЭБУ посредством систем ForteBusiness',
         'url': 'https://main.storage-object.pscloud.io/Pravila_predostavleniya_EBU_posredstvom_sistem_Forte_Business_1706_s_pechatyu_bbfb1fe7ee.pdf',
         'landing_url': 'https://business.forte.kz/ru/documents',
         'discovery_method': 'Search-indexed document on the bank document storage; current status requires version review',
         'source_role': 'client_contract_version_review'},
    ])
    for doc in docs:
        doc['present_before_expansion'] = doc['id'] in BASELINE
        doc['legal_force_note'] = 'Публичный документ банка или отчетность, не государственный нормативный правовой акт; применимость проверяется отдельно.'
        doc['video_date_known'] = False
    assert len({d['id'] for d in docs}) == len(docs)
    write_json(ROOT / 'source_catalog.json', docs)
    print(json.dumps({'selected': len(docs), 'previously_downloaded': len(BASELINE),
                      'additional_candidates': len(docs) - len(BASELINE)}))


def fetch():
    docs = read_json(ROOT / 'source_catalog.json')
    receipt_path = ROOT / 'download_receipts.json'
    receipts = read_json(receipt_path) if receipt_path.exists() else {}
    for doc in docs:
        ident, url = doc['id'], doc['url']
        if urlsplit(url).hostname not in ALLOWED_HOSTS:
            raise ValueError('Host outside explicit document allowlist: ' + url)
        destination = ROOT / (ident + '.pdf')
        if destination.exists():
            if ident not in receipts:
                oldpath = ROOT / (ident + '.json')
                old = read_json(oldpath).get('metadata', {}) if oldpath.exists() else {}
                receipts[ident] = {'retrieved_at_utc': old.get('retrieved_at_utc'),
                                  'origin': 'previously_saved_file', 'url': url}
            write_json(receipt_path, receipts)
            continue
        try:
            request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(request, timeout=55) as response:
                final_url = response.url
                if urlsplit(final_url).hostname not in ALLOWED_HOSTS:
                    raise ValueError('Unexpected redirect destination')
                data = response.read()
                content_type = response.headers.get('Content-Type')
            if not data.startswith(b'%PDF-'):
                raise ValueError('Response is not a PDF')
            destination.write_bytes(data)
            receipts[ident] = {'retrieved_at_utc': utcnow(), 'url': url,
                              'final_url': final_url, 'content_type': content_type,
                              'origin': 'downloaded_in_expansion', 'bytes': len(data),
                              'sha256': hashlib.sha256(data).hexdigest()}
            print(json.dumps({'id': ident, 'bytes': len(data), 'status': 'downloaded'}), flush=True)
        except Exception as exc:
            receipts[ident] = {'url': url, 'attempted_at_utc': utcnow(), 'error': str(exc)}
            print(json.dumps({'id': ident, 'error': str(exc)}, ensure_ascii=True), flush=True)
        write_json(receipt_path, receipts)


def parse():
    from pypdf import PdfReader
    docs = read_json(ROOT / 'source_catalog.json')
    receipts = read_json(ROOT / 'download_receipts.json')
    entries, failures = [], []
    hashes = {}
    for doc in docs:
        ident = doc['id']
        path = ROOT / (ident + '.pdf')
        if not path.exists():
            failures.append({'id': ident, 'error': 'PDF not downloaded'})
            continue
        try:
            data = path.read_bytes()
            reader = PdfReader(path)
            pages = [{'page': i + 1, 'text': p.extract_text() or ''}
                     for i, p in enumerate(reader.pages)]
            digest = hashlib.sha256(data).hexdigest()
            meta = dict(doc, sha256=digest, bytes=len(data), page_count=len(pages),
                        retrieved_at_utc=receipts.get(ident, {}).get('retrieved_at_utc'),
                        parsed_at_utc=utcnow(), characters=sum(len(p['text']) for p in pages),
                        pages_without_text=[p['page'] for p in pages if not p['text'].strip()],
                        pages_below_80_characters=[p['page'] for p in pages if len(p['text'].strip()) < 80],
                        extraction_method='pypdf; every PDF page visited; image-only content may require OCR',
                        full_legal_applicability_confirmed=False,
                        duplicate_of=hashes.get(digest),
                        pdf_path=ident + '.pdf', parsed_path=ident + '.json')
            hashes.setdefault(digest, ident)
            write_json(ROOT / (ident + '.json'), {'metadata': meta, 'pages': pages})
            entries.append(meta)
            print(json.dumps({'id': ident, 'pages': len(pages), 'characters': meta['characters'],
                              'empty_pages': meta['pages_without_text']}, ensure_ascii=True), flush=True)
        except Exception as exc:
            failures.append({'id': ident, 'error': str(exc)})
    write_json(ROOT / 'source_manifest.json', entries)
    write_json(ROOT / 'extraction_validation.json', {
        'checked_at_utc': utcnow(), 'catalog_count': len(docs), 'parsed_count': len(entries),
        'unique_pdf_hashes': len(hashes), 'failures': failures,
        'total_pdf_pages_visited': sum(e['page_count'] for e in entries),
        'all_selected_pdfs_parsed': len(entries) == len(docs),
        'all_image_content_transcribed': False,
        'new_video_review_performed': False,
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['catalog', 'fetch', 'parse'])
    args = parser.parse_args()
    globals()[args.command]()

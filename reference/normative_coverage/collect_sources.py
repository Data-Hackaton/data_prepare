"""Retrieve public official sources for the separate coverage review."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / 'sources'
DOCS = [
    ('V1900019680', 'НБРК №231', 'кассовые операции и инкассация', 'core'),
    ('V2000020075', 'НБРК №14', 'охрана и устройство кассовых помещений', 'core'),
    ('V1700016120', 'НБРК №230', 'платежность банкнот и монет тенге', 'core'),
    ('V1900018545', 'НБРК №49', 'обмен наличной иностранной валюты', 'conditional_operation'),
    ('V2400034348', 'АРРФР №21', 'антитеррористическая защита уязвимых РКО', 'conditional_object'),
    ('V2600038336', 'АРРФР №53', 'информационная безопасность банков', 'core'),
    ('V2200026867', 'МЧС №55 от 21.02.2022', 'пожарная безопасность и электрооборудование', 'additional'),
    ('Z2600000258', 'Закон о банках №258-VIII', 'банковская тайна и применимость банковских требований', 'supporting'),
    ('Z1300000094', 'Закон о персональных данных №94-V', 'конфиденциальность и защита данных клиентов', 'supporting'),
    ('V2300032810', 'Правила мер защиты персональных данных', 'допуск к сведениям и защита носителей', 'additional'),
    ('P1600000832', 'Постановление Правительства №832', 'единые требования ИКТ/ИБ; только при доказанной применимости', 'conditional_object'),
    ('Z1300000073', 'Закон о документах, удостоверяющих личность №73-V', 'оригиналы удостоверений и допустимые способы обращения с ними', 'supporting'),
    ('K1500000414', 'Трудовой кодекс №414-V', 'обязанности сторон, трудовой распорядок и безопасность рабочего места', 'supporting'),
    ('V1500012534', 'МЗСР №927 от 30.11.2015', 'разработка инструкций по безопасности и охране труда работодателем', 'supporting'),
    ('V1500012665', 'МЗСР №1019 от 25.12.2015', 'обучение, инструктажи и проверка знаний по охране труда', 'supporting'),
    ('V1500010889', 'Минэнерго №222 от 19.03.2015', 'техника безопасности при эксплуатации электроустановок потребителей', 'conditional_operation'),
    ('V1500010949', 'Минэнерго №246 от 30.03.2015', 'техническая эксплуатация электроустановок потребителей', 'conditional_operation'),
]

def fetch(item):
    doc_id, short, purpose, role = item
    url = f'https://adilet.zan.kz/api/documents/by-ngr/{doc_id}?language=rus'
    target = SOURCES / (doc_id + '.api.json')
    if target.exists():
        raw = target.read_bytes()
    else:
        request = Request(url, headers={'User-Agent':'Mozilla/5.0', 'Accept':'application/json'})
        with urlopen(request, timeout=35) as response:
            raw = response.read(20_000_001)
        if len(raw) > 20_000_000:
            raise ValueError('response exceeds 20 MB')
    payload = json.loads(raw)
    doc = payload.get('document', payload)
    if doc.get('group_number') != doc_id or doc.get('language') != 'rus':
        raise ValueError('source identity/language mismatch')
    content = doc.get('text_content')
    if not isinstance(content, str) or '<article' not in content or '</article>' not in content:
        raise ValueError('complete HTML article unavailable')
    if not target.exists():
        target.write_bytes(raw)
    (SOURCES/(doc_id+'.html')).write_bytes(content.encode('utf-8'))
    return {
        'id':doc_id, 'short_name':short, 'purpose':purpose, 'role':role,
        'title':doc.get('title_ru'), 'official_name':doc.get('official_name'),
        'page_url':f'https://adilet.zan.kz/rus/docs/{doc_id}', 'api_url':url,
        'uuid':doc.get('id'), 'source_status':doc.get('status'),
        'is_actual':doc.get('is_actual'), 'source_dates_raw':{
            k:doc.get(k) for k in ('start_date','end_date','updated_at','adoption_date')},
        'downloaded_at_utc':datetime.fromtimestamp(target.stat().st_mtime,timezone.utc).isoformat(),
        'response_sha256':hashlib.sha256(raw).hexdigest(),
        'html_sha256':hashlib.sha256(content.encode('utf-8')).hexdigest(),
        'html_characters':len(content), 'status':'downloaded',
    }

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    SOURCES.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch, item):item for item in DOCS}
        for future in as_completed(futures):
            item = futures[future]
            try:
                row = future.result()
            except Exception as error:
                row = {'id':item[0], 'short_name':item[1], 'status':'failed',
                       'error':f'{type(error).__name__}: {error}'}
            results.append(row)
            print(json.dumps({k:row.get(k) for k in ('id','short_name','status','source_status','is_actual','html_characters','error')},ensure_ascii=False),flush=True)
    order = {item[0]:i for i,item in enumerate(DOCS)}
    results.sort(key=lambda row:order[row['id']])
    (ROOT/'source_manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    if any(row['status'] != 'downloaded' for row in results):
        raise SystemExit(1)

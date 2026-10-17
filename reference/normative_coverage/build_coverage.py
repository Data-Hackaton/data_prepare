"""Build an evidence-linked rulebook and a non-destructive scenario coverage audit.

Video observations are inherited preliminary descriptions, not newly reviewed
frames and not authoritative legal labels. All normative quotations below come
from the saved official HTML response, not from the observations.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import ast
import argparse
import csv
import hashlib
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--private-input-root', type=Path, help='Local directory containing dataset_manifest.json and review_observations.py; never committed')
args = parser.parse_args()
PRIVATE_ROOT = args.private_input_root
if PRIVATE_ROOT is not None:
    assert all((PRIVATE_ROOT/name).is_file() for name in ('dataset_manifest.json', 'review_observations.py')), 'Incomplete private inputs'
SAVED_AUDIT = json.loads((ROOT/'coverage_summary.json').read_text(encoding='utf-8'))
SOURCES = json.loads((ROOT/'source_manifest.json').read_text(encoding='utf-8'))
DOCS = {m['id']:json.loads((ROOT/'parsed'/(m['id']+'.json')).read_text(encoding='utf-8')) for m in SOURCES}
STATUS = {'upd':'Обновленный','new':'Новый','yts':'Утративший силу','err':'Исправление ошибки'}
BANK_ROOT = ROOT / 'forte_public'
BANK_SOURCES = json.loads((BANK_ROOT/'source_manifest.json').read_text(encoding='utf-8')) if (BANK_ROOT/'source_manifest.json').exists() else []
BANK_FINDINGS = json.loads((BANK_ROOT/'findings.json').read_text(encoding='utf-8')) if (BANK_ROOT/'findings.json').exists() else []
LABOR_ROOT = ROOT / 'labor_safety'
LABOR_RULES = json.loads((LABOR_ROOT/'rules.json').read_text(encoding='utf-8'))
LABOR_SOURCE_IDS = ['K1500000414', 'V1500012534', 'V1500012665', 'V1500010889', 'V1500010949']

def primary_units(ident):
    d=DOCS[ident]
    if ident.startswith(('Z','K')):
        return d['units']
    first=next(b['order'] for b in d['blocks'] if b['kind']=='heading' and re.search(r'(?:(?:Глава|Раздел)\s+1\.|\b1\.\s+Общие\s+положения)',b['text'],re.I))
    last=next((b['order'] for b in d['blocks'] if b['order']>first and b['kind']=='table' and b['text'].startswith('Приложение')),10**9)
    return [u for u in d['units'] if first<u['start_block']<last]

def ref(spec):
    ident, locator = spec.split(':',1)
    locator, _, subpoint = locator.partition('/')
    if '.' in locator:
        article, point=locator.split('.',1)
        matches=[u for u in DOCS[ident]['units'] if u['article_number']==article and u['point']==point]
        label=f'статья {article}, пункт {point}'
    else:
        point=locator
        matches=[u for u in primary_units(ident) if u['point']==point]
        label=f'пункт {point}'
    assert len(matches)==1,(spec,[u['id'] for u in matches])
    u=matches[0]
    reference_text, reference_url, reference_id, reference_anchor = u['text'],u['url'],u['id'],u['anchor']
    if subpoint:
        blocks=[b for b in DOCS[ident]['blocks'] if u['start_block']<=b['order']<=u['end_block']]
        selected=[(i,b) for i,b in enumerate(blocks) if b['kind']=='subpoint' and b['subpoint']==subpoint]
        assert len(selected)==1,(spec,'subpoint is not unique')
        start,b=selected[0]
        end=next((i for i in range(start+1,len(blocks)) if blocks[i]['kind'] in ('subpoint','note','heading')),len(blocks))
        reference_text='\n'.join(x['text'] for x in blocks[start:end])
        reference_id=b['id']
        # Many official HTML subpoints have no id. Link to their parent point
        # while retaining the exact subpoint text and internal block identifier.
        reference_anchor=b['anchor'] or u['anchor']
        reference_url=b['url'] if b['anchor'] else u['url']
        label+=f', подпункт {subpoint})'
    meta=DOCS[ident]['metadata']
    anchor_count=sum(b.get('anchors',[]).count(reference_anchor) for b in DOCS[ident]['blocks']) if reference_anchor else 0
    return {'spec':spec,'document_id':ident,'document':meta['short_name'],
            'locator':label,'unit_id':reference_id,'parent_unit_id':u['id'],'heading':u['heading'],'url':reference_url,
            'text':reference_text,'source_sha256':DOCS[ident]['source_sha256'],
            'anchor_occurrences_in_source':anchor_count,
            'anchor_note':'При повторяющемся HTML-якоре ориентироваться также на номер пункта и приведенный текст.' if anchor_count>1 else None}

rules=[]
def add(key,title,domain,specs,condition,limit,strength='direct_conditional'):
    rules.append({'id':key,'title':title,'domain':domain,'source_strength':strength,
                  'required_observation':condition,'limits_and_exceptions':limit,
                  'references':[ref(s) for s in specs]})

# Preserve the reviewed 22-topic catalogue as a starting point, with fresh
# official quotations and explicit evidence constraints.
base=json.loads((PARENT/'rule_catalog.json').read_text(encoding='utf-8'))
for item in base:
    specs=list(dict.fromkeys(f"{r['document_id']}:{r['point']}" for r in item['rules']))
    domain='Помещения и допуск' if any(s.startswith('V2000020075') for s in specs) else 'Инкассация' if item['id'].startswith('collector') or 'сумк' in item['title'].lower() or 'инкассац' in item['title'].lower() else 'Кассовая операция'
    add(item['id'],item['title'],domain,specs,
        'Наблюдается действие или вся обязательная процедура, указанные в точном пункте; подтверждены роль участника и стадия операции.',item['limits'])

add('cash_handover_record','Передача наличных между кассовыми работниками','Кассовая операция',
    ['V1900019680:15'],'Видна передача наличных между установленными кассовыми работниками и доступен документ учета.',
    'Сам по себе отсутствующий в кадре бумажный журнал не доказывает отсутствие регистрации. Суммы, подписи и время должны быть читаемы.')
add('day_end_cash','Пересчет, сортировка, упаковка и сдача остатка в конце дня','Кассовая операция',
    ['V1900019680:23','V1900019680:37','V1900019680:64','V1900019680:66','V1900019680:67'],
    'Подтверждено завершение рабочего дня; виден остаток наличности и процедура сдачи.',
    'Уход на несколько секунд не доказывает конец дня. Проводки и итоговую сверку без банковских систем не оценивать.')
add('counterfeit_return','Возврат клиенту банкнот с установленными признаками подделки','Состояние и сортировка денег',
    ['V1900019680:60','V1900019680:61','V1700016120:24'],
    'Видна передача обратно именно банкнот с подтвержденными признаками подделки.',
    'Цвет банкноты, возврат денег или прохождение через счетчик не доказывают подделку. Нужны читаемый результат проверки либо подтвержденный сценарий.')
add('suspect_expertise','Оформление приема сомнительных банкнот на экспертизу','Состояние и сортировка денег',
    ['V1900019680:59','V1700016120:29','V1700016120:30'],
    'Подтверждена категория сомнительных банкнот; показана вся процедура с клиентом и заведующим кассой.',
    'Не смешивать сомнительные, неплатежные и имеющие признаки подделки банкноты. Срок направления на экспертизу не проверяется коротким видео.')
add('dyed_notes','Обработка банкнот, окрашенных краской спецконтейнера','Состояние и сортировка денег',
    ['V1900019680:63-4','V1900019680:63-5'],
    'Установлено окрашивание специальной краской, видна стадия приема или подготовки к экспертизе.',
    'Любое пятно не равно срабатыванию спецконтейнера; для соответствующей стадии проверяются акт, просушка, полистный пересчет и специальная упаковка.')
add('cash_sorting','Сортировка по номиналам и состоянию','Состояние и сортировка денег',
    ['V1900019680:43','V1900019680:45','V1900019680:50','V1900019680:77'],
    'Читаются номиналы или подтверждено состояние банкнот; видна завершенная сортировка, упаковка либо хранение.',
    'Временная общая стопка во время пересчета допустима. Пункт 50 прямо предусматривает сборные пачки с разными номиналами при требуемом оформлении; различие цвета не доказывает различие номиналов.')
add('unfit_recirculation','Возврат ветхих тенге в обращение','Состояние и сортировка денег',
    ['V1700016120:10','V1700016120:11','V1700016120:12','V1900019680:45'],
    'Различимо повреждение, соответствующее критерию Правил, и видна выдача таких денег в обращение.',
    'Не определять платежность по общему ракурсу. Прием ветхой платежной банкноты от клиента сам по себе правомерен.')
add('worn_acceptance','Отказ принимать платежные ветхие тенге','Состояние и сортировка денег',
    ['V1700016120:4','V1700016120:15','V1700016120:25','V1700016120:28','V1700016120:30'],
    'Установлены платежность банкноты и причина отказа именно из-за ветхости.',
    'Без звука и читаемых документов причину возврата часто установить нельзя; неплатежные и сомнительные деньги имеют другой порядок обработки.')
add('bundle_formation','Формирование корешков и пачек банкнот','Состояние и сортировка денег',
    ['V1900019680:46','V1900019680:47','V1900019680:48','V1900019680:49','V1900019680:50'],
    'Показана окончательная упаковка, доступны количество, номинал, бандероль, накладки и пломба либо вакуумный шов.',
    'Разрешены неполные и сборные пачки и разные способы упаковки. Не применять требования к готовой пачке к неупакованной промежуточной стопке.')
add('coin_packaging','Упаковка монет и маркировка мешков','Состояние и сортировка денег',
    ['V1900019680:51','V1900019680:52','V1900019680:53'],
    'Видна завершенная упаковка монет с идентифицируемым видом тары и читаемой маркировкой.',
    'Существуют мешки, пакеты и тюбики; требования различаются. Сумму или число монет по внешнему виду мешка не выводить.')
add('outgoing_packaging','Выдача наличных в надлежащей упаковке','Кассовая операция',
    ['V1900019680:32','V1900019680:33'],
    'Видна выдача пачки клиенту и происхождение ее упаковки.',
    'Учитывать разрешенную упаковку Национального Банка и исключения самого пункта; отсутствие полистного пересчета целой пачки не равно нарушению.')
add('client_recount','Возможность пересчета полученных денег клиентом','Кассовая операция',
    ['V1900019680:35'],'Наблюдается пересчет клиентом у кассы либо в выделенном помещении.',
    'Пункт описывает порядок пересчета; нельзя превращать добровольный отказ клиента от пересчета в автоматически установленное нарушение кассира.')
add('damaged_bag_recount','Вскрытие и пересчет поврежденной инкассаторской сумки','Инкассация',
    ['V1900019680:24','V1900019680:25','V1900019680:41','V1900019680:42'],
    'Нарушение целостности сумки установлено до вскрытия; видны пересчет и присутствие передающего инкассатора.',
    'Пункт 25 прямо относится к поврежденной сумке. Из него нельзя вывести обязанность немедленно вскрыть каждую целую сумку при приеме.')
add('received_bag_recount','Пересчет содержимого вскрытой сумки','Инкассация',
    ['V1900019680:24','V1900019680:25','V1900019680:41','V1900019680:42'],
    'Показан весь рабочий эпизод от вскрытия до окончания обработки; установлено, что пересчет должен выполняться на этой стадии.',
    'Редкие кадры не доказывают пропуск действия. Для целой сумки публичные пункты не устанавливают универсальный срок немедленного пересчета.', 'conditional_general')
add('collection_document_flow','Препроводительные документы при приеме и выдаче инкассации','Инкассация',
    ['V1900019680:24','V1900019680:38','V1900019680:105','V1900019680:106','V1900019680:107'],
    'Подтверждена инкассация и виден весь обмен документами, включая карман сумки.',
    'Документ может быть прикреплен к сумке или цифровым. Переданная карточка не обязательно является удостоверением или препроводительным документом.')
add('collector_documents','Документы и полномочия инкассаторской бригады','Инкассация',
    ['V1900019680:101','V1900019680:111'],
    'Известна роль участника и стадия выдачи документов перед выездом либо перевозки.',
    'Пункт 101 регулирует выдачу документов бригаде. Он сам по себе не устанавливает показ удостоверения кассиру при каждой передаче сумки.', 'conditional_general')
add('collection_documents_storage','Хранение документов инкассации после маршрута','Инкассация',
    ['V1900019680:122','V1900019680:123'],
    'Подтверждено окончание соответствующего маршрута и место хранения инкассированных ценностей.',
    'Для нескольких маршрутов доверенность и служебное удостоверение размещаются после последнего маршрута; обычную рабочую книгу не считать явочной карточкой.')
add('cash_storage','Хранение учтенных наличных в кладовой или сейфовой комнате','Хранение',
    ['V1900019680:74','V1900019680:75','V1900019680:77','V1900019680:80'],
    'Подтверждены содержимое, стадия хранения и тип помещения или устройства.',
    'Требования к сейфовой комнате нельзя автоматически переносить на каждое открытие небольшого рабочего сейфа.')
add('unattended_cash','Наличные или сумка с деньгами оставлены при уходе','Хранение',
    ['V1900019680:20','V1900019680:22','V1900019680:74','V1900019680:80'],
    'Виден уход и доказано наличие принятых наличных либо незавершенное обслуживание клиента.',
    'Пустая инкассаторская сумка не является деньгами. Пункт 22 применяется только до окончания обслуживания клиента.')
add('open_safe','Открытый рабочий сейф','Хранение',
    ['V1900019680:20','V1900019680:80'],
    'В сейфе хранятся ранее принятые деньги, видны отсутствие контроля и возможность несанкционированного доступа.',
    'Краткое открытие во время операции само по себе не запрещено. Прямое универсальное требование закрывать дверь после каждого действия в этих пунктах не сформулировано.', 'conditional_general')
add('keys_stamps','Ключи, печати и штампы оставлены доступными','Хранение',
    ['V1900019680:76','V1900019680:80'],
    'Различим служебный ключ, печать или штамп, установлен тип замка и показана возможность постороннего использования.',
    'Пункт 80 требует внутреннего порядка, исключающего несанкционированное использование; он не предписывает единственное место хранения. Пункт 76 относится к двери кладовой/сейфовой комнаты.', 'conditional_general')
add('service_overlap','Параллельное обслуживание клиентов и риск смешения операций','Кассовая операция',
    ['V1900019680:20','V1900019680:21','V1900019680:22'],
    'Показана работа с деньгами нескольких операций или уход до окончания текущего обслуживания.',
    'Нахождение двух людей у окна либо прием документа второго клиента само по себе не запрещены названными пунктами. Отдельный запрет любой параллельной консультации не подтвержден.', 'conditional_general')
add('atm_cash','Наличные для устройств с автоматической обработкой','Кассовая операция',
    ['V1900019680:55','V1900019680:69','V1900019680:71','V1900019680:72'],
    'Подтверждено, что наличность готовят или загружают в автоматическое устройство.',
    'Не распространять требования к банкоматам на любой счетчик; наличие функций проверки и качество банкнот нуждаются в отдельном подтверждении.')
add('fx_access','Посторонние лица и посторонние деньги в операционной кассе обменного пункта','Валютные операции',
    ['V1900018545:41'],
    'Установлено, что помещение является операционной кассой обменного пункта, а лицо постороннее либо деньги не относятся к деятельности организации.',
    'Нельзя применять этот пункт к произвольной кассе без подтверждения валютного обменного пункта; внешность человека не устанавливает его полномочий.')
add('fx_equipment','Обмен при неисправном обязательном оборудовании','Валютные операции',
    ['V1900018545:11','V1900018545:33','V1900018545:34'],
    'Идет обмен валюты, установлена неисправность конкретного обязательного оборудования или иное несоответствие пункту 11.',
    'Форма корпуса прибора не доказывает его функции или неисправность. Требования применяются с исключениями для автоматизированных пунктов.')
add('fx_display','Информация и обменные курсы для клиентов','Валютные операции',
    ['V1900018545:39','V1900018545:42','V1900018545:46'],
    'Виден весь предназначенный клиенту информационный стенд и читаются курсы соответствующей валюты.',
    'Необозримая часть помещения не считается отсутствующим стендом. Учитывать отдельные требования к банкам, уполномоченным организациям и автоматизированным пунктам.')
add('fx_identity','Идентификация при валютной обменной операции','Валютные операции',
    ['V1900018545:51','V1900018545:53','Z1300000073:6.4'],
    'Известны вид операции и применимые условия пункта 51; показан способ идентификации.',
    'Данные могут поступать через сервис цифровых документов. Финансовые пороги, системную проверку и причины отказа нельзя определять по толщине пачки.')
add('fx_receipt','Подтверждение валютного обмена чеком','Валютные операции',
    ['V1900018545:54'],'Показано завершение именно обменной операции и все доступные способы выдачи подтверждения.',
    'Отсутствие бумажного листа само по себе не исключает допустимое электронное подтверждение; общие кассовые операции банка не тождественны валютному обмену.')
add('fx_refusal_fee','Необоснованный отказ в обмене или комиссия','Валютные операции',
    ['V1900018545:53','V1900018545:57','V1900018545:61'],
    'Подтверждены валюта, ее статус, причина отказа либо взимания комиссии, необходимые остатки и читаемые условия.',
    'Есть исключения по ПОД/ФТ и идентификации; работа с негодной валютой регулируется отдельно. Без звука, сумм и системных данных такой вывод часто недоступен.')
add('fx_note_quality','Проверка и прием негодной иностранной валюты','Валютные операции',
    ['V1900019680:58','V1900018545:58','V1900018545:59','V1900018545:60','V1900018545:60-1','V1900018545:61'],
    'Определены страна-эмитент, статус банкноты и различимое повреждение; известна предлагаемая операция.',
    'Не переносить критерии тенге на иностранную валюту. Негодность, подделка и сомнительность имеют разные последствия.')
add('access_control','Контроль допуска в кассовую зону','Помещения и допуск',
    ['V2000020075:8','V2000020075:16','V2600038336:18','V1900019680:14'],
    'Определены границы кассового узла и права вошедшего; виден проход без предусмотренного контроля.',
    'Открытая дверь не доказывает отсутствие замка; вошедший может быть сменным кассиром. Не применять требования к кладовой к любому рабочему столу.', 'conditional_general')
add('rko_pass_regime','Пропускной режим уязвимого в террористическом отношении РКО','Помещения и допуск',
    ['V2400034348:1','V2400034348:14','V2400034348:15','V2400034348:18','V2400034348:19'],
    'Подтверждено включение объекта в сферу Инструкции; известны его зоны и порядок допуска.',
    'Не считать любую кассу уязвимым объектом автоматически. Наличие формы, отсутствие формы или лицо участника не доказывают полномочий.')
add('session_timeout','Автоматическое завершение сеанса или блокировка','Информационная безопасность',
    ['V2600038336:34','V2600038336:35','V2600038336:71','V2600038336:72'],
    'Подтверждены применимость требования к активу и непрерывная неактивность пользователя более 30 минут, после которой сеанс остается доступным.',
    'Проверить исключения пункта 72. Короткое видео и светящийся экран не доказывают нарушение 30-минутного порога; экран может показывать заставку или заблокированный сеанс.')
add('short_absence_screen','Краткий уход от незаблокированного рабочего места','Информационная безопасность',
    ['V2600038336:36','V2600038336:53','V2600038336:71','V2600038336:72','Z1300000094:22.1'],
    'Подтверждена доступность защищаемой информации постороннему либо известна обязательная локальная политика блокировки.',
    'В публичной процедуре ForteBank 2025 есть п. 35(4), запрещающий оставлять активную сессию клиентской Онлайн-платформы без присмотра; в редакции 2024 это п. 35(3). Применимость к рабочему месту кассира не установлена. Кодекс этики дает общую обязанность конфиденциальности работников, а регламент УЦ — специальный запрет для отношений УЦ. Отдельная обязанность немедленной блокировки любого рабочего экрана кассира пока не подтверждена.', 'general_basis_only')
add('account_sharing','Передача пароля или работа под чужой учетной записью','Информационная безопасность',
    ['V2600038336:40','V2600038336:73'],
    'Читаемы принадлежность учетной записи и факт передачи доступа; роли и согласования известны.',
    'Нельзя определять владельца учетной записи по лицу. Пункт 73 допускает согласованный доступ для непрерывности деятельности с точной идентификацией пользователя.')
add('third_party_system_access','Доступ третьего лица к банковской системе','Информационная безопасность',
    ['V2600038336:36','V2600038336:45','V2600038336:56','V2600038336:57','V2600038336:59'],
    'Установлены статус третьего лица, использование банковского актива и отсутствие надлежащего доступа.',
    'Отсутствие сопровождающего не означает нарушения: пункт 59 допускает альтернативные формы контроля. Прикосновение к ноутбуку не доказывает несанкционированный вход.')
add('paper_protection','Защищаемые бумажные документы оставлены доступными','Информационная безопасность',
    ['V2600038336:76','V2600038336:78','Z1300000094:11.1','Z1300000094:11.2','Z1300000094:22.1'],
    'Установлено наличие защищаемой информации и доступ к ней лица без полномочий либо небезопасное уничтожение.',
    'Обычная закрытая книга не доказывает наличие клиентских сведений. Не объявлять каждую бумагу на столе нарушением политики чистого стола, которой нет в предоставленных материалах.', 'conditional_general')
add('client_data_disclosure','Разглашение клиентских сведений на бумаге или экране','Информационная безопасность',
    ['Z2600000258:69.1','Z2600000258:69.2','Z1300000094:11.1','Z1300000094:11.2','Z1300000094:22.1','V2300032810:21'],
    'Читаются защищаемые сведения и доказан доступ или передача неуполномоченному лицу.',
    'Обзорный ракурс часто не позволяет прочитать экран. Законное согласие и предусмотренные законом основания раскрытия должны быть исключены; не делать вывод об уголовной ответственности.')
add('external_media','Защита данных при использовании внешнего носителя','Информационная безопасность',
    ['V2600038336:45','V2600038336:75','V2600038336:116'],
    'Установлены тип подключенного устройства, действие с защищаемой информацией и применяемый способ контроля.',
    'Нет универсального запрета любого USB-устройства. Пункт 75 предусматривает организационные и технические альтернативы; шифрование и сканирование не видны по корпусу.')
add('fire_end_shift','Приборы оставлены под напряжением после окончания смены','Пожарная безопасность',
    ['V2200026867:83'],
    'Подтверждено окончание рабочего времени, прибор подключен к сети и не подпадает под исключения.',
    'Допускается непрерывная работа по функциональному назначению или инструкции изготовителя; аварийное освещение и системы противопожарной защиты остаются под напряжением. Экран ноутбука на аккумуляторе не доказывает подключение к сети.')
add('fire_electrical_defect','Эксплуатация явно неисправного электрооборудования','Пожарная безопасность',
    ['V2200026867:86','V2200026867:95'],
    'Различим конкретный опасный дефект: поврежденная изоляция, искрение либо нарушение защиты, и прибор продолжает эксплуатироваться.',
    'Старый вид корпуса не доказывает неисправность; требования заводской инструкции и характеристики защиты не определяются по общему видео.')
add('evacuation_blocked','Загроможденный выход или заблокированная эвакуация','Пожарная безопасность',
    ['V2200026867:24','V2200026867:34','V2200026867:36','K1500000414:184.3'],
    'Подтверждено назначение пути или выхода; видно препятствие либо невозможность открыть дверь изнутри без ключа.',
    'Запираемая служебная дверь кассы не обязательно эвакуационный выход. Различать требования кассовой защиты и свободного выхода; учитывать исключения в самих пунктах.')
add('id_collateral','Удостоверение личности принято в залог','Документы клиента',
    ['Z1300000073:23.1','Z1300000073:23.2'],
    'Установлено именно принятие документа в залог или неправомерное изъятие.',
    'Краткая передача удостоверения кассиру для идентификации не является залогом или изъятием. Без контекста цель удержания документа не устанавливается.')
add('digital_id_exception','Цифровое удостоверение вместо пластиковой карточки','Документы клиента',
    ['Z1300000073:6.4','V1900019680:19','V1900019680:31'],
    'При оценке идентификации учитывается использование сервиса цифровых документов.',
    'Отсутствие предъявления физической карточки нельзя само по себе размечать как нарушение. Обычная фотография документа не автоматически равна документу из установленного сервиса.', 'exception')

for item in LABOR_RULES:
    add(item['id'],item['title'],item['domain'],item['specs'],item['condition'],item['limit'],item['strength'])
    rules[-1].update({k:item[k] for k in ['norm_addressee','audit_mode','related_existing_rule_ids']})
    rules[-1]['source_layer']='labor_occupational_electrical'
RULES={r['id']:r for r in rules}
for item in LABOR_RULES:
    for rule_id in item['related_existing_rule_ids']:
        assert rule_id in RULES,(item['id'],rule_id)
        RULES[rule_id].setdefault('supplementary_labor_safety_rule_ids',[]).append(item['id'])
for finding in BANK_FINDINGS:
    for rule_id in finding['related_rule_ids']:
        if rule_id in RULES:
            RULES[rule_id].setdefault('supplementary_public_bank_findings', []).append(finding)
assert len(RULES)==len(rules)

# Source interpretation checks are explicit, not a fabricated claim that the
# unseen test set or every legal proposition has been exhaustively validated.
scenario_map={
 1:(['counterfeit_return','suspect_expertise'],'Нужна подтвержденная категория банкнот и причина возврата; по цвету это не устанавливается.'),
 2:(['identity_procedure','digital_id_exception'],'Проверить весь эпизод и цифровую идентификацию; отсутствие карточки недостаточно.'),
 4:(['previous_cash_storage'],'Пункт 20 прямо относится к ранее принятым деньгам; подтвердить принадлежность стопки завершенной операции.'),
 11:(['fire_end_shift','session_timeout','ls_shift_shutdown','ls_electrical_documents'],'Прямое основание: №55, пункт 83. №927 пункт 15 требует описать отключение либо передачу смене в локальной инструкции; №246 пункт 99 указывает на техническую документацию. Подтвердить конец смены, питание от сети и отсутствие исключения. Эти общие нормы не доказывают, что любая техника должна быть выключена; 30-минутная блокировка этим роликом не проверяется.'),
 13:(['received_bag_recount','damaged_bag_recount'],'Для целой сумки не найден универсальный срок немедленного пересчета; для поврежденной прямо применяется пункт 25. Нужен непрерывный просмотр.'),
 15:(['unattended_cash','cash_storage'],'Подтвердить, что сумка содержит деньги или ценности; пустая тара не образует этого нарушения.'),
 17:(['collection_document_flow','collector_documents'],'Разделить препроводительный документ и удостоверение инкассатора. Универсальная обязанность показывать карточку кассиру при каждой передаче из пункта 101 не следует.'),
 18:(['service_overlap','previous_cash_storage'],'Запрет самого присутствия второго клиента не установлен; доказательством должны быть деньги нескольких операций либо иное конкретное действие.'),
 20:(['open_safe'],'Кратко открытый сейф и незащищенное хранение — разные факты; нужны содержимое, стадия работы и доступность посторонним.'),
 22:(['keys_stamps'],'Подтвердить, что предмет является ключом и что его оставление допускает несанкционированное использование.'),
 24:(['keys_stamps','paper_protection'],'Печати охватывает пункт 80; для книги требуется доказать служебное назначение или защищаемые сведения.'),
 26:(['unattended_cash'],'Подтвердить наличие ранее принятых наличных; пункт об уходе до конца обслуживания требует наличия клиента.'),
 28:(['short_absence_screen','session_timeout','ls_cyber_policy','ls_local_duties'],'ТК: ст. 22 п. 2 пп. 3) и ст. 23 п. 2 пп. 25-1) дают общие обязанности по кибербезопасности, но не задают немедленную блокировку экрана. Ст. 81 предусматривает перерыв для отдыха. ForteBank: п. 35(4) процедуры 2025 запрещает оставлять активную сессию клиентской Онлайн-платформы без присмотра; в версии 2024 это п. 35(3). Применимость к кассиру и системе не доказана. Нужны локальное правило, дата и состояние сеанса; 30-минутный таймаут не заменяет их.'),
 30:(['access_control','fx_access','rko_pass_regime'],'Проверить права вошедшего; №49 пункт 41 применим к обменному пункту, №21 — к объекту соответствующей категории.'),
 32:(['access_control'],'Проверить режим допуска; требование иметь закрывающийся вход не равнозначно запрету любого короткого открытия двери.'),
 33:(['access_control','third_party_system_access'],'Должность и полномочия вошедшего неизвестны; личность и должность нельзя определять по лицу.'),
 34:(['client_presence'],'Прямая связь с пунктом 20; подтвердить, что это пересчет приема именно ушедшего клиента.'),
 38:(['previous_cash_storage'],'Прямая связь с пунктом 20 при подтверждении завершенной первой операции.'),
 40:(['personal_items'],'Прямая связь с пунктом 12; вещи должны принадлежать работнику и находиться в кассовом узле.'),
 44:(['cash_sorting','bundle_formation'],'Допускаются сборные пачки по пункту 50. Для нарушения нужны различимые номиналы и неподходящая завершенная сортировка/упаковка, а не временная общая стопка.'),
 46:(['personal_items'],'Определить предмет и принадлежность; чашка или бутылка не автоматически доказывает распитие алкоголя либо состояние работника.'),
 47:(['previous_cash_storage'],'Прямая связь с пунктом 20; дубликат другого файла не является независимым подтверждением качества классификатора.'),
}

observations=[]
tree=ast.parse((PRIVATE_ROOT/'review_observations.py').read_text(encoding='utf-8-sig')) if PRIVATE_ROOT else ast.parse('')
for node in ast.walk(tree):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='dict':
        fields={k.arg:ast.literal_eval(k.value) for k in node.keywords if k.arg in ('stem','title','observation','level','comparisons','window','limits')}
        if 'stem' in fields:
            observations.append(fields)

def video_number(name):
    return int(re.search(r'-(\d+)',name)[1])

obs_by_number={video_number(o['stem']):o for o in observations}
data=json.loads((PRIVATE_ROOT/'dataset_manifest.json').read_text(encoding='utf-8')) if PRIVATE_ROOT else {'videos':[]}
videos=json.loads((ROOT/'video_coverage.json').read_text(encoding='utf-8')) if PRIVATE_ROOT is None else []
for v in data['videos']:
    number=video_number(v['file'])
    row={'file':v['file'],'label':v['label'],'label_timestamp_sec':v.get('label_timestamp_sec'),
         'video_sha256':v['sha256'],'basis':'preliminary_description_not_new_frame_review'}
    if v['label']=='нарушение':
        assert number in scenario_map and number in obs_by_number, v['file']
        rule_ids,comment=scenario_map[number]
        assert all(x in RULES for x in rule_ids), (number,rule_ids)
        o=obs_by_number[number]
        row.update({'scenario':o['title'],'preliminary_observation':o['observation'],
                    'rule_ids':rule_ids,'coverage_status':'general_basis_only' if number==28 else 'sources_mapped_with_conditions',
                    'review_comment':comment})
    else:
        related=[n for n,o in obs_by_number.items() if any(video_number(c)==number for c in o.get('comparisons',[]))]
        ids=list(dict.fromkeys(k for n in related for k in scenario_map[n][0]))
        row.update({'scenario':'Контрольный ролик с исходной меткой «без нарушения»',
                    'rule_ids':ids,'related_positive_scenarios':related,
                    'coverage_status':'comparison_description_available' if related else 'no_existing_description',
                    'review_comment':'Исходная метка не заменяет проверку всех правил. Здесь не выполнялся новый просмотр видео.'})
    videos.append(row)

summary={
    'created_at_utc':datetime.now(timezone.utc).isoformat(),
    'official_sources_downloaded':len(SOURCES),
    'all_source_text_coverage_complete':all(d['text_coverage_complete'] for d in DOCS.values()),
    'rule_topics':len(rules),
    'videos_in_inventory':len(videos),
    'positive_scenarios_in_inventory':sum(v['label']=='нарушение' for v in videos),
    'positive_scenarios_with_source_mapping':sum(v['label']=='нарушение' and bool(v['rule_ids']) for v in videos),
    'positive_scenarios_with_general_basis_only':[v['file'] for v in videos if v['coverage_status']=='general_basis_only'],
    'negative_videos_without_existing_description':[v['file'] for v in videos if v['coverage_status']=='no_existing_description'],
    'coverage_status_counts':dict(Counter(v['coverage_status'] for v in videos)),
    'universal_legal_coverage_claimed':False,
    'detector_accuracy_measured':False,
    'new_video_review_performed':False,
    'video_date_known':False,
    'interpretation':'Полнота извлечения проверена для выбранных источников. Сопоставление всех известных сценариев с источниками не подтверждает нарушение в каждом ролике и не гарантирует покрытие неизвестных тестовых типов.',
}
previous=json.loads((PARENT/'parsed_documents/manifest.json').read_text(encoding='utf-8'))
if PRIVATE_ROOT is None:
    # Reuse the saved preliminary audit records without reinterpreting video.
    summary['video_inventory_mode'] = 'saved_preliminary_audit_records_not_new_video_review'
    summary['video_audit_snapshot_at_utc'] = SAVED_AUDIT.get('video_audit_snapshot_at_utc', SAVED_AUDIT['created_at_utc'])
    summary['video_observations_in_repository'] = True
else:
    summary['video_inventory_mode'] = 'rebuilt_from_explicit_local_private_inputs'
    summary['video_observations_in_repository'] = True
previous_ids={d['document_id'] for d in previous}
summary['new_source_ids']=sorted(set(DOCS)-previous_ids)
summary['combined_distinct_document_count']=len(set(DOCS)|previous_ids)
summary['retained_history_and_amendment_ids']=sorted(previous_ids-set(DOCS))
summary['public_bank_document_files']=len(BANK_SOURCES)
summary['new_public_bank_files_in_expansion']=sum(not d.get('present_before_expansion', True) for d in BANK_SOURCES)
summary['combined_regulatory_and_bank_document_records']=summary['combined_distinct_document_count']+len(BANK_SOURCES)
summary['public_bank_evidence_cards']=len(BANK_FINDINGS)
summary['bank_document_count_includes_editions_annexes_manuals_and_reports']=True
summary['employee_specific_short_absence_rule_confirmed']=False
summary['bank_source_index']='forte_public/README.md'
summary['comparative_security_index']='comparative_security/README.md'
summary['comparative_sources_establish_forte_employee_obligation']=False
summary['labor_safety_source_ids']=LABOR_SOURCE_IDS
summary['labor_safety_topics_added']=len(LABOR_RULES)
summary['labor_safety_index']='labor_safety/README.md'
summary['labor_safety_audit_modes']=dict(Counter(r['audit_mode'] for r in LABOR_RULES))
summary['labor_safety_immediate_screen_lock_rule_confirmed']=False
summary['reference_workflow_index']='reference_workflows/README.md'
summary['reference_workflow_summary']=json.loads((ROOT/'reference_workflows/summary.json').read_text(encoding='utf-8')) if (ROOT/'reference_workflows/summary.json').exists() else None
summary['bank_pdf_image_text_fully_transcribed']=False
summary['source_text_completeness_scope']=f'Полнота текстового извлечения выше относится к {len(SOURCES)} государственным HTML-источникам. Для PDF банка проверен обход страниц; полный OCR изображений не заявлен.'

outputs=[('rules.json',rules),('coverage_summary.json',summary),('video_coverage.json',videos)]
for name,obj in outputs:
    (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

with (ROOT/'video_coverage.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=['file','label','label_timestamp_sec','scenario','coverage_status','rule_ids','review_comment'])
    writer.writeheader()
    for v in videos:
        writer.writerow({k:('; '.join(v[k]) if k=='rule_ids' else v.get(k,'')) for k in writer.fieldnames})

def md_escape(value):
    return str(value).replace('|','\\|').replace('\n',' ')

lines=['# Каталог проверок по официальным источникам','',
       'Каталог содержит возможные визуальные признаки, общие основания и документальные проверки. Документальная обязанность не размечается как установленное нарушение по одному видео. Для каждого события проверяются адресат, применимость, фактические условия и исключения. Новый просмотр видео не выполнялся.','',
       'Дата съемки неизвестна. Перед юридическим выводом редакцию нормы необходимо сопоставить с датой события. `is_actual` официального API означает выбранную запись источника и сам по себе не отменяет переходные положения.','']
for r in rules:
    lines += [f'<a id="{r["id"]}"></a>','',f"## {r['id']} — {r['title']}",'',f"Направление: {r['domain']}. Характер основания: `{r['source_strength']}`.",'',
              '**Что должно быть установлено:** '+r['required_observation'],'',
              '**Ограничения и исключения:** '+r['limits_and_exceptions'],'']
    if r.get('norm_addressee'):
        lines += ['**Адресат:** '+r['norm_addressee']+'. **Способ проверки:** `'+r['audit_mode']+'`.','']
    if r.get('supplementary_labor_safety_rule_ids'):
        lines += ['**Дополнительные общие основания и документальные проверки:** '+', '.join(f'[{key}](#{key})' for key in r['supplementary_labor_safety_rule_ids'])+'.','']
    for finding in r.get('supplementary_public_bank_findings', []):
        lines += [f"**Дополнительный документ ForteBank — [{finding['id']}]({finding['source_url']}):** {finding['locator']}; PDF-страницы {', '.join(map(str, finding['pdf_pages']))}. {finding['summary']} Ограничение: {finding['limitations']}", '']
    for source in r['references']:
        lines += [f"### [{source['document']}, {source['locator']}]({source['url']})",'',source['text'],'']
        if source['anchor_note']:
            lines += [source['anchor_note'],'']
(ROOT/'rulebook.md').write_text('\n'.join(lines),encoding='utf-8')

lines=['# Проверка нормативного покрытия исходной разметки','',
       'Сохранены ранее записанные предварительные наблюдения. По умолчанию пересборка использует готовый `video_coverage.json`; новые локальные входы можно указать через `--private-input-root`. Здесь видео и кадры повторно не просматривались; эти описания могут содержать ошибки. Метки организатора не раскрывают тип нарушения.','',
       '| Видео | Исходная метка | Сценарий / правила | Что еще проверить |','|---|---|---|---|']
for v in videos:
    links=', '.join(f'[{key}](rulebook.md#{key})' for key in v['rule_ids']) or 'Нет предварительного описания'
    lines.append('| '+' | '.join(md_escape(x) for x in [v['file'],v['label'],v['scenario']+'; '+links,v['review_comment']])+' |')
lines += ['','Ссылки на правила можно найти по их идентификатору в `rulebook.md` или `rules.json`. Нет универсального обещания обнаружения всех нарушений в скрытом тесте. FAQ №9 допускает новые типы, которых нет в обучающем наборе.']
(ROOT/'video_coverage.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

lines=['# Источники и границы покрытия','',
       '| Источник | Назначение | Роль | Официальный текст |','|---|---|---|---|']
for m in SOURCES:
    lines.append(f"| [{m['short_name']}](parsed/{m['id']}.md) | {m['purpose']} | {m['role']} | [{m['id']}]({m['page_url']}) |")
lines += ['','## Проверенные ограничения применимости','',
 '- №231: охватывает кассовые операции и инкассацию коммерческих банков; для этапов, полномочий, системной сверки и бухгалтерского учета нужны дополнительные факты. Весь основной текст и приложения сохранены.',
 '- №14: различать требования к устройству помещения и правила поведения сотрудника. У пунктов 11, 13, 14, 16 есть переходные оговорки до 01.01.2027; они сохранены в исходниках и цитатах.',
 '- №230: критерии платежности относятся к тенге. Для иностранной валюты проверяются №49 и пункт 58 №231.',
 '- №49: отличать уполномоченный банк от уполномоченной организации. Главы о лицензировании и операциях с золотом уполномоченных организаций нельзя автоматически переносить на ForteBank. Пункт 41 используется лишь для операционной кассы обменного пункта.',
 '- №21: требуется подтверждение категории объекта, уязвимого в террористическом отношении. Внешний вид помещения этого не доказывает.',
 '- №53: различать критичные и некритичные информационные активы, учитывая пункты 34–35. Для пункта 71 учитывать исключения пункта 72; не подменять автоматический 30-минутный таймаут немедленной ручной блокировкой.',
 '- №55: для кассового помещения применимы общие положения, электробезопасность и эвакуация. Специальные разделы для школ, нефтебаз, производств и строек не используются как универсальные банковские требования.',
 '- Закон о банках: для банковской тайны в новом законе проверена статья 69. Не переносить автоматически номер статьи 50 старого закона на новый закон.',
 '- Закон о персональных данных и правила защиты: нужны подтверждение характера информации и полномочий получателя. Общая обязанность защищать данные не доказывает факт их разглашения по нечитаемому экрану.',
 '- №832: сохранен как условный дополнительный источник. Пункт 2 ограничивает круг обязанных субъектов; без подтверждения интеграции/статуса объекта он не включен в безусловные правила кассира.',
 '- Закон об удостоверениях: запрет залога (статья 23) не запрещает передавать документ кассиру для обычной идентификации; цифровые документы учитываются по статье 6.',
 '- Трудовой кодекс: статьи 22, 23, 63, 81, 181, 182 и 184 дают общие обязанности, право на перерыв, требования к инструкциям и безопасности. Ответственность работодателя за условия труда не переносится автоматически на кассира. Отдельное правило немедленной блокировки экрана этими статьями не установлено.',
 '- №927: пункты 10–15 задают содержание инструкции работодателя, включая безопасное отключение либо передачу смене при непрерывном процессе. Это не готовая инструкция для каждого вида кассовой техники. Пункт 19 в редакции с 01.07.2026 предусматривает пересмотр не реже одного раза в три года; пункт 20 допускает продление при неизменных условиях.',
 '- №1019: обучение и допуск проверяются по документам. Учитываются условия пункта 6, перечни пункта 7 и исключения пунктов 61–62. Журнал по пункту 71 может быть электронным; по видео нельзя установить отсутствие обучения.',
 '- №222: пункты 19–20, 26–27 относятся к помещениям электроустановок, их допуску и ключам. Пункты 119–120 относятся к работе бригады по наряду, а пункт 581 — к электроинструменту и ручным электрическим машинам. Они не используются как универсальный запрет уходить от ноутбука, оставлять дверь кассы открытой или держать ключ от сейфа на столе.',
 '- №246: техническая эксплуатация электроустановок выполняется подготовленным персоналом либо специализированной организацией; обычное пользование компьютером не превращает кассира в электротехнический персонал. Пункт 99 помогает установить требуемые технические документы и перечни профессий, а не исключение из пожарного запрета без проверки конкретного оборудования.',
 '', '## Что не выдается за дополнительное обязательное правило','',
 '- Утратившие силу №159 и №48, уже сохраненные в прежнем пакете, не используются как текущие основания. Поправки №25 и №78 не считаются самостоятельными правилами поверх консолидированных текстов.',
 '- Найденные правила ликвидации банков №63 (V2600038399) относятся к ликвидационной процедуре и не нужны для обычного кассового ролика.',
 '- Публичная политика «чистого стола» Казахтелекома и материалы иных небанковских организаций не создают обязанностей для кассира ForteBank; они не использованы для закрытия пробела по краткому уходу от экрана.',
 '- Показатели проводок, AML-проверки, остатки по счетам, платежные лимиты и подлинность документов не выводятся из общего ракурса камеры. Ссылки на смежное законодательство в исходных текстах сохранены, но непроверяемые по видео процедуры не объявляются визуальными нарушениями.',
 '', '## Доказуемое покрытие','',
 f"Полные тексты {len(SOURCES)} выбранных официальных источников извлечены и сверены посимвольно без учета пробелов. Создано {len(rules)} тем проверки. Все 22 существующих предварительных описания роликов с меткой нарушения сопоставлены с конкретными источниками и условиями применения.",
 '', 'Это не означает, что в 22 роликах доказано 22 нарушения. Для Х-28 найдены прямые публичные запреты ForteBank для клиентских систем и специальной информации УЦ, но применимость к кассиру и его рабочей системе не подтверждена. Нужна внутренняя инструкция на дату события; общее требование конфиденциальности работника не заменяет ее. В процедуре 2025 правильный номер — 35(4), в редакции 2024 — 35(3). Для других неоднозначных сцен ограничения перечислены по отдельности.',
 '', f"Дополнительно сохранен {len(BANK_SOURCES)} публичный файл ForteBank: [каталог, страницы, редакции и применимость](forte_public/README.md). Это отдельный слой договоров, политик, памяток и отчетов, а не новые государственные НПА. [Недостающие внутренние документы](forte_public/missing_internal_documents.md).",
 '', f"Расширение по трудовому законодательству и безопасности: {len(LABOR_SOURCE_IDS)} новых актов и {len(LABOR_RULES)} дополнительных тем. [Общие основания, адресаты и ограничения](labor_safety/README.md). Документальные проверки отмечены отдельно от условно наблюдаемых признаков.",
 '', 'Ролики без нарушения, для которых нет предварительного описания: '+', '.join(summary['negative_videos_without_existing_description'])+'. Их содержание здесь не выдумывается. Полное распознавание скрытого набора не измерено.']
(ROOT/'scope_audit.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

lines=['# Расширенная нормативная база ForteBank','',
       f"Собраны и извлечены полные HTML-тексты **{len(SOURCES)} официальных источников**. Каталог содержит **{len(rules)} тем проверки**: визуальные признаки с условиями, общие основания и документальные проверки.",'',
       f"**Последнее расширение:** добавлены {len(LABOR_SOURCE_IDS)} актов РК по трудовому законодательству, охране труда и электробезопасности; {len(LABOR_RULES)} новых тем к прежним 66. Для каждой указаны адресат и ограничения. [Результат проверки](labor_safety/README.md).",'',
       f"Вместе с прежним пакетом теперь **{summary['combined_distinct_document_count']} различных нормативных документов**: {len(SOURCES)} источников в этой проверке и {len(summary['retained_history_and_amendment_ids'])} ранее сохраненных актов изменений/утративших силу документов. Новых источников — {len(summary['new_source_ids'])}.",'',
       f"**Расширение по документам самого ForteBank:** сохранен {len(BANK_SOURCES)} PDF-файл банка, включая {summary['new_public_bank_files_in_expansion']} дополнительных. Всего с государственными актами — **{summary['combined_regulatory_and_bank_document_records']} записей документов и редакций**. Это число включает договоры, памятки, отчеты, тарифное приложение и исторические версии; оно не означает столько же независимых запретов.",'',
       '**Границы результата:** все 22 предварительно описанных сценария с меткой нарушения получили ссылки и ограничения. Это полнота учета известных сценариев, а не подтверждение каждого нарушения или гарантия покрытия неизвестных тестовых видео. Для Х-28 найдены специальные публичные запреты ForteBank, но их применимость к кассиру не установлена.','',
       '- [31 публичный документ ForteBank: оригиналы и оценка применимости](forte_public/README.md)',
       '- [Трудовой кодекс, охрана труда и электробезопасность: новые общие основания](labor_safety/README.md)',
       '- [14 проверенных положений документов банка](forte_public/findings.md)',
       '- [Какие внутренние документы еще нужны для кейса](forte_public/missing_internal_documents.md)',
       '- [Х-28: источники США, Европы и международной платёжной отрасли](comparative_security/README.md)',
       '- [Дополнительный поиск внутренних правил ForteBank по Х-28](forte_public/x28_followup/README.md)',
       '- [Эталонные процедуры для всех 80 тем: действия, порядок и исключения](reference_workflows/README.md)',
       '- [Матрица покрытия тем процедурами — 80/80](reference_workflows/topic_coverage.md)',
       '- [Каталог правил с точными пунктами и полными цитатами](rulebook.md)',
       '- [Правила в JSON](rules.json)',
       '- [Сопоставление всех 42 файлов и исходных меток](video_coverage.md)',
       '- [Таблица для Excel](video_coverage.csv)',
       '- [Источники, применимость и проверенные исключения](scope_audit.md)',
       '- [Машиночитаемые показатели покрытия](coverage_summary.json)',
       '- [Реестр источников и контрольные суммы](source_manifest.json)',
       '- [Проверка полноты парсинга](parsing_manifest.json)','',
       '## Существенные уточнения','',
       '1. **Включенная техника после окончания смены:** найден пункт 83 Правил пожарной безопасности №55. Есть исключения для непрерывной работы по назначению/инструкции; свечение экрана не доказывает питание от сети.',
       '2. **Смешанные номиналы:** пункт 50 №231 допускает сборные пачки. Нельзя считать любую общую стопку нарушением сортировки.',
       '3. **Посторонний в обменной кассе:** пункт 41 №49 дает более прямое основание, если подтвержден именно обменный пункт и отсутствие полномочий.',
       '4. **Документы на столе:** добавлены №53 пункт 76, закон о персональных данных статьи 11 и 22 и новый закон о банках статья 69. Нужны доказательства защищаемого содержания и доступа.',
       '5. **Экран при уходе:** п. 35(4) процедуры ForteBank 2025 запрещает оставлять активную сессию клиентской Онлайн-платформы без присмотра; в версии 2024 — п. 35(3). Есть также п. 4.6-1(11) условий ForteBusiness и п. 9.7(7) регламента УЦ, каждый со своей областью. Для кассира нужен внутренний регламент и подтверждение системы. Таймаут №53 в 30 минут не равен немедленной ручной блокировке.','',
       '6. **Общие трудовые обязанности:** ст. 22 ТК закрепляет бережное отношение к имуществу, неразглашение охраняемой тайны и соблюдение требований безопасности. Ст. 23 п. 2 пп. 25-1) требует ознакомления с актами по кибербезопасности. Эти нормы усиливают общую основу, но не устанавливают отдельную немедленную блокировку экрана. Ст. 81 предусматривает право на перерыв.',
       '7. **Завершение работы:** №927 п. 15 требует включать в инструкцию отключение оборудования, сдачу места, уведомление о недостатках, а при непрерывном процессе — передачу смене. №246 п. 99 помогает установить комплект технической документации. Для автоматического вывода по видео нужны конкретная инструкция и режим оборудования.','',
       'Новый просмотр видео в этом пакете не выполнялся. Сохранены исходные предварительные описания и их ограничения; основной видеоразбор и прежний rule_catalog.json не изменены.','']
if PRIVATE_ROOT is None:
    lines=[line for line in lines if not line.startswith('Новый просмотр видео в этом пакете')]
    lines += ['## Состав публикации и пересборка', '',
              'В этом пакете находятся публичные нормативные источники, процедуры и готовая предварительная таблица сопоставления 42 файлов с нормами. Таблица предназначена для приватного репозитория команды, содержит ограничения и не является новой экспертной разметкой. Новый просмотр видео и кадров при сборке не выполняется.', '',
              'Порядок сборки и зависимости описаны в [PUBLISHING.md](PUBLISHING.md). Для нормативной пересборки видеоданные не требуются.', '']
(ROOT/'README.md').write_text('\n'.join(lines),encoding='utf-8')

validation={
    'rule_ids_unique':len(RULES)==len(rules),
    'every_rule_has_resolved_official_references':all(r['references'] for r in rules),
    'source_html_hashes_match':all(hashlib.sha256((ROOT/'sources'/(ident+'.html')).read_bytes()).hexdigest()==d['source_sha256'] for ident,d in DOCS.items()),
    'all_text_coverage_checks_pass':all(d['text_coverage_complete'] for d in DOCS.values()),
    'no_fabricated_final_video_verdicts':all(v['basis']=='preliminary_description_not_new_frame_review' for v in videos),
    'labor_safety_rules_have_addressee_and_mode':all(r.get('norm_addressee') and r.get('audit_mode') for r in rules if r.get('source_layer')=='labor_occupational_electrical'),
    'labor_safety_sources_resolved':all(s in DOCS for s in LABOR_SOURCE_IDS),
    'x28_stays_general_basis_only':RULES['short_absence_screen']['source_strength']=='general_basis_only',
}
validation['all_22_positive_inventory_entries_accounted_for']=sum(v['label']=='нарушение' and bool(v['rule_ids']) for v in videos)==22
validation['all_saved_scenario_rule_ids_resolve']=all(set(v['rule_ids'])<=set(RULES) for v in videos)
assert all(validation.values()),validation
(ROOT/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))

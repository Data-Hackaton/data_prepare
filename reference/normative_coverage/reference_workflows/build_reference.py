"""Assemble public-normative reference workflows without reading any videos."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import csv

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

definitions = read(ROOT/'definitions.json')
rules = read(BASE/'rules.json')
available = {ref['spec']: ref for rule in rules for ref in rule['references']}
available.update(read(ROOT/'additional_references.json'))
topic_definitions = read(ROOT/'topic_definitions.json')
topic_input = topic_definitions['topic_procedures']
rule_map = {rule['id']: rule for rule in rules}
topic_map = {topic['rule_id']: topic for topic in topic_input}
assert len(topic_map) == len(topic_input), 'Duplicate topic procedure'
assert set(topic_map) == set(rule_map), {'missing': sorted(set(rule_map)-set(topic_map)), 'extra': sorted(set(topic_map)-set(rule_map))}
assert len(rule_map) == 80, 'Reassess the requested 80-topic scope if the catalog changes'
topics = []
coverage = []
for rule in rules:
    topic = topic_map[rule['id']]
    assert topic['steps'] and topic['exceptions'] and topic['evidence']
    assert all(item['kind'] in topic_definitions['exception_kind_meanings'] for item in topic['exceptions'])
    step_specs = {spec for step in topic['steps'] for spec in step['source_specs']}
    exception_specs = {spec for item in topic['exceptions'] for spec in item['source_specs']}
    catalog_specs = {ref['spec'] for ref in rule['references']}
    assert catalog_specs <= step_specs | exception_specs, (rule['id'], sorted(catalog_specs-step_specs-exception_specs))
    for i, step in enumerate(topic['steps']):
        step['id'] = f's{i+1:02d}'
        assert step['source_specs'] and step['kind'] and step['video_verification']
    for edge in topic['ordering']:
        assert 0 <= edge['before'] < edge['after'] < len(topic['steps'])
        assert edge['basis'] in definitions['ordering_basis']
        edge['before_step'] = topic['steps'][edge['before']]['id']
        edge['after_step'] = topic['steps'][edge['after']]['id']
    assert all(key in {w['id'] for w in definitions['workflows']} for key in topic['linked_workflows'])
    topic.update({'id':'topic_'+rule['id'], 'title':rule['title'], 'domain':rule['domain'],
                  'catalog_source_strength':rule['source_strength'],
                  'catalog_required_observation':rule['required_observation'],
                  'catalog_limits_and_exceptions':rule['limits_and_exceptions'],
                  'catalog_reference_specs':sorted(catalog_specs),
                  'source_specs':sorted(step_specs | exception_specs)})
    topics.append(topic)
    coverage.append({'rule_id':rule['id'], 'title':rule['title'], 'procedure_id':topic['id'],
                     'procedure_type':topic['procedure_type'], 'step_count':len(topic['steps']),
                     'exception_count':len(topic['exceptions']), 'catalog_references':sorted(catalog_specs),
                     'procedure_references':topic['source_specs'], 'missing_references':[],
                     'expansion_status':'expanded_with_applicability_gap' if topic['procedure_type']=='unresolved_requirement_check' else 'expanded',
                     'procedure_link':'topics.md#'+topic['id']})
metadata = {item['id']: item for item in read(BASE/'source_manifest.json')}
used = set()

def collect(value):
    if isinstance(value, dict):
        used.update(value.get('source_specs', []))
        for child in value.values():
            collect(child)
    elif isinstance(value, list):
        for child in value:
            collect(child)

collect(definitions)
collect(topics)
assert used <= available.keys(), sorted(used-available.keys())
refs = {key: available[key] for key in sorted(used)}
workflows = definitions['workflows']
assert len({w['id'] for w in workflows}) == len(workflows)
for workflow in workflows:
    ids = {step['id'] for step in workflow['steps']}
    assert len(ids) == len(workflow['steps'])
    for step in workflow['steps']:
        step.setdefault('norm_status', 'direct_requirement_with_conditions')
        assert step['source_specs'] and step['limits'] and step['video_verification']
    for edge in workflow['ordering']:
        assert edge['before'] in ids and edge['after'] in ids
        assert edge['basis'] in definitions['ordering_basis']
    adjacency = {key: [] for key in ids}
    for edge in workflow['ordering']:
        adjacency[edge['before']].append(edge['after'])
    def visit(key, path):
        assert key not in path, ('cycle', workflow['id'], key)
        for child in adjacency[key]:
            visit(child, path | {key})
    for key in ids:
        visit(key, set())
    for branch in workflow['branches']:
        if 'route' in branch:
            assert branch['route'] in {w['id'] for w in workflows}

source_ids = {ref['document_id'] for ref in refs.values()}
for ident in source_ids:
    assert hashlib.sha256((BASE/'sources'/f'{ident}.html').read_bytes()).hexdigest() == metadata[ident]['html_sha256']
    assert all(ref['source_sha256'] == metadata[ident]['html_sha256'] for ref in refs.values() if ref['document_id'] == ident)

assembled = {**definitions, 'built_at_utc': datetime.now(timezone.utc).isoformat(),
             'all_80_rule_topics_covered':set(topic_map)==set(rule_map),
             'topic_procedure_count':len(topics), 'topic_procedures':topics, 'topic_coverage':coverage,
             'exception_kind_meanings':topic_definitions['exception_kind_meanings'],
             'exception_classification_note':topic_definitions['exception_classification_note'],
             'references': refs, 'source_metadata': {key: metadata[key] for key in sorted(source_ids)}}
write(ROOT/'workflows.json', assembled)

mode_names = {'partly_observable':'Видно частично', 'context_required':'Нужен контекст',
              'not_visually_verifiable':'По общему видео не проверяется'}
def cite(specs):
    return '; '.join(f"[{refs[key]['document']}, {refs[key]['locator']}]({refs[key]['url']})" for key in specs)
def cell(value):
    return value.replace('|', '\\|').replace('\n', '<br>')

lines = ['# Эталонные процедуры кассовой работы по открытым нормам РК', '',
         f"**Версия 2 · 17.10.2026.** Развёрнуты **{len(topics)} из {len(rules)} тем** каталога в отдельные процедуры: {sum(len(t['steps']) for t in topics)} шагов действий и проверки. Сохранены восемь общих маршрутов первой версии. Это нормативная модель для разметки и проверки; утверждение её как внутреннего регламента ForteBank не подтверждено.", '',
         '**Начать здесь:** [все 80 процедур](topics.md) · [матрица покрытия 80/80](topic_coverage.md) · [JSON для системы](workflows.json) · [проверка результата](validation.json).', '',
         'Полнота 80/80 означает наличие процедуры для каждой темы текущего каталога. Она не означает 80 обученных детекторов, доказанность нарушений или полноту всего законодательства. Документальные проверки, требования к системам и незакрытый вопрос немедленной блокировки экрана сохранены в соответствующих категориях.', '',
         'Каталог законов отвечает на вопрос «какое требование действует». Эти процедуры добавляют «при какой операции, кто и что должен сделать, какие есть условия и исключения». Данные о фактических действиях берутся только из проверяемой записи и подтверждённого контекста.', '',
         '## Как устроен эталон', '',
         'Для каждой операции указаны условия применения, ожидаемые действия, ссылки на нормы, наблюдаемость и альтернативные ветки. Нумерация ниже помогает читать процедуру. Она сама по себе не означает запрета любого иного порядка: прямые требования до/после вынесены в отдельный блок.', '',
         'Для шага используются статусы **выполнен**, **есть противоречащий факт**, **не наблюдается/данных недостаточно**, **не применим**. Последние два статуса не являются доказанным нарушением и не добавляют третий итоговый вердикт в обязательный API кейса.', '',
         '**Пропуск обязательного действия** можно оценивать только при установленной операции, применимой обязанности, отсутствии исключения и достаточной видимости всего нужного этапа. Нельзя считать пропуском действие, которое могло произойти до начала ролика, за кадром или в системе.', '',
         '## Восемь общих маршрутов', '']
for w in workflows:
    lines.append(f"- [{w['title']}](#{w['id']}) — контрольных шагов: {len(w['steps'])}.")
for w in workflows:
    lines += ['', f'<a id="{w["id"]}"></a>', '', f"## {w['title']}", '',
              '**Кто:** '+w['actor']+'.', '', '**Применимость:** '+w['applicability'], '',
              '| Шаг | Ожидаемое действие | Основание | Проверка и ограничения |', '|---|---|---|---|']
    for i, step in enumerate(w['steps'], 1):
        condition = (' Только если: '+step['when']) if step.get('when') else ''
        subtype = ' '+', '.join(step.get('source_subpoints', [])) if step.get('source_subpoints') else ''
        limit = mode_names[step['video_verification']]+'. '+step['limits']
        if step['norm_status'] == 'requires_local_instruction':
            limit += ' Конкретизация — в применимой инструкции банка.'
        if step['norm_status'] == 'unresolved_for_employee_workstation':
            limit += ' Этот шаг не закрывает пробел по немедленной блокировке экрана.'
        lines.append(f"| {i}. `{step['id']}` | {cell(step['action']+condition)} | {cite(step['source_specs'])}{subtype} | {cell(limit)} |")
    if w['ordering']:
        lines += ['', '**Зависимости порядка:**', '']
        for edge in w['ordering']:
            label = 'Прямо задано нормой' if edge['basis']=='explicit_normative_order' else 'Логическая зависимость'
            lines.append(f"- `{edge['before']}` → `{edge['after']}`. **{label}:** {edge['meaning']} {cite(edge['source_specs'])}.")
    else:
        lines += ['', 'Отдельных универсальных связей «любой предыдущий шаг строго раньше следующего» для этой процедуры здесь не установлено. Условия и сроки указаны в самих шагах.']
    for item in w['invariants']:
        lines += ['', '**Условие на протяжении операции:** '+item['requirement']+' '+cite(item['source_specs'])+'. '+item['limits']]
    for branch in w['branches']:
        route = ('Перейти к процедуре ['+branch['route']+'](#'+branch['route']+').') if branch.get('route') else branch['required_action']
        lines += ['', '**Ветка:** '+branch['when']+' '+route+' '+(cite(branch['source_specs'])+'. ' if branch.get('source_specs') else '')+branch['limits']]

lines += ['', '## Как использовать при обучении и проверке', '',
          '1. Подтвердить вид операции и подходящую редакцию нормы.',
          '2. Для каждого применимого шага разметить наблюдение, временной интервал, кадры и ограничения видимости. Проверяющий подтверждает метку; текст закона сам по себе её не создаёт.',
          '3. Сохранять отдельно примеры правильного выполнения, подтверждённого отклонения и недостаточной наблюдаемости. Не размечать скрытые проводки или подлинность банкнот по догадке.',
          '4. Сравнивать события с условиями и зависимостями процедуры. Проверять возможные альтернативные ветки до постановки метки отклонения.',
          '5. Проверять результат на отложенных записях; дубликаты и фрагменты одной записи не разносить между обучением и проверкой.', '',
          'Поля будущей разметки перечислены в `expected_record_fields` файла [workflows.json](workflows.json). Сами видеозаписи здесь не просматривались и новые фактические метки не создавались.', '',
          '## Границы версии', '']
lines += ['- '+item for item in definitions['global_limits']]
lines += ['', 'Источники США/Европы не использованы для установления обязательных шагов этих процедур. Х-28 остаётся с неподтверждённой применимостью конкретного правила немедленной ручной блокировки к рабочей системе кассира.', '',
          '## Файлы', '',
          '- [Все 80 процедур с условиями и исключениями](topics.md)',
          '- [Матрица покрытия тем](topic_coverage.md)',
          '- [Матрица покрытия в CSV](topic_coverage.csv)',
          '- [Процедуры, полные цитаты, ссылки и контрольные суммы в JSON](workflows.json)',
          '- [Редактируемое описание процедур](definitions.json)',
          '- [Редактируемые определения 80 тематических процедур](topic_definitions.json)',
          '- [Дополнительные ссылки на цифровые документы и исключения для помещений](additional_references.json)',
          '- [Проверка ссылок, условий и исключений](validation.json)',
          '- [Повторяемая проверка данных](verify_reference.py)',
          '- [Каталог 80 тем](../rulebook.md)',
          '- [Основная база](../README.md)', '',
          'Для пересборки запустить из этой папки последовательно `python build_reference.py`, `python ../build_coverage.py`, `python verify_reference.py`. Проверка сверяет 80 идентификаторов, исходные ограничения, цитаты, контрольные суммы, связи порядка и ссылки. Она не заменяет оценку применимости к конкретному событию.', '']
(ROOT/'README.md').write_text('\n'.join(lines), encoding='utf-8')

kind_names = {'required_action':'Требуемое действие', 'conditional_action':'Условное действие',
              'review_check':'Проверка доказательств', 'applicability_check':'Проверка применимости',
              'unresolved_requirement':'Требование пока не установлено'}
type_names = {'operator_procedure':'Порядок действий', 'standing_condition':'Условие при работе',
              'document_audit':'Документальная проверка', 'system_control_audit':'Проверка настройки и работы системы',
              'premises_audit':'Проверка помещения и режима', 'document_and_visual_review':'Документы и наблюдение',
              'general_obligation_review':'Проверка общей обязанности', 'unresolved_requirement_check':'Проверка незакрытой применимости'}
exception_names = {'express_normative_exception':'Исключение, прямо указанное в норме',
                   'permitted_alternative':'Допустимый вариант', 'applicability_limit':'Предел применимости',
                   'evidence_limit':'Ограничение доказательств', 'conditional_branch':'Условная ветка'}
lines = ['# Все 80 тем: эталонные процедуры и исключения', '',
         'Каждая карточка соответствует ровно одному идентификатору основного каталога. В неё включены все исходные нормативные ссылки и ограничения, а также отдельные действия, условия и исключения. Полные цитаты и SHA-256 источников находятся в [workflows.json](workflows.json).', '',
         'Шаги «Проверка применимости» и «Проверка доказательств» относятся к проверяющему и не создают новых обязанностей кассира. Нумерация описывает маршрут чтения; обязательный порядок до/после отмечен отдельно. Дата события и редакция акта должны быть подтверждены. Статус «не наблюдается» не равен нарушению.', '',
         'Условные записи разделены по смыслу: прямое исключение из нормы, допустимый вариант исполнения, предел применимости, условная ветка и ограничение доказательств. Недостаточная видимость не является законным освобождением от обязанности; она ограничивает вывод проверяющего.', '',
         '[Матрица 80/80](topic_coverage.md) · [Общие маршруты](README.md) · [Проверка](validation.json)', '', '## Указатель', '']
last_domain = None
for topic in topics:
    if topic['domain'] != last_domain:
        lines += ['', '**'+topic['domain']+'**', '']
        last_domain = topic['domain']
    lines.append(f"- [{topic['rule_id']} — {topic['title']}](#{topic['id']})")
for topic in topics:
    lines += ['', f'<a id="{topic["id"]}"></a>', '', f"## {topic['rule_id']} — {topic['title']}", '',
              '**Вид процедуры:** '+type_names[topic['procedure_type']]+'.', '', '**Адресат:** '+topic['actor']+'.', '',
              '**Применимость:** '+topic['applicability'], '', '**Ожидаемый результат:** '+topic['expected_outcome'], '',
              '| Шаг | Действие и его роль | Точный пункт | Наблюдаемость |', '|---|---|---|---|']
    for step in topic['steps']:
        lines.append(f"| {step['id']} | **{kind_names[step['kind']]}:** {cell(step['action'])} | {cite(step['source_specs'])} | {mode_names[step['video_verification']]} |")
    lines += ['', '**Исключения, альтернативы и ограничения:**', '']
    for item in topic['exceptions']:
        lines.append('- **'+exception_names[item['kind']]+': '+item['condition']+'** '+item['behavior']+' '+cite(item['source_specs'])+'.')
    if topic['ordering']:
        lines += ['', '**Обязательный порядок, прямо указанный в источнике:**', '']
        for edge in topic['ordering']:
            lines.append(f"- `{edge['before_step']}` → `{edge['after_step']}`. {cite(edge['source_specs'])}.")
    else:
        lines += ['', 'Отдельный универсальный запрет менять порядок всех соседних шагов не установлен; условия, сроки и этапы указаны в тексте действий.']
    lines += ['', '**Доказательства для проверки:** '+ '; '.join(topic['evidence'])+'.', '',
              '**Исходное условие каталога:** '+topic['catalog_required_observation'], '',
              '**Сохранённые ограничения каталога:** '+topic['catalog_limits_and_exceptions'], '',
              '**Все исходные нормативные ссылки темы:** '+cite(topic['catalog_reference_specs'])+'.']
    if topic['linked_workflows']:
        names={w['id']:w['title'] for w in workflows}
        lines += ['', '**Общие маршруты:** '+ '; '.join(f"[{names[key]}](README.md#{key})" for key in topic['linked_workflows'])+'.']
(ROOT/'topics.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')

write(ROOT/'topic_coverage.json', {'catalog_topics':len(rules), 'expanded_topics':len(coverage),
                                 'missing_topic_ids':[], 'unknown_topic_ids':[], 'scope':'catalog_topic_expansion_only', 'rows':coverage})
lines=['# Матрица покрытия 80 тем', '',
       'Проверено соответствие по идентификаторам: каждая тема имеет отдельную процедуру; все её исходные ссылки связаны с действиями или исключениями. Это проверка структурной полноты, а не подтверждение всех нарушений по видео.', '',
       'В столбце «условные записи» посчитаны исключения, допустимые варианты, пределы применимости, условные ветки и ограничения доказательств. Их тип указан в каждой процедуре.', '',
       '| Тема | Процедура | Тип | Шаги / условные записи | Пункты из каталога | Статус |', '|---|---|---|---|---|---|']
for row in coverage:
    lines.append(f"| `{row['rule_id']}` | [{cell(row['title'])}]({row['procedure_link']}) | {type_names[row['procedure_type']]} | {row['step_count']} / {row['exception_count']} | {len(row['catalog_references'])} | {'Развёрнута; применимость запрета не подтверждена' if row['expansion_status']=='expanded_with_applicability_gap' else 'Развёрнута'} |")
lines += ['', '[JSON матрицы](topic_coverage.json) · [CSV](topic_coverage.csv) · [Проверка](validation.json) · [Основной каталог](../rulebook.md)', '']
(ROOT/'topic_coverage.md').write_text('\n'.join(lines), encoding='utf-8')
with (ROOT/'topic_coverage.csv').open('w', encoding='utf-8-sig', newline='') as file:
    writer=csv.DictWriter(file, fieldnames=['rule_id','title','procedure_id','procedure_type','step_count','exception_count','catalog_references','procedure_references','expansion_status','procedure_link'])
    writer.writeheader()
    for row in coverage:
        writer.writerow({key:'; '.join(value) if isinstance(value,list) else value for key,value in row.items() if key!='missing_references'})

summary = {'workflow_count':len(workflows), 'step_count':sum(len(w['steps']) for w in workflows),
           'schema_version':'2.0', 'topic_procedure_count':len(topics),
           'topic_step_count':sum(len(t['steps']) for t in topics),
           'topic_exception_count':sum(len(t['exceptions']) for t in topics),
           'topic_exception_count_scope':'exceptions_alternatives_applicability_branches_and_evidence_limits',
           'topic_condition_kinds':dict(Counter(e['kind'] for t in topics for e in t['exceptions'])),
           'topic_coverage_scope':'all_80_catalog_topics_expanded_not_all_violations_proven',
           'missing_topic_ids':[], 'unknown_topic_ids':[],
           'topic_procedure_types':dict(Counter(t['procedure_type'] for t in topics)),
           'distinct_references':len(refs), 'official_source_count':len(source_ids),
           'step_observability':dict(Counter(s['video_verification'] for w in workflows for s in w['steps'])),
           'topic_step_observability':dict(Counter(s['video_verification'] for t in topics for s in t['steps'])),
           'new_video_labels_created':False, 'model_trained':False,
           'bank_approved_internal_regulation':False, 'all_80_rule_topics_covered':True,
           'universal_legal_coverage_claimed':False, 'short_absence_immediate_lock_gap_closed':False}
write(ROOT/'summary.json', summary)
print(json.dumps(summary, ensure_ascii=False, indent=2))

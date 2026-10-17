"""Validate the 80-topic normative dataset; never opens videos or trains a model."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
import csv
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


data = read(ROOT/'workflows.json')
summary = read(ROOT/'summary.json')
rules = read(BASE/'rules.json')
rule_map = {r['id']: r for r in rules}
topics = data['topic_procedures']
topic_map = {t['rule_id']: t for t in topics}
refs = data['references']
manifest = {s['id']: s for s in read(BASE/'source_manifest.json')}
sources = {k: read(BASE/'parsed'/f'{k}.json') for k in data['source_metadata']}
checks, details = {}, {}


def check(name, condition, detail=None):
    checks[name] = bool(condition)
    if detail is not None:
        details[name] = detail


def specs(value):
    if isinstance(value, dict):
        return set(value.get('source_specs', [])) | set().union(*(specs(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(specs(v) for v in value))
    return set()


check('exactly_80_unique_topics_match_catalog', len(topics) == len(topic_map) == len(rule_map) == 80
      and set(topic_map) == set(rule_map))
check('no_original_references_lost', all(
    {r['spec'] for r in rule_map[t['rule_id']]['references']} <= specs(t['steps']) | specs(t['exceptions'])
    for t in topics))
check('original_conditions_and_limits_preserved_verbatim', all(
    t['catalog_required_observation'] == rule_map[t['rule_id']]['required_observation']
    and t['catalog_limits_and_exceptions'] == rule_map[t['rule_id']]['limits_and_exceptions']
    and t['catalog_source_strength'] == rule_map[t['rule_id']]['source_strength'] for t in topics))
check('all_step_branch_and_order_references_resolve', specs(topics) | specs(data['workflows']) <= set(refs))
check('every_topic_has_actor_scope_outcome_evidence', all(
    all(t.get(k) for k in ['actor', 'applicability', 'expected_outcome', 'evidence', 'steps', 'exceptions'])
    for t in topics))
step_kinds = {'required_action', 'conditional_action', 'review_check', 'applicability_check', 'unresolved_requirement'}
modes = {'partly_observable', 'context_required', 'not_visually_verifiable'}
check('every_step_has_action_citation_role_and_observability', all(
    s['action'] and s['source_specs'] and s['kind'] in step_kinds and s['video_verification'] in modes
    for t in topics for s in t['steps']))
check('each_condition_classified_and_cited', all(
    e['condition'] and e['behavior'] and e['source_specs'] and e['kind'] in data['exception_kind_meanings']
    for t in topics for e in t['exceptions']))

quote_mismatches = []
for key, ref in refs.items():
    source = sources[ref['document_id']]
    matches = [u for u in source['units'] + source['blocks'] if u['id'] == ref['unit_id']]
    if not any(u['text'] == ref['text'] for u in matches):
        quote_mismatches.append(key)
check('all_quotes_match_saved_source_units_verbatim', not quote_mismatches, quote_mismatches)
catalog_refs = {r['spec']: r for rule in rules for r in rule['references']}
expected_refs = {**catalog_refs, **read(ROOT/'additional_references.json')}
check('reference_metadata_matches_catalog_or_identified_addition', all(r == expected_refs[k] for k, r in refs.items()))
check('only_official_adilet_sources_used_for_obligations', all(
    urlsplit(r['url']).scheme == 'https' and urlsplit(r['url']).hostname == 'adilet.zan.kz'
    for r in refs.values()))
check('source_html_hashes_match_manifest_and_citations', all(
    digest(BASE/'sources'/f'{key}.html') == manifest[key]['html_sha256'] == sources[key]['source_sha256']
    for key in sources) and all(r['source_sha256'] == manifest[r['document_id']]['html_sha256'] for r in refs.values()))
check('saved_source_text_extraction_complete', all(s['text_coverage_complete'] for s in sources.values()))
check('temporal_note_is_explicitly_identified_not_numbered_law',
      refs['V2000020075:16@transition_until_2027']['source_fragment_kind'] == 'temporal_editorial_note')

workflow_ids = {w['id'] for w in data['workflows']}
check('eight_broad_workflows_preserved_and_topic_links_resolve', len(workflow_ids) == len(data['workflows']) == 8
      and all(set(t['linked_workflows']) <= workflow_ids for t in topics))
check('topic_step_ids_unique', all(len({s['id'] for s in t['steps']}) == len(t['steps']) for t in topics))
check('topic_order_links_valid_and_only_explicit_order_marked', all(
    0 <= e['before'] < e['after'] < len(t['steps'])
    and e['before_step'] == t['steps'][e['before']]['id'] and e['after_step'] == t['steps'][e['after']]['id']
    and e['basis'] == 'explicit_normative_order' and e['source_specs']
    for t in topics for e in t['ordering']))


def acyclic(workflow):
    adjacency = {s['id']: [] for s in workflow['steps']}
    for e in workflow['ordering']:
        if e['before'] not in adjacency or e['after'] not in adjacency:
            return False
        adjacency[e['before']].append(e['after'])
    def visit(key, path):
        return key not in path and all(visit(child, path | {key}) for child in adjacency[key])
    return all(visit(key, set()) for key in adjacency)


check('broad_workflow_order_graphs_acyclic', all(acyclic(w) for w in data['workflows']))
coverage = read(ROOT/'topic_coverage.json')
rows = coverage['rows']
csv_rows = list(csv.DictReader((ROOT/'topic_coverage.csv').open(encoding='utf-8-sig', newline='')))
check('json_csv_coverage_each_have_80_distinct_matching_rows',
      len(rows) == len(csv_rows) == len({r['rule_id'] for r in rows}) == 80
      and {r['rule_id'] for r in csv_rows} == set(rule_map)
      and rows == data['topic_coverage'] and not coverage['missing_topic_ids'] and not coverage['unknown_topic_ids'])
check('matrix_counts_and_references_match_actual_procedures', all(
    r['step_count'] == len(topic_map[r['rule_id']]['steps'])
    and r['exception_count'] == len(topic_map[r['rule_id']]['exceptions'])
    and set(r['procedure_references']) == specs(topic_map[r['rule_id']]['steps']) | specs(topic_map[r['rule_id']]['exceptions'])
    and not r['missing_references'] for r in rows))
check('csv_values_match_json_values', all(all(
    cr[k] == ('; '.join(v) if isinstance(v, list) else str(v)) for k, v in jr.items() if k != 'missing_references')
    for cr, jr in zip(csv_rows, rows)))
check('summary_counts_match_actual_data',
      summary['topic_procedure_count'] == len(topics)
      and summary['topic_step_count'] == sum(len(t['steps']) for t in topics)
      and summary['topic_exception_count'] == sum(len(t['exceptions']) for t in topics)
      and summary['topic_condition_kinds'] == dict(Counter(e['kind'] for t in topics for e in t['exceptions']))
      and summary['distinct_references'] == len(refs) and summary['official_source_count'] == len(sources))

# Regression safeguards for high-risk exceptions. These check retention, not legal interpretation.
sentinels = {
    'digital_cash_document_path': ('cash_document_execution', ['V1900019680:10-1'], ['цифров']),
    'sealed_payout_and_partial_packaging': ('withdrawal_count', ['V1900019680:32'], ['упаков']),
    'mixed_bundles_and_vacuum_alternative': ('bundle_formation', ['V1900019680:48', 'V1900019680:49', 'V1900019680:50'], ['вакуум', 'остат']),
    'two_person_collection_exception': ('collector_team', ['V1900019680:99'], ['двух', 'краск']),
    'premises_temporal_and_automated_exceptions': ('secure_cash_area', ['V2000020075:18', 'V2000020075:16@transition_until_2027'], ['01.01.2027', 'автомат']),
    'fx_amount_boundary_and_digital_identity': ('fx_identity', ['V1900018545:51', 'Z1300000073:6.4'], ['500 000', 'не выше', 'цифров']),
    'fx_board_location_alternatives': ('fx_display', ['V1900018545:39'], ['0,4', 'вне помещения', 'сайте', 'автомат']),
    'timeout_scope_and_exceptions': ('session_timeout', ['V2600038336:34', 'V2600038336:35', 'V2600038336:71', 'V2600038336:72'], ['более 30', 'некритич']),
    'account_continuity_exception': ('account_sharing', ['V2600038336:73'], ['непрерывност', 'согласован', 'идентификац']),
    'third_party_controls_are_alternatives': ('third_party_system_access', ['V2600038336:59'], ['как минимум одну', 'альтернатив']),
    'paper_and_media_protection_alternatives': ('paper_protection', ['V2600038336:76', 'V2600038336:78'], ['альтернатив', 'этап уничтожения']),
    'external_media_authorization_and_methods': ('external_media', ['V2600038336:75', 'V2600038336:116'], ['альтернатив', 'авторизац']),
    'continuous_power_exception': ('fire_end_shift', ['V2200026867:83'], ['функциональн', 'изготовител']),
    'cash_window_grilles_and_exit_conditions': ('evacuation_blocked', ['V2200026867:24', 'V2200026867:34', 'V2200026867:36'], ['касс', 'изнутри', 'дублирующ']),
    'instruction_review_and_extension': ('ls_instruction_lifecycle', ['V1500012534:19', 'V1500012534:20'], ['три года', '01.07.2026', 'пересмотрено']),
    'training_exceptions_and_electronic_journal': ('ls_training', ['V1500012665:6', 'V1500012665:61', 'V1500012665:62', 'V1500012665:71'], ['перемещение', 'освобожд', 'эцп']),
    'electrical_deputy_exception_not_blanket_exemption': ('ls_electrical_roles', ['V1500010949:4'], ['10 ква', 'замещающ', 'не общее освобождение']),
    'electrical_work_and_key_return_exceptions': ('ls_electrical_room_access', ['V1500010889:26', 'V1500010889:27'], ['не запирать', 'следующего рабочего дня', 'денежному сейфу']),
}
for name, (rid, required_specs, tokens) in sentinels.items():
    t = topic_map[rid]
    text = json.dumps(t, ensure_ascii=False).lower()
    check(name, set(required_specs) <= specs(t) and all(token in text for token in tokens))

gap = topic_map['short_absence_screen']
check('x28_gap_retained_in_procedure_matrix_and_summary',
      gap['procedure_type'] == 'unresolved_requirement_check'
      and gap['universal_immediate_lock_obligation_confirmed'] is False
      and gap['final_violation_from_short_absence_alone_allowed'] is False
      and next(r for r in rows if r['rule_id'] == 'short_absence_screen')['expansion_status'] == 'expanded_with_applicability_gap'
      and summary['short_absence_immediate_lock_gap_closed'] is False)
check('no_bank_approval_training_or_universal_legal_coverage_claim', all(summary[k] is False for k in
      ['new_video_labels_created', 'model_trained', 'bank_approved_internal_regulation', 'universal_legal_coverage_claimed']))
check('annotation_schema_preserves_unknown_and_requires_version_and_exception_review',
      {'not_observed', 'not_applicable', 'contradicted', 'satisfied'} == set(data['observation_statuses'])
      and {'rule_id', 'norm_version_at_event_date', 'exception_check', 'reviewer_confirmation'} <= set(data['expected_record_fields']))

broken_links = []
for file in [ROOT/'README.md', ROOT/'topics.md', ROOT/'topic_coverage.md']:
    for target in re.findall(r'\]\(([^)]+)\)', file.read_text(encoding='utf-8')):
        if urlsplit(target).scheme:
            continue
        path, _, anchor = unquote(target).partition('#')
        resolved = (file.parent/path).resolve() if path else file
        if not resolved.is_file():
            broken_links.append({'from':file.name, 'target':target, 'reason':'missing file'})
        elif anchor and f'<a id="{anchor}"></a>' not in resolved.read_text(encoding='utf-8'):
            broken_links.append({'from':file.name, 'target':target, 'reason':'missing explicit anchor'})
check('all_local_links_and_explicit_anchors_resolve', not broken_links, broken_links)
topics_md = (ROOT/'topics.md').read_text(encoding='utf-8')
check('all_80_topics_rendered_once_with_matching_headings', all(
    topics_md.count(f'<a id="{t["id"]}"></a>') == 1 and topics_md.count(f'## {t["rule_id"]} — ') == 1 for t in topics))
main_summary = read(BASE/'coverage_summary.json')
check('main_summary_updated_without_claiming_new_video_analysis',
      main_summary['reference_workflow_summary'] == summary
      and main_summary['rule_topics'] == 80 and main_summary['videos_in_inventory'] == 42
      and main_summary['positive_scenarios_in_inventory'] == 22
      and main_summary['new_video_review_performed'] is False
      and main_summary['employee_specific_short_absence_rule_confirmed'] is False)
check('main_corpus_validation_passes', all(read(BASE/'validation.json').values()))

artifact_files = ['definitions.json', 'topic_definitions.json', 'additional_references.json',
                  'workflows.json', 'summary.json', 'topics.md', 'README.md',
                  'topic_coverage.json', 'topic_coverage.csv', 'topic_coverage.md']
report = {
    'schema_version':'2.0', 'checked_at_utc':datetime.now(timezone.utc).isoformat(),
    'passed':all(checks.values()), 'checks':checks, 'details':details,
    'check_count':len(checks), 'passed_check_count':sum(checks.values()),
    'topic_count':len(topics), 'topic_step_count':summary['topic_step_count'],
    'conditional_record_count':summary['topic_exception_count'],
    'reference_count':len(refs), 'official_source_count':len(sources),
    'artifact_sha256':{name:digest(ROOT/name) for name in artifact_files},
    'scope':'Catalog coverage, verbatim quotation fidelity, saved-source integrity, exception retention, order graph consistency, cross-file agreement and local links.',
    'limitations':[
        '80/80 is completeness of expansion of the existing catalog, not all legislation or all confirmed violations.',
        'Condition classifications include evidence limits; these are not legal exemptions.',
        'The immediate screen-lock requirement for the cashier remains unconfirmed.',
        'Event dates, local policies and actual video behavior are not established by these checks.',
        'No independent legal approval, model training or accuracy evaluation is performed.'
    ],
    'reproduce':'python build_reference.py; python ../build_coverage.py; python verify_reference.py'
}
(ROOT/'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k:report[k] for k in ['passed','check_count','passed_check_count','topic_count','topic_step_count','conditional_record_count','reference_count']}, ensure_ascii=False, indent=2))
if not report['passed']:
    print('FAILED:', [name for name, passed in checks.items() if not passed])
    raise SystemExit(1)

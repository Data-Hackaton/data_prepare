"""Update the publication's review scope and refresh its SHA-256 inventory."""
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent/'data_prepare_publish'
DEST=REPO/'data/cvat/full-42'

def main():
    manifest_path=DEST/'manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    progress=manifest['qa_progress']
    assert progress['requested_review_frame_step']==5
    assert progress['requested_reviewed_frames']==progress['requested_review_target_frames']==8696
    assert progress['requested_review_screening_complete']
    stats=json.loads((ROOT/'qa_20261017/staged_corrections.json').read_text(encoding='utf-8'))
    patches=sum(x['patches_applied'] for x in stats)
    changed=sum(x['distinct_object_frames_changed'] for x in stats)
    tracks=manifest['exported_tracks']
    number=lambda n:f'{n:,}'.replace(',',' ')
    file=DEST/'README.md'
    old=file.read_text(encoding='utf-8')
    remainder=old[old.index('## Где находится полный датасет'):]
    intro=f'''# Все 42 видео: разметка CVAT и проверка с шагом 5

Обновление 18 октября 2026 года: все **42 видео** проверены по выбранному пользователем шагу **0, 5, 10, 15… и последний кадр**. Фактически просмотрено **8 696 / 8 696 выбранных кадров (100%)**. Журналы сохраняют номера кадров, области просмотра и пути изображений-доказательств; ранее проведённый сплошной просмотр также сохранён.

В CVAT внесено **{number(patches)} подтверждённых исправлений**, затронувших **{number(changed)} пар объект–кадр** в уникальных источниках. Исправлены классы и границы отражений, дубли людей и кистей, ложные детекции, видимые пропуски кистей и купюр, отдельные состояния предметов. X-47/X-48 наследуют правки своих побайтно идентичных X-4/X-5.

Сохранена полная плотность аннотаций: **43 230 исходных кадров, шаг 1, {number(tracks)} треков**. Новый шаг 5 относится к визуальной проверке. Все 42 задачи обратно прочитаны из CVAT; официальный проектный экспорт и 42 отдельных архива проверены на наличие аннотаций каждого исходного кадра. Пропущенных или удалённых исходных кадров нет.

Между просмотренными кадрами используется сопровождение или интерполяция по исходным timestamps. Это ассистированная разметка с завершённой выборочной проверкой; точность каждой границы на всех промежуточных кадрах не подтверждена. Неоднозначные случаи сохранены без неподтверждённых удалений. Поле `requested_review_screening_complete` относится к выполненному шагу 5; `review_completed=false` и `all_object_geometry_validated=false` сохраняют различие со сплошной проверкой каждого объекта.

- [Покрытие выбранных кадров по каждому видео](reports/qa_20261017/progress.json).
- [Все применённые исправления](../../../../cvat_tools/manual/dense_corrections.json), привязанные к неизменяемому baseline и кадрам-доказательствам.
- [Статистика применения](reports/qa_20261017/staged_corrections.json) и [автоматический аудит всех исходных кадров](reports/qa_20261017/audit_summary.json).
- `review-baseline.zip` содержит JSON до исправлений; `frame-audit.zip` — SHA-256 пикселей и технические признаки каждого кадра. Рендеринг и автоматические записи не засчитывались как визуальный просмотр.

'''
    file.write_text(intro+remainder,encoding='utf-8')
    top=REPO/'README.md'
    text=top.read_text(encoding='utf-8')
    replacement=(f'**Обновление 18.10.2026:** [разметка всех 42 видео](data/cvat/full-42/README.md) — '
        f'проверены **8 696 / 8 696 выбранных кадров с шагом 5 (100%)**, внесено {number(patches)} исправлений, '
        f'обновлены CVAT и общий/42 отдельных экспорта. Аннотации сохраняют все 43 230 исходных кадров с шагом 1 '
        f'({number(tracks)} треков); промежуточная геометрия сопровождается или интерполируется.')
    text,count=re.subn(r'^\*\*Новый результат 17\.10\.2026:\*\*[^\n]*',replacement,text,count=1,flags=re.M)
    assert count==1,'Publication intro changed; inspect before overwriting'
    top.write_text(text,encoding='utf-8')
    # README is part of the published inventory, so update after all content changes.
    for item in manifest['files']:
        path=REPO/item['path']
        item['bytes']=path.stat().st_size
        item['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(patches=patches,object_frames_changed=changed,tracks=tracks,
        requested_reviewed=8696,requested_total=8696)))

if __name__=='__main__':main()

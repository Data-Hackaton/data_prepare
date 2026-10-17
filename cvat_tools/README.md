# Скрипты обработки всех 42 видео

Результаты, состав датасета и порядок импорта: [data/cvat/full-42](../data/cvat/full-42/README.md).

Скрипты сохранены из локального запуска на Windows, Python 3.12, CVAT 2.79.0, NVIDIA RTX 4060. `requirements.lock.txt` фиксирует использованное окружение. Исходный рабочий каталог содержал рядом `data_prepare/`, `data/`, `cvat_local/` и `cvat_tools/`.

Для повторного запуска в такой структуре клонировать официальный CVAT с тегом v2.79.0 в `cvat_local/`, поместить эти инструменты в соседний `cvat_tools/`, а данные репозитория — в соседний `data/`. `Start-Cvat.ps1` использует Docker Compose и локальный override на `http://localhost:48080`. `bootstrap_and_upload.py --bootstrap` создаёт локальную учётную запись; пароль хранится только в локальном `admin.env`.

Основной порядок: `upload_full_videos.py` → `prepare_annotation_schema.py` → `frame_times.py` → `download_detector.py` → `convert_detector_fp32.py` → `track_videos.py` → `assemble_annotations.py X-1 ...` → `import_annotations.py X-1 ...` → `verify_cvat.py` → `export_annotations.py`. Существующие архивы `assembled.zip` и `automatic.zip` позволяют использовать уже рассчитанные результаты после распаковки в рабочий каталог; повторный расчёт модели для импорта готовой разметки не нужен.

`manual/overrides/*.json` заменяет соответствующие исходные записи scene-файлов. `deduplicate_people.py` консервативно устраняет подтверждённые двойные рамки. `check_people_dedup.py` и `check_annotation_pipeline.py` проверяют различение людей, границы треков, неизвестные состояния и реальные timestamps.

`revise_own_annotations.py` обновляет только собственные неизменённые объекты, сохраняет резервную копию и отказывается заменять пользовательские изменения. Серверные ID и localhost-ссылки в отчётах относятся к исходному запуску; после создания нового проекта сначала сформировать новый `cvat-full-project.json` через загрузку видео. Для простого переноса используйте отдельные CVAT ZIP из каталога результата.

Это автоматическое сопровождение с просмотренными ключевыми кадрами. Полная ручная проверка каждого кадра не выполнена; статус заданий оставлен `in progress`.

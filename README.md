# data_prepare

Подготовка датасета Datathon 26, эталон нормы и всё, что связано с CVAT. Видео и разметка в git не попадают; общий каталог данных — `../data` рядом с репозиториями, в контейнере это `/data`.

Всё запускается через docker compose из `infra`:

```sh
cd ../infra
docker compose --profile tools build data-prepare
docker compose --profile tools run --rm data-prepare <команда> [аргументы]
```

Сервис монтирует `../data` → `/data`, `../Datathon26` → `/raw` (только чтение), `reference/` → `/app/reference`, поэтому правки эталона не требуют пересборки. Тесты: `docker compose --profile tools run --rm data-prepare pytest -q -p no:cacheprovider tests`.

## prepare

```sh
docker compose --profile tools run --rm data-prepare prepare /raw/open.zip
```

Результат:
- `data/videos/X-<n>.mov` — имена приведены к ASCII: в исходнике X-1 и X-2 с латинской X, остальные с кириллической Х.
- `data/labels.csv`: `video, n, source_name, verdict, timecode_sec, sha256, duplicate_of, duration_sec, fps, width, height`.

Что в данных на 17.10:
- 42 видео, уникальных 40: 21 с нарушением, 19 без. Пропущены номера 6, 7, 9, 36, 41, 42.
- X-47 побайтно совпадает с X-4, но таймкод нарушения 68 с против 57 с — вопрос организаторам. X-48 = X-5, оба без нарушения.
- Все видео 464×848, 30 fps, 11–143 с.
- При разбиении на train/val дубли держать в одной части.

## contact-sheets

```sh
docker compose --profile tools run --rm data-prepare contact-sheets --verdict no_violation
docker compose --profile tools run --rm data-prepare contact-sheets --videos X-1 --fps 2 --crop 300:200:20:300 --suffix _desk
```

Раскадровки с таймкодами в `data/sheets/<video>_<стр>.jpg`, по умолчанию 1 кадр/с, 8×4 кадра на страницу.

## Эталон нормы → feature store

`reference/scenarios.yaml` — шаблоны сценариев: эталонный порядок действий (L2) и инварианты, кандидаты в правила decision:

| Сценарий | Видео | Эталонный порядок |
|---|---|---|
| `client_service` | X-3, X-5, X-19, X-35, X-37, X-39 | клиент вошёл → передал документ/деньги → кассир рассмотрел документ → деньги в машинку → сейф открыт → положил/взял → сейф закрыт → отдал клиенту → клиент ушёл |
| `collection` | X-14, X-16 | инкассатор вошёл → передал сумку → вскрытие сумки → пачки в машинку → сортировка → в сейф → сейф закрыт → ноутбук |
| `cash_handling` | X-8, X-10, X-21, X-31, X-43, X-45 | (из сейфа) → машинка → сортировка по стопкам |
| `leave_workplace` | X-12, X-23, X-25, X-27, X-29 | ноутбук → (в сейф) → сейф закрыт → (свет) → кассир ушёл |

Инварианты: сейф открыт не дольше 20 с (в эталоне 2–11 с, медиана 5); клиент и кассир уходят при закрытом сейфе; деньги идут в сейф после машинки.

`reference/actions.yaml` — журнал действий по 19 видео без нарушений, снят по раскадровкам (±1 с, `certain: false` — под вопросом). Описание сцен и открытые вопросы — `docs/norm.md` в рабочей папке.

```sh
docker compose --profile tools run --rm data-prepare reference-actions --check-only   # только проверка
docker compose --profile tools run --rm data-prepare reference-actions                # проверка + запись
```

Проверяется словарь, что видео без нарушений, таймкоды, порядок шагов по шаблону, обязательные шаги, инварианты. При ошибках store не пишется. Действия вне шаблона (например, `phone_call` в X-14) выводятся отдельно — это вопросы к валидации.

Feature store (`data/features/`, ключ — sha256 видео):

| Файл | Что |
|---|---|
| `<sha256>/actions.parquet` | `video, sha256, scene, scenario, instance, step, t_start, t_end, action, actor, object, target, certain, source` |
| `reference/scenarios.parquet` | шаги шаблонов по порядку |
| `reference/invariants.parquet` | инварианты с параметрами |
| `reference/summary.json` | покрытие шагов по экземплярам, длительность открытого сейфа |
| `index.parquet` | какие видео, таблицы и источники лежат в store |

`source=reference_r0` — эталон, снятый человеком. Действия, распознанные моделью, лягут рядом с другим `source`, и их можно сравнивать с эталоном построчно.

## Дальше

- `sample-frames` — ~800 кадров из чистых видео для разметки, split по видео.
- CVAT (поднят в `~/cvat`, http://localhost:48080): `labels.json`, `cvat_io upload/export`.
- `build-datasets` — CVAT COCO → датасеты YOLO и RF-DETR.
- `augment` — отражение, поворот, перспектива, кроп: проверка устойчивости к другому ракурсу.

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

Инварианты: сейф открыт не дольше 20 с (в эталоне 2–11 с, медиана 5); клиент и кассир уходят при закрытом сейфе; деньги идут в сейф после машинки; при клиенте пачку не делят и деньги при себе не оставляют; после ухода клиента деньги не пересчитывают; посторонние предметы на стол не кладут. По всему видео — «положил–убрал»: деньги прошлого клиента не лежат на столе, когда приходит следующий (`video_invariants`). У инварианта `norm` — id из `reference/norms.yaml` (Правила №231, пп. 12 и 20) или `null`.

`reference/violations.yaml` — каталог нарушений с журналами действий: X-1, X-4 (57 и 68 с, X-47 — копия X-4), X-38, X-34, X-40. Проверка требует, чтобы каждое нарушение ловилось правилом не дальше 3 с от размеченной секунды.

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
| `reference/invariants.parquet` | инварианты шаблонов и видео с параметрами и нормативом |
| `reference/norms.parquet` | нормативы: акт, пункт, URL, цитата |
| `reference/violations.parquet` | каталог нарушений: секунда, тип, норматив, какими правилами пойман |
| `reference/summary.json` | покрытие шагов по экземплярам, длительность открытого сейфа |
| `index.parquet` | какие видео, таблицы и источники лежат в store |

`source=reference_r0` — эталон, снятый человеком. Действия, распознанные моделью, лягут рядом с другим `source`, и их можно сравнивать с эталоном построчно.

## Кадры для детектора и CVAT

```sh
docker compose --profile tools run --rm data-prepare sample-frames            # → data/frames/r1/images, manifest.csv
docker compose --profile tools run --rm cv python -m cv.prelabel             # Grounding DINO → prelabels.coco.json, preview/
docker compose --profile tools run --rm data-prepare cvat-io upload           # проект datathon-l1-r1, задачи r1-train-NN / r1-val-NN
docker compose --profile tools run --rm data-prepare cvat-io export           # → data/frames/r1/cvat_export/*.zip (COCO 1.0)
```

`sample-frames`: 19 чистых видео, 2 кадра/с, бюджет 800 кадров делится пропорционально длительности; внутри видео — равные интервалы времени, в каждом кадр с наибольшим движением. Val — целиком X-19, X-27, X-37, X-45 (сцены A, B, D, E).

CVAT: http://localhost:48080, логин `admin`, пароль в `~/cvat/admin.env`. Схема меток — `cvat/labels.json`.

### Правила для валидатора

Каждый кадр открыть, исправить предразметку, переключить job в `completed`.

| Метка | Как размечать |
|---|---|
| `person` | человек в комнате, включая стоящего в открытой двери; бокс по всему видимому телу. `role` — по желанию (cashier/client/collector) |
| `reflection` | человек в стекле или за стеклом: отражение или в соседнем помещении. Предразметка ставит таким `person` — **сменить метку**, а не удалять бокс |
| `hand` | кисть без предплечья, у всех людей в комнате; руки в отражении не размечать |
| `banknotes` | пачка, стопка или отдельные купюры — один бокс на компактную группу; в руке, на столе, в лотке машинки |
| `id_card` | карточка документа с любой стороны |
| `cash_machine` | счётная машинка целиком |
| `safe` | сейф целиком вместе с открытой дверцей; `state` open/closed |
| `door` | стеклянная дверь в перегородке; `state` open/closed |
| `phone` | мобильный телефон; стационарный на столе не размечать |
| `bag` | зелёная инкассаторская сумка |
| `table` | рабочая поверхность кассового стола (деревянный стол кассира); белый стол на переднем плане — не размечать |
| `foreign_object` | посторонний предмет на кассовом столе: одежда, личная сумка, кружка; `kind` — clothing / personal_bag / cup / other. Одежда и сумка **на человеке** — не размечать |
| `computer` | ноутбук или монитор; `kind` — laptop / monitor; `screen` — active (рабочий экран) / locked (экран блокировки) / off (выключен или крышка закрыта) |

Стационарный телефон, бумаги и мебель (кроме кассового стола) не размечаем. Если предмет закрыт рукой больше чем наполовину — не размечать.

### Раунд r1b — кадры из видео с нарушениями

Одежда, личные сумки и чужие деньги на столе почти не встречаются в чистых видео, поэтому для них отдельный раунд:

```sh
docker compose --profile tools run --rm data-prepare sample-frames --round r1b --episodes X-4:57,68 X-38:33 X-34:13 X-40:17 --full X-40
docker compose --profile tools run --rm cv python -m cv.prelabel --round r1b
docker compose --profile tools run --rm data-prepare cvat-io upload --round r1b
```

129 кадров, все в train детектора. Видео X-4, X-38, X-34, X-40 после этого не годятся для честной оценки decision — она делается на остальных видео с нарушениями.

## Дальше

- `build-datasets` — CVAT COCO → датасеты YOLO и RF-DETR.
- `augment` — отражение, поворот, перспектива, кроп: проверка устойчивости к другому ракурсу.

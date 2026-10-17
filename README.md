# data_prepare

Подготовка датасета Datathon 26, эталон нормы и всё, что связано с CVAT. Данные лежат в этом репозитории в `data/`, в контейнерах это `/data`.

**Данные хакатона используются только внутри команды:** репозиторий приватный, публиковать и выкладывать видео наружу нельзя (FAQ организаторов). Тестовые видео жюри сюда не попадают.

| Путь | Что |
|---|---|
| `data/videos/X-<n>.mov`, `data/labels.csv` | обучающие видео (ASCII-имена) и разметка организаторов |
| `data/sheets/` | раскадровки с таймкодами |
| `data/frames/r1/`, `data/frames/r1b/` | кадры для детектора (`images/`, `manifest.csv`), предразметка `prelabels.coco.json`, выгрузка CVAT `cvat_export/*.zip` (COCO 1.0) |
| `data/cvat/datathon-l1-r1.zip`, `data/cvat/datathon-l1-r1b.zip` | полные бэкапы проектов CVAT: CVAT → Projects → **Create from backup** |
| `data/features/` | feature store: журналы действий, события, каталог нарушений |
| `data/NBRK_*.md` | тексты Правил НБРК №14 и №231 |

Не хранятся (см. `.gitignore`): `data/cache/` — веса моделей, скачиваются при первом запуске; `data/runs/` — прогоны обучения; `data/datasets/` — пересобираются `build-datasets`.

Выгрузки CVAT на 17.10 15:09 — предразметка Grounding DINO **до** ручной валидации; после валидации повторить `cvat-io export` и `cvat-io backup` и закоммитить.

## Нормативная база и 80 эталонных процедур

В [reference/normative_coverage](reference/normative_coverage/README.md) добавлена исследованная база: 17 консолидированных государственных источников, 4 сохранённых исторических акта/поправки и 31 публичный PDF ForteBank. Источники США/Европы вынесены в отдельный сравнительный раздел и не устанавливают обязанности кассира по законодательству РК.

- [Все 80 процедур](reference/normative_coverage/reference_workflows/topics.md): 241 шаг, точные пункты, исполнители, применимость и доказательства.
- [Матрица 80/80](reference/normative_coverage/reference_workflows/topic_coverage.md): исходные ссылки каждой темы сохранены.
- [JSON для интеграции](reference/normative_coverage/reference_workflows/workflows.json): 187 ссылок, полные цитаты и 116 условных записей (исключения, допустимые варианты, ветки и ограничения).
- [Проверка](reference/normative_coverage/reference_workflows/validation.json) и [воспроизводимая сборка](reference/normative_coverage/PUBLISHING.md).

Это нормативная основа для разметки и проверки. Её добавление не подключает автоматически все 80 тем к существующему `reference-actions`/`sop_events` и не обучает модель. Для Х-28 требование немедленной блокировки именно рабочего места кассира остаётся неподтверждённым. Порядок чтения шагов не создаёт обязательной последовательности: зависимости до/после указаны отдельно.

В [таблице сопоставления 42 файлов](reference/normative_coverage/video_coverage.md) сохранены предварительные наблюдения, ссылки на нормы и ограничения прежней проверки. Таблица предназначена для приватного репозитория команды; она не является подтверждением всех нарушений. При нормативной пересборке видео не обрабатываются.

Всё запускается через docker compose из `infra`:

```sh
cd ../infra
docker compose --profile tools build data-prepare
docker compose --profile tools run --rm data-prepare <команда> [аргументы]
```

Сервис монтирует `data/` → `/data`, `../Datathon26` → `/raw` (только чтение, нужен только для `prepare`), `reference/` → `/app/reference`, поэтому правки эталона не требуют пересборки. Тесты: `docker compose --profile tools run --rm data-prepare pytest -q -p no:cacheprovider tests`.

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

События (`<sha256>/events.parquet`, `reference/events_report.md`): каждое действие журнала сверяется с процедурой (подход NVIDIA SOP Monitoring Blueprints — упорядоченные шаги, пропуски, порядок, действия вне процедуры) и правилами и получает статус:

| Статус | Когда |
|---|---|
| `expected` — ожидаемое | шаг процедуры на своём месте, правила не сработали |
| `warning` — предупреждение | не по порядку, вне процедуры, пропущен обязательный шаг (событие `missing_step`), правило без норматива |
| `violation` — нарушение | правило с нормативом или с `severity: violation` (подтверждённое нарушение) |

Итог видео — самый тяжёлый статус. Проверка требует: у чистых видео нет нарушений, у видео из каталога итог — нарушение. Копия отчёта — `reference/events_report.md` в этом репозитории.

`source=reference_r0` — эталон, снятый человеком. Действия, распознанные моделью, лягут рядом с другим `source`, и их можно сравнивать с эталоном построчно.

## Процедуры как конечные автоматы

L3 (`src/data_prepare/sop_fsm.py`) — автоматы `transitions` по шаблонам `reference/scenarios.yaml`:
- **процедура** — указатель по шагам: переход вперёд на первый подходящий шаг, «не по порядку», «вне шаблона»;
- **инварианты** — `Forbidden`, `ForbiddenAfter`, `Before`, `MaxDuration`;
- **на видео** — `DeskCarryover`.

`reference-actions` и сервис работают на них. Старые `check_instance`/`check_video` в `reference_actions.py` — эталон для `tests/test_sop_fsm.py`: на всех журналах результат одинаковый.

Схемы процедур, экземпляров и сцены — [`docs/procedures.md`](docs/procedures.md), mermaid. Генерирует `computer-vision`: `python -m decision.fsm --diagrams`.

## Предразметка целых видео для CVAT

`data/cvat/prelabels-video-yolo.zip` содержит по файлу `X-n.xml` на каждое из 42 видео (копии X-47 и X-48 тоже). Формат «CVAT for video 1.1»: предсказания YOLO26s (4 кадра/с) в виде треков с ключевыми кадрами, номера кадров исходные (30 кадров/с).
- Люди — треки с ролью (`cashier`, `client`, `unknown`).
- Остальные классы связаны по классу и перекрытию.

Импорт:
1. Создать задачу в CVAT из того же `X-n.mov`: шаг кадров 1, начальный кадр 0, метки из `cvat/labels.json`.
2. Actions → Upload annotations → «CVAT 1.1» → `X-n.xml`.

Разметчик правит, а не рисует с нуля. Самые слабые классы детектора — `banknotes`, `id_card`, `phone`, `bag`.

Пересборка: `docker compose --profile tools run --rm cv python -m cv.export_cvat --detector yolo` (из `infra`, нужен кэш L1 `cv.infer`).

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
| `ignore_zone` | «заклеенное» стекло: стеклянная стена, дверь, окно, где отражаются люди и предметы. Один бокс на кадр, по всей стеклянной области; `kind` — glass / window / other. Внутри зоны мелкие предметы не размечаем (кроме лежащих на кассовом столе), людей — `reflection`, кроме входящих в дверь |

Предразметка ставит `ignore_zone` сама: стекло ищется на 6 кадрах видео, берётся медиана (камера неподвижна). Внутри зоны она уже выбросила мелкие предметы не на столе и переименовала людей целиком в стекле в `reflection`; валидатору остаётся поправить границу зоны и спорных людей у двери. Детектор учится находить `ignore_zone` как класс, поэтому на новом ракурсе стекло найдётся без ручной настройки, а decision отбрасывает всё, что внутри.

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

# События по видео: сверка с эталонной процедурой

Статусы: **ожидаемое** — шаг процедуры на своём месте; **предупреждение** — отклонение без подтверждённого норматива; **нарушение** — сработало правило с нормативом или подтверждённое как нарушение. Источник событий — эталонный журнал (`reference_r0`); `?` — наблюдение под вопросом.

| Видео | Разметка | Итог сверки | Ожидаемых | Предупреждений | Нарушений |
|---|---|---|---|---|---|
| X-1 | нарушение (22 с) | нарушение | 7 | 0 | 2 |
| X-3 | норма | ожидаемое | 4 | 0 | 0 |
| X-4 | нарушение (57 с, 68 с) | нарушение | 5 | 1 | 3 |
| X-5 | норма | ожидаемое | 13 | 0 | 0 |
| X-8 | норма | ожидаемое | 7 | 0 | 0 |
| X-10 | норма | ожидаемое | 4 | 0 | 0 |
| X-12 | норма | ожидаемое | 4 | 0 | 0 |
| X-14 | норма | предупреждение | 9 | 1 | 0 |
| X-16 | норма | ожидаемое | 3 | 0 | 0 |
| X-19 | норма | ожидаемое | 12 | 0 | 0 |
| X-21 | норма | ожидаемое | 4 | 0 | 0 |
| X-23 | норма | ожидаемое | 3 | 0 | 0 |
| X-25 | норма | ожидаемое | 5 | 0 | 0 |
| X-27 | норма | ожидаемое | 5 | 0 | 0 |
| X-29 | норма | ожидаемое | 2 | 0 | 0 |
| X-31 | норма | ожидаемое | 2 | 0 | 0 |
| X-34 | нарушение (13 с) | нарушение | 3 | 0 | 1 |
| X-35 | норма | ожидаемое | 7 | 0 | 0 |
| X-37 | норма | ожидаемое | 3 | 0 | 0 |
| X-38 | нарушение (33 с) | нарушение | 2 | 0 | 1 |
| X-39 | норма | ожидаемое | 14 | 0 | 0 |
| X-40 | нарушение (17 с) | нарушение | 2 | 0 | 2 |
| X-43 | норма | ожидаемое | 3 | 0 | 0 |
| X-45 | норма | ожидаемое | 3 | 0 | 0 |

## X-1 — нарушение (сцена A)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:01.0 | клиент: person_enter | ожидаемое | client_service #1 · шаг 1 |  |
| 0:05.5–0:06.5 | клиент: give id_card → cashier | ожидаемое | client_service #1 · шаг 2 |  |
| 0:07.0–0:08.0 | кассир: inspect id_card | ожидаемое | client_service #1 · шаг 3 |  |
| 0:09.5–0:10.5 | клиент: give banknotes → cashier | ожидаемое | client_service #1 · шаг 4 |  |
| 0:14.0–0:15.0 | кассир: put banknotes → cash_machine | ожидаемое | client_service #1 · шаг 5 |  |
| 0:19.0–0:19.8 | кассир: take banknotes → cash_machine | ожидаемое | client_service #1 · шаг 6 |  |
| 0:20.8–0:21.8 | кассир: split_bundle banknotes | **нарушение** | client_service #1 | forbidden:split_bundle, out_of_template |
| 0:22.0–0:23.0 | кассир: give banknotes → client | ожидаемое | client_service #1 · шаг 15 |  |
| 0:23.0–0:25.8 | кассир: keep banknotes | **нарушение** | client_service #1 | forbidden:keep, out_of_template |

## X-3 — ожидаемое (сцена A)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:02.0 | клиент: person_enter | ожидаемое | client_service #1 · шаг 1 |  |
| 0:07.0 | клиент: give id_card → cashier ? | ожидаемое | client_service #1 · шаг 2 |  |
| 0:09.0–0:15.0 | кассир: inspect id_card ? | ожидаемое | client_service #1 · шаг 3 |  |
| 0:17.0–0:18.0 | кассир: put banknotes → cash_machine ? | ожидаемое | client_service #1 · шаг 5 |  |

## X-4 — нарушение (сцена A)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:44.0–0:47.0 | кассир: use_laptop ? | ожидаемое | client_service #1 · шаг 9 |  |
| 0:47.5–0:48.5 | кассир: give document → client ? | ожидаемое | client_service #1 · шаг 15 |  |
| 0:48.0 | кассир: put banknotes → desk ? | **предупреждение** | client_service #1 · шаг 7 | order |
| 0:50.0–0:53.0 | клиент: person_leave | ожидаемое | client_service #1 · шаг 16 |  |
| 0:56.5 | клиент: person_enter | **нарушение** | client_service #2 · шаг 1 | desk_carryover:banknotes · Правила №231, п.20 |
| 1:01.0 | клиент: give id_card → cashier | ожидаемое | client_service #2 · шаг 2 |  |
| 1:01.5–1:03.0 | кассир: inspect id_card | ожидаемое | client_service #2 · шаг 3 |  |
| 1:04.5–1:05.5 | клиент: give banknotes → cashier | **нарушение** | client_service #2 · шаг 4 | desk_carryover:banknotes · Правила №231, п.20 |
| 1:06.0 | кассир: put banknotes → desk | **нарушение** | client_service #2 · шаг 7 | desk_carryover:banknotes · Правила №231, п.20 |

## X-5 — ожидаемое (сцена A)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:02.0 | клиент: person_enter | ожидаемое | client_service #1 · шаг 1 |  |
| 0:07.0 | клиент: give id_card → cashier ? | ожидаемое | client_service #1 · шаг 2 |  |
| 0:08.0–0:15.0 | кассир: inspect id_card | ожидаемое | client_service #1 · шаг 3 |  |
| 0:25.0 | кассир: put banknotes → cash_machine ? | ожидаемое | client_service #1 · шаг 5 |  |
| 0:32.0–0:44.0 | кассир: use_laptop ? | ожидаемое | client_service #1 · шаг 9 |  |
| 0:46.0 | кассир: safe_open | ожидаемое | client_service #1 · шаг 11 |  |
| 0:47.0–0:51.0 | кассир: take banknotes → safe ? | ожидаемое | client_service #1 · шаг 13 |  |
| 0:52.0 | кассир: safe_close | ожидаемое | client_service #1 · шаг 14 |  |
| 0:54.0 | кассир: give banknotes → client ? | ожидаемое | client_service #1 · шаг 15 |  |
| 0:56.0 | клиент: person_leave | ожидаемое | client_service #1 · шаг 16 |  |
| 1:01.0 | клиент: person_enter | ожидаемое | client_service #2 · шаг 1 |  |
| 1:09.0 | клиент: give id_card → cashier ? | ожидаемое | client_service #2 · шаг 2 |  |
| 1:10.0–1:11.0 | кассир: inspect id_card ? | ожидаемое | client_service #2 · шаг 3 |  |

## X-8 — ожидаемое (сцена B)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:01.0–0:04.0 | кассир: put banknotes → cash_machine | ожидаемое | cash_handling #1 · шаг 5 |  |
| 0:08.0–0:17.0 | кассир: sort_banknotes ? | ожидаемое | cash_handling #1 · шаг 6 |  |
| 0:19.0 | кассир: safe_open | ожидаемое | cash_handling #2 · шаг 2 |  |
| 0:20.0–0:23.0 | кассир: take banknotes → safe ? | ожидаемое | cash_handling #2 · шаг 3 |  |
| 0:24.0 | кассир: safe_close | ожидаемое | cash_handling #2 · шаг 4 |  |
| 0:28.0–0:29.0 | кассир: put banknotes → cash_machine | ожидаемое | cash_handling #2 · шаг 5 |  |
| 0:32.0–0:37.0 | кассир: paperwork | ожидаемое | cash_handling #2 · шаг 7 |  |

## X-10 — ожидаемое (сцена B)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:01.0–0:02.0 | кассир: put banknotes → cash_machine | ожидаемое | cash_handling #1 · шаг 5 |  |
| 0:03.0–0:06.0 | кассир: sort_banknotes ? | ожидаемое | cash_handling #1 · шаг 6 |  |
| 0:07.0 | кассир: put banknotes → cash_machine | ожидаемое | cash_handling #2 · шаг 5 |  |
| 0:08.0–0:15.0 | кассир: sort_banknotes ? | ожидаемое | cash_handling #2 · шаг 6 |  |

## X-12 — ожидаемое (сцена B)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:00.0–0:09.0 | кассир: use_laptop | ожидаемое | leave_workplace #1 · шаг 1 |  |
| 0:25.0–0:31.0 | кассир: safe_close ? | ожидаемое | leave_workplace #1 · шаг 5 |  |
| 0:32.0 | кассир: lights_off | ожидаемое | leave_workplace #1 · шаг 7 |  |
| 0:37.0 | кассир: person_leave | ожидаемое | leave_workplace #1 · шаг 8 |  |

## X-14 — предупреждение (сцена B)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:00.0–0:31.0 | кассир: open_bag | ожидаемое | collection #1 · шаг 4 |  |
| 0:28.0–0:33.0 | кассир: take banknotes → bag | ожидаемое | collection #1 · шаг 5 |  |
| 0:34.0–0:39.0 | кассир: put bag → safe_top | ожидаемое | collection #1 · шаг 6 |  |
| 0:43.0 | кассир: phone_call ? | **предупреждение** | collection #1 | out_of_template |
| 0:45.0–0:47.0 | кассир: put banknotes → cash_machine | ожидаемое | collection #1 · шаг 7 |  |
| 0:48.0–1:51.0 | кассир: sort_banknotes | ожидаемое | collection #1 · шаг 8 |  |
| 1:55.0 | кассир: safe_open | ожидаемое | collection #1 · шаг 9 |  |
| 2:02.0–2:06.0 | кассир: put banknotes → safe | ожидаемое | collection #1 · шаг 10 |  |
| 2:06.0 | кассир: safe_close | ожидаемое | collection #1 · шаг 11 |  |
| 2:08.0–2:22.0 | кассир: use_laptop | ожидаемое | collection #1 · шаг 12 |  |

## X-16 — ожидаемое (сцена A)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:03.0 | инкассатор: person_enter | ожидаемое | collection #1 · шаг 1 |  |
| 0:08.0–0:17.0 | инкассатор: give bag → cashier | ожидаемое | collection #1 · шаг 2 |  |
| 0:09.0–0:15.0 | кассир: inspect document ? | ожидаемое | collection #1 · шаг 3 |  |

## X-19 — ожидаемое (сцена A)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:02.0 | клиент: person_enter | ожидаемое | client_service #1 · шаг 1 |  |
| 0:07.0 | клиент: give id_card → cashier ? | ожидаемое | client_service #1 · шаг 2 |  |
| 0:09.0–0:11.0 | кассир: inspect id_card | ожидаемое | client_service #1 · шаг 3 |  |
| 0:13.0–0:14.0 | кассир: put banknotes → cash_machine ? | ожидаемое | client_service #1 · шаг 5 |  |
| 0:24.0–0:33.0 | кассир: use_laptop | ожидаемое | client_service #1 · шаг 9 |  |
| 0:37.0 | кассир: safe_open | ожидаемое | client_service #1 · шаг 11 |  |
| 0:38.0–0:40.0 | кассир: take banknotes → safe ? | ожидаемое | client_service #1 · шаг 13 |  |
| 0:41.0 | кассир: safe_close | ожидаемое | client_service #1 · шаг 14 |  |
| 0:42.0 | кассир: give banknotes → client ? | ожидаемое | client_service #1 · шаг 15 |  |
| 0:43.0 | клиент: person_leave | ожидаемое | client_service #1 · шаг 16 |  |
| 0:49.0 | клиент: person_enter | ожидаемое | client_service #2 · шаг 1 |  |
| 0:54.0 | клиент: give id_card → cashier ? | ожидаемое | client_service #2 · шаг 2 |  |

## X-21 — ожидаемое (сцена B)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:00.0 | кассир: safe_open ? | ожидаемое | cash_handling #1 · шаг 2 |  |
| 0:01.0–0:06.0 | кассир: take banknotes → safe | ожидаемое | cash_handling #1 · шаг 3 |  |
| 0:07.0 | кассир: safe_close | ожидаемое | cash_handling #1 · шаг 4 |  |
| 0:11.0–0:19.0 | кассир: put banknotes → cash_machine | ожидаемое | cash_handling #1 · шаг 5 |  |

## X-23 — ожидаемое (сцена B)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:00.0–0:04.0 | кассир: use_laptop | ожидаемое | leave_workplace #1 · шаг 1 |  |
| 0:06.0–0:11.0 | кассир: safe_close ? | ожидаемое | leave_workplace #1 · шаг 5 |  |
| 0:12.0 | кассир: person_leave | ожидаемое | leave_workplace #1 · шаг 8 |  |

## X-25 — ожидаемое (сцена B)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:00.0–0:03.0 | кассир: paperwork | ожидаемое | leave_workplace #1 · шаг 2 |  |
| 0:08.0 | кассир: safe_open | ожидаемое | leave_workplace #1 · шаг 3 |  |
| 0:09.0–0:12.0 | кассир: put document → safe ? | ожидаемое | leave_workplace #1 · шаг 4 |  |
| 0:19.0–0:23.0 | кассир: safe_close | ожидаемое | leave_workplace #1 · шаг 5 |  |
| 0:24.0 | кассир: person_leave | ожидаемое | leave_workplace #1 · шаг 8 |  |

## X-27 — ожидаемое (сцена B)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:00.0–0:08.0 | кассир: use_laptop ? | ожидаемое | leave_workplace #1 · шаг 1 |  |
| 0:12.0 | кассир: safe_open | ожидаемое | leave_workplace #1 · шаг 3 |  |
| 0:13.0 | кассир: put document → safe ? | ожидаемое | leave_workplace #1 · шаг 4 |  |
| 0:14.0–0:18.0 | кассир: safe_close | ожидаемое | leave_workplace #1 · шаг 5 |  |
| 0:19.0 | кассир: person_leave | ожидаемое | leave_workplace #1 · шаг 8 |  |

## X-29 — ожидаемое (сцена B)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:00.0–0:06.0 | кассир: use_laptop | ожидаемое | leave_workplace #1 · шаг 1 |  |
| 0:08.0 | кассир: person_leave | ожидаемое | leave_workplace #1 · шаг 8 |  |

## X-31 — ожидаемое (сцена C)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:02.0 | кассир: person_enter | ожидаемое | cash_handling #1 · шаг 1 |  |
| 0:17.0–0:23.0 | кассир: put banknotes → cash_machine | ожидаемое | cash_handling #1 · шаг 5 |  |

## X-34 — нарушение (сцена D)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:03.0 | клиент: person_enter | ожидаемое | client_service #1 · шаг 1 |  |
| 0:06.5–0:07.5 | клиент: give banknotes → cashier | ожидаемое | client_service #1 · шаг 4 |  |
| 0:12.0–0:14.0 | клиент: person_leave | ожидаемое | client_service #1 · шаг 16 |  |
| 0:12.5–0:15.5 | кассир: put banknotes → cash_machine | **нарушение** | client_service #1 · шаг 5 | forbidden_after:put, order · Правила №231, п.20 |

## X-35 — ожидаемое (сцена D)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:01.0 | клиент: person_enter | ожидаемое | client_service #1 · шаг 1 |  |
| 0:07.0 | клиент: give banknotes → cashier ? | ожидаемое | client_service #1 · шаг 4 |  |
| 0:11.0–0:21.0 | кассир: put banknotes → cash_machine | ожидаемое | client_service #1 · шаг 5 |  |
| 0:42.0 | кассир: safe_open | ожидаемое | client_service #1 · шаг 11 |  |
| 0:43.0–0:46.0 | кассир: put banknotes → safe | ожидаемое | client_service #1 · шаг 12 |  |
| 0:47.0 | кассир: safe_close | ожидаемое | client_service #1 · шаг 14 |  |
| 0:50.0 | клиент: person_leave | ожидаемое | client_service #1 · шаг 16 |  |

## X-37 — ожидаемое (сцена D)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:02.0 | клиент: person_enter | ожидаемое | client_service #1 · шаг 1 |  |
| 0:08.0 | клиент: give banknotes → cashier ? | ожидаемое | client_service #1 · шаг 4 |  |
| 0:11.0–0:13.0 | кассир: put banknotes → cash_machine | ожидаемое | client_service #1 · шаг 5 |  |

## X-38 — нарушение (сцена D)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:24.0 | кассир: put banknotes → desk ? | ожидаемое | client_service #1 · шаг 7 |  |
| 0:26.0–0:28.0 | клиент: person_leave | ожидаемое | client_service #1 · шаг 16 |  |
| 0:32.0–0:34.0 | клиент: person_enter | **нарушение** | client_service #2 · шаг 1 | desk_carryover:banknotes · Правила №231, п.20 |

## X-39 — ожидаемое (сцена D)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:01.0 | клиент: person_enter | ожидаемое | client_service #1 · шаг 1 |  |
| 0:07.0 | клиент: give banknotes → cashier | ожидаемое | client_service #1 · шаг 4 |  |
| 0:11.0–0:19.0 | кассир: put banknotes → cash_machine | ожидаемое | client_service #1 · шаг 5 |  |
| 0:29.0 | кассир: safe_open | ожидаемое | client_service #1 · шаг 11 |  |
| 0:30.0–0:32.0 | кассир: put banknotes → safe | ожидаемое | client_service #1 · шаг 12 |  |
| 0:33.0 | кассир: safe_close | ожидаемое | client_service #1 · шаг 14 |  |
| 0:34.0 | клиент: person_leave | ожидаемое | client_service #1 · шаг 16 |  |
| 0:45.0 | клиент: person_enter | ожидаемое | client_service #2 · шаг 1 |  |
| 0:50.0 | клиент: give banknotes → cashier ? | ожидаемое | client_service #2 · шаг 4 |  |
| 0:56.0–0:58.0 | кассир: put banknotes → cash_machine | ожидаемое | client_service #2 · шаг 5 |  |
| 1:06.0 | кассир: safe_open | ожидаемое | client_service #2 · шаг 11 |  |
| 1:07.0–1:09.0 | кассир: put banknotes → safe | ожидаемое | client_service #2 · шаг 12 |  |
| 1:11.0 | кассир: safe_close | ожидаемое | client_service #2 · шаг 14 |  |
| 1:13.0 | клиент: person_leave | ожидаемое | client_service #2 · шаг 16 |  |

## X-40 — нарушение (сцена E)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:02.0–0:04.0 | кассир: person_enter | ожидаемое | cash_handling #1 · шаг 1 |  |
| 0:14.0 | кассир: put foreign_object → desk | **нарушение** | cash_handling #1 | forbidden:put, out_of_template · Правила №231, п.12 |
| 0:16.0 | кассир: put foreign_object → desk ? | **нарушение** | cash_handling #1 | forbidden:put, out_of_template · Правила №231, п.12 |
| 0:20.0–0:23.0 | кассир: put banknotes → cash_machine ? | ожидаемое | cash_handling #1 · шаг 5 |  |

## X-43 — ожидаемое (сцена E)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:00.0–0:02.0 | кассир: put banknotes → cash_machine | ожидаемое | cash_handling #1 · шаг 5 |  |
| 0:07.0 | кассир: put banknotes → cash_machine | ожидаемое | cash_handling #1 · шаг 5 |  |
| 0:12.0–0:22.0 | кассир: sort_banknotes | ожидаемое | cash_handling #1 · шаг 6 |  |

## X-45 — ожидаемое (сцена E)

| Время | Событие | Статус | Сценарий · шаг | Правило · норматив |
|---|---|---|---|---|
| 0:01.0–0:03.0 | кассир: put banknotes → cash_machine | ожидаемое | cash_handling #1 · шаг 5 |  |
| 0:09.0–0:11.0 | кассир: put banknotes → cash_machine | ожидаемое | cash_handling #1 · шаг 5 |  |
| 0:13.0–0:31.0 | кассир: sort_banknotes | ожидаемое | cash_handling #1 · шаг 6 |  |

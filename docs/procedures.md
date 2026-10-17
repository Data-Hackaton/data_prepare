# Процедуры и автоматы L2/L3

Сгенерировано `python -m decision.fsm --diagrams` из `reference/scenarios.yaml` и `decision/fsm.py`.

## Обслуживание клиента — приём или выдача наличных (`client_service`)

Обязательные шаги: 1_person_enter_client.

```mermaid
stateDiagram-v2
  direction LR
  state "s1_person_enter_client" as s1_person_enter_client
  state "s2_give_client_cashier" as s2_give_client_cashier
  state "s3_inspect_cashier" as s3_inspect_cashier
  state "s4_give_client_cashier" as s4_give_client_cashier
  state "s5_put_cashier_cash_machine" as s5_put_cashier_cash_machine
  state "s6_take_cashier_cash_machine" as s6_take_cashier_cash_machine
  state "s7_put_cashier_desk" as s7_put_cashier_desk
  state "s8_take_cashier_desk" as s8_take_cashier_desk
  state "s9_use_laptop_cashier" as s9_use_laptop_cashier
  state "s10_paperwork_cashier" as s10_paperwork_cashier
  state "s11_safe_open_cashier" as s11_safe_open_cashier
  state "s12_put_cashier_safe" as s12_put_cashier_safe
  state "s13_take_cashier_safe" as s13_take_cashier_safe
  state "s14_safe_close_cashier" as s14_safe_close_cashier
  state "s15_give_cashier_client" as s15_give_cashier_client
  state "s16_person_leave_client" as s16_person_leave_client
  s1_person_enter_client --> s2_give_client_cashier: далее
  s1_person_enter_client --> s3_inspect_cashier: далее
  s1_person_enter_client --> s4_give_client_cashier: далее
  s1_person_enter_client --> s5_put_cashier_cash_machine: далее
  s1_person_enter_client --> s6_take_cashier_cash_machine: далее
  s1_person_enter_client --> s7_put_cashier_desk: далее
  s1_person_enter_client --> s8_take_cashier_desk: далее
  s1_person_enter_client --> s9_use_laptop_cashier: далее
  s1_person_enter_client --> s10_paperwork_cashier: далее
  s1_person_enter_client --> s11_safe_open_cashier: далее
  s1_person_enter_client --> s12_put_cashier_safe: далее
  s1_person_enter_client --> s13_take_cashier_safe: далее
  s1_person_enter_client --> s14_safe_close_cashier: далее
  s1_person_enter_client --> s15_give_cashier_client: далее
  s1_person_enter_client --> s16_person_leave_client: далее
  s2_give_client_cashier --> s3_inspect_cashier: далее
  s2_give_client_cashier --> s4_give_client_cashier: далее
  s2_give_client_cashier --> s5_put_cashier_cash_machine: далее
  s2_give_client_cashier --> s6_take_cashier_cash_machine: далее
  s2_give_client_cashier --> s7_put_cashier_desk: далее
  s2_give_client_cashier --> s8_take_cashier_desk: далее
  s2_give_client_cashier --> s9_use_laptop_cashier: далее
  s2_give_client_cashier --> s10_paperwork_cashier: далее
  s2_give_client_cashier --> s11_safe_open_cashier: далее
  s2_give_client_cashier --> s12_put_cashier_safe: далее
  s2_give_client_cashier --> s13_take_cashier_safe: далее
  s2_give_client_cashier --> s14_safe_close_cashier: далее
  s2_give_client_cashier --> s15_give_cashier_client: далее
  s2_give_client_cashier --> s16_person_leave_client: далее
  s3_inspect_cashier --> s4_give_client_cashier: далее
  s3_inspect_cashier --> s5_put_cashier_cash_machine: далее
  s3_inspect_cashier --> s6_take_cashier_cash_machine: далее
  s3_inspect_cashier --> s7_put_cashier_desk: далее
  s3_inspect_cashier --> s8_take_cashier_desk: далее
  s3_inspect_cashier --> s9_use_laptop_cashier: далее
  s3_inspect_cashier --> s10_paperwork_cashier: далее
  s3_inspect_cashier --> s11_safe_open_cashier: далее
  s3_inspect_cashier --> s12_put_cashier_safe: далее
  s3_inspect_cashier --> s13_take_cashier_safe: далее
  s3_inspect_cashier --> s14_safe_close_cashier: далее
  s3_inspect_cashier --> s15_give_cashier_client: далее
  s3_inspect_cashier --> s16_person_leave_client: далее
  s4_give_client_cashier --> s5_put_cashier_cash_machine: далее
  s4_give_client_cashier --> s6_take_cashier_cash_machine: далее
  s4_give_client_cashier --> s7_put_cashier_desk: далее
  s4_give_client_cashier --> s8_take_cashier_desk: далее
  s4_give_client_cashier --> s9_use_laptop_cashier: далее
  s4_give_client_cashier --> s10_paperwork_cashier: далее
  s4_give_client_cashier --> s11_safe_open_cashier: далее
  s4_give_client_cashier --> s12_put_cashier_safe: далее
  s4_give_client_cashier --> s13_take_cashier_safe: далее
  s4_give_client_cashier --> s14_safe_close_cashier: далее
  s4_give_client_cashier --> s15_give_cashier_client: далее
  s4_give_client_cashier --> s16_person_leave_client: далее
  s5_put_cashier_cash_machine --> s6_take_cashier_cash_machine: далее
  s5_put_cashier_cash_machine --> s7_put_cashier_desk: далее
  s5_put_cashier_cash_machine --> s8_take_cashier_desk: далее
  s5_put_cashier_cash_machine --> s9_use_laptop_cashier: далее
  s5_put_cashier_cash_machine --> s10_paperwork_cashier: далее
  s5_put_cashier_cash_machine --> s11_safe_open_cashier: далее
  s5_put_cashier_cash_machine --> s12_put_cashier_safe: далее
  s5_put_cashier_cash_machine --> s13_take_cashier_safe: далее
  s5_put_cashier_cash_machine --> s14_safe_close_cashier: далее
  s5_put_cashier_cash_machine --> s15_give_cashier_client: далее
  s5_put_cashier_cash_machine --> s16_person_leave_client: далее
  s6_take_cashier_cash_machine --> s7_put_cashier_desk: далее
  s6_take_cashier_cash_machine --> s8_take_cashier_desk: далее
  s6_take_cashier_cash_machine --> s9_use_laptop_cashier: далее
  s6_take_cashier_cash_machine --> s10_paperwork_cashier: далее
  s6_take_cashier_cash_machine --> s11_safe_open_cashier: далее
  s6_take_cashier_cash_machine --> s12_put_cashier_safe: далее
  s6_take_cashier_cash_machine --> s13_take_cashier_safe: далее
  s6_take_cashier_cash_machine --> s14_safe_close_cashier: далее
  s6_take_cashier_cash_machine --> s15_give_cashier_client: далее
  s6_take_cashier_cash_machine --> s16_person_leave_client: далее
  s7_put_cashier_desk --> s8_take_cashier_desk: далее
  s7_put_cashier_desk --> s9_use_laptop_cashier: далее
  s7_put_cashier_desk --> s10_paperwork_cashier: далее
  s7_put_cashier_desk --> s11_safe_open_cashier: далее
  s7_put_cashier_desk --> s12_put_cashier_safe: далее
  s7_put_cashier_desk --> s13_take_cashier_safe: далее
  s7_put_cashier_desk --> s14_safe_close_cashier: далее
  s7_put_cashier_desk --> s15_give_cashier_client: далее
  s7_put_cashier_desk --> s16_person_leave_client: далее
  s8_take_cashier_desk --> s9_use_laptop_cashier: далее
  s8_take_cashier_desk --> s10_paperwork_cashier: далее
  s8_take_cashier_desk --> s11_safe_open_cashier: далее
  s8_take_cashier_desk --> s12_put_cashier_safe: далее
  s8_take_cashier_desk --> s13_take_cashier_safe: далее
  s8_take_cashier_desk --> s14_safe_close_cashier: далее
  s8_take_cashier_desk --> s15_give_cashier_client: далее
  s8_take_cashier_desk --> s16_person_leave_client: далее
  s9_use_laptop_cashier --> s10_paperwork_cashier: далее
  s9_use_laptop_cashier --> s11_safe_open_cashier: далее
  s9_use_laptop_cashier --> s12_put_cashier_safe: далее
  s9_use_laptop_cashier --> s13_take_cashier_safe: далее
  s9_use_laptop_cashier --> s14_safe_close_cashier: далее
  s9_use_laptop_cashier --> s15_give_cashier_client: далее
  s9_use_laptop_cashier --> s16_person_leave_client: далее
  s10_paperwork_cashier --> s11_safe_open_cashier: далее
  s10_paperwork_cashier --> s12_put_cashier_safe: далее
  s10_paperwork_cashier --> s13_take_cashier_safe: далее
  s10_paperwork_cashier --> s14_safe_close_cashier: далее
  s10_paperwork_cashier --> s15_give_cashier_client: далее
  s10_paperwork_cashier --> s16_person_leave_client: далее
  s11_safe_open_cashier --> s12_put_cashier_safe: далее
  s11_safe_open_cashier --> s13_take_cashier_safe: далее
  s11_safe_open_cashier --> s14_safe_close_cashier: далее
  s11_safe_open_cashier --> s15_give_cashier_client: далее
  s11_safe_open_cashier --> s16_person_leave_client: далее
  s12_put_cashier_safe --> s13_take_cashier_safe: далее
  s12_put_cashier_safe --> s14_safe_close_cashier: далее
  s12_put_cashier_safe --> s15_give_cashier_client: далее
  s12_put_cashier_safe --> s16_person_leave_client: далее
  s13_take_cashier_safe --> s14_safe_close_cashier: далее
  s13_take_cashier_safe --> s15_give_cashier_client: далее
  s13_take_cashier_safe --> s16_person_leave_client: далее
  s14_safe_close_cashier --> s15_give_cashier_client: далее
  s14_safe_close_cashier --> s16_person_leave_client: далее
  s15_give_cashier_client --> s16_person_leave_client: далее
  [*] --> s1_person_enter_client
```

## Инкассация — передача и вскрытие сумок (`collection`)

Обязательные шаги: .

```mermaid
stateDiagram-v2
  direction LR
  state "s1_person_enter_collector" as s1_person_enter_collector
  state "s2_give_collector_cashier" as s2_give_collector_cashier
  state "s3_inspect_cashier" as s3_inspect_cashier
  state "s4_open_bag_cashier" as s4_open_bag_cashier
  state "s5_take_cashier_bag" as s5_take_cashier_bag
  state "s6_put_cashier_safe_top" as s6_put_cashier_safe_top
  state "s7_put_cashier_cash_machine" as s7_put_cashier_cash_machine
  state "s8_sort_banknotes_cashier" as s8_sort_banknotes_cashier
  state "s9_safe_open_cashier" as s9_safe_open_cashier
  state "s10_put_cashier_safe" as s10_put_cashier_safe
  state "s11_safe_close_cashier" as s11_safe_close_cashier
  state "s12_use_laptop_cashier" as s12_use_laptop_cashier
  s1_person_enter_collector --> s2_give_collector_cashier: далее
  s1_person_enter_collector --> s3_inspect_cashier: далее
  s1_person_enter_collector --> s4_open_bag_cashier: далее
  s1_person_enter_collector --> s5_take_cashier_bag: далее
  s1_person_enter_collector --> s6_put_cashier_safe_top: далее
  s1_person_enter_collector --> s7_put_cashier_cash_machine: далее
  s1_person_enter_collector --> s8_sort_banknotes_cashier: далее
  s1_person_enter_collector --> s9_safe_open_cashier: далее
  s1_person_enter_collector --> s10_put_cashier_safe: далее
  s1_person_enter_collector --> s11_safe_close_cashier: далее
  s1_person_enter_collector --> s12_use_laptop_cashier: далее
  s2_give_collector_cashier --> s3_inspect_cashier: далее
  s2_give_collector_cashier --> s4_open_bag_cashier: далее
  s2_give_collector_cashier --> s5_take_cashier_bag: далее
  s2_give_collector_cashier --> s6_put_cashier_safe_top: далее
  s2_give_collector_cashier --> s7_put_cashier_cash_machine: далее
  s2_give_collector_cashier --> s8_sort_banknotes_cashier: далее
  s2_give_collector_cashier --> s9_safe_open_cashier: далее
  s2_give_collector_cashier --> s10_put_cashier_safe: далее
  s2_give_collector_cashier --> s11_safe_close_cashier: далее
  s2_give_collector_cashier --> s12_use_laptop_cashier: далее
  s3_inspect_cashier --> s4_open_bag_cashier: далее
  s3_inspect_cashier --> s5_take_cashier_bag: далее
  s3_inspect_cashier --> s6_put_cashier_safe_top: далее
  s3_inspect_cashier --> s7_put_cashier_cash_machine: далее
  s3_inspect_cashier --> s8_sort_banknotes_cashier: далее
  s3_inspect_cashier --> s9_safe_open_cashier: далее
  s3_inspect_cashier --> s10_put_cashier_safe: далее
  s3_inspect_cashier --> s11_safe_close_cashier: далее
  s3_inspect_cashier --> s12_use_laptop_cashier: далее
  s4_open_bag_cashier --> s5_take_cashier_bag: далее
  s4_open_bag_cashier --> s6_put_cashier_safe_top: далее
  s4_open_bag_cashier --> s7_put_cashier_cash_machine: далее
  s4_open_bag_cashier --> s8_sort_banknotes_cashier: далее
  s4_open_bag_cashier --> s9_safe_open_cashier: далее
  s4_open_bag_cashier --> s10_put_cashier_safe: далее
  s4_open_bag_cashier --> s11_safe_close_cashier: далее
  s4_open_bag_cashier --> s12_use_laptop_cashier: далее
  s5_take_cashier_bag --> s6_put_cashier_safe_top: далее
  s5_take_cashier_bag --> s7_put_cashier_cash_machine: далее
  s5_take_cashier_bag --> s8_sort_banknotes_cashier: далее
  s5_take_cashier_bag --> s9_safe_open_cashier: далее
  s5_take_cashier_bag --> s10_put_cashier_safe: далее
  s5_take_cashier_bag --> s11_safe_close_cashier: далее
  s5_take_cashier_bag --> s12_use_laptop_cashier: далее
  s6_put_cashier_safe_top --> s7_put_cashier_cash_machine: далее
  s6_put_cashier_safe_top --> s8_sort_banknotes_cashier: далее
  s6_put_cashier_safe_top --> s9_safe_open_cashier: далее
  s6_put_cashier_safe_top --> s10_put_cashier_safe: далее
  s6_put_cashier_safe_top --> s11_safe_close_cashier: далее
  s6_put_cashier_safe_top --> s12_use_laptop_cashier: далее
  s7_put_cashier_cash_machine --> s8_sort_banknotes_cashier: далее
  s7_put_cashier_cash_machine --> s9_safe_open_cashier: далее
  s7_put_cashier_cash_machine --> s10_put_cashier_safe: далее
  s7_put_cashier_cash_machine --> s11_safe_close_cashier: далее
  s7_put_cashier_cash_machine --> s12_use_laptop_cashier: далее
  s8_sort_banknotes_cashier --> s9_safe_open_cashier: далее
  s8_sort_banknotes_cashier --> s10_put_cashier_safe: далее
  s8_sort_banknotes_cashier --> s11_safe_close_cashier: далее
  s8_sort_banknotes_cashier --> s12_use_laptop_cashier: далее
  s9_safe_open_cashier --> s10_put_cashier_safe: далее
  s9_safe_open_cashier --> s11_safe_close_cashier: далее
  s9_safe_open_cashier --> s12_use_laptop_cashier: далее
  s10_put_cashier_safe --> s11_safe_close_cashier: далее
  s10_put_cashier_safe --> s12_use_laptop_cashier: далее
  s11_safe_close_cashier --> s12_use_laptop_cashier: далее
  [*] --> s1_person_enter_collector
```

## Работа с наличностью без посетителей (`cash_handling`)

Обязательные шаги: 5_put_cashier_cash_machine.

```mermaid
stateDiagram-v2
  direction LR
  state "s1_person_enter_cashier" as s1_person_enter_cashier
  state "s2_safe_open_cashier" as s2_safe_open_cashier
  state "s3_take_cashier_safe" as s3_take_cashier_safe
  state "s4_safe_close_cashier" as s4_safe_close_cashier
  state "s5_put_cashier_cash_machine" as s5_put_cashier_cash_machine
  state "s6_sort_banknotes_cashier" as s6_sort_banknotes_cashier
  state "s7_paperwork_cashier" as s7_paperwork_cashier
  state "s8_use_laptop_cashier" as s8_use_laptop_cashier
  s1_person_enter_cashier --> s2_safe_open_cashier: далее
  s1_person_enter_cashier --> s3_take_cashier_safe: далее
  s1_person_enter_cashier --> s4_safe_close_cashier: далее
  s1_person_enter_cashier --> s5_put_cashier_cash_machine: далее
  s2_safe_open_cashier --> s3_take_cashier_safe: далее
  s2_safe_open_cashier --> s4_safe_close_cashier: далее
  s2_safe_open_cashier --> s5_put_cashier_cash_machine: далее
  s3_take_cashier_safe --> s4_safe_close_cashier: далее
  s3_take_cashier_safe --> s5_put_cashier_cash_machine: далее
  s4_safe_close_cashier --> s5_put_cashier_cash_machine: далее
  s5_put_cashier_cash_machine --> s6_sort_banknotes_cashier: далее
  s5_put_cashier_cash_machine --> s7_paperwork_cashier: далее
  s5_put_cashier_cash_machine --> s8_use_laptop_cashier: далее
  s6_sort_banknotes_cashier --> s7_paperwork_cashier: далее
  s6_sort_banknotes_cashier --> s8_use_laptop_cashier: далее
  s7_paperwork_cashier --> s8_use_laptop_cashier: далее
  [*] --> s1_person_enter_cashier
```

## Уход кассира с рабочего места (`leave_workplace`)

Обязательные шаги: 8_person_leave_cashier.

```mermaid
stateDiagram-v2
  direction LR
  state "s1_use_laptop_cashier" as s1_use_laptop_cashier
  state "s2_paperwork_cashier" as s2_paperwork_cashier
  state "s3_screen_lock_cashier" as s3_screen_lock_cashier
  state "s4_safe_open_cashier" as s4_safe_open_cashier
  state "s5_put_cashier_safe" as s5_put_cashier_safe
  state "s6_safe_close_cashier" as s6_safe_close_cashier
  state "s7_lights_off_cashier" as s7_lights_off_cashier
  state "s8_person_leave_cashier" as s8_person_leave_cashier
  s1_use_laptop_cashier --> s2_paperwork_cashier: далее
  s1_use_laptop_cashier --> s3_screen_lock_cashier: далее
  s1_use_laptop_cashier --> s4_safe_open_cashier: далее
  s1_use_laptop_cashier --> s5_put_cashier_safe: далее
  s1_use_laptop_cashier --> s6_safe_close_cashier: далее
  s1_use_laptop_cashier --> s7_lights_off_cashier: далее
  s1_use_laptop_cashier --> s8_person_leave_cashier: далее
  s2_paperwork_cashier --> s3_screen_lock_cashier: далее
  s2_paperwork_cashier --> s4_safe_open_cashier: далее
  s2_paperwork_cashier --> s5_put_cashier_safe: далее
  s2_paperwork_cashier --> s6_safe_close_cashier: далее
  s2_paperwork_cashier --> s7_lights_off_cashier: далее
  s2_paperwork_cashier --> s8_person_leave_cashier: далее
  s3_screen_lock_cashier --> s4_safe_open_cashier: далее
  s3_screen_lock_cashier --> s5_put_cashier_safe: далее
  s3_screen_lock_cashier --> s6_safe_close_cashier: далее
  s3_screen_lock_cashier --> s7_lights_off_cashier: далее
  s3_screen_lock_cashier --> s8_person_leave_cashier: далее
  s4_safe_open_cashier --> s5_put_cashier_safe: далее
  s4_safe_open_cashier --> s6_safe_close_cashier: далее
  s4_safe_open_cashier --> s7_lights_off_cashier: далее
  s4_safe_open_cashier --> s8_person_leave_cashier: далее
  s5_put_cashier_safe --> s6_safe_close_cashier: далее
  s5_put_cashier_safe --> s7_lights_off_cashier: далее
  s5_put_cashier_safe --> s8_person_leave_cashier: далее
  s6_safe_close_cashier --> s7_lights_off_cashier: далее
  s6_safe_close_cashier --> s8_person_leave_cashier: далее
  s7_lights_off_cashier --> s8_person_leave_cashier: далее
  [*] --> s1_use_laptop_cashier
```

## Экземпляры процедуры (L2)

```mermaid
stateDiagram-v2
  direction LR
  state "none" as none
  state "cash_handling" as cash_handling
  state "client_service" as client_service
  state "leave_workplace" as leave_workplace
  none --> client_service: client_enters
  none --> cash_handling: other
  cash_handling --> client_service: client_enters
  cash_handling --> leave_workplace: cashier_leaves
  client_service --> client_service: client_enters
  client_service --> leave_workplace: cashier_leaves
  leave_workplace --> client_service: client_enters
  leave_workplace --> cash_handling: cashier_back
  [*] --> none
```

## Сцена: client (`client_present`)

```mermaid
stateDiagram-v2
  direction LR
  state "absent" as absent
  state "present" as present
  absent --> present: client_present
  present --> absent: client_present
  [*] --> absent
```

## Сцена: visitors (`visitors`)

```mermaid
stateDiagram-v2
  direction LR
  state "none" as none
  state "one" as one
  state "many" as many
  none --> one: visitors
  none --> many: visitors
  one --> none: visitors
  one --> many: visitors
  many --> none: visitors
  many --> one: visitors
  [*] --> none
```

## Сцена: pair (`two_at_cashier`)

```mermaid
stateDiagram-v2
  direction LR
  state "alone" as alone
  state "two" as two
  alone --> two: two_at_cashier
  two --> alone: two_at_cashier
  [*] --> alone
```

## Сцена: cashier (`cashier_present`)

```mermaid
stateDiagram-v2
  direction LR
  state "away" as away
  state "here" as here
  away --> here: cashier_present
  here --> away: cashier_present
  [*] --> away
```

## Сцена: desk_money (`money_on_desk`)

```mermaid
stateDiagram-v2
  direction LR
  state "empty" as empty
  state "placed" as placed
  empty --> placed: money_on_desk
  placed --> empty: money_on_desk
  [*] --> empty
```

## Сцена: machine_money (`money_in_machine`)

```mermaid
stateDiagram-v2
  direction LR
  state "empty" as empty
  state "placed" as placed
  empty --> placed: money_in_machine
  placed --> empty: money_in_machine
  [*] --> empty
```

## Сцена: desk_foreign (`foreign_on_desk`)

```mermaid
stateDiagram-v2
  direction LR
  state "empty" as empty
  state "placed" as placed
  empty --> placed: foreign_on_desk
  placed --> empty: foreign_on_desk
  [*] --> empty
```

## Сцена: desk_bag (`bag_on_desk`)

```mermaid
stateDiagram-v2
  direction LR
  state "empty" as empty
  state "placed" as placed
  empty --> placed: bag_on_desk
  placed --> empty: bag_on_desk
  [*] --> empty
```

## Сцена: bundles (`bundles_at_cashier`)

```mermaid
stateDiagram-v2
  direction LR
  state "none" as none
  state "one" as one
  state "two" as two
  none --> one: bundles_at_cashier
  none --> two: bundles_at_cashier
  one --> none: bundles_at_cashier
  one --> two: bundles_at_cashier
  two --> none: bundles_at_cashier
  two --> one: bundles_at_cashier
  [*] --> none
```

## Сцена: screen (`screen_on`)

```mermaid
stateDiagram-v2
  direction LR
  state "off" as off
  state "on" as on
  off --> on: screen_on
  on --> off: screen_on
  [*] --> off
```

## Сцена: phone (`phone_at_head`)

```mermaid
stateDiagram-v2
  direction LR
  state "down" as down
  state "at_head" as at_head
  down --> at_head: phone_at_head
  at_head --> down: phone_at_head
  [*] --> down
```

# PROGRESS.md - трекер прогресса

---

## ТЕКУЩИЙ СТАТУС

**Дата обновления:** 2026-05-29  
**Фаза:** Bootstrap / стабилизация Render и ЕСКЛП  
**Последняя задача:** фиксация состояния обвязки и исправление join в `esklp_lookup.py`  
**Статус сборки:** все задачи из `feature_list.json` в `passing`  
**Статус тестов:** `pytest` проходит, `ruff check .` чистый  
**Render:** `GET https://new-agent-pk.onrender.com/health` возвращает `{"status":"ok"}`  

---

## ЧТО СДЕЛАНО

### Базовая инфраструктура

- Инициализирован проект `new-agent-pk` и GitHub-репозиторий.
- Собран FastAPI backend с `/health`, `/tools/*`, OpenAPI-схемой и Render-конфигурацией.
- Добавлены зависимости, тестовый контур `pytest`, линтер `ruff`, `.env.example`, `render.yaml`.
- Реальный `data/pk_list.json` подключён локально и используется сервисом, но не должен коммититься без отдельного разрешения.

### Инструменты агента

- `POST /tools/parse_offer` парсит КП из текста или Excel.
- `POST /tools/search_esklp` ищет кандидатов ЕСКЛП по торговому наименованию.
- `POST /tools/match_pk` сопоставляет SKU с ПK, использует fuzzy-логику и LLM fallback.
- `POST /tools/upload_base` загружает базовую Excel-выгрузку.
- `POST /tools/build_excel` собирает итоговый Excel и отдаёт `download_url`.
- `GET/POST /tools/pk_list` возвращает статический список ПK.

### ЕСКЛП

- `EsklpLookup` читает упрощённые Excel-файлы ЕСКЛП с одной строкой заголовков, без `skiprows`.
- `tn_smnn_*.xlsx` читается по колонкам: `Торговое наименование`, `Код узла СМНН`, `Стандартизованное МНН`, `Стандартизованная лекарственная форма`, дозировка.
- `esklp_smnn_*.xlsx` читается по колонкам: `Код узла СМНН`, `Наименование ФТГ`, `код АТХ`, `Наименование`.
- `esklp_tn` и `esklp_smnn` связываются через нормализованный ключ СМНН, устойчивый к пробелам, неразрывным пробелам и суффиксу `.0`.
- `search_esklp` возвращает `mnn`, `form`, `dosage`, `smnn_code`, `atx_code`, `atx_name`, `ftg_name`, `score`.
- Проверка на реальной локальной папке `esklp_20260507_excel_00001`: 22 236 строк, `Ибупрофен` находится с `M01AE01`, `Ибупрофен`, `НПВП`.

### Render/admin endpoints

- Добавлен `POST /admin/upload_esklp` с защитой `X-Admin-Token` из `ADMIN_TOKEN`.
- Добавлен `POST /admin/reload_esklp`: сразу возвращает `{"status":"loading"}`, загрузка идёт в фоне.
- Добавлен `GET /admin/esklp_status`: показывает `ESKLP_DIR`, список `.xlsx`, `esklp_tn_rows`, `status`, `error`, `sample`.
- `EsklpLookup` закреплён как singleton на процесс; reload атомарно подменяет экземпляр после успешной загрузки.
- Скрипт `scripts/upload_esklp.py` загружает локальные `.xlsx` из `ESKLP_DIR` на Render.

### Архитектурные решения

- `D-007` зафиксировано в `DECISIONS.md`: в LLM-контекст для `match_pk` передаются АТХ и ФТГ из `esklp_smnn`, чтобы различать препараты с одинаковым веществом в разных областях.

---

## ЧТО ЗАБЛОКИРОВАНО

Нет активных блокеров в `feature_list.json`.

Операционный риск: после каждого деплоя Render нужно вызвать `/admin/reload_esklp`, если файлы ЕСКЛП уже загружены на диск, чтобы singleton подхватил актуальные данные.

---

## ПРОВЕРКИ

```powershell
python -m pytest
ruff check .
Invoke-WebRequest -UseBasicParsing https://new-agent-pk.onrender.com/health -TimeoutSec 30
```

Последний подтверждённый локальный результат:

- `python -m pytest` - `16 passed`
- `ruff check .` - `All checks passed`
- Render `/health` - `{"status":"ok"}`

---

## СЛЕДУЮЩИЙ ШАГ

После деплоя текущего коммита на Render:

1. Вызвать `POST /admin/reload_esklp`.
2. Проверить `GET /admin/esklp_status`: `status=ready`, `esklp_tn_rows=22236`, `sample` заполнен.
3. Проверить `POST /tools/search_esklp` с `{"trade_name":"Ибупрофен"}`.

---

## ЖУРНАЛ СЕССИЙ

| Сессия | Дата | Завершено | Итог |
|---|---|---|---|
| 1 | 2026-05-27/28 | F-001, F-002, F-101, F-102, F-201, F-203, F-202, F-205, F-204, F-301, F-302, F-401 | Локальная цепочка готова, D-007 добавил АТХ/ФТГ |
| 2 | 2026-05-29 | F-003, F-402, admin upload/reload/status, Render upload flow, simplified ESKLP parser | Render health проверен, ЕСКЛП грузится асинхронно, lookup singleton, parser читает упрощённые Excel по заголовкам |
| 3 | 2026-05-29 | Обновление обвязки, фиксация статусов, fix join в `esklp_lookup.py` | Все задачи в `passing`; join по СМНН нормализован |

---

*Обновлять в конце каждой сессии и перед сменой архитектурного состояния.*

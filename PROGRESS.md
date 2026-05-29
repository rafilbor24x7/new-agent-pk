# PROGRESS.md - трекер прогресса

---

## ТЕКУЩИЙ СТАТУС

**Дата обновления:** 2026-05-29  
**Фаза:** завершение спринта / эксплуатационная документация  
**Последняя задача:** финальное обновление обвязки и README перед завершением спринта  
**Статус сборки:** все задачи из `feature_list.json` в `passing`  
**Статус тестов:** `python -m pytest` проходит, `ruff check .` чистый  
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

- `EsklpLookup` читает упрощённые `.xlsx` файлы ЕСКЛП с одной строкой заголовков, без `skiprows`.
- Чтение ЕСКЛП идёт через `pd.read_excel(..., engine="openpyxl", dtype=str)`.
- `tn_smnn_*.xlsx` читается по колонкам: `Торговое наименование`, `Код узла СМНН`, `Стандартизованное МНН`, `Стандартизованная лекарственная форма`, дозировка.
- `esklp_smnn_*.xlsx` читается по колонкам: `Код узла СМНН`, `Наименование ФТГ`, `код АТХ`, `Наименование`.
- `esklp_tn` и `esklp_smnn` связываются через нормализованный ключ СМНН, устойчивый к пробелам, неразрывным пробелам и суффиксу `.0`.
- `esklp_smnn` является необязательным: если он не загрузился, поиск всё равно работает по `tn_smnn`, а `atx_code`, `atx_name`, `ftg_name` возвращаются как `null`.
- Проверка на реальной локальной папке `esklp_20260507_excel_00001`: 22 236 строк, `Ибупрофен` находится с `M01AE01`, `Ибупрофен`, `НПВП`.

### Render/admin endpoints

- `POST /admin/upload_esklp` загружает `.xlsx` файлы ЕСКЛП на Render, защищён `X-Admin-Token`.
- `POST /admin/reload_esklp` сразу возвращает `{"status":"loading"}`, загрузка идёт в фоне.
- `GET /admin/esklp_status` показывает `ESKLP_DIR`, список `.xlsx`, `esklp_tn_rows`, `columns`, `status`, `error`, `sample`.
- `POST /admin/esklp_debug` показывает первые строки `esklp_tn`, SQL `LIKE`-совпадения и rapidfuzz-score для диагностики поиска.
- `EsklpLookup` закреплён как singleton на процесс; reload атомарно подменяет экземпляр после успешной загрузки.
- `scripts/upload_esklp.py` загружает локальные `.xlsx` из `ESKLP_DIR` на Render.

### Архитектурные решения

- `D-007` зафиксировано в `DECISIONS.md`: в LLM-контекст для `match_pk` передаются АТХ и ФТГ из `esklp_smnn`, чтобы различать препараты с одинаковым веществом в разных областях.

---

## ЧТО ЗАБЛОКИРОВАНО

Активных блокеров в `feature_list.json` нет.

Операционное условие: после деплоя или загрузки файлов ЕСКЛП на Render нужно вызвать `/admin/reload_esklp`, чтобы singleton подхватил актуальные данные.

Наблюдение: поиск по латинице вроде `Ibuprofen` может возвращать пустой список, если в ЕСКЛП торговые наименования лежат кириллицей. Для диагностики добавлен `/admin/esklp_debug`; отдельная задача на транслитерацию пока не заведена.

---

## ПРОВЕРКИ

```powershell
python -m pytest
ruff check .
Invoke-WebRequest -UseBasicParsing https://new-agent-pk.onrender.com/health -TimeoutSec 30
```

Последний подтверждённый локальный результат:

- `python -m pytest` - `19 passed`
- `ruff check .` - `All checks passed`
- Render `/health` - `{"status":"ok"}`

---

## ПЕРВЫЙ ЗАПУСК НА RENDER

1. Задать ENV-переменные на Render: `ADMIN_TOKEN`, `ESKLP_DIR`, `DEEPSEEK_API_KEY` при необходимости LLM.
2. Задать локально те же `ADMIN_TOKEN` и `ESKLP_DIR`, где `ESKLP_DIR` указывает на папку с `.xlsx` файлами ЕСКЛП.
3. Выполнить `python scripts/upload_esklp.py`.
4. Вызвать `POST https://new-agent-pk.onrender.com/admin/reload_esklp` с заголовком `X-Admin-Token`.
5. Проверить `GET /admin/esklp_status`: `status=ready`, `esklp_tn_rows=22236`, `sample` и `columns` заполнены.
6. Проверить `POST /tools/search_esklp` с `{"trade_name":"Ибупрофен"}`.

---

## ЖУРНАЛ СЕССИЙ

| Сессия | Дата | Завершено | Итог |
|---|---|---|---|
| 1 | 2026-05-27/28 | F-001, F-002, F-101, F-102, F-201, F-203, F-202, F-205, F-204, F-301, F-302, F-401 | Локальная цепочка готова, D-007 добавил АТХ/ФТГ |
| 2 | 2026-05-29 | F-003, F-402, admin upload/reload/status, Render upload flow, simplified ESKLP parser | Render health проверен, ЕСКЛП грузится асинхронно, lookup singleton |
| 3 | 2026-05-29 | Обновление обвязки, фиксация статусов, fix join в `esklp_lookup.py` | Все задачи в `passing`; join по СМНН нормализован |
| 4 | 2026-05-29 | openpyxl, optional `esklp_smnn`, status columns, `/admin/esklp_debug`, README | Спринт закрыт документацией первого запуска и диагностикой Render |

---

*Обновлять в конце каждой сессии и перед сменой архитектурного состояния.*

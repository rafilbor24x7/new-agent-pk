# PROGRESS.md — Трекер прогресса

---

## ТЕКУЩИЙ СТАТУС

**Фаза:** Bootstrap
**Последняя задача:** F-204 — POST /tools/build_excel
**Статус сборки:** ✅ verification_cmd F-204 прошёл (`PASSED`)
**Статус тестов:** ✅ `pytest` прошёл (8 passed), `ruff check .` чистый

---

## ЧТО СДЕЛАНО

### F-001 — Репозиторий, зависимости, структура папок

- Инициализирован git-репозиторий.
- Создана структура `app/`, `app/api/`, `app/services/`, `app/models/`, `app/db/`, `data/`, `tests/fixtures/` по `ARCHITECTURE.md`.
- Скопированы из `../agentKP` модули `parser_offer.py`, `normalizer.py`, `matcher.py`, `excel_builder.py`, `models/sku.py`.
- Созданы `requirements.txt`, `.gitignore`, `.env.example`, `render.yaml`, `pytest.ini`.
- Скопированы фикстуры `base_sample.xlsx` и `offer_sample.xlsx` в `tests/fixtures/`.
- Создана минимальная фикстура `tests/fixtures/esklp_test/tn_smnn_test.xlsx` на 5 строк.
- Реальный `pk_list.json` на 295 ПК скопирован локально в `data/pk_list.json`; файл не добавлялся в git без отдельного разрешения.
- Добавлен минимальный bootstrap-тест импортов зависимостей.

**Команды проверки:**

```powershell
pip install -r requirements.txt; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; python -c "import fastapi, pandas, openpyxl, duckdb, openai, rapidfuzz; print('OK')"
pytest
ruff check .
```

**Результат:** F-001 passing.

---


### F-002 — FastAPI backend, GET /health

- Проверен запуск `uvicorn app.main:app --port 8000`.
- `GET /health` возвращает `{"status":"ok"}`.
- `pytest` и `ruff check .` проходят.

**Результат:** F-002 passing.

### F-101 — Загрузка ЕСКЛП в DuckDB при старте

- Реализован `EsklpLookup`: читает `tn_smnn_*.xlsx` из `ESKLP_DIR`, пропускает 4 строки шапки, нормализует колонки `trade_name`, `mnn`, `form`, `dosage`, `smnn_code`.
- Данные загружаются в in-memory DuckDB таблицу `esklp_tn`.
- Поиск работает через `rapidfuzz.token_sort_ratio`, возвращает top-3 с `score`.
- Добавлены тестовые данные `data/esklp_test/tn_smnn_test.xlsx` и тест `tests/test_esklp_lookup.py`.

**Результат:** F-101 passing.

### F-102 — Загрузка списка 295 ПК из data/pk_list.json

- Добавлен сервис `app.services.pk_list.load_pk_list()` с Pydantic-валидацией `{tg, tk, pk}`.
- Подключён router `app.api.tools` в `app.main`.
- Реализован `GET /tools/pk_list`, возвращающий локальный список из 295 ПК.
- Реальный `data/pk_list.json` остаётся локальным и не коммитится.

**Результат:** F-102 passing.

### F-201 — POST /tools/search_esklp

- Добавлен Pydantic-вход `SearchEsklpRequest`.
- Реализован `POST /tools/search_esklp` поверх `EsklpLookup`.
- Endpoint возвращает список кандидатов с `mnn`, `form`, `dosage`, `score`.
- Добавлен тест инструмента через `TestClient`.

**Результат:** F-201 passing.

### F-203 — POST /tools/parse_offer

- Реализован `POST /tools/parse_offer` для JSON `{text}` и multipart `file`/`text`.
- Текстовый парсинг использует `parse_offer_text()` из скопированного модуля.
- Excel-парсинг использует `read_offer_excel()` и `extract_offer_skus()`.
- Добавлен тест парсинга текста через HTTP-инструмент.

**Результат:** F-203 passing.

### D-007 — ЕСКЛП АТХ/ФТГ для match_pk

- Зафиксировано архитектурное решение в `DECISIONS.md`.
- `EsklpLookup` дополнительно читает `esklp_smnn_*.xlsx`, выбирает рабочий лист `esklp_smnn_*` и загружает DuckDB-таблицу `esklp_smnn`.
- `esklp_tn` связывается с `esklp_smnn` по `smnn_code`; `search()` возвращает `atx_code`, `atx_name`, `ftg_name`.
- Добавлены тестовые фикстуры `esklp_smnn_test.xlsx` в `tests/fixtures/esklp_test/` и `data/esklp_test/`.
- `/tools/match_pk` принимает и передаёт LLM поля АТХ/ФТГ вместе с МНН, формой и дозировкой.

### F-202 — POST /tools/match_pk

- Добавлен сервис `pk_matcher.py` для подбора ПК по SKU и справочнику 295 ПК.
- Реализован `POST /tools/match_pk`.
- При высокой уверенности используется fuzzy/точное попадание, при низкой — `DeepSeekLLMClient` с полным списком ПК и классификацией ЕСКЛП.
- Тест покрывает лекарство с МНН, БАД без МНН и медизделие с mock LLM.

**Результат:** F-202 passing.

### F-205 — POST /tools/upload_base

- Добавлен in-memory store `app.services.base_store` для основной Excel-выгрузки.
- Реализован `POST /tools/upload_base`: multipart Excel → `{file_id, rows, columns_ok, missing_columns}`.
- Валидируются обязательные колонки базовой выгрузки.
- Добавлен HTTP-тест загрузки `tests/fixtures/base_sample.xlsx`.

**Результат:** F-205 passing.

### F-204 — POST /tools/build_excel

- Добавлен in-memory store `app.services.result_store` для собранных Excel-файлов.
- Реализован `POST /tools/build_excel`: `{base_file_id, matched_skus}` → `{download_url}`.
- Реализован `GET /tools/download/{file_id}` для скачивания результата.
- Сборка использует существующий `excel_builder.build_result_workbook_bytes()`.
- Добавлен тест загрузки базы, сборки Excel и скачивания валидного `.xlsx`.

**Результат:** F-204 passing.
## СЛЕДУЮЩИЙ ШАГ

**Задача:** F-301 — OpenAPI схема для /tools/*

**Что сделать:**`n1. Создать Web Service на Render.`n2. Подставить публичный `RENDER_URL`.`n3. Проверить `GET https://<RENDER_URL>/health`.

---

## БЛОКЕРЫ

| ID | Описание | Статус |
|---|---|---|
| B-001 | `pk_list.json` с реальными 295 ПК | ✅ Файл предоставлен локально, не коммитить без явного разрешения |
| B-002 | Реальные файлы ЕСКЛП | ✅ Папка предоставлена локально, не коммитить |
| B-003 | `DEEPSEEK_API_KEY` на Render | Нужно настроить до F-003 |
| B-004 | `RENDER_URL` | Подставить после деплоя F-003 |

---

## ЖУРНАЛ СЕССИЙ

| Сессия | Дата | Завершено | Начато | Итог |
|---|---|---|---|---|
| 1 | 2026-05-27/28 | F-001, F-002, F-101, F-102, F-201, F-203, F-202 | F-001 | Инструменты parse/search/match готовы, D-007 добавил АТХ/ФТГ, `pytest` зелёный, `ruff` чистый |

---

*Обновлять в конце каждой сессии*

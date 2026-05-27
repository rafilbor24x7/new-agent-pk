# PROGRESS.md — Трекер прогресса

---

## ТЕКУЩИЙ СТАТУС

**Фаза:** Bootstrap
**Последняя задача:** F-203 — POST /tools/parse_offer
**Статус сборки:** ✅ verification_cmd F-203 прошёл (`OK`)
**Статус тестов:** ✅ `pytest` прошёл, `ruff check .` чистый

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
## СЛЕДУЮЩИЙ ШАГ

**Задача:** F-202 — POST /tools/match_pk

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
| 1 | 2026-05-27 | F-001, F-002 | F-001 | Bootstrap F-001/F-002 завершён, `/health` проверен, `pytest` зелёный, `ruff` чистый |

---

*Обновлять в конце каждой сессии*

# AGENTS.md — Главный файл инструкций для агента

> Этот файл читается агентом ПЕРВЫМ в каждой сессии. Не удалять. Не сокращать.

---

## 1. ЧТО ЭТО ЗА ПРОЕКТ

**Название:** `new-agent-pk`
**Описание:** ReAct-агент для сопоставления SKU из КП производителей с товарными подкатегориями (ПК) аптечной сети. Backend предоставляет набор HTTP-инструментов, которые вызывает агент в Яндекс AI Studio через MCP. Никакого собственного UI — интерфейс живёт в Яндекс Студии.
**Тип:** REST API (набор инструментов для MCP-агента)

---

## 2. СТЕК И ОКРУЖЕНИЕ

**Язык / Runtime:** Python 3.11
**Основные зависимости:** FastAPI, uvicorn, pandas, openpyxl, duckdb, httpx, python-multipart, openai (DeepSeek-совместимый клиент), rapidfuzz, transliterate
**Менеджер пакетов:** pip + venv
**ОС и окружение:** Ubuntu 22.04 / Render (backend)

### Команды запуска
```
Установить зависимости : pip install -r requirements.txt
Запустить backend      : uvicorn app.main:app --reload --port 8000
Запустить тесты        : pytest
Линтер                 : ruff check .
```

---

## 3. АРХИТЕКТУРА

```
new-agent-pk/
├── app/
│   ├── main.py                  # FastAPI app, роутеры, CORS
│   ├── api/
│   │   └── tools.py             # /tools/* — все MCP-инструменты
│   ├── services/
│   │   ├── esklp_lookup.py      # поиск МНН по торговому названию в ЕСКЛП
│   │   ├── parser_offer.py      # парсинг КП (из старого проекта)
│   │   ├── normalizer.py        # нормализация наименований (из старого проекта)
│   │   ├── matcher.py           # скоринг SKU → ПК (из старого проекта)
│   │   ├── llm_client.py        # DeepSeek tool-use клиент
│   │   └── excel_builder.py     # сборка итогового Excel (из старого проекта)
│   ├── models/
│   │   └── sku.py               # SKUItem, MatchResult (из старого проекта)
│   └── db/
│       └── esklp.py             # DuckDB с таблицей esklp_tn (из ЕСКЛП)
├── data/
│   └── pk_list.json             # статичный список 295 ПК (ТГ→ТК→ПК)
├── tests/
│   └── fixtures/
│       ├── base_sample.xlsx     # тестовая основная выгрузка
│       └── offer_sample.xlsx    # тестовое КП
├── requirements.txt
└── render.yaml
```

**Ключевые архитектурные инварианты:**
- Каждый `/tools/*` эндпоинт делает ровно одно действие и возвращает JSON
- LLM не формирует Excel напрямую — только возвращает JSON
- Агент не рассчитывает производные показатели (ФМ, маржа и т.д.)
- ЕСКЛП загружается в DuckDB при старте сервиса, не при каждом запросе
- Список 295 ПК статичный, хранится в `data/pk_list.json`

---

## 4. ИНСТРУМЕНТЫ (MCP-эндпоинты)

Это главное отличие от старого проекта. Каждый эндпоинт — отдельный инструмент для агента в Яндекс Студии.

| Эндпоинт | Что делает | Входные данные | Выходные данные |
|---|---|---|---|
| `POST /tools/parse_offer` | Парсит КП (текст или Excel) → список SKU | text или file | List[SKUItem] |
| `POST /tools/search_esklp` | Ищет МНН по торговому названию в ЕСКЛП | trade_name | mnn, form, dosage |
| `POST /tools/match_pk` | Подбирает ПК из 295 по SKU + МНН | sku + mnn + form | pk, confidence, candidates |
| `POST /tools/clarify_sku` | Обновляет поля SKU после уточнения | sku_id, field, value | updated SKU |
| `POST /tools/build_excel` | Собирает итоговый Excel | List[matched SKU] | download_url |
| `GET /tools/pk_list` | Возвращает полный список 295 ПК | — | List[{tg, tk, pk}] |
| `GET /health` | Проверка доступности | — | {status: ok} |

---

## 5. ЖЁСТКИЕ ПРАВИЛА РАБОТЫ

### 5.1 WIP = 1
- Одновременно активной может быть только одна задача
- Нельзя начинать следующую пока текущая не в `passing`

### 5.2 Definition of Done
1. ✅ `ruff check .` — без ошибок
2. ✅ `pytest` — все тесты проходят
3. ✅ Команда верификации из feature_list.json выполнена
4. ✅ Код закоммичен

### 5.3 Запреты
- Не рефакторить код вне текущей задачи
- Не менять архитектуру без записи в DECISIONS.md
- Не коммитить файлы ЕСКЛП (`data/esklp_*/` в .gitignore)
- Не коммитить `data/pk_list.json` без явного указания — файл содержит бизнес-данные

### 5.4 Откуда брать код
Следующие файлы копируются из старого проекта (`../agentKP` или указанного пути) БЕЗ изменений, только если проходят тесты:
- `services/parser_offer.py`
- `services/normalizer.py`
- `services/matcher.py`
- `services/excel_builder.py`
- `models/sku.py`
- `tests/fixtures/`

---

## 6. ПРОТОКОЛ НАЧАЛА СЕССИИ (Clock-in)

1. Прочитать AGENTS.md
2. Прочитать PROGRESS.md
3. Прочитать feature_list.json — найти задачи `active` или `not_started`
4. **Если F-001 не в `passing`** — пропустить проверки, начать F-001
5. **Если F-001 в `passing`** — проверить `uvicorn` и `pytest`, при ошибках зафиксировать в PROGRESS.md
6. Начать работу

---

## 7. ПРОТОКОЛ ЗАВЕРШЕНИЯ СЕССИИ (Clock-out)

1. `pytest` — все зелёные
2. `ruff check .` — чисто
3. Обновить feature_list.json
4. Обновить PROGRESS.md
5. `git commit -m "[session] <описание>"`

---

## 8. СПЕЦИФИКА ПРОЕКТА

### 8.1 ЕСКЛП
- Файлы ЕСКЛП лежат локально в папке `data/esklp_*/`
- При старте сервиса `esklp_lookup.py` загружает `tn_smnn_*.xlsx` в DuckDB (in-memory)
- Путь к папке ЕСКЛП: ENV-переменная `ESKLP_DIR`
- Файлы ЕСКЛП НЕ коммитятся в git

### 8.2 Список ПК
- 295 подкатегорий, статичный, не меняется
- Хранится в `data/pk_list.json` как `[{"tg": "...", "tk": "...", "pk": "..."}]`
- Загружается в память при старте, не в БД
- Передаётся LLM целиком при каждом вызове `/tools/match_pk`

### 8.3 LLM
- Провайдер: DeepSeek
- Модель: `deepseek-chat`
- Base URL: `https://api.deepseek.com`
- Клиент: openai SDK с `base_url="https://api.deepseek.com"`
- ENV-переменная: `DEEPSEEK_API_KEY`
- Ответы всегда JSON, валидируются Pydantic

### 8.4 Confidence
- `>= 0.90` → auto_matched
- `0.65–0.89` → review_required (агент показывает кандидатов в чате)
- `< 0.65` → need_clarification (агент задаёт вопрос)

---

## 9. ССЫЛКИ

| Документ | Содержание |
|---|---|
| `ARCHITECTURE.md` | Детали модулей и схема данных |
| `PROGRESS.md` | Текущий прогресс |
| `DECISIONS.md` | Лог решений |
| `SPRINT_CONTRACT.md` | Контракт спринта |
| `feature_list.json` | Задачи |

---

*Версия: 1.0 | Проект: new-agent-pk*

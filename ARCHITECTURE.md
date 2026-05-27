# ARCHITECTURE.md — Архитектура new-agent-pk

---

## 1. ОБЩАЯ СХЕМА

```
Менеджер (Яндекс AI Studio — чат)
        ↓ пишет в чат КП или загружает файл
Агент в Яндекс Студии (YandexGPT / DeepSeek)
        ↓ вызывает инструменты через MCP
Render — FastAPI backend (new-agent-pk)
        ├── /tools/parse_offer      → парсинг КП
        ├── /tools/search_esklp     → МНН из ЕСКЛП
        ├── /tools/match_pk         → выбор ПК из 295
        ├── /tools/upload_base      → загрузка выгрузки
        ├── /tools/build_excel      → сборка Excel
        └── /tools/pk_list          → список 295 ПК
        ↓
DuckDB (in-memory) — ЕСКЛП (tn_smnn)
DeepSeek API        — LLM для match_pk и parse_offer
```

---

## 2. СТРУКТУРА ПАПОК

```
new-agent-pk/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── tools.py              # все /tools/* роуты
│   ├── services/
│   │   ├── esklp_lookup.py       # НОВЫЙ: поиск в ЕСКЛП
│   │   ├── parser_offer.py       # из agentKP
│   │   ├── normalizer.py         # из agentKP
│   │   ├── matcher.py            # из agentKP — доработан
│   │   ├── llm_client.py         # НОВЫЙ: tool-use формат
│   │   └── excel_builder.py      # из agentKP
│   ├── models/
│   │   └── sku.py                # из agentKP — расширен
│   └── db/
│       └── esklp.py              # DuckDB соединение
├── data/
│   ├── pk_list.json              # 295 ПК — заполняет заказчик
│   └── esklp_*/                  # НЕ коммитить (в .gitignore)
├── tests/
│   ├── fixtures/
│   │   ├── esklp_test/           # минимальный тест ЕСКЛП (5 строк)
│   │   ├── base_sample.xlsx
│   │   └── offer_sample.xlsx
│   ├── test_esklp_lookup.py
│   ├── test_tools.py
│   └── test_e2e.py
├── requirements.txt
├── render.yaml
├── .env.example
└── .gitignore
```

---

## 3. ОПИСАНИЕ МОДУЛЕЙ

### esklp_lookup.py — Поиск МНН по торговому названию
- **Что делает:** при старте загружает `tn_smnn_*.xlsx` из `ESKLP_DIR` в DuckDB, предоставляет `search(trade_name) → List[{mnn, form, dosage, score}]`
- **Алгоритм:** rapidfuzz `token_sort_ratio >= 75` по колонке `trade_name`
- **Важно:** skiprows=4 (шапка ЕСКЛП — 4 строки), имена колонок задаются вручную

### matcher.py — Подбор ПК (доработан vs agentKP)
**Три уровня поиска:**
1. Fuzzy-match МНН в pk_list (rapidfuzz >= 80) → confidence 0.85–0.95
2. LLM с полным списком 295 ПК → confidence из ответа LLM
3. Если МНН пустое (БАД, медизделие) → сразу LLM по названию и категории

### llm_client.py — DeepSeek клиент
- openai SDK, base_url=`https://api.deepseek.com`
- Всегда запрашивает JSON-ответ
- Валидирует через Pydantic
- Retry 3 раза при невалидном JSON

### tools.py — MCP-эндпоинты
- Каждый роут имеет `description` на русском — для агента в Студии
- Все входные/выходные модели описаны Pydantic-схемами
- Ошибки возвращаются как `{"error": "...", "detail": "..."}`

---

## 4. ИНВАРИАНТЫ

| # | Инвариант |
|---|---|
| I-1 | LLM не формирует Excel — только JSON с данными |
| I-2 | Агент не рассчитывает ФМ, маржу, бонус из процента |
| I-3 | ЕСКЛП загружается один раз при старте, не при каждом запросе |
| I-4 | Список 295 ПК статичный, в памяти, не в БД |
| I-5 | Каждый /tools/* делает ровно одно действие |
| I-6 | Файлы ЕСКЛП никогда не коммитятся в git |

---

## 5. СХЕМА ДАННЫХ

### DuckDB — таблица esklp_tn
```sql
CREATE TABLE esklp_tn (
    trade_name    VARCHAR,   -- торговое наименование
    mnn           VARCHAR,   -- стандартизованное МНН
    form          VARCHAR,   -- лекарственная форма
    dosage        VARCHAR,   -- дозировка (строка)
    smnn_code     VARCHAR    -- код узла СМНН
);
```

### data/pk_list.json
```json
[
  {"tg": "Лекарственные препараты", "tk": "Анальгетики", "pk": "Ибупрофен таблетки"},
  {"tg": "Лекарственные препараты", "tk": "Анальгетики", "pk": "Парацетамол таблетки"},
  ...
]
```

---

## 6. ENV-ПЕРЕМЕННЫЕ

```
# Обязательные
DEEPSEEK_API_KEY=        # ключ DeepSeek API
ESKLP_DIR=               # путь к папке с файлами ЕСКЛП

# Опциональные
PORT=8000
CONFIDENCE_AUTO=0.90
CONFIDENCE_REVIEW=0.65
SESSION_TTL_HOURS=2
```

---

*Версия 1.0 | Проект: new-agent-pk*

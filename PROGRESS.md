# PROGRESS.md — Трекер прогресса

---

## ТЕКУЩИЙ СТАТУС

**Фаза:** Bootstrap
**Последняя задача:** F-001 — Репозиторий, зависимости, структура папок
**Статус сборки:** ✅ verification_cmd F-001 прошёл (`OK`)
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

## СЛЕДУЮЩИЙ ШАГ

**Задача:** F-002 — FastAPI backend, GET /health

**Что сделать:**
1. Подключить роутеры FastAPI согласно `ARCHITECTURE.md`.
2. Убедиться, что `uvicorn app.main:app --port 8000` стартует без ошибок.
3. Проверить `GET /health → {"status": "ok"}`.
4. Обновить `feature_list.json` и `PROGRESS.md` после verification_cmd F-002.

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
| 1 | 2026-05-27 | F-001 | F-001 | Bootstrap завершён, verification_cmd=`OK`, `pytest` зелёный, `ruff` чистый |

---

*Обновлять в конце каждой сессии*

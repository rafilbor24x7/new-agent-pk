# SPRINT_CONTRACT.md — Спринт 1

---

## СПРИНТ 1 — Backend инструменты для MCP-агента

**Дата начала:** 2026-05-27
**Цель:** Рабочий набор HTTP-инструментов на Render, готовый к подключению в Яндекс AI Studio как MCP-сервер.

---

## 1. ОБЪЁМ

| ID | Название | Приоритет |
|---|---|---|
| F-001 | Репозиторий, зависимости, структура | critical |
| F-002 | FastAPI backend, GET /health | critical |
| F-003 | Деплой на Render | critical |
| F-101 | ЕСКЛП в DuckDB | critical |
| F-102 | Список 295 ПК, GET /tools/pk_list | critical |
| F-201 | POST /tools/search_esklp | critical |
| F-202 | POST /tools/match_pk | critical |
| F-203 | POST /tools/parse_offer | critical |
| F-204 | POST /tools/build_excel | critical |
| F-205 | POST /tools/upload_base | critical |
| F-301 | OpenAPI схема для всех инструментов | critical |
| F-302 | Описания инструментов на русском | high |
| F-401 | E2E тест полного pipeline | critical |
| F-402 | Финальный чеклист | critical |

---

## 2. ЧТО НЕ ВХОДИТ

- ❌ Frontend, HTML-страницы, UI
- ❌ Telegram-бот
- ❌ Авторизация пользователей
- ❌ Хранение истории обработок
- ❌ Расчёт коммерческих показателей
- ❌ Изменение бизнес-логики скопированных сервисов

---

## 3. ОПРЕДЕЛЕНИЕ «ГОТОВО»

Спринт завершён когда:
1. `https://<render-url>/openapi.json` доступен публично
2. Яндекс AI Studio может импортировать этот URL как MCP-сервер
3. Все 5 инструментов (`parse_offer`, `search_esklp`, `match_pk`, `upload_base`, `build_excel`) вызываются и возвращают корректный JSON
4. E2E тест с реальными файлами заказчика: минимум 3 из 5 SKU получают верную ПК

---

## 4. ВАЖНЫЕ ЗАВИСИМОСТИ

До начала F-101 заказчик должен:
- Положить файлы ЕСКЛП в `data/esklp_*/`
- Предоставить `data/pk_list.json` с 295 ПК

До начала F-401 заказчик должен:
- Предоставить реальные `base_sample.xlsx` и `offer_sample.xlsx`

---

*Версия 1.0*

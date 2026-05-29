# new-agent-pk

REST API для ReAct-агента сопоставления SKU из коммерческих предложений с товарными подкатегориями аптечной сети.

## Локальный запуск

```powershell
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Проверка:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health
```

## Переменные окружения

- `ESKLP_DIR` - папка с файлами ЕСКЛП `.xlsx`.
- `ADMIN_TOKEN` - токен для `/admin/*` endpoint'ов.
- `DEEPSEEK_API_KEY` - ключ LLM, нужен для fallback в `/tools/match_pk`.

## Первый запуск на Render

1. На Render задать ENV-переменные:

```text
ADMIN_TOKEN=<секретный токен>
ESKLP_DIR=data/esklp_20260507_excel_00001
DEEPSEEK_API_KEY=<ключ DeepSeek, если нужен LLM>
```

2. Локально задать `ADMIN_TOKEN` и путь к папке с файлами ЕСКЛП:

```powershell
$env:ADMIN_TOKEN="<тот же токен>"
$env:ESKLP_DIR="C:\Projects\new-agent-pk\esklp_20260507_excel_00001"
```

3. Загрузить файлы ЕСКЛП на Render:

```powershell
python scripts\upload_esklp.py
```

Скрипт отправляет все `.xlsx` из локального `ESKLP_DIR` в:

```text
https://new-agent-pk.onrender.com/admin/upload_esklp
```

4. После загрузки запустить фоновую перезагрузку ЕСКЛП в процессе Render:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "https://new-agent-pk.onrender.com/admin/reload_esklp" `
  -Headers @{ "X-Admin-Token" = $env:ADMIN_TOKEN }
```

Ответ сразу будет:

```json
{"status":"loading"}
```

5. Проверить статус:

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "https://new-agent-pk.onrender.com/admin/esklp_status" `
  -Headers @{ "X-Admin-Token" = $env:ADMIN_TOKEN }
```

Ожидаемо:

```json
{
  "status": "ready",
  "esklp_tn_rows": 22236
}
```

6. Проверить поиск:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "https://new-agent-pk.onrender.com/tools/search_esklp" `
  -ContentType "application/json" `
  -Body '{"trade_name":"Ибупрофен"}'
```

## Диагностика ЕСКЛП

Если поиск возвращает пустой список, проверить:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "https://new-agent-pk.onrender.com/admin/esklp_debug" `
  -Headers @{ "X-Admin-Token" = $env:ADMIN_TOKEN } `
  -ContentType "application/json" `
  -Body '{"trade_name":"Ibuprofen"}'
```

Endpoint показывает первые строки `esklp_tn`, SQL `LIKE`-совпадения и rapidfuzz-score.

## Проверки перед коммитом

```powershell
python -m pytest
ruff check .
```

# BankruptScout — сбор данных Федресурс / КАД (Scrapy)

Scrapy-проект для массового сбора информации о банкротствах. Ввод ИНН из Excel-файла, запросы к [bankrot.fedresurs.ru](https://bankrot.fedresurs.ru/) для получения номеров дел и дат, затем поиск электронных документов на [kad.arbitr.ru](https://kad.arbitr.ru/). Результаты сохраняются в реляционную БД через **SQLAlchemy 2.0**.

## Почему Scrapy

- Встроенная очередь, **middleware** (ретраи с backoff, ротация User-Agent, прокси), **pipelines** в БД, автоматическое ограничение нагрузки (`AUTOTHROTTLE`).
- **ЕФРСБ** — JSON API (без браузера): `/backend/prsnbankrupts` и `/backend/cmpbankrupts`.
- **КАД** — `POST /Kad/SearchInstances` + разбор HTML; при блокировке можно включить **`KAD_USE_PLAYWRIGHT=true`**.

## Эндпоинты

**bankrot.fedresurs.ru** (XHR):

- `GET /backend/prsnbankrupts?searchString={ИНН}&limit=15&offset=0` — физлица;
- `GET /backend/cmpbankrupts?searchString={ИНН}&limit=15&offset=0` — юрлица.

Заголовки `Referer`/`Origin` и ротация User-Agent задаются в [`scraper/api_clients/bankruptcy_registry.py`](scraper/api_clients/bankruptcy_registry.py).

**kad.arbitr.ru**:

- `POST /Kad/SearchInstances` — JSON-тело → HTML-ответ (`#b-cases`);
- `GET /Card/{guid}` — карточка дела с документами.

## Стек

- Python 3.11+
- Scrapy, scrapy-playwright, Playwright (Chromium)
- SQLAlchemy 2.0
- PostgreSQL (Docker) или SQLite (локально)
- openpyxl

## Конфигурация БД

**`DATABASE_URL`**: по умолчанию `sqlite:///./data/scraper.db`, для PostgreSQL: `postgresql+psycopg2://user:pass@host:5432/dbname`.

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `DATABASE_URL` | DSN БД |
| `INPUT_XLSX` | Путь к `.xlsx` со списком ИНН |
| `INPUT_XLSX_SHEET` | Имя листа (опционально) |
| `INPUT_XLSX_COLUMN` | Буква колонки (опционально) |
| `INNS` | ИНН через запятую (альтернатива файлу) |
| `ROBOTSTXT_OBEY` | `true`/`false` (по умолчанию `false`) |
| `DOWNLOAD_DELAY`, `CONCURRENT_REQUESTS` | Настройки нагрузки |
| `RETRY_TIMES`, `RETRY_BACKOFF_BASE` | Ретраи и backoff |
| `HTTP_PROXY` / `HTTPS_PROXY` | Прокси (опционально) |
| `SCRAPY_JOBDIR` | Каталог для resume Scrapy |
| `PLAYWRIGHT_HEADLESS`, `PLAYWRIGHT_NAV_TIMEOUT_MS` | Настройки браузера |
| `KAD_USE_PLAYWRIGHT` | `true` — fallback через Playwright при блокировке КАД |

## Локальный запуск

```powershell
cd bankruptscout
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

Генерация тестового Excel (120+ строк):

```powershell
python scripts/generate_test_data.py
```

Запуск полного цикла:

```powershell
$env:INPUT_XLSX = "input\sample_inns.xlsx"
$env:PYTHONPATH = "$PWD"
python scripts/launch.py
```

Отдельные пауки:

```powershell
python -m scrapy crawl bankruptcy_search -a xlsx_path=input/sample_inns.xlsx
python -m scrapy crawl court_docs
```

## Docker Compose

```powershell
docker compose build
docker compose run --rm -e INPUT_XLSX=/data/sample_inns.xlsx scraper
```

Предварительно сгенерируйте `input/sample_inns.xlsx` через `scripts/generate_test_data.py`.

## Схема данных

- **`insolvency_records`** — ИНН, № дела, последняя дата (ЕФРСБ), уникальность `(inn, case_number)`.
- **`arbitration_documents`** — № дела, дата, название документа, URL; уникальность `(case_number, doc_title, last_event_date)`.
- **`completed_inns`** — resume: обработанный ИНН не запрашивается повторно (по умолчанию `skip_processed=true`).

## Логи и ошибки

- Логирование в stdout (`LOG_LEVEL`).
- Ретраи с экспоненциальной задержкой (`scraper.middlewares.BackoffRetryMiddleware`).
- CAPTCHA/блокировка — запись с `doc_title="(error)"` в КАД.

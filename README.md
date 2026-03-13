# StockWatch

Telegram-first IHSG alert engine for dividend reminders, corporate actions, watchlist rules, unusual activity, and market summaries.

StockWatch is not a generic stock dashboard. It is built to reduce noise and push actionable market events directly to Telegram, so you do not need to keep opening a dashboard manually.

## What It Does

- Sends `dividend alerts` and daily reminders until ex-date
- Tracks `corporate actions` such as RUPS and tender offers from KSEI sources
- Evaluates `watchlist rules` like `price_above`, `price_below`, `volume_multiple_gt`, and `breakout_20d_high`
- Detects `unusual activity` on the active market universe
- Sends `morning` and `end-of-day` market summaries
- Exposes `Telegram bot commands` and inline buttons for operational control
- Provides a lightweight `admin panel` for logs, events, jobs, and watchlist config

## Product Direction

Core principle:
- Telegram is the primary interface
- Alerts should be actionable
- Noise should be suppressed
- Dashboard is secondary

Main components:
- `Event Collector`
- `Signal Engine`
- `Telegram Notifier`
- `Watchlist Rules Engine`

## Feature Set

### Alerts

- `💰 Dividend Alert`
- `🏛️ Corporate Action Alert`
- `🔄 Corporate Action Update`
- `👀 Watchlist Alert`
- `⚡ Unusual Activity`
- `📰 Market Summary`

### Anti-Spam

- Same automatic alert is not sent more than `1x` per day
- `ALERT_MIN_SEVERITY` filters out low-priority alerts
- `ALERT_MAX_PER_DAY` limits total daily automatic alert volume
- Manual trigger from Telegram/admin bypasses normal daily dedup and quota
- Technical field changes such as `raw_payload` and `source_url` are ignored for Telegram update alerts

### Telegram Operations

- Inline menu for system, data, collect, alerts, summary, and watchlist
- Command-based CRUD for watchlist rules
- Progress indicator for long-running actions such as `Collect All`
- Retry handling for Telegram `429` rate limits

## Architecture

Flow:
1. Collectors fetch events, symbols, and market snapshots
2. Parsers normalize events
3. Signals evaluate reminders and alerts
4. Notifiers format and send Telegram messages
5. Storage persists events, alert logs, jobs, and watchlist rules

Main runtime modules:
- `stockwatch/collectors/`
- `stockwatch/parsers/`
- `stockwatch/signals/`
- `stockwatch/notifiers/`
- `stockwatch/jobs/`
- `stockwatch/storage/`
- `stockwatch/bot/`
- `stockwatch/config/`
- `stockwatch/utils/`

Entry points:
- `main.py`
- `run_jobs.py`
- `streamlit_app.py`
- `stockwatchctl`

## Data Sources

### Symbols

- KSEI master securities for full IDX symbol universe

### Events

- `KSEI calendar/detail`
  - best for dividend and date-structured event records
- `KSEI publications`
  - `meeting-announcement`
  - `meeting-convocation`
  - `minutes-of-meeting`
  - `rights-distribution`
  - `masr`

### Market Prices

- `Yahoo Finance` for selective `.JK` market prices
- `TradingView most active Indonesia` for dynamic priority universe

### Coverage Notes

- Full symbol universe is loaded from KSEI
- Event coverage is broader than before because it combines KSEI calendar plus KSEI publications
- Market price collection is selective, not full-market by default
- Event-only symbols auto-expand into the active market universe when needed

## Repository Layout

```text
stockwatch/
├── data/
├── deploy/
│   └── systemd/
├── docs/
├── stockwatch/
│   ├── bot/
│   ├── collectors/
│   ├── config/
│   ├── jobs/
│   ├── notifiers/
│   ├── parsers/
│   ├── signals/
│   ├── storage/
│   └── utils/
├── main.py
├── run_jobs.py
├── stockwatchctl
└── streamlit_app.py
```

## Quick Start

```bash
cd /home/kac0/project/stockwatch
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
./stockwatchctl bootstrap
./stockwatchctl
```

Default behavior:
- `./stockwatchctl` runs `all-in-one`
- admin port defaults to `8501`
- admin port can be overridden with `STOCKWATCH_ADMIN_PORT` in `.env`

After initial setup, the simplest run command is:

```bash
cd /home/kac0/project/stockwatch
./stockwatchctl
```

## Runtime Modes

- `./stockwatchctl bootstrap`
  - initialize DB, collect symbols, collect events, collect market
- `./stockwatchctl worker`
  - scheduler only
- `./stockwatchctl bot`
  - Telegram command bot only
- `./stockwatchctl ops`
  - scheduler + Telegram bot
- `./stockwatchctl admin`
  - Streamlit admin only
- `./stockwatchctl`
  - default `all-in-one`
- `./stockwatchctl all-in-one`
  - scheduler + Telegram bot + Streamlit admin
- `./stockwatchctl job collect-events`
  - run a single job directly

## Scheduled Jobs

Current schedule:
- `07:30 WIB` morning summary
- `07:50 WIB` collect symbols
- `08:00 WIB` collect events
- `08:05 WIB` collect market
- `08:10 WIB` dividend alerts
- `09:00-15:30 WIB` watchlist alerts every 30 minutes
- `09:15-15:45 WIB` unusual activity every 30 minutes
- `16:30 WIB` end-of-day summary
- `18:00 WIB` collect events
- `18:05 WIB` collect market
- `19:15 WIB` corporate action alerts

Manual triggers from Telegram or admin panel run immediately and do not wait for the schedule.

## Available Jobs

- `init-db`
- `collect-symbols`
- `collect-events`
- `collect-market`
- `collect-all`
- `dividend-alerts`
- `corporate-actions`
- `watchlist-alerts`
- `unusual-activity`
- `market-summary --session morning`
- `market-summary --session eod`
- `scheduler`

## Telegram Bot Commands

### Navigation

- `/menu`
- `/help`
- `/status`

### Data

- `/symbols`
- `/symbols_find QUERY`
- `/events`
- `/market`

### Collection

- `/collect_symbols`
- `/collect_events`
- `/collect_market`
- `/collect_all`

### Alerts

- `/dividend_alerts`
- `/corporate_actions`
- `/watchlist_alerts`
- `/unusual_activity`

### Summary

- `/summary_morning`
- `/summary_eod`

### Watchlist CRUD

- `/watchlist_show`
- `/watchlist_help`
- `/watchlist_add BBCA price_above > 10000`
- `/watchlist_update 1 BBCA price_above > 10200 0 high on`
- `/watchlist_delete 1`
- `/watchlist_enable 1`
- `/watchlist_disable 1`

Inline buttons are also available for common actions, data browsing, and refresh jobs.

## Admin Panel

The admin panel is intentionally lightweight. It is meant for:
- viewing active events
- viewing event updates
- viewing recent alerts
- viewing recent jobs
- editing watchlist rules
- manually triggering jobs

Typical actions available in admin:
- `Init DB`
- `Collect symbols`
- `Collect events`
- `Collect market`
- `Collect all`
- `Run dividend alerts`
- `Run corporate action alerts`
- `Run watchlist alerts`
- `Run unusual activity`
- `Run morning summary`
- `Run EOD summary`

## Configuration

Example `.env`:

```dotenv
STOCKWATCH_DB_PATH=data/stockwatch.db
STOCKWATCH_ENV=dev
STOCKWATCH_ADMIN_PORT=8501

TELEGRAM_BOT_TOKEN=replace_me
TELEGRAM_CHAT_ID=replace_me
TELEGRAM_ENABLED=false
TELEGRAM_COMMANDS_ENABLED=true
TELEGRAM_COMMAND_CHAT_IDS=-5168829564
TELEGRAM_POLL_TIMEOUT_SECONDS=10
TELEGRAM_COMMAND_WORKERS=4

ALERT_MIN_SEVERITY=medium
ALERT_MAX_PER_DAY=20

WATCHLIST_RULES_PATH=data/watchlist_rules.json

MARKET_PRIORITY_SYMBOLS_PATH=data/bootstrap_symbols.csv
MARKET_PRIORITY_LIMIT=100

KSEI_CALENDAR_MONTHS_AHEAD=1
KSEI_PUBLICATION_MONTHS_BACK=1
KSEI_PUBLICATION_MAX_AGE_DAYS=45
```

Key notes:
- `TELEGRAM_COMMAND_CHAT_IDS` limits which chats can execute bot commands
- `STOCKWATCH_ADMIN_PORT` defaults to `8501` if omitted
- `MARKET_PRIORITY_SYMBOLS_PATH` is a fallback priority universe, not the primary live source

## Deployment

### Simple VPS Run

```bash
cd /opt/stockwatch
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
nano .env
./stockwatchctl bootstrap
./stockwatchctl
```

### Recommended Production Layout

Use two `systemd` services:
- `stockwatch-ops`
- `stockwatch-admin`

This is more stable than a single `all-in-one` service because scheduler/bot and admin restart independently.

Ready-made service files:
- `deploy/systemd/stockwatch-ops.service`
- `deploy/systemd/stockwatch-admin.service`
- `deploy/systemd/stockwatch-all-in-one.service`
- `deploy/systemd/stockwatch-ops.local.service`
- `deploy/systemd/stockwatch-admin.local.service`
- `deploy/systemd/stockwatch-all-in-one.local.service`

### Generic systemd Deploy

```bash
cd /opt/stockwatch
sudo cp deploy/systemd/stockwatch-ops.service /etc/systemd/system/
sudo cp deploy/systemd/stockwatch-admin.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stockwatch-ops
sudo systemctl enable --now stockwatch-admin
sudo systemctl status stockwatch-ops
sudo systemctl status stockwatch-admin
```

View logs:

```bash
sudo journalctl -u stockwatch-ops -f
sudo journalctl -u stockwatch-admin -f
```

### Host-Ready systemd Files

For the current host:

```bash
cd /home/kac0/project/stockwatch
sudo cp deploy/systemd/stockwatch-ops.local.service /etc/systemd/system/stockwatch-ops.service
sudo cp deploy/systemd/stockwatch-admin.local.service /etc/systemd/system/stockwatch-admin.service
sudo systemctl daemon-reload
sudo systemctl enable --now stockwatch-ops
sudo systemctl enable --now stockwatch-admin
```

If you want single-service mode on this host:

```bash
cd /home/kac0/project/stockwatch
sudo cp deploy/systemd/stockwatch-all-in-one.local.service /etc/systemd/system/stockwatch-all-in-one.service
sudo systemctl daemon-reload
sudo systemctl enable --now stockwatch-all-in-one
```

Do not enable `stockwatch-all-in-one` together with `stockwatch-ops` + `stockwatch-admin`.

## Troubleshooting

### Bot Does Not Respond

- ensure `ops` or `bot` is running
- check logs with `journalctl`
- verify Telegram credentials in `.env`

### Admin Port Already in Use

- change `STOCKWATCH_ADMIN_PORT` in `.env`
- or stop the old process/service using that port

### Telegram 429 Rate Limit

- the bot retries automatically
- avoid running many manual triggers in quick succession
- check service logs if repeated rate limits occur

### Virtualenv Broken After Moving the Repo

Python virtualenv stores absolute paths. Recreate it:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

### Reset Basic Operations

```bash
./stockwatchctl bootstrap
./stockwatchctl ops
```

## Current Limitations

- Dividend `ex-date` is still estimated as the next business day after `cum-date`
- IDX official disclosure is not yet the primary source because access from this server is blocked by Cloudflare
- Corporate action coverage is now much broader via KSEI publications, but still not identical to all IDX disclosures
- Watchlist rules are still file-based under the hood
- Admin panel is operational, not a full production-grade control panel with auth/roles

## Documentation

- System design: [docs/telegram-alert-engine.md](docs/telegram-alert-engine.md)
- Operations manual: [docs/operations-manual.md](docs/operations-manual.md)

## License

Internal project unless you define otherwise.

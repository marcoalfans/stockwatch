# StockLab Telegram Alert Engine

## 1. Ringkasan revisi dari sistem lama ke sistem baru

Sistem lama berangkat dari paradigma dashboard analisa saham umum. Revisi ini mengubah StockLab menjadi mesin alert Telegram yang memonitor event dan sinyal penting, lalu hanya mengirim informasi yang actionable.

Perubahan inti:

- dari `dashboard-first` ke `Telegram-first`
- dari `banyak widget` ke `sedikit alert bernilai`
- dari `analisa generik` ke `event-driven workflow`
- dari `manual checking` ke `scheduler + notifier`

## 2. Alasan kenapa sistem lama terlalu generik

- Fitur market overview, chart, dan indikator teknikal lengkap sudah banyak tersedia di aplikasi lain
- User tetap harus membuka dashboard untuk mencari informasi
- Insight penting tenggelam oleh noise visual
- Nilai harian rendah jika tidak ada alert/action
- Kompleksitas UI tinggi, tetapi urgensi keputusan tidak meningkat signifikan

## 3. Definisi produk baru: StockLab Telegram Alert Engine

StockLab adalah sistem pemantau saham Indonesia yang:

- mengumpulkan event penting
- mengevaluasi signal penting pada watchlist
- mengirim notifikasi ringkas ke Telegram
- memiliki anti-spam, dedup, severity, dan scheduler otomatis

Dashboard hanya opsional sebagai admin panel ringan untuk:

- melihat event baru
- melihat history alert
- melihat status job
- mengubah rule watchlist

## 4. Daftar fitur inti yang benar-benar penting

1. Dividend notifier
2. Corporate action watcher
3. Watchlist rule engine
4. Unusual activity detector
5. Morning summary
6. End-of-day summary
7. Telegram notifier dengan retry
8. Alert deduplication
9. Scheduler otomatis
10. Log pengiriman dan job

## 5. Arsitektur sistem ringan

Komponen:

1. `Event Collector`
   - mengambil dividend events
   - mengambil corporate action events
   - mengambil market snapshot harian
2. `Signal Engine`
   - daily dividend reminder
   - watchlist rule evaluation
   - unusual activity detection
   - market summary generation
3. `Telegram Notifier`
   - format message
   - kirim message
   - retry
   - log result
4. `Watchlist Rules Engine`
   - threshold harga
   - breakout / breakdown
   - volume multiple
   - ex-date proximity

## 6. Struktur folder project

```text
stocklab/
├── docs/
│   └── telegram-alert-engine.md
├── data/
│   ├── bootstrap_symbols.csv
│   ├── bootstrap_dividends.csv
│   ├── bootstrap_corporate_actions.csv
│   └── watchlist_rules.json
├── stocklab/
│   ├── collectors/
│   ├── parsers/
│   ├── signals/
│   ├── notifiers/
│   ├── jobs/
│   ├── storage/
│   ├── config/
│   └── utils/
├── streamlit_app.py
├── run_jobs.py
├── .env.example
└── pyproject.toml
```

## 7. Data model / database schema

### `symbols`

- `symbol`
- `company_name`
- `sector`
- `subsector`

### `market_prices`

- `symbol`
- `trade_date`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `traded_value`

### `events`

- `event_id`
- `source_type` (`dividend`, `rights_issue`, `stock_split`, dll)
- `symbol`
- `company_name`
- `title`
- `event_key`
- `announcement_date`
- `cum_date`
- `ex_date`
- `recording_date`
- `payment_date`
- `effective_date`
- `value_per_share`
- `estimated_yield`
- `source_url`
- `status`
- `severity`
- `fingerprint`
- `raw_payload`
- `created_at`
- `updated_at`

### `event_history`

- `history_id`
- `event_id`
- `change_type` (`created`, `updated`)
- `field_name`
- `old_value`
- `new_value`
- `changed_at`

### `alert_log`

- `alert_id`
- `alert_type`
- `symbol`
- `event_id`
- `severity`
- `dedup_key`
- `message_hash`
- `status`
- `channel`
- `sent_at`
- `response_payload`

### `watchlists`

- `watchlist_id`
- `name`
- `user_id`

### `watchlist_rules`

- `rule_id`
- `watchlist_id`
- `symbol`
- `rule_type`
- `operator`
- `threshold_value`
- `lookback_days`
- `enabled`
- `priority`

### `job_runs`

- `job_run_id`
- `job_name`
- `status`
- `started_at`
- `finished_at`
- `notes`

## 8. Scheduler design

Default schedule:

- `07:30 WIB` morning summary
- `08:00 WIB` collect all events
- `08:10 WIB` daily dividend reminders
- `every 30 min market hours` watchlist + unusual activity
- `16:30 WIB` EOD market summary
- `18:00 WIB` collect all events again
- `19:15 WIB` corporate action alerts

## 9. Telegram integration design

- gunakan `Telegram Bot API`
- credentials dari `.env`
- function reusable: `send_telegram_message(text, parse_mode="HTML")`
- retry `3x` dengan backoff
- log semua result ke `alert_log`
- severity filter di level notifier

## 10. Alert format examples

### Dividend alert

```text
[DIVIDEND ALERT]
BBCA - Bank Central Asia
Last Price: Rp9.850
Dividend: Rp270/share
Estimated Yield: 2.74%
Cum Date: 18 Apr 2026
Ex Date: 19 Apr 2026
Recording Date: 22 Apr 2026
Payment Date: 25 Apr 2026
Days to Ex Date: 3
Status: Masih eligible untuk dividend capture
```

### Corporate action update

```text
[CORPORATE ACTION UPDATE]
TICKER: EXCL
Event: Rights Issue
Jadwal berubah:
Old Ex Date: 12 Apr 2026
New Ex Date: 15 Apr 2026
Priority: High
```

### Watchlist breakout

```text
[WATCHLIST ALERT]
ANTM breakout 20-day high
Close: Rp1.945
Resistance 20D: Rp1.920
Volume: 2.4x avg20
Priority: High
```

## 11. Dividend reminder flow

1. collector menemukan event dividend
2. parser normalisasi dan bentuk `event_key`
3. storage upsert event
4. jika event baru: kirim first alert
5. setiap hari cek event `ex_date >= today`
6. kirim reminder harian jika belum pernah dikirim pada hari itu
7. `H-7`, `H-3`, `H-1`, dan hari `H` naikkan priority
8. stop reminder setelah ex-date lewat

## 12. Corporate action flow

1. collect event baru
2. normalisasi source type
3. hitung fingerprint event
4. jika fingerprint baru: alert `created`
5. jika event key sama tapi fingerprint berubah: simpan diff ke `event_history`
6. kirim update alert dengan old vs new values

## 13. Watchlist rule engine design

Rule minimum:

- `price_above`
- `price_below`
- `volume_multiple_gt`
- `ex_date_within_days`
- `breakout_20d_high`
- `breakdown_20d_low`
- `drawdown_from_peak_pct`

Setiap rule menghasilkan:

- `triggered`
- `severity`
- `dedup_key`
- `message payload`

## 14. Anti-spam and dedup logic

Rules:

- alert identik tidak boleh dikirim lebih dari sekali per hari
- low severity masuk log dulu, default tidak dikirim
- maximum alert penting per hari dibatasi
- watchlist diprioritaskan dibanding universe umum
- gunakan `dedup_key = alert_type + symbol + event_or_rule + date_bucket`

## 15. MVP scope

- bootstrap symbol master
- ingest dividend + corporate action dari collector live KSEI
- ingest EOD prices dengan `yfinance`
- Telegram sender + retry
- daily dividend alert
- watchlist rules basic
- unusual activity basic
- morning/eod summary
- APScheduler runner
- Streamlit admin panel ringan

## 16. Phase 2 scope

- parser source resmi yang lebih kuat untuk IDX/KSEI
- granular intraday watcher
- multi-chat routing
- richer corporate action coverage
- web form CRUD untuk watchlist rules
- PostgreSQL migration

## 17. Langkah implementasi step-by-step

1. buat schema SQLite
2. buat bootstrap data symbols dan corporate actions
3. bangun collectors untuk dividend, corporate action, market price
4. bangun parser normalisasi event
5. bangun repository upsert + diff history
6. bangun formatter Telegram
7. bangun sender dengan retry + log
8. bangun dividend reminder job
9. bangun watchlist rule evaluator
10. bangun unusual activity detector
11. bangun summary builder
12. jadwalkan job dengan APScheduler
13. tambahkan admin panel ringan

## 18. Skeleton code project

Skeleton code sudah disiapkan di package `stocklab`.

## 19. Contoh file .env

```dotenv
STOCKLAB_ENV=dev
STOCKLAB_DB_PATH=data/stocklab.db
TELEGRAM_BOT_TOKEN=replace_with_real_token
TELEGRAM_CHAT_ID=replace_with_real_chat_id
TELEGRAM_ENABLED=false
ALERT_MIN_SEVERITY=medium
ALERT_MAX_PER_DAY=20
WATCHLIST_RULES_PATH=data/watchlist_rules.json
```

## 20. Contoh config untuk bot token dan group chat id

Gunakan `.env` dan jangan hardcode di source:

```python
token = settings.telegram_bot_token
chat_id = settings.telegram_chat_id
```

## 21. Contoh job runner

```bash
python run_jobs.py collect-all
python run_jobs.py dividend-alerts
python run_jobs.py scheduler
```

## 22. Contoh fungsi kirim Telegram message

Lihat `stocklab/notifiers/telegram.py`.

## 23. Contoh data table untuk dividend events

| symbol | company_name | cum_date | ex_date | payment_date | dividend_per_share | estimated_yield |
|---|---|---|---|---|---|---|
| BBCA | Bank Central Asia | 2026-04-18 | 2026-04-19 | 2026-04-25 | 270 | 2.74 |

## 24. Contoh rule config untuk watchlist

```json
[
  {"symbol":"BBCA","rule_type":"price_above","operator":">","threshold_value":10000,"priority":"high"},
  {"symbol":"ANTM","rule_type":"volume_multiple_gt","operator":">=","threshold_value":2.0,"priority":"medium"},
  {"symbol":"TLKM","rule_type":"ex_date_within_days","operator":"<=","threshold_value":3,"priority":"high"}
]
```

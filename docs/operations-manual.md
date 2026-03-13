# StockWatch Operations Manual

Detailed operational reference for running, configuring, and maintaining StockWatch.

This document preserves the more detailed content that previously lived in the root `README.md`. The main README is now optimized for a GitHub project landing page, while this file is meant for day-to-day operators.

## Core Workflow

1. Collector mengambil event dan market snapshot
2. Parser menormalisasi event
3. Signal engine mengevaluasi reminder, watchlist rules, dan unusual activity
4. Notifier mengirim alert ke Telegram dengan dedup dan retry
5. Admin panel ringan hanya untuk melihat event, log, dan konfigurasi lokal

## Stack

- `Python 3.11+`
- `SQLite`
- `APScheduler`
- `requests`
- `pandas`
- `streamlit`

## Fitur Saat Ini

- `Dividend notifier`: alert dividen baru, reminder harian sampai ex-date, stop otomatis setelah ex-date lewat
- `Corporate action watcher`: event baru dan update material untuk dividend, rights issue, stock split, reverse stock split, buyback, tender offer, merger/acquisition, dan RUPS dari source KSEI
- `Watchlist alert engine`: rule `price_above`, `price_below`, `volume_multiple_gt`, `ex_date_within_days`, `breakout_20d_high`, `breakdown_20d_low`, dan `drawdown_from_peak_pct`
- `Unusual activity detector`: alert aktivitas harga/volume yang tidak biasa pada universe market yang aktif
- `Daily market summary`: summary pagi dan end-of-day ke Telegram
- `Telegram notifier`: formatting rapi, emoji per alert type, retry, logging, dan manual trigger
- `Telegram command bot`: control plane ringan untuk menjalankan job dan cek status langsung dari Telegram
- `Anti-spam`: dedup harian, severity filter, dan limit alert otomatis per hari
- `Selective market ingestion`: hanya fetch harga untuk saham watchlist, event aktif, dan priority/liquid universe harian
- `Admin panel`: observability event, update, alert, job run, watchlist rules, dan tombol trigger manual

## Alert Types

- `💰 Dividend Alert`
- `🏛️ Corporate Action Alert`
- `🔄 Corporate Action Update`
- `👀 Watchlist Alert`
- `⚡ Unusual Activity`
- `📰 Market Summary`

## Anti-Spam Rules

- alert otomatis yang sama tidak dikirim lebih dari `1x` per hari
- `low severity` tidak dikirim jika `ALERT_MIN_SEVERITY=medium`
- limit alert otomatis dibatasi oleh `ALERT_MAX_PER_DAY`
- manual trigger bypass dedup dan kuota harian otomatis
- perubahan teknis seperti `raw_payload` dan `source_url` tidak dikirim sebagai update Telegram

## Data Coverage

- `Full symbol universe`: seluruh emiten IDX aktif dari KSEI
- `Full event coverage`: event dari `calendar/detail KSEI` ditambah `publications corporate action KSEI`
- `Selective market coverage`: harga hanya diambil untuk symbol yang relevan dengan alert engine
- `Dynamic priority universe`: top most active Indonesia harian dari TradingView
- `Auto-expand`: symbol event KSEI di luar priority universe tetap ikut masuk ke market collector

## Struktur Utama

- `docs/telegram-alert-engine.md`: desain revisi total sistem
- `streamlit_app.py`: admin panel ringan
- `run_jobs.py`: CLI runner untuk init, collect, summary, scheduler
- `main.py`: single launcher untuk `bootstrap`, `worker`, `bot`, `ops`, `admin`, dan `all-in-one`
- `stockwatch/config/`: settings dan env
- `stockwatch/storage/`: koneksi DB, schema, repository
- `stockwatch/collectors/`: ingestion event dan market snapshot
- `stockwatch/parsers/`: normalisasi event
- `stockwatch/signals/`: dividend reminder, watchlist rules, unusual activity, summary builder
- `stockwatch/notifiers/`: formatter dan Telegram sender
- `stockwatch/bot/`: Telegram command bot dan inline menu
- `stockwatch/jobs/`: job runner terjadwal
- `stockwatch/utils/`: helpers tanggal, logging, retry, dan watchlist rules
- `data/`: watchlist rule config dan data runtime lokal

## Menjalankan

```bash
cd /home/kac0/project/stockwatch
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
./stockwatchctl bootstrap
./stockwatchctl
```

Shortcut harian:

```bash
cd /home/kac0/project/stockwatch
./stockwatchctl
```

Port admin bisa disimpan di `.env` lewat `STOCKWATCH_ADMIN_PORT`. Jika tidak diisi, default tetap `8501`.

## Menjalankan Scheduler

```bash
./stockwatchctl worker
```

## Job yang Tersedia

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

## Admin Panel Actions

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

## Telegram Bot Commands

- `/help`
- `/status`
- `/collect_symbols`
- `/collect_events`
- `/collect_market`
- `/collect_all`
- `/dividend_alerts`
- `/corporate_actions`
- `/watchlist_alerts`
- `/unusual_activity`
- `/summary_morning`
- `/summary_eod`
- `/watchlist_show`
- `/watchlist_help`
- `/watchlist_add BBCA price_above > 10000`
- `/watchlist_update 1 BBCA price_above > 10200 0 high on`
- `/watchlist_delete 1`
- `/watchlist_enable 1`
- `/watchlist_disable 1`
- `/menu`

Bot juga mendukung `inline buttons` untuk operasi cepat.

## Entry Points

- `./stockwatchctl bootstrap`
- `./stockwatchctl worker`
- `./stockwatchctl bot`
- `./stockwatchctl ops`
- `./stockwatchctl admin`
- `./stockwatchctl`
- `./stockwatchctl all-in-one`

## Deploy ke VPS Production

Paling sederhana:

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

### systemd

File service siap pakai:

- `deploy/systemd/stockwatch-ops.service`
- `deploy/systemd/stockwatch-admin.service`
- `deploy/systemd/stockwatch-all-in-one.service`
- `deploy/systemd/stockwatch-ops.local.service`
- `deploy/systemd/stockwatch-admin.local.service`
- `deploy/systemd/stockwatch-all-in-one.local.service`

Template generic untuk `/opt/stockwatch`:

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

Untuk host ini:

```bash
cd /home/kac0/project/stockwatch
sudo cp deploy/systemd/stockwatch-ops.local.service /etc/systemd/system/stockwatch-ops.service
sudo cp deploy/systemd/stockwatch-admin.local.service /etc/systemd/system/stockwatch-admin.service
sudo systemctl daemon-reload
sudo systemctl enable --now stockwatch-ops
sudo systemctl enable --now stockwatch-admin
```

Jangan aktifkan `stockwatch-all-in-one` bersamaan dengan `stockwatch-ops` + `stockwatch-admin`.

## Konfigurasi Telegram

Gunakan `.env`:

```dotenv
TELEGRAM_BOT_TOKEN=replace_me
TELEGRAM_CHAT_ID=replace_me
TELEGRAM_COMMANDS_ENABLED=true
TELEGRAM_COMMAND_CHAT_IDS=-5168829564
STOCKWATCH_ADMIN_PORT=8501
WATCHLIST_RULES_PATH=data/watchlist_rules.json
MARKET_PRIORITY_SYMBOLS_PATH=data/bootstrap_symbols.csv
MARKET_PRIORITY_LIMIT=100
KSEI_CALENDAR_MONTHS_AHEAD=1
KSEI_PUBLICATION_MONTHS_BACK=1
KSEI_PUBLICATION_MAX_AGE_DAYS=45
```

## Troubleshooting

### Bot Telegram tidak merespons

- pastikan `ops` atau `bot` sedang jalan
- cek log: `sudo journalctl -u stockwatch-ops -f`
- test lokal: `./stockwatchctl python -c "import yfinance, stockwatch; print('ok')"`

### Port admin sudah dipakai

- ubah `STOCKWATCH_ADMIN_PORT` di `.env`
- atau hentikan proses lama yang masih memakai port itu

### Kena rate limit Telegram

- bot sudah retry otomatis untuk `429`
- hindari trigger manual beruntun
- cek log service untuk melihat frekuensi request

### Setelah pindah folder repo, virtualenv bermasalah

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

### Reset operasional dasar

```bash
./stockwatchctl bootstrap
./stockwatchctl ops
```

## Sumber Event Production

- `Dividend / corporate action events`: live collector dari `web.ksei.co.id`
  - `KSEI calendar/detail`
  - `KSEI publications`
- `Symbol universe`: master securities live dari KSEI
- `Market prices`: live snapshot dari `yfinance` untuk selective market universe
- `Priority universe`: TradingView most active Indonesia

File bootstrap event di `data/` hanya berfungsi sebagai contoh format atau fallback dev, bukan source production utama.

## Batasan MVP Saat Ini

- `Ex-date` dividend dari KSEI masih diestimasi sebagai next business day setelah `cum-date`
- source IDX disclosure resmi belum dijadikan jalur utama karena akses dari server ini diblokir Cloudflare
- corporate action coverage sudah jauh lebih luas lewat publikasi resmi KSEI, tetapi belum identik 100% dengan seluruh keterbukaan informasi IDX
- watchlist rules masih berbasis file JSON di bawahnya
- admin panel masih observability-first, belum role/auth production

## Jadwal Otomatis

- `07:30 WIB` morning summary
- `07:50 WIB` collect symbols
- `08:00 WIB` collect events
- `08:05 WIB` collect market
- `08:10 WIB` dividend alerts
- `09:00-15:30 WIB` watchlist alerts per 30 menit
- `09:15-15:45 WIB` unusual activity per 30 menit
- `16:30 WIB` end-of-day summary
- `18:00 WIB` collect events
- `18:05 WIB` collect market
- `19:15 WIB` corporate action alerts

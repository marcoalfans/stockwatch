# StockLab

StockLab sekarang direvisi menjadi `Telegram-based IHSG Alert Engine`, bukan dashboard saham generik. Fokus produk adalah event penting, reminder, watchlist alert, unusual activity, dan ringkasan pasar yang dikirim otomatis ke Telegram.

## Core workflow

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
- `streamlit` untuk admin panel ringan

## Fitur Saat Ini

- `Dividend notifier`: alert dividen baru, reminder harian sampai ex-date, stop otomatis setelah ex-date lewat
- `Corporate action watcher`: event baru dan update material untuk dividend, rights issue, stock split, reverse stock split, buyback, tender offer, dan RUPS jika tersedia dari source
- `Watchlist alert engine`: rule `price_above`, `price_below`, `volume_multiple_gt`, `ex_date_within_days`, dan `breakout_20d_high`
- `Unusual activity detector`: alert aktivitas harga/volume yang tidak biasa pada universe market yang aktif
- `Daily market summary`: summary pagi dan end-of-day ke Telegram
- `Telegram notifier`: formatting rapi, emoji per alert type, retry, logging, dan manual trigger dari admin
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
- manual trigger dari admin bypass dedup dan kuota harian otomatis
- perubahan teknis seperti `raw_payload` dan `source_url` tidak dikirim sebagai update Telegram

## Data Coverage

- `Full symbol universe`: seluruh emiten IDX aktif dari KSEI
- `Full event coverage`: seluruh event yang bisa ditarik dari calendar/detail KSEI
- `Selective market coverage`: harga hanya diambil untuk symbol yang relevan dengan alert engine
- `Dynamic priority universe`: top most active Indonesia harian dari TradingView
- `Auto-expand`: symbol event KSEI di luar priority universe tetap ikut masuk ke market collector

## Struktur utama

- `docs/telegram-alert-engine.md`: desain revisi total sistem
- `streamlit_app.py`: admin panel ringan
- `run_jobs.py`: CLI runner untuk init, collect, summary, scheduler
- `stocklab/config/`: settings dan env
- `stocklab/storage/`: koneksi DB, schema, repository
- `stocklab/collectors/`: ingestion event dan market snapshot
- `stocklab/parsers/`: normalisasi event
- `stocklab/signals/`: dividend reminder, watchlist rules, unusual activity, summary builder
- `stocklab/notifiers/`: formatter dan Telegram sender
- `stocklab/jobs/`: job runner terjadwal
- `data/`: bootstrap symbol master, corporate action seed, watchlist rule config

## Menjalankan

```bash
cd /home/kac0/project/stocklab
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
python main.py --mode bootstrap
python main.py --mode all-in-one
```

## Menjalankan scheduler

```bash
source .venv/bin/activate
python main.py --mode worker
```

## Job yang tersedia

- `init-db`
- `collect-symbols`
- `collect-events`
- `collect-market`
- `collect-all`
- `dividend-alerts`
- `corporate-actions`
- `watchlist-alerts`
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

## Entry point sederhana

- `python main.py --mode bootstrap`
  - inisialisasi DB lalu jalankan `collect-symbols`, `collect-events`, dan `collect-market`
- `python main.py --mode worker`
  - jalankan scheduler saja
- `python main.py --mode admin`
  - jalankan admin panel saja
- `python main.py --mode all-in-one`
  - jalankan scheduler + admin panel dalam satu command

## Deploy ke VPS production

Paling sederhana:

```bash
cd /opt/stocklab
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
nano .env
python main.py --mode bootstrap
python main.py --mode all-in-one
```

Untuk production yang lebih rapi, gunakan `systemd` dan biasanya pisahkan:

- `stocklab-worker`: `python main.py --mode worker`
- `stocklab-admin`: `python main.py --mode admin --port 8501`

`all-in-one` saya sediakan untuk kemudahan single-command, tetapi secara operasional 2 service tetap lebih kuat karena restart dan observability lebih bersih.

## Konfigurasi Telegram

Gunakan `.env`:

```dotenv
TELEGRAM_BOT_TOKEN=replace_me
TELEGRAM_CHAT_ID=replace_me
WATCHLIST_RULES_PATH=data/watchlist_rules.json
MARKET_PRIORITY_SYMBOLS_PATH=data/bootstrap_symbols.csv
MARKET_PRIORITY_LIMIT=100
```

Credential tidak di-hardcode di source code final.

## Sumber event production

Untuk production, alert event tidak lagi mengambil data dari sample/seed CSV.

- `Dividend / corporate action events`: live collector dari `web.ksei.co.id`
- `Symbol universe`: master securities live dari KSEI untuk seluruh emiten IDX aktif
- `Market prices`: live snapshot dari `yfinance` hanya untuk simbol yang relevan dengan alert engine:
  - simbol watchlist
  - simbol event aktif dari KSEI
  - priority/liquid universe live dari TradingView `most active Indonesian stocks`
  - auto-expand jika KSEI menemukan simbol event baru di luar priority universe
  - fallback ke `MARKET_PRIORITY_SYMBOLS_PATH` jika source live priority universe gagal

File bootstrap event di folder `data/` kini hanya berfungsi sebagai contoh format data atau cadangan dev, bukan sumber alert production.

## Batasan MVP Saat Ini

- `Ex-date` dividend dari KSEI saat ini masih diestimasi sebagai next business day setelah `cum-date`
- corporate action coverage masih mengikuti apa yang muncul di KSEI calendar/detail
- watchlist rules masih berbasis file JSON, belum CRUD penuh dari admin
- admin panel masih fokus observability, belum role/auth production

## Jadwal otomatis

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

Jika Anda menekan tombol `Run dividend alerts` di admin panel, job dijalankan saat itu juga. Itu manual trigger, jadi tidak menunggu jadwal `08:10 WIB`.

CREATE TABLE IF NOT EXISTS symbols (
    symbol TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    sector TEXT,
    subsector TEXT,
    shares_outstanding INTEGER
);

CREATE TABLE IF NOT EXISTS market_prices (
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    traded_value REAL,
    PRIMARY KEY (symbol, trade_date)
);

CREATE TABLE IF NOT EXISTS index_prices (
    index_code TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (index_code, trade_date)
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    company_name TEXT,
    title TEXT,
    event_key TEXT NOT NULL UNIQUE,
    announcement_date DATE,
    cum_date DATE,
    ex_date DATE,
    recording_date DATE,
    payment_date DATE,
    effective_date DATE,
    value_per_share REAL,
    estimated_yield REAL,
    source_url TEXT,
    status TEXT DEFAULT 'active',
    severity TEXT DEFAULT 'medium',
    fingerprint TEXT NOT NULL,
    raw_payload TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS event_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    change_type TEXT NOT NULL,
    field_name TEXT,
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alert_log (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,
    symbol TEXT,
    event_id INTEGER,
    severity TEXT NOT NULL,
    dedup_key TEXT NOT NULL,
    message_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    channel TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_payload TEXT
);

CREATE INDEX IF NOT EXISTS idx_alert_log_dedup_key ON alert_log(dedup_key);

CREATE TABLE IF NOT EXISTS watchlists (
    watchlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    user_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, user_id)
);

CREATE TABLE IF NOT EXISTS watchlist_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    operator TEXT NOT NULL,
    threshold_value REAL NOT NULL,
    lookback_days INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    priority TEXT DEFAULT 'medium'
);

CREATE TABLE IF NOT EXISTS job_runs (
    job_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    notes TEXT
);

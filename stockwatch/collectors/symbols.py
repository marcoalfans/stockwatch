from __future__ import annotations

from io import BytesIO
import zipfile

from bs4 import BeautifulSoup
import pandas as pd
import requests

from stockwatch.config.settings import BASE_DIR


KSEI_ARCHIVE_URL = "https://web.ksei.co.id/archive_download/master_securities"
KSEI_BASE_URL = "https://web.ksei.co.id"
USER_AGENT = "StockWatch/0.1 (+https://example.local)"


def collect_symbols() -> pd.DataFrame:
    try:
        return _collect_symbols_from_ksei()
    except Exception:
        return pd.read_csv(BASE_DIR / "data" / "bootstrap_symbols.csv")


def _collect_symbols_from_ksei() -> pd.DataFrame:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    html = session.get(KSEI_ARCHIVE_URL, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")
    download_links = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if href and "StatisEfek" in href and href.endswith(".zip"):
            download_links.append(href)
    if not download_links:
        raise RuntimeError("No KSEI master securities download found")

    latest_href = sorted(download_links, reverse=True)[0]
    response = session.get(f"{KSEI_BASE_URL}{latest_href}", timeout=60)
    response.raise_for_status()

    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        inner_name = archive.namelist()[0]
        with archive.open(inner_name) as handle:
            frame = pd.read_csv(handle, sep="|", dtype=str, encoding="cp1252")

    equities = frame[
        (frame["Type"] == "EQUITY")
        & (frame["Status"] == "ACTIVE")
        & (frame["Stock Exchange"] == "IDX")
        & (frame["Code"].str.fullmatch(r"[A-Z]{4,5}", na=False))
    ].copy()

    equities["company_name"] = equities["Description"].fillna(equities["Issuer"]).astype(str).str.strip()
    equities["sector"] = equities["Sector"].fillna("Unknown").astype(str).str.strip()
    equities["subsector"] = equities["Sector"].fillna("Unknown").astype(str).str.strip()
    equities["shares_outstanding"] = pd.to_numeric(equities["Num. of Sec"], errors="coerce").fillna(0).astype(int)
    equities = equities.rename(columns={"Code": "symbol"})
    equities = equities[["symbol", "company_name", "sector", "subsector", "shares_outstanding"]]
    equities = equities.drop_duplicates("symbol").sort_values("symbol").reset_index(drop=True)
    return equities

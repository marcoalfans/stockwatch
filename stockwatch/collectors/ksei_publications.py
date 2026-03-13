from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import re

from bs4 import BeautifulSoup
import pandas as pd
import requests

from stockwatch.collectors.ksei import BASE_URL, USER_AGENT, _get_with_retry, _parse_id_date


PUBLICATION_SPECS = (
    {"slug": "meeting-announcement", "default_source_type": "rups"},
    {"slug": "meeting-convocation", "default_source_type": "rups"},
    {"slug": "minutes-of-meeting", "default_source_type": "rups"},
    {"slug": "rights-distribution", "default_source_type": "rights_issue"},
    {"slug": "masr", "default_source_type": "corporate_action"},
)


@dataclass(slots=True)
class PublicationEvent:
    source_type: str
    symbol: str
    company_name: str
    title: str
    description: str
    announcement_date: date
    effective_date: date
    source_url: str
    status: str
    value_per_share: float | None
    estimated_yield: float | None
    cum_date: date | None
    ex_date: date | None
    recording_date: date | None
    payment_date: date | None


def collect_ksei_publication_events(
    symbols: pd.DataFrame,
    months_back: int = 1,
    max_age_days: int = 45,
) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    company_lookup = _build_company_lookup(symbols)
    records: list[PublicationEvent] = []
    for month_value, year_value in _iter_months_back(months_back):
        for spec in PUBLICATION_SPECS:
            records.extend(
                _fetch_publication_page(
                    session=session,
                    company_lookup=company_lookup,
                    slug=spec["slug"],
                    default_source_type=spec["default_source_type"],
                    month_value=month_value,
                    year_value=year_value,
                    max_age_days=max_age_days,
                )
            )

    if not records:
        return pd.DataFrame()

    frame = pd.DataFrame([asdict(record) for record in records])
    frame = frame.drop_duplicates(subset=["source_type", "symbol", "source_url"]).reset_index(drop=True)
    return frame


def _fetch_publication_page(
    session: requests.Session,
    company_lookup: dict[str, tuple[str, str]],
    slug: str,
    default_source_type: str,
    month_value: str,
    year_value: int,
    max_age_days: int,
) -> list[PublicationEvent]:
    url = f"{BASE_URL}/publications/corporate-action-schedules/{slug}?Month={month_value}&Year={year_value}"
    response = _get_with_retry(session, url)
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")
    body = table.find("tbody") if table else None
    if body is None:
        return []

    today = date.today()
    valid_symbols = {symbol for symbol, _company in company_lookup.values()}
    rows: list[PublicationEvent] = []
    for tr in body.find_all("tr"):
        columns = tr.find_all("td")
        if len(columns) < 3:
            continue

        link = tr.find("a", href=True)
        subject = " ".join(columns[1].get_text(" ", strip=True).split())
        published_at = _parse_id_date(columns[2].get_text(" ", strip=True))
        if not subject or published_at is None:
            continue
        if (today - published_at).days > max_age_days:
            continue

        source_type = _publication_source_type(default_source_type, subject)
        symbol = _extract_symbol(subject)
        if symbol and symbol not in valid_symbols:
            symbol = None
        company_name = _extract_company_name(slug, subject)
        if symbol is None and company_name:
            matched = company_lookup.get(_normalize_company_name(company_name))
            if matched is not None:
                symbol, company_name = matched
        if not symbol:
            continue

        if not company_name:
            matched = company_lookup.get(_normalize_company_name(subject))
            if matched is not None:
                symbol, company_name = matched
        if not company_name:
            company_name = symbol

        href = link["href"] if link else url
        source_url = href if href.startswith("http") else BASE_URL + href
        rows.append(
            PublicationEvent(
                source_type=source_type,
                symbol=symbol,
                company_name=company_name,
                title=subject,
                description=subject,
                announcement_date=published_at,
                effective_date=published_at,
                source_url=source_url,
                status="active",
                value_per_share=None,
                estimated_yield=None,
                cum_date=None,
                ex_date=None,
                recording_date=None,
                payment_date=None,
            )
        )
    return rows


def _iter_months_back(months_back: int) -> list[tuple[str, int]]:
    today = date.today()
    pairs: list[tuple[str, int]] = []
    month = today.month
    year = today.year
    for offset in range(months_back + 1):
        current_month = month - offset
        current_year = year
        while current_month <= 0:
            current_month += 12
            current_year -= 1
        pairs.append((f"{current_month:02d}", current_year))
    return pairs


def _build_company_lookup(symbols: pd.DataFrame) -> dict[str, tuple[str, str]]:
    lookup: dict[str, tuple[str, str]] = {}
    for row in symbols.to_dict("records"):
        symbol = str(row.get("symbol") or "").strip().upper()
        company_name = str(row.get("company_name") or "").strip()
        if not symbol or not company_name:
            continue
        normalized = _normalize_company_name(company_name)
        lookup.setdefault(normalized, (symbol, company_name))
    return lookup


def _normalize_company_name(value: str) -> str:
    normalized = value.upper().strip()
    normalized = normalized.replace("TBK.", "TBK")
    normalized = normalized.replace(", PT", "")
    normalized = normalized.replace(" PT,", " ")
    normalized = re.sub(r"^PT\s+", "", normalized)
    normalized = re.sub(r"\s+TBK$", "", normalized)
    normalized = normalized.replace(".", " ")
    normalized = normalized.replace(",", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _extract_symbol(subject: str) -> str | None:
    matched = re.search(r"\(([A-Z]{4,5})\)(?!.*\([A-Z]{4,5}\))", subject)
    if matched:
        candidate = matched.group(1)
        if candidate in {"RUPST", "RUPSL", "RUPSU", "RUPO", "RUPSLB"}:
            return None
        return candidate
    return None


def _extract_company_name(slug: str, subject: str) -> str:
    text = " ".join(subject.split())
    if slug in {"meeting-announcement", "meeting-convocation", "minutes-of-meeting"}:
        text = re.sub(r"^(Revisi|Pembatalan)\s+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^(Pemberitahuan|Panggilan|Risalah)\s+Rapat Umum Pemegang Saham.*?\)\s*", "", text, flags=re.IGNORECASE)
    elif slug == "rights-distribution":
        text = re.sub(r"^(Distribusi|Jadwal Distribusi|Perubahan Jadwal Distribusi)\s+HMETD\s+", "", text, flags=re.IGNORECASE)
    elif slug == "masr":
        text = re.sub(r"^(Jadwal|Perubahan Tanggal|Pengumuman)\s+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*\([A-Z]{4,5}\)\s*$", "", text)

    text = re.sub(r"\s+", " ", text).strip(" -")
    return text


def _publication_source_type(default_source_type: str, subject: str) -> str:
    upper_subject = subject.upper()
    if "TENDER" in upper_subject:
        return "tender_offer"
    if "RIGHT" in upper_subject or "HMETD" in upper_subject:
        return "rights_issue"
    if "REVERSE STOCK" in upper_subject:
        return "reverse_stock_split"
    if "STOCK SPLIT" in upper_subject:
        return "stock_split"
    if "MERGER" in upper_subject:
        return "merger"
    if "ACQUISITION" in upper_subject or "AKUISISI" in upper_subject:
        return "acquisition"
    return default_source_type

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
import re
import time

from bs4 import BeautifulSoup
import pandas as pd
import requests


BASE_URL = "https://web.ksei.co.id"
USER_AGENT = "StockWatch/0.1 (+https://example.local)"
REQUEST_RETRIES = 3
REQUEST_BACKOFF_SECONDS = 1.5

CATEGORY_MAP = {
    "CASH DIVIDEND": "dividend",
    "SHARE BONUS": "bonus_share",
    "BONUS SHARE": "bonus_share",
    "RIGHT ISSUE": "rights_issue",
    "STOCK SPLIT": "stock_split",
    "REVERSE STOCK SPLIT": "reverse_stock_split",
    "BUYBACK": "buyback",
    "MEETING": "rups",
    "TENDER OFFER": "tender_offer",
}


@dataclass(slots=True)
class CalendarDetail:
    detail_type: str
    detail_date: date
    category: str
    company_name: str
    security_code: str
    security_name: str
    record_date: date | None
    effective_date: date | None
    start_date: date | None
    deadline_date: date | None
    description: str
    source_url: str


def collect_live_ksei_events(symbols: pd.DataFrame, months_ahead: int = 1) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    symbol_master = symbols.set_index("symbol")[["company_name", "sector", "subsector"]].to_dict("index")
    detail_targets = _calendar_detail_targets(session, months_ahead=months_ahead)
    details = []
    for detail_type, detail_date in detail_targets:
        details.extend(_fetch_detail_page(session, detail_type, detail_date))

    if not details:
        return pd.DataFrame()

    frame = pd.DataFrame([asdict(detail) for detail in details])
    frame = frame[frame["security_code"].astype(str).str.fullmatch(r"[A-Z]{4,5}")].copy()
    if frame.empty:
        return frame

    frame["source_type"] = frame["category"].map(CATEGORY_MAP)
    frame = frame[frame["source_type"].notna()].copy()
    if frame.empty:
        return frame

    frame["cum_date"] = frame.apply(lambda row: row["detail_date"] if row["detail_type"] == "cum" else None, axis=1)
    frame["recording_date"] = frame.apply(
        lambda row: row["detail_date"] if row["detail_type"] == "rec" else row["record_date"],
        axis=1,
    )
    frame["payment_date"] = frame.apply(
        lambda row: row["detail_date"] if row["detail_type"] == "eff" else row["effective_date"],
        axis=1,
    )
    frame["effective_date"] = frame["payment_date"]
    frame["ex_date"] = frame["cum_date"].apply(_next_business_day)
    frame["value_per_share"] = frame["description"].apply(_extract_rupiah_amount)
    frame["symbol"] = frame["security_code"]
    frame["title"] = frame["category"].str.title()
    frame["announcement_date"] = date.today()
    frame["status"] = "active"
    frame["estimated_yield"] = None
    frame["source_url"] = BASE_URL + frame["source_url"]
    original_company = frame["company_name"].copy()
    frame["company_name"] = [
        symbol_master.get(sym, {}).get("company_name", _normalize_company_name(company))
        for sym, company in zip(frame["symbol"], original_company)
    ]
    for col in ["announcement_date", "cum_date", "ex_date", "recording_date", "payment_date", "effective_date"]:
        frame[col] = pd.to_datetime(frame[col], errors="coerce")
    frame["value_per_share"] = pd.to_numeric(frame["value_per_share"], errors="coerce")
    frame["estimated_yield"] = pd.to_numeric(frame["estimated_yield"], errors="coerce")

    frame = (
        frame.groupby(["source_type", "symbol", "description"], dropna=False, as_index=False)
        .agg(
            company_name=("company_name", "first"),
            title=("title", "first"),
            announcement_date=("announcement_date", "max"),
            cum_date=("cum_date", "max"),
            ex_date=("ex_date", "max"),
            recording_date=("recording_date", "max"),
            payment_date=("payment_date", "max"),
            effective_date=("effective_date", "max"),
            value_per_share=("value_per_share", "max"),
            estimated_yield=("estimated_yield", "first"),
            source_url=("source_url", "first"),
            status=("status", "first"),
        )
        .sort_values(["source_type", "symbol"])
    )
    for col in ["announcement_date", "cum_date", "ex_date", "recording_date", "payment_date", "effective_date"]:
        frame[col] = pd.to_datetime(frame[col], errors="coerce").dt.date
    return frame


def _calendar_detail_targets(session: requests.Session, months_ahead: int) -> set[tuple[str, date]]:
    targets: set[tuple[str, date]] = set()
    today = date.today()
    months = []
    year = today.year
    month = today.month
    for offset in range(months_ahead + 1):
        calc_month = month + offset
        calc_year = year + (calc_month - 1) // 12
        calc_month = ((calc_month - 1) % 12) + 1
        months.append((calc_month, calc_year))

    for calc_month, calc_year in months:
        url = f"{BASE_URL}/ksei_calendar/get_json/event-{calc_month:02d}-{calc_year}-all.json"
        response = _get_with_retry(session, url)
        response.raise_for_status()
        payload = response.json()
        for group in payload.get("data", []):
            for event in group.get("events", []):
                description = event.get("description", "")
                match = re.search(r"/detail/(cum|rec|eff)/(\d{4}-\d{2}-\d{2})", description)
                if not match:
                    continue
                targets.add((match.group(1), datetime.strptime(match.group(2), "%Y-%m-%d").date()))
    return targets


def _fetch_detail_page(session: requests.Session, detail_type: str, detail_date: date) -> list[CalendarDetail]:
    url = f"{BASE_URL}/ksei_calendar/detail/{detail_type}/{detail_date.isoformat()}"
    html = _get_with_retry(session, url).text
    soup = BeautifulSoup(html, "html.parser")

    rows: list[CalendarDetail] = []
    for category_section in soup.select("section.accordion--secondary"):
        category = category_section.select_one("h2.accordion__title")
        if category is None:
            continue
        category_name = category.get_text(" ", strip=True).upper()
        for company_section in category_section.select("section.accordion--last"):
            company_title = company_section.select_one("h2.accordion__title")
            if company_title is None:
                continue
            company_name = company_title.get_text(" ", strip=True)
            for dl in company_section.select("dl.accordion-dl"):
                parsed = _parse_dl(dl)
                security_code = parsed["security"].get("Security Code")
                if not security_code:
                    continue
                rows.append(
                    CalendarDetail(
                        detail_type=detail_type,
                        detail_date=detail_date,
                        category=category_name,
                        company_name=company_name,
                        security_code=security_code.strip(),
                        security_name=parsed["security"].get("Security Name", "").strip(),
                        record_date=_parse_id_date(parsed["dates"].get("Record Date")),
                        effective_date=_parse_id_date(parsed["dates"].get("Effective Date")),
                        start_date=_parse_id_date(parsed["dates"].get("Start Date")),
                        deadline_date=_parse_id_date(parsed["dates"].get("Deadline Date")),
                        description=parsed["description"].strip(),
                        source_url=f"/ksei_calendar/detail/{detail_type}/{detail_date.isoformat()}",
                    )
                )
    return rows


def _parse_dl(dl) -> dict:
    result = {"security": {}, "dates": {}, "description": ""}
    current_key = None
    for child in dl.children:
        name = getattr(child, "name", None)
        if name == "dt":
            current_key = child.get_text(" ", strip=True)
        elif name == "dd" and current_key == "Security Detail":
            result["security"] = _extract_labeled_items(child)
        elif name == "dd" and current_key == "CA Date":
            result["dates"] = _extract_labeled_items(child)
        elif name == "dd" and current_key == "CA Description":
            result["description"] = child.get_text("\n", strip=True)
    return result


def _extract_labeled_items(node) -> dict[str, str]:
    data: dict[str, str] = {}
    for item in node.select("li.event-detail-list__item"):
        label = item.select_one("b")
        value = item.select_one("span")
        if label and value:
            data[label.get_text(" ", strip=True).rstrip(":")] = value.get_text(" ", strip=True)
    return data


def _parse_id_date(value: str | None) -> date | None:
    if not value or value == "-":
        return None
    months = {
        "Januari": 1,
        "Februari": 2,
        "Maret": 3,
        "April": 4,
        "Mei": 5,
        "Juni": 6,
        "Juli": 7,
        "Agustus": 8,
        "September": 9,
        "Oktober": 10,
        "November": 11,
        "Desember": 12,
        "January": 1,
        "February": 2,
        "March": 3,
        "April": 4,
        "May": 5,
        "June": 6,
        "July": 7,
        "August": 8,
        "September": 9,
        "October": 10,
        "November": 11,
        "December": 12,
    }
    parts = value.split()
    if len(parts) != 3:
        return None
    day = int(parts[0])
    month = months.get(parts[1])
    year = int(parts[2])
    if month is None:
        return None
    return date(year, month, day)


def _next_business_day(value: date | None) -> date | None:
    if value is None:
        return None
    next_day = value + pd.offsets.BDay(1)
    return next_day.date() if hasattr(next_day, "date") else next_day


def _extract_rupiah_amount(text: str) -> float | None:
    if not text:
        return None
    match = re.search(r"Rp\s*([0-9\.\,]+)", text, re.IGNORECASE)
    if not match:
        return None
    raw = match.group(1).replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _normalize_company_name(value: str) -> str:
    return value.replace(", PT", " Tbk").replace(" Tbk, PT", " Tbk").strip()


def _get_with_retry(session: requests.Session, url: str, timeout: int = 20) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(REQUEST_RETRIES):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt == REQUEST_RETRIES - 1:
                break
            time.sleep(REQUEST_BACKOFF_SECONDS * (attempt + 1))
    assert last_error is not None
    raise last_error

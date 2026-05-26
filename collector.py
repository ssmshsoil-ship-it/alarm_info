from __future__ import annotations

import argparse
import datetime as dt
from email.utils import parsedate_to_datetime
import hashlib
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests


BASE_DIR = Path(__file__).resolve().parent
SOURCES_PATH = BASE_DIR / "sources.json"
ALERTS_PATH = BASE_DIR / "alerts.json"


def now_kst() -> dt.datetime:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))


def load_sources() -> dict:
    with SOURCES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_datetime(value: str) -> str:
    if value:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
        except Exception:
            pass
    return now_kst().date().isoformat()


def infer_region(text: str, regions: list[str]) -> str:
    for region in regions:
        if region != "전국" and region in text:
            return region
    return "전국"


def infer_category(text: str, fallback: str, keywords: list[str]) -> str:
    for keyword in keywords:
        if keyword in text:
            if keyword == "작물보호제":
                return "농약"
            if keyword == "농자재":
                return "농업뉴스"
            return keyword
    return fallback or "농업뉴스"


def source_from_entry(source_title: str, link: str, feed_name: str) -> str:
    if source_title:
        return clean_text(source_title)
    host = urlparse(link).netloc.replace("www.", "")
    return host or feed_name


def make_id(link: str, title: str) -> str:
    raw = f"{link}|{title}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:16]


def build_summary(title: str, category: str) -> list[str]:
    guide = "원문 링크에서 신청기간, 대상지역, 신청방법을 재확인하세요."
    if category in {"상토", "비료", "퇴비", "종자", "농약", "농업e지", "보조사업"}:
        return [
            f"{category} 관련 정보가 감지되었습니다.",
            "신청기간, 대상자, 신청처가 있는지 확인이 필요합니다.",
            guide,
        ]
    return [
        "농업 관련 신규 정보가 감지되었습니다.",
        "지역과 품목 관련성이 있는지 확인이 필요합니다.",
        guide,
    ]


def child_text(node: ET.Element, name: str) -> str:
    child = node.find(name)
    if child is not None and child.text:
        return child.text
    return ""


def source_text(node: ET.Element) -> str:
    for child in node:
        if child.tag.endswith("source") and child.text:
            return child.text
    return ""


def fetch_feed_items(url: str) -> list[dict]:
    response = requests.get(
        url,
        timeout=25,
        headers={"User-Agent": "kFarmAI-alert-test/1.0"},
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    items = root.findall(".//item")
    parsed_items = []
    for item in items:
        parsed_items.append(
            {
                "title": child_text(item, "title"),
                "summary": child_text(item, "description"),
                "link": child_text(item, "link"),
                "published": child_text(item, "pubDate"),
                "source": source_text(item),
            }
        )
    return parsed_items


def collect() -> list[dict]:
    sources = load_sources()
    keywords = sources.get("keywords", [])
    regions = sources.get("regions", ["전국"])
    alerts: list[dict] = []

    for feed in sources.get("feeds", []):
        try:
            entries = fetch_feed_items(feed["url"])
        except Exception as exc:
            print(f"수집 실패: {feed.get('name')} - {exc}")
            continue
        for entry in entries[:20]:
            title = clean_text(entry.get("title", ""))
            summary = clean_text(entry.get("summary", ""))
            link = entry.get("link", "")
            combined = f"{title} {summary}"
            if keywords and not any(k in combined for k in keywords):
                continue

            category = infer_category(combined, feed.get("category", ""), keywords)
            published_at = parse_datetime(entry.get("published", ""))
            source = source_from_entry(entry.get("source", ""), link, feed.get("name", "수집정보"))
            alerts.append(
                {
                    "id": make_id(link, title),
                    "title": title,
                    "source": source,
                    "region": infer_region(combined, regions),
                    "category": category,
                    "published_at": published_at,
                    "startDate": published_at,
                    "endDate": "",
                    "deadline": "",
                    "method": "원문 확인 필요",
                    "url": link,
                    "summary": build_summary(title, category),
                    "collected_at": now_kst().isoformat(timespec="seconds"),
                }
            )

    deduped = {}
    for alert in alerts:
        deduped[alert["id"]] = alert
    return sorted(deduped.values(), key=lambda x: x.get("published_at", ""), reverse=True)


def load_existing() -> list[dict]:
    if not ALERTS_PATH.exists():
        return []
    try:
        with ALERTS_PATH.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload.get("alerts", []) if isinstance(payload, dict) else payload
    except Exception:
        return []


def save_alerts(alerts: list[dict]) -> None:
    payload = {
        "generated_at": now_kst().isoformat(timespec="seconds"),
        "timezone": "Asia/Seoul",
        "alerts": alerts[:200],
    }
    with ALERTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def telegram_message(alerts: list[dict], limit: int = 8) -> str:
    lines = [
        "[kFarmAI 상토업계 알람]",
        f"수집시각: {now_kst().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    if not alerts:
        lines.append("새로 표시할 관련 정보가 없습니다.")
        return "\n".join(lines)

    for i, alert in enumerate(alerts[:limit], 1):
        lines.append(f"{i}. [{alert.get('category', '농업뉴스')}] {alert.get('title', '')}")
        lines.append(f"   출처: {alert.get('source', '')} / 날짜: {alert.get('published_at', '')}")
        if alert.get("url"):
            lines.append(f"   {alert['url']}")
        lines.append("")
    lines.append("정확한 신청기간, 대상자, 금액은 원문과 담당기관을 재확인하세요.")
    return "\n".join(lines).strip()


def send_telegram(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 없어 텔레그램 발송은 건너뜁니다.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text[:3900],
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    response.raise_for_status()
    print("텔레그램 발송 완료")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send-telegram", action="store_true")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()

    existing = load_existing()
    collected = collect()
    merged = {a.get("id"): a for a in existing if a.get("id")}
    for alert in collected:
      merged[alert["id"]] = alert
    final_alerts = sorted(
        merged.values(),
        key=lambda x: (x.get("published_at", ""), x.get("collected_at", "")),
        reverse=True,
    )
    save_alerts(final_alerts)
    print(f"수집 {len(collected)}건, 전체 저장 {len(final_alerts[:200])}건")

    if args.send_telegram:
        send_telegram(telegram_message(collected, limit=args.limit))


if __name__ == "__main__":
    main()

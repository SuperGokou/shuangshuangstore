"""Scrape JunAn order pages and their full tracking pages.

This script uses your own JunAn account. It does not bypass CAPTCHA.
When the saved browser session is missing or expired, it opens Chromium,
fills credentials from `.env`, and waits for you to enter the CAPTCHA.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from dotenv import load_dotenv
from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://www.junanex.com"
LOGIN_URL = f"{BASE_URL}/user/login"

ORDER_PAGES = [
    {
        "key": "not_submitted",
        "label": "未发往库房",
        "url": f"{BASE_URL}/orders",
    },
    {
        "key": "processing",
        "label": "库房处理中",
        "url": f"{BASE_URL}/orders/processing",
    },
    {
        "key": "departed",
        "label": "已运往中国",
        "url": f"{BASE_URL}/orders/departed",
    },
]

LOCAL_ORDER_RE = re.compile(r"\bZC\d{8,}[A-Z]{1,4}\b", re.I)
DOMESTIC_TRACKING_RE = re.compile(r"\b(?:SF|YT|YTO|STO|ZTO|JD|EMS)\d{8,}\b", re.I)
DATE_RE = re.compile(r"(20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}(?:日)?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)|(?<!\d)(?:\d{3,4}[-\s]?)?\d{7,8}(?:[-\s]\d{1,6})?(?!\d)")


@dataclass(frozen=True)
class Settings:
    email: str
    password: str
    headless: bool
    session_path: Path
    output_path: Path
    max_pages: int
    max_order_detail_pages: int
    max_tracking_pages: int
    login_timeout_seconds: int
    slow_mo_ms: int


def first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def read_plain_env_credentials() -> tuple[str, str]:
    """Accept a local .env that contains only two plain lines: email then password."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return "", ""

    lines = []
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip().strip("'\"")
        if stripped and not stripped.startswith("#") and "=" not in stripped:
            lines.append(stripped)

    if len(lines) >= 2:
        return lines[0], lines[1]
    return "", ""


def truthy(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    email = first_env("JUNANEX_EMAIL", "JUNAN_EMAIL", "JUNANEX_USER", "JUNANEX_USERNAME", "EMAIL", "LOGIN_EMAIL")
    password = first_env("JUNANEX_PASSWORD", "JUNAN_PASSWORD", "PASSWORD", "LOGIN_PASSWORD")
    if not email or not password:
        plain_email, plain_password = read_plain_env_credentials()
        email = email or plain_email
        password = password or plain_password

    if not email or not password:
        print(
            "ERROR: Put JUNANEX_EMAIL and JUNANEX_PASSWORD in .env, "
            "or use two plain lines: email on line 1 and password on line 2.",
            file=sys.stderr,
        )
        sys.exit(2)

    session_path = ROOT / os.environ.get("JUNANEX_SESSION_PATH", ".junanex/session.json")
    output_path = ROOT / os.environ.get("JUNANEX_OUTPUT_PATH", "data/junanex-orders.json")
    headless = truthy(os.environ.get("JUNANEX_HEADLESS"), default=session_path.exists())

    return Settings(
        email=email,
        password=password,
        headless=headless,
        session_path=session_path,
        output_path=output_path,
        max_pages=max(1, int(os.environ.get("JUNANEX_MAX_PAGES", "10"))),
        max_order_detail_pages=max(0, int(os.environ.get("JUNANEX_MAX_ORDER_DETAIL_PAGES", "200"))),
        max_tracking_pages=max(0, int(os.environ.get("JUNANEX_MAX_TRACKING_PAGES", "120"))),
        login_timeout_seconds=max(30, int(os.environ.get("JUNANEX_LOGIN_TIMEOUT_SECONDS", "600"))),
        slow_mo_ms=max(0, int(os.environ.get("JUNANEX_SLOW_MO_MS", "0"))),
    )


def ensure_logged_in(context: BrowserContext, page: Page, settings: Settings) -> None:
    page.goto(f"{BASE_URL}/orders/departed", wait_until="domcontentloaded", timeout=60_000)
    if not is_login_page(page):
        return

    if settings.headless:
        raise RuntimeError(
            "JunAn session expired or not created. Set JUNANEX_HEADLESS=false, run again, "
            "type the CAPTCHA in the opened browser, and click 登录."
        )

    print("JunAn requires CAPTCHA. I filled email/password; please enter CAPTCHA and click 登录.")
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
    page.fill("input[name='email'], #email", settings.email)
    page.fill("input[name='password'], #password", settings.password)
    try:
        page.locator("input[name='captcha'], #captcha").first.focus(timeout=5_000)
    except PlaywrightTimeoutError:
        pass

    deadline = time.time() + settings.login_timeout_seconds
    while time.time() < deadline:
        page.wait_for_timeout(1_000)
        if not is_login_page(page):
            settings.session_path.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(settings.session_path))
            print(f"Saved JunAn session: {settings.session_path.relative_to(ROOT)}")
            return

    raise TimeoutError("Timed out waiting for CAPTCHA login.")


def is_login_page(page: Page) -> bool:
    if "/user/login" in page.url:
        return True
    try:
        return page.locator("input[name='email'], #email").first.is_visible(timeout=700)
    except PlaywrightTimeoutError:
        return False


def scrape_orders(page: Page, settings: Settings) -> list[dict[str, Any]]:
    orders: list[dict[str, Any]] = []
    for config in ORDER_PAGES:
        page_orders = scrape_order_category(page, config, settings.max_pages)
        print(f"{config['label']}: {len(page_orders)} order(s)")
        orders.extend(page_orders)

    orders = dedupe_orders(orders)

    detail_count = 0
    for order in orders:
        detail_url = order.get("order_detail_url")
        needs_contact = not order.get("recipient_phone") or not order.get("recipient_address")
        if not detail_url or not needs_contact or detail_count >= settings.max_order_detail_pages:
            continue
        detail_count += 1
        detail = scrape_order_detail_page(page, detail_url)
        merge_missing(order, detail)
        print(f"  recipient detail {detail_count}: {order.get('local_order_number') or detail_url}")

    tracking_count = 0
    for order in orders:
        url = order.get("tracking_page_url") or order.get("detail_url")
        if not url or tracking_count >= settings.max_tracking_pages:
            continue
        tracking_count += 1
        detail = scrape_tracking_page(page, url)
        order.update({key: value for key, value in detail.items() if value})
        print(f"  tracking {tracking_count}: {order.get('local_order_number') or url}")

    return orders


def merge_missing(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if value and not target.get(key):
            target[key] = value


def scrape_order_category(page: Page, config: dict[str, str], max_pages: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    next_url = config["url"]

    for page_number in range(1, max_pages + 1):
        page.goto(next_url, wait_until="domcontentloaded", timeout=60_000)
        wait_quietly(page)
        if is_login_page(page):
            raise RuntimeError(f"Session expired while opening {next_url}")

        snapshot = extract_order_table(page)
        for row in snapshot["rows"]:
            record = parse_order_row(row, config, page.url, page_number)
            if record:
                if not record.get("tracking_page_url") and row_has_full_tracking_action(row):
                    resolved_url = resolve_tracking_url_by_click(page, int(row.get("row_index", -1)))
                    if resolved_url:
                        record["tracking_page_url"] = resolved_url
                        record["tracking_url_resolved_by_click"] = True
                records.append(record)

        next_link = snapshot.get("next_url") or ""
        if not next_link or next_link == next_url:
            break
        next_url = next_link

    return records


def wait_quietly(page: Page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except PlaywrightTimeoutError:
        page.wait_for_timeout(1_000)


def extract_order_table(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const clean = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const abs = (href) => {
            try { return href ? new URL(href, location.href).href : ''; } catch { return href || ''; }
          };
          const attrs = (el) => ({
            text: clean(el.innerText || el.value),
            href: abs(el.getAttribute('href') || el.getAttribute('formaction') || el.dataset?.url || el.dataset?.href || ''),
            title: clean(el.getAttribute('title') || el.getAttribute('aria-label') || el.getAttribute('data-original-title')),
            className: el.className || '',
            onclick: el.getAttribute('onclick') || '',
            dataset: Object.assign({}, el.dataset || {})
          });
          const tables = Array.from(document.querySelectorAll('table'));
          const table = tables.sort((a, b) => b.querySelectorAll('tr').length - a.querySelectorAll('tr').length)[0];
          const headers = table
            ? Array.from(table.querySelectorAll('thead th')).map((th) => clean(th.innerText))
            : [];
          const allRows = table ? Array.from(table.querySelectorAll('tr')) : [];
          const rows = allRows
            .filter((row) => !row.closest('thead') && row.querySelectorAll('td').length > 0)
            .map((row, rowIndex) => {
              const cells = Array.from(row.querySelectorAll('td')).map((cell, index) => ({
                header: headers[index] || `Column ${index + 1}`,
                text: clean(cell.innerText),
                html: cell.innerHTML,
                links: Array.from(cell.querySelectorAll('a[href]')).map(attrs),
                controls: Array.from(cell.querySelectorAll('button, input[type=button], input[type=submit]')).map(attrs)
              }));
              return {
                row_index: rowIndex,
                text: clean(row.innerText),
                cells,
                links: Array.from(row.querySelectorAll('a[href]')).map(attrs)
              };
            });
          const next = Array.from(document.querySelectorAll('a[href]')).find((a) => /下一页|下页|Next|›|»/.test(clean(a.innerText)));
          return { headers, rows, next_url: next ? abs(next.getAttribute('href')) : '' };
        }
        """
    )


def resolve_tracking_url_by_click(page: Page, row_index: int) -> str:
    if row_index < 0:
        return ""

    original_url = page.url
    marked = page.evaluate(
        """
        (rowIndex) => {
          const clean = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          document.querySelectorAll('[data-codex-logistics-click]').forEach((node) => {
            delete node.dataset.codexLogisticsClick;
          });
          const table = Array.from(document.querySelectorAll('table'))
            .sort((a, b) => b.querySelectorAll('tr').length - a.querySelectorAll('tr').length)[0];
          if (!table) return false;
          const rows = Array.from(table.querySelectorAll('tr'))
            .filter((row) => !row.closest('thead') && row.querySelectorAll('td').length > 0);
          const row = rows[rowIndex];
          if (!row) return false;
          const candidates = Array.from(row.querySelectorAll('a, button, input[type=button], input[type=submit]'));
          const target = candidates.find((el) => {
            const text = [
              clean(el.innerText || el.value),
              clean(el.getAttribute('title')),
              clean(el.getAttribute('aria-label')),
              clean(el.getAttribute('data-original-title')),
              el.className || '',
              el.getAttribute('onclick') || ''
            ].join(' ');
            return /完整物流|物流信息|tracking/i.test(text) && !/复制|copy/i.test(text);
          });
          if (!target) return false;
          target.dataset.codexLogisticsClick = '1';
          return true;
        }
        """,
        row_index,
    )
    if not marked:
        return ""

    trigger = page.locator("[data-codex-logistics-click='1']").first
    try:
        with page.expect_popup(timeout=4_000) as popup_info:
            trigger.click(timeout=5_000)
        popup = popup_info.value
        wait_quietly(popup)
        url = popup.url
        popup.close()
        return url if url != "about:blank" else ""
    except PlaywrightTimeoutError:
        wait_quietly(page)
        if page.url != original_url:
            url = page.url
            page.goto(original_url, wait_until="domcontentloaded", timeout=60_000)
            wait_quietly(page)
            return url
    except Exception as exc:
        print(f"  could not click complete tracking for row {row_index + 1}: {exc}")

    return ""


def parse_order_row(row: dict[str, Any], config: dict[str, str], source_url: str, page_number: int) -> dict[str, Any] | None:
    cells = row.get("cells", [])
    if not cells:
        return None

    values = {cell.get("header", ""): cell.get("text", "") for cell in cells}
    text = row.get("text", "")
    local_number = first_match(LOCAL_ORDER_RE, text)
    if not local_number and len(text) < 12:
        return None

    recipient_cell = get_cell(cells, ["收件人", "概要", "Recipient"])
    status_cell = get_cell(cells, ["发递单状态", "发货单状态", "状态", "Status"])
    item_cell = get_cell(cells, ["内件明细", "物品", "Items"])

    tracking_url = find_full_tracking_url(row)
    order_detail_url = find_order_detail_url(row, local_number)
    copy_url = find_copy_logistics_url(row)
    domestic_tracking = first_match(DOMESTIC_TRACKING_RE, status_cell.get("text", "") if status_cell else text)
    status_text = strip_action_text(status_cell.get("text", "") if status_cell else "")
    recipient_text = strip_action_text(recipient_cell.get("text", "") if recipient_cell else "")
    recipient_phone = extract_phone(recipient_text)
    recipient_address = extract_address(recipient_text)

    stable_fallback_id = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:12]

    record = {
        "id": f"{config['key']}-{local_number or stable_fallback_id}",
        "source": "junanex",
        "source_category": config["key"],
        "page_label": config["label"],
        "source_url": source_url,
        "source_page": page_number,
        "local_order_number": local_number,
        "order_detail_url": order_detail_url,
        "tracking_page_url": tracking_url,
        "copy_logistics_url": copy_url,
        "recipient_summary": recipient_text,
        "recipient_name": first_line(recipient_text),
        "recipient_region": second_line(recipient_text),
        "recipient_phone": recipient_phone,
        "recipient_address": recipient_address,
        "has_id_number": "有身份证号" in recipient_text,
        "has_id_image": "有身份证图片" in recipient_text,
        "order_status": status_text,
        "latest_status": latest_status_from_text(status_text) or default_status(config["key"]),
        "latest_time": first_match(DATE_RE, status_text),
        "domestic_tracking": domestic_tracking,
        "item_summary": first_line(item_cell.get("text", "") if item_cell else ""),
        "items_detail": strip_action_text(item_cell.get("text", "") if item_cell else ""),
        "actual_weight": get_value(cells, ["实际重量"]),
        "billing_weight": get_value(cells, ["计费重量"]),
        "total_fee": get_value(cells, ["实际总扣费", "扣费", "运费", "费用"]),
        "raw_text": text,
        "raw_cells": values,
        "tracking_history": [],
    }
    return record


def get_cell(cells: list[dict[str, Any]], needles: list[str]) -> dict[str, Any] | None:
    for cell in cells:
        header = cell.get("header", "")
        if any(needle.lower() in header.lower() for needle in needles):
            return cell
    return None


def get_value(cells: list[dict[str, Any]], needles: list[str]) -> str:
    cell = get_cell(cells, needles)
    return strip_action_text(cell.get("text", "")) if cell else ""


def find_order_detail_url(row: dict[str, Any], local_number: str) -> str:
    actions = collect_actions(row)
    for action in actions:
        haystack = action_haystack(action)
        if local_number and local_number in haystack:
            url = url_from_action(action)
            if is_order_detail_url(url):
                return url

    for action in actions:
        url = url_from_action(action)
        if is_order_detail_url(url):
            return url

    return ""


def is_order_detail_url(url: str) -> bool:
    if not url:
        return False
    normalized = url.rstrip("/")
    order_list_urls = {config["url"].rstrip("/") for config in ORDER_PAGES}
    if normalized in order_list_urls:
        return False
    return "/orders" in normalized and not re.search(r"tracking|logistics|captcha|login", normalized, re.I)


def scrape_order_detail_page(page: Page, url: str) -> dict[str, Any]:
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    wait_quietly(page)
    if is_login_page(page):
        raise RuntimeError(f"Session expired while opening order detail {url}")

    snapshot = page.evaluate(
        """
        () => {
          const clean = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const pairs = [];
          const pushPair = (label, value) => {
            const cleanLabel = clean(label).replace(/[：:]+$/, '');
            const cleanValue = clean(value);
            if (cleanLabel && cleanValue && cleanLabel !== cleanValue) {
              pairs.push({ label: cleanLabel, value: cleanValue });
            }
          };

          document.querySelectorAll('tr').forEach((row) => {
            const cells = Array.from(row.children).map((cell) => clean(cell.innerText)).filter(Boolean);
            if (cells.length >= 2) {
              for (let i = 0; i < cells.length - 1; i += 2) {
                pushPair(cells[i], cells[i + 1]);
              }
              if (cells.length === 2) pushPair(cells[0], cells[1]);
            }
          });

          document.querySelectorAll('dt').forEach((dt) => {
            const dd = dt.nextElementSibling;
            if (dd) pushPair(dt.innerText, dd.innerText);
          });

          document.querySelectorAll('label').forEach((label) => {
            const id = label.getAttribute('for');
            const control = id ? document.getElementById(id) : label.parentElement?.querySelector('input, textarea, select');
            if (control) pushPair(label.innerText, control.value || control.innerText);
          });

          document.querySelectorAll('input, textarea, select').forEach((control) => {
            const label = control.getAttribute('name') || control.getAttribute('id') || control.getAttribute('placeholder') || control.getAttribute('aria-label');
            if (label) pushPair(label, control.value || control.innerText);
          });

          return {
            url: location.href,
            title: document.title,
            pairs,
            text: clean(document.body.innerText)
          };
        }
        """
    )

    pairs = snapshot.get("pairs", [])
    text = snapshot.get("text", "")
    return {
        "order_detail_url": snapshot.get("url", url),
        "recipient_name": first_pair_value(pairs, ["收件人", "收货人", "姓名", "name"]) or extract_recipient_name(text),
        "recipient_phone": first_pair_value(pairs, ["电话", "手机", "联系电话", "mobile", "phone", "tel"]) or extract_phone(text),
        "recipient_address": first_pair_value(pairs, ["收货地址", "详细地址", "地址", "address"]) or extract_address(text),
    }


def first_pair_value(pairs: list[dict[str, Any]], needles: list[str]) -> str:
    for pair in pairs:
        label = str(pair.get("label", ""))
        if any(needle.lower() in label.lower() for needle in needles):
            return cleanup_contact_value(str(pair.get("value", "")))
    return ""


def extract_recipient_name(text: str) -> str:
    return extract_labeled_value(text, ["收件人", "收货人", "姓名", "Name"])


def extract_phone(text: str) -> str:
    match = PHONE_RE.search(text or "")
    if not match:
        return ""
    return cleanup_contact_value(match.group(0))


def extract_address(text: str) -> str:
    value = extract_labeled_value(text, ["收货地址", "详细地址", "地址", "Address"])
    if value:
        return cleanup_contact_value(value)

    for chunk in re.split(r"\s{2,}|\n| {3,}", text or ""):
        candidate = cleanup_contact_value(chunk)
        if 8 <= len(candidate) <= 160 and re.search(r"省|市|区|县|镇|路|街|号|室|村|China|中国", candidate, re.I):
            if not LOCAL_ORDER_RE.search(candidate) and not DOMESTIC_TRACKING_RE.search(candidate):
                return candidate
    return ""


def extract_labeled_value(text: str, labels: list[str]) -> str:
    clean_text = re.sub(r"\s+", " ", text or "").strip()
    if not clean_text:
        return ""
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_labels = [
        "收件人",
        "收货人",
        "姓名",
        "电话",
        "手机",
        "联系电话",
        "地址",
        "收货地址",
        "详细地址",
        "邮编",
        "身份证",
        "发货单",
        "内件",
        "重量",
        "扣费",
        "状态",
        "备注",
    ]
    stop_pattern = "|".join(re.escape(label) for label in stop_labels if label not in labels)
    match = re.search(rf"(?:{label_pattern})\s*[:：]?\s*(.*?)(?=\s+(?:{stop_pattern})\s*[:：]?|$)", clean_text, re.I)
    return cleanup_contact_value(match.group(1)) if match else ""


def cleanup_contact_value(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" ：:-")


def find_full_tracking_url(row: dict[str, Any]) -> str:
    actions = collect_actions(row)
    for action in actions:
        haystack = action_haystack(action)
        if ("完整物流" in haystack or "tracking" in haystack.lower() or "物流信息" in haystack) and "复制" not in haystack:
            url = url_from_action(action)
            if url:
                return url
    return ""


def find_copy_logistics_url(row: dict[str, Any]) -> str:
    actions = collect_actions(row)
    for action in actions:
        haystack = action_haystack(action)
        if "复制物流" in haystack or "copy" in haystack.lower():
            url = url_from_action(action)
            if url:
                return url
    return ""


def row_has_full_tracking_action(row: dict[str, Any]) -> bool:
    for action in collect_actions(row):
        haystack = action_haystack(action)
        if ("完整物流" in haystack or "物流信息" in haystack or "tracking" in haystack.lower()) and "复制" not in haystack:
            return True
    return False


def collect_actions(row: dict[str, Any]) -> list[dict[str, Any]]:
    actions = list(row.get("links", []))
    for cell in row.get("cells", []):
        actions.extend(cell.get("links", []))
        actions.extend(cell.get("controls", []))
    return actions


def action_haystack(action: dict[str, Any]) -> str:
    dataset = action.get("dataset") if isinstance(action.get("dataset"), dict) else {}
    values = [str(action.get(key, "")) for key in ["text", "title", "className", "onclick", "href"]]
    values.extend(str(value) for value in dataset.values())
    return " ".join(values)


def url_from_action(action: dict[str, Any]) -> str:
    dataset = action.get("dataset") if isinstance(action.get("dataset"), dict) else {}
    candidates = [str(action.get("href", "")), *[str(value) for value in dataset.values()], url_from_onclick(action.get("onclick", ""))]
    for candidate in candidates:
        normalized = normalize_url_candidate(candidate)
        if normalized:
            return normalized
    return ""


def normalize_url_candidate(value: str) -> str:
    candidate = (value or "").strip()
    if not candidate or candidate.startswith("#") or candidate.lower().startswith("javascript:"):
        return ""
    if not re.search(r"^(https?://|/)|tracking|logistics|orders", candidate, re.I):
        return ""
    return urljoin(BASE_URL, candidate)


def url_from_onclick(onclick: str) -> str:
    if not onclick:
        return ""
    match = re.search(r"['\"]((?:https?://|/)[^'\"]+)['\"]", onclick, re.I)
    if match:
        return match.group(1)
    match = re.search(r"['\"]([^'\"]*(?:tracking|logistics|orders)[^'\"]*)['\"]", onclick, re.I)
    return match.group(1) if match else ""


def scrape_tracking_page(page: Page, url: str) -> dict[str, Any]:
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    wait_quietly(page)
    snapshot = page.evaluate(
        """
        () => {
          const clean = (value) => (value || '').replace(/\\s+/g, ' ').trim();
          const rows = Array.from(document.querySelectorAll('tr')).map((row) => clean(row.innerText)).filter(Boolean);
          const items = Array.from(document.querySelectorAll('li, .timeline li, .track li, .logistics li, .step, .event'))
            .map((node) => clean(node.innerText))
            .filter((text) => text.length > 5);
          return {
            url: location.href,
            title: document.title,
            rows,
            items,
            text: clean(document.body.innerText)
          };
        }
        """
    )
    events = parse_tracking_events(snapshot.get("items", []) + snapshot.get("rows", []) + snapshot.get("text", "").split("  "))
    latest = events[0] if events else {}
    return {
        "detail_url": snapshot.get("url", url),
        "latest_status": latest.get("status", ""),
        "latest_time": latest.get("time", ""),
        "tracking_history": events,
    }


def parse_tracking_events(chunks: list[str]) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    seen: set[str] = set()
    for chunk in chunks:
        text = re.sub(r"\s+", " ", str(chunk)).strip()
        if len(text) < 8:
            continue
        date_match = DATE_RE.search(text)
        if date_match:
            time_text = date_match.group(1)
            status = text.replace(time_text, "").strip(" -：:|")
        else:
            if not any(word in text for word in ["运输", "到达", "离开", "清关", "派送", "签收", "收货", "入库"]):
                continue
            time_text = ""
            status = text
        key = f"{time_text}|{status}"
        if status and key not in seen:
            events.append({"time": time_text, "status": status})
            seen.add(key)
    return events[:12]


def dedupe_orders(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for record in records:
        key = record.get("local_order_number") or record.get("tracking_page_url") or record["id"]
        existing = merged.get(key)
        if not existing:
            record["categories"] = [record["source_category"]]
            record["page_labels"] = [record["page_label"]]
            merged[key] = record
            continue
        if record["source_category"] not in existing["categories"]:
            existing["categories"].append(record["source_category"])
        if record["page_label"] not in existing["page_labels"]:
            existing["page_labels"].append(record["page_label"])
        for field, value in record.items():
            if not existing.get(field) and value:
                existing[field] = value
    return list(merged.values())


def build_output(orders: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "junanex",
        "source_pages": ORDER_PAGES,
        "summary": {
            "total": len(orders),
            "not_submitted": sum(1 for item in orders if "not_submitted" in item.get("categories", [])),
            "processing": sum(1 for item in orders if "processing" in item.get("categories", [])),
            "departed": sum(1 for item in orders if "departed" in item.get("categories", [])),
            "with_tracking_page": sum(1 for item in orders if item.get("tracking_page_url") or item.get("detail_url")),
            "with_tracking_history": sum(1 for item in orders if item.get("tracking_history")),
        },
        "orders": orders,
    }


def strip_action_text(value: str) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    for phrase in ["复制物流信息网址", "完整物流信息", "确认客户已收货", "有身份证号", "有身份证图片"]:
        text = text.replace(phrase, " ")
    return re.sub(r"\s+", " ", text).strip()


def first_line(value: str) -> str:
    return re.split(r"\s{2,}|\n", value.strip())[0].strip() if value else ""


def second_line(value: str) -> str:
    parts = [part.strip() for part in re.split(r"\s{2,}|\n", value.strip()) if part.strip()]
    return parts[1] if len(parts) > 1 else ""


def latest_status_from_text(value: str) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    if not text:
        return ""
    pieces = re.split(r"(?=20\d{2}[-/年]\d{1,2})|(?=#\d+)", text)
    return pieces[0].strip() if pieces else text


def default_status(stage: str) -> str:
    return {
        "not_submitted": "未发往库房",
        "processing": "库房处理中",
        "departed": "已运往中国",
    }.get(stage, "待确认")


def first_match(pattern: re.Pattern[str], value: str) -> str:
    match = pattern.search(value or "")
    return match.group(0) if match else ""


def main() -> None:
    settings = load_settings()
    settings.output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=settings.headless, slow_mo=settings.slow_mo_ms)
        context_args: dict[str, Any] = {"viewport": {"width": 1600, "height": 1100}, "locale": "zh-CN"}
        if settings.session_path.exists():
            context_args["storage_state"] = str(settings.session_path)
        context = browser.new_context(**context_args)
        page = context.new_page()
        try:
            ensure_logged_in(context, page, settings)
            orders = scrape_orders(page, settings)
            settings.output_path.write_text(json.dumps(build_output(orders), ensure_ascii=False, indent=2), encoding="utf-8")
            context.storage_state(path=str(settings.session_path))
            print(f"Wrote {len(orders)} orders to {settings.output_path.relative_to(ROOT)}")
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()

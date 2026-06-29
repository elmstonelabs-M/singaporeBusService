from __future__ import annotations

from datetime import date, timedelta
from html import escape

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.core.config import get_settings
from app.services.log_service import (
    build_today_usage_summary,
    clamp_log_limit,
    read_recent_arrivals_log_lines,
)
from app.services.retention_service import (
    RETENTION_DAYS,
    RETENTION_PLATFORMS,
    RetentionService,
    get_retention_service,
)
from app.utils.time_utils import singapore_now

router = APIRouter(prefix="/ops", tags=["ops"])
page_router = APIRouter(tags=["ops"])


@router.get("/logs", summary="Get recent application logs and today's usage summary")
async def get_ops_logs(
    limit: int = Query(default=100, ge=1, le=500),
    token: str | None = Query(default=None),
    x_ops_token: str | None = Header(default=None, alias="X-Ops-Token"),
) -> dict:
    settings = get_settings()
    _ensure_authorized(settings.ops_log_token, token, x_ops_token)
    if not settings.log_file_path:
        raise HTTPException(status_code=404, detail="Application file logging is not enabled.")

    bounded_limit = clamp_log_limit(limit)
    return {
        "log_file": settings.log_file_path,
        "limit": bounded_limit,
        "today": build_today_usage_summary(settings.log_file_path),
        "lines": read_recent_arrivals_log_lines(settings.log_file_path, bounded_limit),
    }


@router.get("/retention", summary="Get user retention metrics")
async def get_ops_retention(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    platform: str = Query(default="all"),
    token: str | None = Query(default=None),
    x_ops_token: str | None = Header(default=None, alias="X-Ops-Token"),
    service: RetentionService = Depends(get_retention_service),
) -> dict:
    settings = get_settings()
    _ensure_authorized(settings.ops_log_token, token, x_ops_token)
    resolved_start_date, resolved_end_date = _resolve_retention_dates(start_date, end_date)
    return await service.get_retention_range(
        resolved_start_date,
        resolved_end_date,
        platform=platform,
    )


@page_router.get("/ops/logs", response_class=HTMLResponse, include_in_schema=False)
async def get_ops_logs_page(
    limit: int = Query(default=100, ge=1, le=500),
    token: str | None = Query(default=None),
    x_ops_token: str | None = Header(default=None, alias="X-Ops-Token"),
) -> HTMLResponse:
    settings = get_settings()
    _ensure_authorized(settings.ops_log_token, token, x_ops_token)
    if not settings.log_file_path:
        raise HTTPException(status_code=404, detail="Application file logging is not enabled.")

    bounded_limit = clamp_log_limit(limit)
    today = build_today_usage_summary(settings.log_file_path)
    lines = read_recent_arrivals_log_lines(settings.log_file_path, bounded_limit)
    return HTMLResponse(_render_logs_page(settings.log_file_path, bounded_limit, today, lines))


@page_router.get("/ops/retention", response_class=HTMLResponse, include_in_schema=False)
async def get_ops_retention_page(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    platform: str = Query(default="all"),
    token: str | None = Query(default=None),
    x_ops_token: str | None = Header(default=None, alias="X-Ops-Token"),
    service: RetentionService = Depends(get_retention_service),
) -> HTMLResponse:
    settings = get_settings()
    _ensure_authorized(settings.ops_log_token, token, x_ops_token)
    resolved_start_date, resolved_end_date = _resolve_retention_dates(start_date, end_date)
    payload = await service.get_retention_range(
        resolved_start_date,
        resolved_end_date,
        platform=platform,
    )
    return HTMLResponse(_render_retention_page(payload, token))


def _ensure_authorized(
    expected_token: str | None,
    query_token: str | None,
    header_token: str | None,
) -> None:
    if not expected_token:
        raise HTTPException(status_code=403, detail="OPS_LOG_TOKEN is not configured.")
    if header_token != expected_token and query_token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid ops log token.")


def _resolve_retention_dates(
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    today = singapore_now().date()
    resolved_end_date = end_date or today
    resolved_start_date = start_date or (resolved_end_date - timedelta(days=30))
    return resolved_start_date, resolved_end_date


def _render_logs_page(log_file: str, limit: int, today: dict, lines: list[str]) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td>{escape(item['endpoint'])}</td>"
        f"<td>{item['request_count']}</td>"
        f"<td>{item['ip_count']}</td>"
        f"<td>{item['device_count']}</td>"
        "</tr>"
        for item in today["top_endpoints"]
    )
    if not rows:
        rows = '<tr><td colspan="4">No app usage found for today.</td></tr>'

    platform_rows = "\n".join(
        "<tr>"
        f"<td>{escape(item['platform'])}</td>"
        f"<td>{item['request_count']}</td>"
        f"<td>{item['ip_count']}</td>"
        f"<td>{item['device_count']}</td>"
        "</tr>"
        for item in today["platforms"]
    )
    if not platform_rows:
        platform_rows = '<tr><td colspan="4">No platform requests found for today.</td></tr>'

    log_text = escape("\n".join(reversed(lines)))
    stats_cards = "\n".join(
        [
            _render_stat_card("Date", escape(today["date"])),
            _render_stat_card("Requests", today["request_count"]),
            _render_stat_card("Request IPs", today["ip_count"]),
            _render_stat_card("Active Devices", today["device_count"]),
            _render_stat_card("Platforms", today["platform_count"]),
            _render_stat_card("Client Errors (4xx)", today["client_error_count"]),
            _render_stat_card("Server Errors (5xx)", today["server_error_count"]),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ops Logs</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #17202a; background: #f6f8fa; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 24px; margin: 0 0 16px; }}
    h2 {{ font-size: 18px; margin: 28px 0 12px; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
    }}
    .stat, table, pre {{ background: #fff; border: 1px solid #d7dee7; border-radius: 8px; }}
    .stat {{ padding: 14px; }}
    .label {{ color: #5b6776; font-size: 12px; }}
    .value {{ font-size: 24px; margin-top: 6px; }}
    table {{ width: 100%; border-collapse: collapse; overflow: hidden; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #e6ebf1; text-align: left; }}
    th {{ background: #eef3f8; font-size: 13px; }}
    pre {{ padding: 16px; overflow: auto; white-space: pre-wrap; word-break: break-word; }}
    .meta {{ color: #5b6776; font-size: 13px; }}
  </style>
</head>
<body>
  <main>
    <h1>Ops Logs</h1>
    <p class="meta">
      Endpoint: /v1/bus-stops/{{bus_stop_code}}/arrivals |
      Log file: {escape(log_file)} |
      Recent lines: {limit} |
      Stats timezone: Asia/Singapore
    </p>
    <section class="stats">
      {stats_cards}
    </section>
    <h2>Top Endpoints</h2>
    <table>
      <thead><tr><th>Endpoint</th><th>Requests</th><th>Request IPs</th><th>Devices</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <h2>Platform Requests</h2>
    <table>
      <thead><tr><th>Platform</th><th>Requests</th><th>Request IPs</th><th>Devices</th></tr></thead>
      <tbody>{platform_rows}</tbody>
    </table>
    <h2>Recent Logs</h2>
    <pre>{log_text}</pre>
  </main>
</body>
</html>"""


def _render_stat_card(label: str, value: object) -> str:
    return (
        '<div class="stat">'
        f'<div class="label">{escape(str(label))}</div>'
        f'<div class="value">{escape(str(value))}</div>'
        "</div>"
    )


def _render_retention_page(payload: dict, token: str | None) -> str:
    day_headers = "".join(f"<th>{day}D</th>" for day in RETENTION_DAYS)
    rows = "\n".join(_render_retention_row(row) for row in payload["rows"])
    if not rows:
        rows = f'<tr><td colspan="{len(RETENTION_DAYS) + 2}">No retention data found.</td></tr>'
    platform_options = "\n".join(
        _render_platform_option(platform, payload["platform"])
        for platform in RETENTION_PLATFORMS
    )
    token_input = (
        f'<input type="hidden" name="token" value="{escape(token)}">'
        if token
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ops Retention</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #17202a; background: #f6f8fa; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 24px; margin: 0 0 16px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      background: #fff;
      border: 1px solid #d7dee7;
      border-radius: 8px;
    }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #e6ebf1; text-align: right; }}
    th {{ background: #eef3f8; font-size: 13px; }}
    th:first-child, td:first-child {{ text-align: left; }}
    .meta {{ color: #5b6776; font-size: 13px; }}
    .muted {{ color: #8792a2; }}
    .toolbar {{ display: flex; gap: 12px; align-items: end; margin: 16px 0; }}
    label {{ display: grid; gap: 6px; color: #5b6776; font-size: 13px; }}
    select, input {{ padding: 8px 10px; border: 1px solid #cfd8e3; border-radius: 6px; }}
    button {{
      padding: 8px 14px;
      border: 1px solid #95a3b8;
      border-radius: 6px;
      background: #fff;
      color: #17202a;
      cursor: pointer;
      font: inherit;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Ops Retention</h1>
    <p class="meta">
      Range: {escape(payload["start_date"])} to {escape(payload["end_date"])} |
      Timezone: {escape(payload["timezone"])}
    </p>
    <form class="toolbar" method="get">
      {token_input}
      <label>
        Platform
        <select name="platform">
          {platform_options}
        </select>
      </label>
      <label>
        Start Date
        <input type="date" name="start_date" value="{escape(payload["start_date"])}">
      </label>
      <label>
        End Date
        <input type="date" name="end_date" value="{escape(payload["end_date"])}">
      </label>
      <button type="submit">查询</button>
    </form>
    <table>
      <thead><tr><th>Date</th><th>New Users</th>{day_headers}</tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </main>
</body>
</html>"""


def _render_platform_option(platform: str, selected_platform: str) -> str:
    labels = {
        "all": "All",
        "ios": "iOS",
        "android": "Android",
        "unknown": "Unknown",
    }
    selected = " selected" if platform == selected_platform else ""
    return f'<option value="{platform}"{selected}>{labels.get(platform, platform)}</option>'


def _render_retention_row(row: dict) -> str:
    cells = [
        f"<td>{escape(row['cohort_date'])}</td>",
        f"<td>{row['new_users']}</td>",
    ]
    for day in RETENTION_DAYS:
        metric = row["retention"][str(day)]
        cells.append(f"<td>{_format_retention_metric(metric)}</td>")
    return f"<tr>{''.join(cells)}</tr>"


def _format_retention_metric(metric: dict) -> str:
    retained_users = metric["retained_users"]
    rate = metric["rate"]
    if retained_users is None or rate is None:
        return '<span class="muted">-</span>'
    return f"{retained_users} / {rate * 100:.1f}%"

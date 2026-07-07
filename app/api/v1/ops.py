from __future__ import annotations

import json
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
    engagement = payload["engagement"]
    overview = engagement["overview"]
    day_headers = "".join(f"<th>{day}D</th>" for day in RETENTION_DAYS)
    retention_rows = "\n".join(_render_retention_row(row) for row in payload["rows"])
    if not retention_rows:
        retention_rows = (
            f'<tr><td colspan="{len(RETENTION_DAYS) + 2}">No retention data found.</td></tr>'
        )
    daily_rows = "\n".join(_render_daily_active_row(row) for row in engagement["rows"])
    if not daily_rows:
        daily_rows = '<tr><td colspan="7">No active user data found.</td></tr>'
    overview_cards = "\n".join(
        [
            _render_overview_card("DAU", overview["dau"], "Daily Active Users"),
            _render_overview_card("WAU", overview["wau"], "Weekly Active Users"),
            _render_overview_card("MAU", overview["mau"], "Monthly Active Users"),
            _render_overview_card(
                "DAU / MAU",
                _format_rate_value(overview["dau_mau_rate"]),
                "User Stickiness",
            ),
            _render_overview_card(
                "WAU / MAU",
                _format_rate_value(overview["wau_mau_rate"]),
                "Weekly Stickiness",
            ),
            _render_overview_card("New Users", overview["new_users"], "New Users Today"),
        ]
    )
    platform_options = "\n".join(
        _render_platform_option(platform, payload["platform"])
        for platform in RETENTION_PLATFORMS
    )
    token_input = (
        f'<input type="hidden" name="token" value="{escape(token)}">'
        if token
        else ""
    )
    dashboard_data = _json_for_script(
        {
            "engagementRows": engagement["rows"],
            "cohortDetails": {
                row["cohort_date"]: row.get("detail", {})
                for row in payload["rows"]
            },
        }
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Retention & Engagement</title>
  {_retention_page_styles()}
</head>
<body>
  <main>
    <h1>Retention & Engagement</h1>
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
      <button class="primary-button" type="submit">&#26597;&#35810;</button>
    </form>
    <section class="overview-grid" aria-label="Overview">
      {overview_cards}
    </section>
    <section class="panel">
      <div class="section-heading">
        <h2>Active Users Trend</h2>
        <div class="legend">
          <span><i class="dot dau-dot"></i>DAU</span>
          <span><i class="dot wau-dot"></i>WAU</span>
          <span><i class="dot mau-dot"></i>MAU</span>
        </div>
      </div>
      <div class="chart-wrap">
        <svg id="active-users-chart" role="img" aria-label="Active users trend chart"></svg>
        <div id="chart-tooltip" class="chart-tooltip" hidden></div>
      </div>
    </section>
    <section class="panel">
      <h2>Daily Active Statistics</h2>
      <div class="table-wrap">
        <table id="daily-stats-table">
          <thead>
            <tr>
              <th data-sort="date">Date</th>
              <th data-sort="number">DAU</th>
              <th data-sort="number">WAU</th>
              <th data-sort="number">MAU</th>
              <th data-sort="number">DAU/MAU</th>
              <th data-sort="number">WAU/MAU</th>
              <th data-sort="number">New Users</th>
            </tr>
          </thead>
          <tbody>{daily_rows}</tbody>
        </table>
      </div>
    </section>
    <section class="panel">
      <h2>Cohort Retention</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Install Date</th><th>New Users</th>{day_headers}</tr></thead>
          <tbody>{retention_rows}</tbody>
        </table>
      </div>
    </section>
  </main>
  <div id="cohort-drawer-backdrop" class="drawer-backdrop" hidden></div>
  <aside id="cohort-drawer" class="drawer" aria-hidden="true" hidden>
    <div class="drawer-header">
      <h2>Cohort Details</h2>
      <button class="icon-button" type="button" data-close-drawer>&times;</button>
    </div>
    <dl class="detail-grid">
      <div><dt>Install Date</dt><dd id="drawer-install-date">-</dd></div>
      <div><dt>New Users</dt><dd id="drawer-new-users">-</dd></div>
      <div><dt>D1</dt><dd id="drawer-d1">-</dd></div>
      <div><dt>D3</dt><dd id="drawer-d3">-</dd></div>
      <div><dt>D7</dt><dd id="drawer-d7">-</dd></div>
      <div><dt>Current Active Users</dt><dd id="drawer-current-active">-</dd></div>
      <div><dt>Average Active Days</dt><dd id="drawer-average-days">-</dd></div>
      <div><dt>Latest Active Date</dt><dd id="drawer-latest-active">-</dd></div>
    </dl>
  </aside>
  <script id="dashboard-data" type="application/json">{dashboard_data}</script>
  {_retention_page_script()}
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
    cohort_date = escape(row["cohort_date"], quote=True)
    cells = [
        (
            '<td><button type="button" class="cohort-link" '
            f'data-cohort="{cohort_date}">{cohort_date}</button></td>'
        ),
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


def _render_overview_card(title: str, value: object, caption: str) -> str:
    return (
        '<article class="metric-card">'
        f'<div class="metric-title">{escape(title)}</div>'
        f'<div class="metric-value">{escape(str(value))}</div>'
        f'<div class="metric-caption">{escape(caption)}</div>'
        "</article>"
    )


def _render_daily_active_row(row: dict) -> str:
    row_date = escape(row["date"], quote=True)
    dau_mau_rate = row["dau_mau_rate"]
    wau_mau_rate = row["wau_mau_rate"]
    return (
        "<tr>"
        f'<td data-value="{row_date}">{row_date}</td>'
        f'<td data-value="{row["dau"]}">{row["dau"]}</td>'
        f'<td data-value="{row["wau"]}">{row["wau"]}</td>'
        f'<td data-value="{row["mau"]}">{row["mau"]}</td>'
        f'<td data-value="{_sort_rate_value(dau_mau_rate)}">{_format_rate_value(dau_mau_rate)}</td>'
        f'<td data-value="{_sort_rate_value(wau_mau_rate)}">{_format_rate_value(wau_mau_rate)}</td>'
        f'<td data-value="{row["new_users"]}">{row["new_users"]}</td>'
        "</tr>"
    )


def _format_rate_value(rate: float | None) -> str:
    if rate is None:
        return "-"
    return f"{rate * 100:.1f}%"


def _sort_rate_value(rate: float | None) -> str:
    if rate is None:
        return "-1"
    return str(rate)


def _json_for_script(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _retention_page_styles() -> str:
    return """<style>
    :root {
      --bg: #f6f8fa;
      --surface: #fff;
      --text: #17202a;
      --muted: #5b6776;
      --border: #d7dee7;
      --soft-border: #e6ebf1;
      --header: #eef3f8;
      --hover: #f8fbff;
      --primary: #2563eb;
      --success: #16a34a;
      --warning: #d97706;
      --shadow: 0 18px 45px rgba(15, 23, 42, 0.18);
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #0f172a;
        --surface: #111827;
        --text: #e5e7eb;
        --muted: #9ca3af;
        --border: #374151;
        --soft-border: #243244;
        --header: #1f2937;
        --hover: #182235;
        --shadow: 0 18px 45px rgba(0, 0, 0, 0.35);
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, sans-serif;
      color: var(--text);
      background: var(--bg);
    }
    main { max-width: 1180px; margin: 0 auto; padding: 24px; }
    h1 { font-size: 24px; margin: 0 0 16px; }
    h2 { font-size: 18px; margin: 0; }
    .meta { color: var(--muted); font-size: 13px; }
    .muted { color: var(--muted); }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: end;
      margin: 16px 0;
    }
    label { display: grid; gap: 6px; color: var(--muted); font-size: 13px; }
    select, input, button {
      padding: 8px 10px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--surface);
      color: var(--text);
      font: inherit;
    }
    button { cursor: pointer; }
    .primary-button { padding: 8px 14px; border-color: #95a3b8; }
    .overview-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin: 18px 0;
    }
    .metric-card, .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
    }
    .metric-card { padding: 14px; min-width: 0; }
    .metric-title { color: var(--muted); font-size: 12px; }
    .metric-value { font-size: 26px; margin-top: 8px; line-height: 1.1; }
    .metric-caption { color: var(--muted); font-size: 13px; margin-top: 6px; }
    .panel { margin-top: 18px; padding: 16px; }
    .section-heading {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 12px;
    }
    .legend { display: flex; flex-wrap: wrap; gap: 12px; color: var(--muted); font-size: 13px; }
    .legend span { display: inline-flex; align-items: center; gap: 6px; }
    .dot { width: 9px; height: 9px; border-radius: 999px; display: inline-block; }
    .dau-dot { background: var(--primary); }
    .wau-dot { background: var(--success); }
    .mau-dot { background: var(--warning); }
    .chart-wrap { position: relative; height: 320px; min-height: 260px; }
    #active-users-chart { display: block; width: 100%; height: 100%; }
    .chart-tooltip {
      position: fixed;
      z-index: 20;
      pointer-events: none;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 9px 10px;
      color: var(--text);
      font-size: 12px;
      line-height: 1.5;
    }
    .table-wrap {
      margin-top: 12px;
      max-height: 460px;
      overflow: auto;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--surface);
    }
    table { width: 100%; border-collapse: collapse; }
    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--soft-border);
      text-align: right;
      white-space: nowrap;
    }
    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: var(--header);
      font-size: 13px;
    }
    th:first-child, td:first-child { text-align: left; }
    th[data-sort] { cursor: pointer; user-select: none; }
    th[data-sort]::after { content: "  \\2195"; color: var(--muted); font-size: 11px; }
    tbody tr:hover { background: var(--hover); }
    .cohort-link {
      border: 0;
      background: transparent;
      color: var(--primary);
      padding: 0;
      text-align: left;
    }
    .drawer-backdrop {
      position: fixed;
      inset: 0;
      z-index: 30;
      background: rgba(15, 23, 42, 0.38);
    }
    .drawer {
      position: fixed;
      top: 0;
      right: 0;
      z-index: 31;
      width: min(420px, 92vw);
      height: 100vh;
      background: var(--surface);
      border-left: 1px solid var(--border);
      box-shadow: var(--shadow);
      padding: 18px;
      transform: translateX(100%);
      transition: transform 160ms ease;
    }
    .drawer.open { transform: translateX(0); }
    .drawer-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }
    .icon-button {
      width: 34px;
      height: 34px;
      padding: 0;
      border-radius: 6px;
      font-size: 22px;
      line-height: 1;
    }
    .detail-grid { display: grid; gap: 10px; margin: 0; }
    .detail-grid div {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 12px 0;
      border-bottom: 1px solid var(--soft-border);
    }
    dt { color: var(--muted); }
    dd { margin: 0; font-weight: 600; text-align: right; }
    [hidden] { display: none !important; }
    @media (max-width: 720px) {
      main { padding: 16px; }
      .overview-grid { grid-template-columns: 1fr; }
      .toolbar { display: grid; grid-template-columns: 1fr; }
      .section-heading { align-items: start; flex-direction: column; }
      .chart-wrap { height: 280px; }
    }
  </style>"""


def _retention_page_script() -> str:
    return """<script>
    (() => {
      const raw = document.getElementById("dashboard-data");
      const data = raw ? JSON.parse(raw.textContent || "{}") : {};
      const engagementRows = data.engagementRows || [];
      const cohortDetails = data.cohortDetails || {};
      const svg = document.getElementById("active-users-chart");
      const tooltip = document.getElementById("chart-tooltip");
      const chartWrap = svg ? svg.parentElement : null;
      let chartPoints = [];
      const series = [
        { key: "dau", label: "DAU", color: "#2563eb" },
        { key: "wau", label: "WAU", color: "#16a34a" },
        { key: "mau", label: "MAU", color: "#d97706" },
      ];

      function makeSvg(tag, attrs) {
        const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
        Object.entries(attrs || {}).forEach(([key, value]) => el.setAttribute(key, value));
        return el;
      }

      function drawChart() {
        if (!svg) return;
        const rect = svg.getBoundingClientRect();
        const width = Math.max(320, rect.width || 320);
        const height = Math.max(260, rect.height || 320);
        const pad = { top: 18, right: 18, bottom: 38, left: 48 };
        const plotWidth = width - pad.left - pad.right;
        const plotHeight = height - pad.top - pad.bottom;
        svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
        svg.replaceChildren();
        chartPoints = [];

        if (!engagementRows.length) {
          const text = makeSvg("text", {
            x: width / 2,
            y: height / 2,
            "text-anchor": "middle",
            fill: "#8792a2",
          });
          text.textContent = "No data";
          svg.appendChild(text);
          return;
        }

        const maxY = Math.max(1, ...engagementRows.flatMap((row) => [
          row.dau || 0,
          row.wau || 0,
          row.mau || 0,
        ]));
        const xFor = (index) => {
          if (engagementRows.length === 1) return pad.left + plotWidth / 2;
          return pad.left + (index * plotWidth) / (engagementRows.length - 1);
        };
        const yFor = (value) => pad.top + plotHeight - ((value || 0) / maxY) * plotHeight;

        for (let tick = 0; tick <= 4; tick += 1) {
          const y = pad.top + (plotHeight * tick) / 4;
          const value = Math.round(maxY - (maxY * tick) / 4);
          svg.appendChild(makeSvg("line", {
            x1: pad.left,
            y1: y,
            x2: width - pad.right,
            y2: y,
            stroke: "rgba(135,146,162,0.25)",
          }));
          const label = makeSvg("text", {
            x: pad.left - 10,
            y: y + 4,
            "text-anchor": "end",
            fill: "#8792a2",
            "font-size": "11",
          });
          label.textContent = value;
          svg.appendChild(label);
        }

        const labelEvery = Math.max(1, Math.ceil(engagementRows.length / 6));
        engagementRows.forEach((row, index) => {
          const x = xFor(index);
          chartPoints.push({ x, row });
          if (index % labelEvery === 0 || index === engagementRows.length - 1) {
            const label = makeSvg("text", {
              x,
              y: height - 10,
              "text-anchor": "middle",
              fill: "#8792a2",
              "font-size": "11",
            });
            label.textContent = row.date.slice(5);
            svg.appendChild(label);
          }
        });

        series.forEach((item) => {
          const path = engagementRows.map((row, index) => {
            const command = index === 0 ? "M" : "L";
            return `${command} ${xFor(index)} ${yFor(row[item.key])}`;
          }).join(" ");
          svg.appendChild(makeSvg("path", {
            d: path,
            fill: "none",
            stroke: item.color,
            "stroke-width": "2.4",
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
          }));
        });
      }

      function showTooltip(event) {
        if (!tooltip || !chartPoints.length) return;
        const rect = svg.getBoundingClientRect();
        const mouseX = event.clientX - rect.left;
        const nearest = chartPoints.reduce((best, point) => {
          return Math.abs(point.x - mouseX) < Math.abs(best.x - mouseX) ? point : best;
        }, chartPoints[0]);
        const row = nearest.row;
        tooltip.innerHTML = [
          `<strong>${row.date}</strong>`,
          `DAU: ${row.dau}`,
          `WAU: ${row.wau}`,
          `MAU: ${row.mau}`,
        ].join("<br>");
        tooltip.hidden = false;
        tooltip.style.left = `${event.clientX + 12}px`;
        tooltip.style.top = `${event.clientY + 12}px`;
      }

      function hideTooltip() {
        if (tooltip) tooltip.hidden = true;
      }

      function setupTableSort() {
        const table = document.getElementById("daily-stats-table");
        if (!table || !table.tHead || !table.tBodies.length) return;
        const headers = Array.from(table.tHead.rows[0].cells);
        let activeIndex = -1;
        let ascending = true;
        headers.forEach((header, index) => {
          if (!header.dataset.sort) return;
          header.addEventListener("click", () => {
            ascending = activeIndex === index ? !ascending : true;
            activeIndex = index;
            const rows = Array.from(table.tBodies[0].rows);
            rows.sort((left, right) => {
              const leftValue = left.cells[index].dataset.value || left.cells[index].textContent;
              const rightValue = right.cells[index].dataset.value || right.cells[index].textContent;
              if (header.dataset.sort === "number") {
                return (parseFloat(leftValue) - parseFloat(rightValue)) * (ascending ? 1 : -1);
              }
              return leftValue.localeCompare(rightValue) * (ascending ? 1 : -1);
            });
            table.tBodies[0].replaceChildren(...rows);
          });
        });
      }

      function formatPercent(rate) {
        return rate == null ? "-" : `${(rate * 100).toFixed(1)}%`;
      }

      function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value == null || value === "" ? "-" : String(value);
      }

      function setupDrawer() {
        const drawer = document.getElementById("cohort-drawer");
        const backdrop = document.getElementById("cohort-drawer-backdrop");
        if (!drawer || !backdrop) return;

        const close = () => {
          drawer.classList.remove("open");
          drawer.setAttribute("aria-hidden", "true");
          window.setTimeout(() => {
            drawer.hidden = true;
            backdrop.hidden = true;
          }, 160);
        };

        document.querySelectorAll(".cohort-link").forEach((button) => {
          button.addEventListener("click", () => {
            const detail = cohortDetails[button.dataset.cohort] || {};
            setText("drawer-install-date", detail.install_date);
            setText("drawer-new-users", detail.new_users);
            setText("drawer-d1", formatPercent(detail.d1_rate));
            setText("drawer-d3", formatPercent(detail.d3_rate));
            setText("drawer-d7", formatPercent(detail.d7_rate));
            setText("drawer-current-active", detail.current_active_users);
            setText("drawer-average-days", detail.average_active_days);
            setText("drawer-latest-active", detail.latest_active_date);
            drawer.hidden = false;
            backdrop.hidden = false;
            window.requestAnimationFrame(() => {
              drawer.classList.add("open");
              drawer.setAttribute("aria-hidden", "false");
            });
          });
        });
        document.querySelectorAll("[data-close-drawer]").forEach((button) => {
          button.addEventListener("click", close);
        });
        backdrop.addEventListener("click", close);
        document.addEventListener("keydown", (event) => {
          if (event.key === "Escape" && !drawer.hidden) close();
        });
      }

      drawChart();
      setupTableSort();
      setupDrawer();
      if (chartWrap) {
        chartWrap.addEventListener("mousemove", showTooltip);
        chartWrap.addEventListener("mouseleave", hideTooltip);
      }
      window.addEventListener("resize", drawChart);
    })();
  </script>"""

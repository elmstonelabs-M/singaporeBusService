from __future__ import annotations

from html import escape

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.core.config import get_settings
from app.services.log_service import (
    build_today_usage_summary,
    clamp_log_limit,
    read_recent_log_lines,
)

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
        "lines": read_recent_log_lines(settings.log_file_path, bounded_limit),
    }


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
    lines = read_recent_log_lines(settings.log_file_path, bounded_limit)
    return HTMLResponse(_render_logs_page(settings.log_file_path, bounded_limit, today, lines))


def _ensure_authorized(
    expected_token: str | None,
    query_token: str | None,
    header_token: str | None,
) -> None:
    if not expected_token:
        raise HTTPException(status_code=403, detail="OPS_LOG_TOKEN is not configured.")
    if header_token != expected_token and query_token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid ops log token.")


def _render_logs_page(log_file: str, limit: int, today: dict, lines: list[str]) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td>{escape(item['endpoint'])}</td>"
        f"<td>{item['request_count']}</td>"
        f"<td>{item['ip_count']}</td>"
        "</tr>"
        for item in today["top_endpoints"]
    )
    if not rows:
        rows = '<tr><td colspan="3">No app usage found for today.</td></tr>'

    log_text = escape("\n".join(lines))
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
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }}
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
    <p class="meta">Log file: {escape(log_file)} | Recent lines: {limit} | Stats timezone: Asia/Singapore</p>
    <section class="stats">
      <div class="stat"><div class="label">Date</div><div class="value">{escape(today["date"])}</div></div>
      <div class="stat"><div class="label">Requests</div><div class="value">{today["request_count"]}</div></div>
      <div class="stat"><div class="label">Request IPs</div><div class="value">{today["ip_count"]}</div></div>
      <div class="stat"><div class="label">Errors</div><div class="value">{today["error_count"]}</div></div>
    </section>
    <h2>Top Endpoints</h2>
    <table>
      <thead><tr><th>Endpoint</th><th>Requests</th><th>Request IPs</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <h2>Recent Logs</h2>
    <pre>{log_text}</pre>
  </main>
</body>
</html>"""

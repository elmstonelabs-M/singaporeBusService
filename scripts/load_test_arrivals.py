from __future__ import annotations

import argparse
import asyncio
import os
import random
import re
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import httpx

DEFAULT_BASE_URL = "https://trackbusapi.sgbtt.top"
DEFAULT_MONITOR_HOST = "35.197.135.48"
DEFAULT_MONITOR_USER = "devlop"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUS_STOP_CODE_RE = re.compile(r"^\d{5}$")


@dataclass(frozen=True)
class HostSample:
    cpu_percent: float
    memory_used_mb: float
    memory_total_mb: float
    load_1m: float


@dataclass(frozen=True)
class ContainerSample:
    name: str
    cpu_percent: float
    memory_percent: float


@dataclass
class StageResult:
    users: int
    duration_seconds: float
    latencies_ms: list[float] = field(default_factory=list)
    statuses: Counter[str] = field(default_factory=Counter)
    station_counts: Counter[str] = field(default_factory=Counter)
    host_samples: list[HostSample] = field(default_factory=list)
    container_samples: list[ContainerSample] = field(default_factory=list)
    monitor_error: str | None = None

    @property
    def request_count(self) -> int:
        return len(self.latencies_ms)

    @property
    def failed_count(self) -> int:
        return sum(count for status, count in self.statuses.items() if status != "2xx")

    @property
    def error_rate(self) -> float:
        if not self.request_count:
            return 1.0
        return self.failed_count / self.request_count

    @property
    def requests_per_second(self) -> float:
        return self.request_count / self.duration_seconds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gradually load test random real bus stop arrival endpoints.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--station-source-url",
        default=None,
        help="Static data package URL used to load real bus stop codes.",
    )
    parser.add_argument(
        "--station-codes",
        default=None,
        help="Optional comma-separated real bus stop codes instead of loading static data.",
    )
    parser.add_argument(
        "--stages",
        default="10,50,100,200,500",
        help="Comma-separated concurrent virtual users. Default: 10,50,100,200,500",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30,
        help="Seconds to run each stage. Default: 30",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5,
        help="Seconds each user waits between requests. Default: 5",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10,
        help="Per-request timeout in seconds. Default: 10",
    )
    parser.add_argument(
        "--max-error-rate",
        type=float,
        default=0.05,
        help="Stop after a stage when error rate exceeds this value. Default: 0.05",
    )
    parser.add_argument(
        "--max-p95-ms",
        type=float,
        default=3000,
        help="Stop after a stage when P95 latency exceeds this value. Default: 3000",
    )
    parser.add_argument(
        "--monitor-host",
        default=DEFAULT_MONITOR_HOST,
        help=f"SSH server to monitor. Default: {DEFAULT_MONITOR_HOST}",
    )
    parser.add_argument(
        "--monitor-user",
        default=DEFAULT_MONITOR_USER,
        help=f"SSH user for monitoring. Default: {DEFAULT_MONITOR_USER}",
    )
    parser.add_argument(
        "--monitor-port",
        type=int,
        default=22,
        help="SSH port for monitoring. Default: 22",
    )
    parser.add_argument(
        "--ssh-key",
        default=str(default_ssh_key()),
        help="SSH private key path used for monitoring.",
    )
    parser.add_argument(
        "--monitor-interval",
        type=float,
        default=2,
        help="Seconds between server resource samples. Default: 2",
    )
    parser.add_argument(
        "--no-monitor",
        action="store_true",
        help="Disable SSH server resource monitoring.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Start immediately without the safety countdown.",
    )
    args = parser.parse_args()
    args.stages = parse_stages(args.stages, parser)
    args.ssh_key = str(Path(args.ssh_key).expanduser())
    args.base_url = args.base_url.rstrip("/")
    args.station_source_url = (
        args.station_source_url
        or f"{args.base_url}/v1/static-data/package"
    )
    args.station_codes = parse_station_codes(args.station_codes, parser)

    if args.duration <= 0:
        parser.error("--duration must be greater than 0")
    if args.interval < 0:
        parser.error("--interval must be 0 or greater")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    if not 0 <= args.max_error_rate <= 1:
        parser.error("--max-error-rate must be between 0 and 1")
    if args.max_p95_ms <= 0:
        parser.error("--max-p95-ms must be greater than 0")
    if not 1 <= args.monitor_port <= 65535:
        parser.error("--monitor-port must be between 1 and 65535")
    if args.monitor_interval <= 0:
        parser.error("--monitor-interval must be greater than 0")
    return args


def default_ssh_key() -> Path:
    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
    if temp_dir:
        prepared_key = Path(temp_dir) / "codex-ssh" / "id_ed25519"
        if prepared_key.exists():
            return prepared_key
    return PROJECT_ROOT / ".ssh-temp" / "id_ed25519"


def parse_stages(value: str, parser: argparse.ArgumentParser) -> list[int]:
    try:
        stages = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError:
        parser.error("--stages must contain comma-separated positive integers")
    if not stages or any(stage <= 0 for stage in stages):
        parser.error("--stages must contain comma-separated positive integers")
    return stages


def parse_station_codes(
    value: str | None,
    parser: argparse.ArgumentParser,
) -> list[str] | None:
    if value is None:
        return None
    station_codes = sorted({item.strip() for item in value.split(",") if item.strip()})
    if not station_codes or any(not BUS_STOP_CODE_RE.fullmatch(code) for code in station_codes):
        parser.error("--station-codes must contain comma-separated 5-digit bus stop codes")
    return station_codes


async def load_station_codes(args: argparse.Namespace) -> list[str]:
    if args.station_codes:
        return args.station_codes

    timeout = httpx.Timeout(60)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(args.station_source_url)
        response.raise_for_status()
        payload = response.json()

    bus_routes = payload.get("data", {}).get("bus_routes", [])
    station_codes = sorted(
        {
            item.get("bus_stop_code")
            for item in bus_routes
            if isinstance(item, dict)
            and isinstance(item.get("bus_stop_code"), str)
            and BUS_STOP_CODE_RE.fullmatch(item["bus_stop_code"])
        }
    )
    if not station_codes:
        raise ValueError(f"No real bus stop codes found at {args.station_source_url}")
    return station_codes


def percentile(values: list[float], percentage: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def classify_status(status_code: int) -> str:
    if 200 <= status_code < 300:
        return "2xx"
    return f"{status_code // 100}xx"


async def virtual_user(
    user_id: int,
    client: httpx.AsyncClient,
    base_url: str,
    station_codes: list[str],
    interval: float,
    deadline: float,
    result: StageResult,
) -> None:
    if interval:
        await asyncio.sleep(random.uniform(0, interval))

    headers = {"X-Device-ID": f"load-test-{user_id}"}
    while time.monotonic() < deadline:
        station_code = random.choice(station_codes)
        target = f"{base_url}/v1/bus-stops/{station_code}/arrivals"
        result.station_counts[station_code] += 1
        started_at = time.perf_counter()
        try:
            response = await client.get(target, headers=headers)
            result.statuses[classify_status(response.status_code)] += 1
        except httpx.TimeoutException:
            result.statuses["timeout"] += 1
        except httpx.HTTPError:
            result.statuses["network_error"] += 1
        finally:
            result.latencies_ms.append((time.perf_counter() - started_at) * 1000)

        if interval and time.monotonic() < deadline:
            await asyncio.sleep(min(interval, max(0, deadline - time.monotonic())))


async def run_stage(
    client: httpx.AsyncClient,
    base_url: str,
    station_codes: list[str],
    users: int,
    duration: float,
    interval: float,
    args: argparse.Namespace,
) -> StageResult:
    result = StageResult(users=users, duration_seconds=duration)
    deadline = time.monotonic() + duration
    async with asyncio.TaskGroup() as task_group:
        if not args.no_monitor:
            task_group.create_task(monitor_server(result, deadline, args))
        for user_id in range(users):
            task_group.create_task(
                virtual_user(
                    user_id,
                    client,
                    base_url,
                    station_codes,
                    interval,
                    deadline,
                    result,
                )
            )
    return result


def remote_monitor_command(interval: float) -> str:
    return (
        "LC_ALL=C; "
        "read _ user nice system idle iowait irq softirq steal _ < /proc/stat; "
        "prev_idle=$((idle+iowait)); "
        "prev_total=$((user+nice+system+idle+iowait+irq+softirq+steal)); "
        f"while sleep {interval:g}; do "
        "read _ user nice system idle iowait irq softirq steal _ < /proc/stat; "
        "idle_now=$((idle+iowait)); "
        "total_now=$((user+nice+system+idle+iowait+irq+softirq+steal)); "
        "idle_delta=$((idle_now-prev_idle)); total_delta=$((total_now-prev_total)); "
        "cpu=$(awk -v i=$idle_delta -v t=$total_delta "
        "'BEGIN { if (t > 0) printf \"%.2f\", 100*(t-i)/t; else print \"0\" }'); "
        "mem_total=$(awk '/MemTotal:/ { printf \"%.2f\", $2/1024 }' /proc/meminfo); "
        "mem_available=$(awk '/MemAvailable:/ { printf \"%.2f\", $2/1024 }' /proc/meminfo); "
        "mem_used=$(awk -v t=$mem_total -v a=$mem_available "
        "'BEGIN { printf \"%.2f\", t-a }'); "
        "load=$(awk '{ print $1 }' /proc/loadavg); "
        "printf 'HOST|%s|%s|%s|%s\\n' \"$cpu\" \"$mem_used\" \"$mem_total\" \"$load\"; "
        "docker stats --no-stream --format "
        "'CONTAINER|{{.Name}}|{{.CPUPerc}}|{{.MemPerc}}' 2>/dev/null || true; "
        "prev_idle=$idle_now; prev_total=$total_now; "
        "done"
    )


async def monitor_server(
    result: StageResult,
    deadline: float,
    args: argparse.Namespace,
) -> None:
    command = [
        "ssh",
        "-i",
        args.ssh_key,
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-p",
        str(args.monitor_port),
        f"{args.monitor_user}@{args.monitor_host}",
        remote_monitor_command(args.monitor_interval),
    ]
    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert process.stdout is not None
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=remaining)
            except TimeoutError:
                break
            if not line:
                break
            parse_monitor_line(line.decode("utf-8", errors="replace").strip(), result)

        if process.returncode not in (None, 0) and not result.monitor_error:
            assert process.stderr is not None
            error = (await process.stderr.read()).decode("utf-8", errors="replace").strip()
            result.monitor_error = error or f"SSH monitoring exited with code {process.returncode}"
    except (OSError, ValueError) as exc:
        result.monitor_error = str(exc)
    finally:
        if process is not None and process.returncode is None:
            try:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except TimeoutError:
                    process.kill()
                    await process.wait()
            except ProcessLookupError:
                pass


def parse_monitor_line(line: str, result: StageResult) -> None:
    parts = line.split("|")
    try:
        if len(parts) == 5 and parts[0] == "HOST":
            result.host_samples.append(
                HostSample(
                    cpu_percent=float(parts[1]),
                    memory_used_mb=float(parts[2]),
                    memory_total_mb=float(parts[3]),
                    load_1m=float(parts[4]),
                )
            )
        elif len(parts) == 4 and parts[0] == "CONTAINER":
            result.container_samples.append(
                ContainerSample(
                    name=parts[1],
                    cpu_percent=float(parts[2].rstrip("%")),
                    memory_percent=float(parts[3].rstrip("%")),
                )
            )
    except ValueError:
        return


def print_result(result: StageResult) -> tuple[float, float]:
    p50 = percentile(result.latencies_ms, 0.50)
    p95 = percentile(result.latencies_ms, 0.95)
    p99 = percentile(result.latencies_ms, 0.99)
    maximum = max(result.latencies_ms, default=0)
    average = statistics.fmean(result.latencies_ms) if result.latencies_ms else 0
    statuses = ", ".join(
        f"{status}={count}" for status, count in sorted(result.statuses.items())
    )

    print(
        f"{result.users:>5} users | {result.request_count:>6} requests | "
        f"{result.requests_per_second:>7.2f} RPS | "
        f"errors {result.error_rate:>6.2%}"
    )
    print(f"            unique bus stops requested: {len(result.station_counts)}")
    print(
        f"            latency ms: avg={average:.1f}, p50={p50:.1f}, "
        f"p95={p95:.1f}, p99={p99:.1f}, max={maximum:.1f}"
    )
    print(f"            statuses: {statuses or 'none'}")
    print_resource_result(result)
    return result.error_rate, p95


def print_resource_result(result: StageResult) -> None:
    if result.monitor_error:
        print(f"            monitoring error: {result.monitor_error}")
        return
    if not result.host_samples:
        print("            server resources: no samples collected")
        return

    cpu_values = [sample.cpu_percent for sample in result.host_samples]
    memory_values = [sample.memory_used_mb for sample in result.host_samples]
    memory_total = result.host_samples[-1].memory_total_mb
    load_values = [sample.load_1m for sample in result.host_samples]
    print(
        f"            host: CPU avg={statistics.fmean(cpu_values):.1f}% "
        f"max={max(cpu_values):.1f}% | "
        f"memory avg={statistics.fmean(memory_values):.0f}MB "
        f"max={max(memory_values):.0f}MB / {memory_total:.0f}MB | "
        f"load1 max={max(load_values):.2f}"
    )

    names = sorted({sample.name for sample in result.container_samples})
    for name in names:
        samples = [sample for sample in result.container_samples if sample.name == name]
        print(
            f"            container {name}: CPU max={max(s.cpu_percent for s in samples):.1f}% "
            f"| memory max={max(s.memory_percent for s in samples):.1f}%"
        )


async def main() -> None:
    args = parse_args()
    print("Random real bus stop arrival load test")
    print(f"API base URL: {args.base_url}")
    if args.station_codes:
        print("Loading real bus stop codes from: --station-codes")
    else:
        print(f"Loading real bus stop codes from: {args.station_source_url}")
    try:
        station_codes = await load_station_codes(args)
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise SystemExit(f"Failed to load real bus stop codes: {exc}") from exc
    print(f"Loaded {len(station_codes)} real bus stop codes.")
    print("Request shape: /v1/bus-stops/{random_bus_stop_code}/arrivals")
    print(f"Stages: {args.stages}")
    print(
        f"Each stage: {args.duration:g}s | User request interval: {args.interval:g}s | "
        f"Timeout: {args.timeout:g}s"
    )
    print(
        f"Automatic stop: error rate > {args.max_error_rate:.1%} "
        f"or P95 > {args.max_p95_ms:g}ms"
    )
    if args.no_monitor:
        print("Server monitoring: disabled")
    else:
        print(
            f"Server monitoring: {args.monitor_user}@{args.monitor_host}:{args.monitor_port} "
            f"every {args.monitor_interval:g}s"
        )
    print("Run this only against a server you own or are authorized to test.")

    if not args.yes:
        for seconds in range(5, 0, -1):
            print(f"Starting in {seconds}s... Press Ctrl+C to cancel.", end="\r", flush=True)
            await asyncio.sleep(1)
        print(" " * 60, end="\r")

    limits = httpx.Limits(
        max_connections=max(args.stages) + 20,
        max_keepalive_connections=max(args.stages) + 20,
    )
    timeout = httpx.Timeout(args.timeout)
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        for users in args.stages:
            print(f"\nRunning stage with {users} users...")
            result = await run_stage(
                client=client,
                base_url=args.base_url,
                station_codes=station_codes,
                users=users,
                duration=args.duration,
                interval=args.interval,
                args=args,
            )
            error_rate, p95 = print_result(result)
            if error_rate > args.max_error_rate or p95 > args.max_p95_ms:
                print("\nStop threshold reached. Higher concurrency stages were skipped.")
                break

    print("\nLoad test finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nLoad test cancelled.")

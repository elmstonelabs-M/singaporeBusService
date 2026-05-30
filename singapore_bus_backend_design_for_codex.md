| 项目 | 内容 |
| --- | --- |
| 文档用途 | 交给 Codex 生成服务端项目、接口、数据库模型、缓存逻辑、测试与部署脚本 |
| 目标客户端 | Flutter iOS + Android App |
| 服务端主语言 | Python 3.12+ |
| 主框架 | FastAPI |
| 数据源 | LTA DataMall API User Guide v6.8（21 Apr 2026） |
| 核心功能 | 实时公交到站、附近巴士站、站点搜索、收藏分组、首页聚合 |

本文档以“可直接拆分给 Codex 执行”为目标，包含架构设计、数据库设计、接口设计、缓存策略、异常处理、开发流程、测试标准和 Codex 任务拆分。


---

# 新加坡实时公交到站 App 服务端设计文档
Python / FastAPI / PostgreSQL + PostGIS / Redis 方案（Codex 开发版）

# 目录

1. 1. 项目定位与范围
1. 2. LTA DataMall 数据源摘要
1. 3. UI 到服务端能力映射
1. 4. 总体架构设计
1. 5. 技术栈与选型
1. 6. 数据模型与数据库设计
1. 7. Redis 缓存设计
1. 8. 后端 API 设计
1. 9. LTA Client 与数据标准化
1. 10. 核心业务流程
1. 11. 项目目录结构
1. 12. 配置与环境变量
1. 13. Docker 与本地开发
1. 14. 测试策略
1. 15. 安全与稳定性规范
1. 16. 部署流程
1. 17. Codex 开发任务拆分
1. 18. 验收标准
1. 19. 附录：UI 参考与关键规则


---

# 1. 项目定位与范围

本项目是一个面向新加坡通勤用户的实时公交到站 App 服务端。Flutter 客户端负责 UI 展示，Python 服务端负责 LTA 数据接入、缓存、标准化、搜索、附近站点、收藏和首页聚合。

## 1.1 服务端必须解决的问题

- 隐藏 LTA AccountKey，避免客户端反编译后泄露。
- 把 LTA 原始 JSON 转换成 UI 可直接消费的结构，例如 Arr、2m、12m、拥挤颜色、是否无障碍。
- 对 20 秒级实时数据做合理缓存，降低 LTA 调用频率和服务端成本。
- 支持附近巴士站、站点搜索、收藏站点、Home/Work 分组。
- 在 LTA 无数据时，结合 BusRoutes 首末班信息返回 No Est. Available 或 Not In Operation。
- 为后期推送提醒、用户登录、路线规划、MRT 异常提醒预留扩展空间。

## 1.2 MVP 范围

| 优先级 | 功能 | 说明 |
| --- | --- | --- |
| P0 | 实时到站 | 按 BusStopCode 查询所有服务，返回每条服务的未来 3 班车。 |
| P0 | 附近巴士站 | 根据用户经纬度返回一定半径内的站点，按距离排序。 |
| P0 | 站点搜索 | 支持 5 位站点编号、道路名、站点描述模糊搜索。 |
| P1 | 收藏分组 | 支持 Home / Work / 自定义分组与线路收藏。 |
| P1 | 首页聚合 | 一次请求返回收藏分组 + 附近站点 + 最新到站。 |
| P2 | 首末班判断 | 当无实时数据时，返回更准确的运营状态。 |
| P2 | 用户登录 | Apple / Google 登录，可在 MVP 后接入。 |
| P3 | 到站提醒 | 基于推送服务实现提前提醒。 |

# 2. LTA DataMall 数据源摘要

本文档基于 LTA DataMall API User Guide v6.8。LTA 文档要求 API 以 HTTPS GET 调用，Header 中传入 AccountKey；默认返回 JSON。除 Bus Arrival 等特殊接口外，列表类 API 通常需要使用 $skip 分页，每次最多返回 500 条记录。

| 数据集 | 用途 | 接口 | 更新频率/特性 |
| --- | --- | --- | --- |
| Bus Arrival | 实时到站、拥挤度、车辆类型、是否无障碍、是否实时定位 | /v3/BusArrival?BusStopCode=83139 | 20 秒；按站点查询；可选 ServiceNo。 |
| Bus Stops | 站点搜索、附近站点、地图定位 | /BusStops | Ad hoc；含 BusStopCode、RoadName、Description、Latitude、Longitude。 |
| Bus Routes | 线路经过站点、站点顺序、首末班判断 | /BusRoutes | Ad hoc；含 ServiceNo、Direction、StopSequence、First/Last Bus。 |
| Bus Services | 线路基础信息、运营商、方向、频率 | /BusServices | Ad hoc；含 ServiceNo、Operator、Category、Origin/Destination、频率。 |
| Train Service Alerts | 后期 MRT 异常提醒 | /TrainServiceAlerts | Ad hoc；可作为未来扩展。 |

## 2.1 Bus Arrival 关键字段

| 字段 | 含义 | 服务端处理 |
| --- | --- | --- |
| ServiceNo | 巴士线路号 | 作为 UI 主标题，例如 36、106、857。 |
| Operator | 运营商 SBST/SMRT/TTS/GAS | 保留给详情页或调试，不必在首页强展示。 |
| NextBus / NextBus2 / NextBus3 | 未来 1-3 班车结构 | 统一转成 arrivals 数组。 |
| EstimatedArrival | 预计到站时间，SST GMT+8 | 计算 minutes/display；小于 1 分钟显示 Arr。 |
| Monitored | 0=排班，1=基于车辆位置估算 | 返回 monitored: true/false，可用于 UI 小图标。 |
| Load | SEA/SDA/LSD | 映射为 green/yellow/red。 |
| Feature | WAB 或空 | WAB 表示轮椅友好。 |
| Type | SD/DD/BD | 单层/双层/铰接巴士，可选展示。 |
| Latitude/Longitude | 车辆估算位置 | 后期可用于地图车辆位置，MVP 可保留。 |

## 2.2 到站时间与状态规则

- 所有到站分钟数向下取整。3:49 显示 3m，1:59 显示 1m，0:59 显示 Arr。
- 如果 LTA 返回 EstimatedArrival，优先显示到站数据，即使当前时间略超出官方首末班。
- 如果没有到站数据，且根据 BusRoutes 当前仍在运营，返回 No Est. Available。
- 如果没有到站数据，且根据 BusRoutes 当前不在运营，返回 Not In Operation。
- Load 映射：SEA=绿色，SDA=黄色/琥珀色，LSD=红色。

# 3. UI 到服务端能力映射

根据截图，App 首页由顶部定位、搜索栏、收藏卡片、附近站点列表、展开站点到站列表组成。服务端应提供聚合接口，减少 Flutter 的多次请求和复杂处理。

| UI 区域 | 显示内容 | 对应服务端能力 |
| --- | --- | --- |
| 顶部定位 | Marina Bay, Singapore | 客户端定位后可由前端反地理编码，也可后端预留 /location/reverse。MVP 可先前端处理。 |
| 搜索框 | 5-digit Bus Stop Code, road or location | /v1/bus-stops/search?q=xxx。 |
| Home / Work 卡片 | 收藏线路 + 三班车 ETA | /v1/home 聚合收藏分组和 arrivals。 |
| Nearby Bus Stops | 站点编号、距离、站名、道路名 | /v1/bus-stops/nearby。 |
| 展开站点 | 该站所有线路及到站 | /v1/bus-stops/{code}/arrivals。 |
| 星标按钮 | 收藏/取消收藏线路 | POST/DELETE /v1/favorites。 |
| 拥挤颜色点 | 绿/黄/红 | 服务端统一返回 load_color。 |

# 4. 总体架构设计

```
Flutter App
  |
  | HTTPS JSON
  v
FastAPI Backend
  |
  |-- PostgreSQL + PostGIS: 巴士站、路线、线路、用户收藏
  |
  |-- Redis: 实时到站缓存、搜索缓存、附近站点缓存
  |
  |-- LTAClient: 统一请求 LTA DataMall API
  |
  |-- Scheduler/Worker: 每日同步 BusStops/BusRoutes/BusServices
  v
LTA DataMall API
```

## 4.1 分层设计

| 层级 | 职责 | 典型文件 |
| --- | --- | --- |
| API Layer | 接收 HTTP 请求、参数校验、返回 Schema | app/api/v1/*.py |
| Service Layer | 业务逻辑：到站转换、附近站点、收藏聚合 | app/services/*.py |
| Client Layer | 封装 LTA HTTP 请求、重试、超时、错误处理 | app/clients/lta_client.py |
| Repository/Model | 数据库读写、SQLAlchemy 模型 | app/models/*.py |
| Schema Layer | Pydantic 请求/响应结构 | app/schemas/*.py |
| Cache Layer | Redis get/set、TTL、fallback | app/core/cache.py |
| Task Layer | 静态数据同步任务 | app/tasks/*.py |

## 4.2 请求链路

```
GET /v1/bus-stops/83139/arrivals
  -> arrivals.py: 参数校验
  -> ArrivalService.get_arrivals(bus_stop_code)
  -> Redis GET arrival:83139
       hit  -> 返回标准化 JSON
       miss -> LTAClient.get_bus_arrival(83139)
            -> normalize_lta_arrivals()
            -> Redis SET arrival:83139 TTL=20
            -> 返回标准化 JSON
```

# 5. 技术栈与选型

| 模块 | 推荐技术 | 原因 |
| --- | --- | --- |
| Web 框架 | FastAPI | 异步性能好、自动文档、Pydantic 校验、适合 Flutter 调用。 |
| HTTP 客户端 | httpx.AsyncClient | 适合异步请求 LTA，支持 timeout 和连接池。 |
| 数据库 | PostgreSQL 16 + PostGIS | 站点经纬度查询、空间索引、可靠事务。 |
| ORM | SQLAlchemy 2.x Async | 类型清晰，便于 Codex 生成和维护。 |
| 迁移 | Alembic | 数据库结构版本管理。 |
| 缓存 | Redis 7 | 20 秒级实时数据缓存、搜索缓存。 |
| 任务调度 | APScheduler 或 Celery Beat | 每日同步静态数据。MVP 用 APScheduler 即可。 |
| 测试 | pytest + pytest-asyncio + respx | 异步接口测试、Mock LTA HTTP。 |
| 部署 | Docker + Railway/Render/Fly.io/AWS | 易迁移，适合早期产品。 |
| 监控 | Sentry + structured logging | 定位线上 LTA 异常和接口错误。 |

## 5.1 Python 版本规范

- 使用 Python 3.12 或以上。
- 全项目开启类型标注。
- Pydantic v2。
- 异步数据库和异步 HTTP 请求，不在 async 代码中使用阻塞 requests。
- 所有外部请求必须有 timeout、retry、日志。

# 6. 数据模型与数据库设计

数据库主要存储静态交通数据和用户数据。实时到站数据不建议长期落库，除非后期做历史分析或到站预测。MVP 使用 Redis 缓存即可。

## 6.1 ERD 简化关系

```
users 1---N favorite_groups 1---N favorite_items

bus_stops 1---N bus_routes
bus_services 1---N bus_routes (by service_no + direction)

favorite_items references:
  - bus_stop_code
  - service_no
```

## 6.2 表结构

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE bus_stops (
    bus_stop_code VARCHAR(5) PRIMARY KEY,
    road_name TEXT NOT NULL,
    description TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    location GEOGRAPHY(POINT, 4326) NOT NULL,
    search_text TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX idx_bus_stops_location
ON bus_stops USING GIST(location);

CREATE INDEX idx_bus_stops_search
ON bus_stops USING GIN(to_tsvector('english', search_text));
```

```sql
CREATE TABLE bus_routes (
    id BIGSERIAL PRIMARY KEY,
    service_no VARCHAR(10) NOT NULL,
    operator VARCHAR(10),
    direction SMALLINT NOT NULL,
    stop_sequence INTEGER NOT NULL,
    bus_stop_code VARCHAR(5) NOT NULL REFERENCES bus_stops(bus_stop_code),
    distance_km NUMERIC(7, 2),
    wd_first_bus VARCHAR(4),
    wd_last_bus VARCHAR(4),
    sat_first_bus VARCHAR(4),
    sat_last_bus VARCHAR(4),
    sun_first_bus VARCHAR(4),
    sun_last_bus VARCHAR(4),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(service_no, direction, stop_sequence, bus_stop_code)
);

CREATE INDEX idx_bus_routes_stop ON bus_routes(bus_stop_code);
CREATE INDEX idx_bus_routes_service ON bus_routes(service_no);
```

```sql
CREATE TABLE bus_services (
    id BIGSERIAL PRIMARY KEY,
    service_no VARCHAR(10) NOT NULL,
    operator VARCHAR(10),
    direction SMALLINT NOT NULL,
    category TEXT,
    origin_code VARCHAR(5),
    destination_code VARCHAR(5),
    am_peak_freq TEXT,
    am_offpeak_freq TEXT,
    pm_peak_freq TEXT,
    pm_offpeak_freq TEXT,
    loop_desc TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(service_no, direction)
);
```

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    device_id TEXT UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE favorite_groups (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    emoji TEXT,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE favorite_items (
    id UUID PRIMARY KEY,
    group_id UUID NOT NULL REFERENCES favorite_groups(id) ON DELETE CASCADE,
    bus_stop_code VARCHAR(5) NOT NULL REFERENCES bus_stops(bus_stop_code),
    service_no VARCHAR(10) NOT NULL,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(group_id, bus_stop_code, service_no)
);
```

# 7. Redis 缓存设计

| 缓存对象 | Key 示例 | TTL | 说明 |
| --- | --- | --- | --- |
| 站点到站 | arrival:83139 | 20 秒 | LTA 更新频率为 20 秒，TTL 与其接近。 |
| 站点单线路到站 | arrival:83139:36 | 20 秒 | 当 UI 只查单线路时使用。 |
| 附近站点 | nearby:1.284:103.861:800 | 60 秒 | 经纬度做网格化/四舍五入，减少 key 数量。 |
| 搜索结果 | search:marina | 1 天 | 静态站点搜索结果变化少。 |
| LTA fallback | arrival:last_good:83139 | 2-5 分钟 | LTA 短暂失败时返回旧数据并标记 stale。 |

## 7.1 缓存策略

- 优先读 Redis，miss 时才请求 LTA。
- LTA 请求成功后，同时写短 TTL 正常缓存和稍长 TTL last_good 缓存。
- LTA 超时或 5xx 时，若 last_good 存在，返回 stale=true，避免前端空白。
- 不要缓存用户敏感数据。收藏数据可直接读 DB，必要时再加用户级缓存。

# 8. 后端 API 设计

所有接口使用 JSON，路径统一以 /v1 开头。响应格式保持稳定，Flutter 端不要直接依赖 LTA 原始字段。

## 8.1 通用响应规范

```json
{
  "data": {},
  "meta": {
    "request_id": "req_abc123",
    "updated_at": "2026-05-19T21:10:00+08:00",
    "stale": false
  }
}
```

## 8.2 健康检查

```
GET /health

Response:
{
  "status": "ok",
  "database": "ok",
  "redis": "ok"
}
```

## 8.3 查询实时到站

```
GET /v1/bus-stops/{bus_stop_code}/arrivals
GET /v1/bus-stops/{bus_stop_code}/arrivals?service_no=36
```

```json
{
  "data": {
    "bus_stop_code": "83139",
    "updated_at": "2026-05-19T21:10:00+08:00",
    "services": [
      {
        "service_no": "36",
        "operator": "SBST",
        "is_favorite": true,
        "arrivals": [
          {
            "sequence": 1,
            "display": "2m",
            "minutes": 2,
            "status": "ARRIVING",
            "load": "SEA",
            "load_color": "green",
            "wheelchair": true,
            "bus_type": "DD",
            "monitored": true,
            "estimated_arrival": "2026-05-19T21:12:00+08:00"
          }
        ]
      }
    ]
  },
  "meta": {
    "stale": false
  }
}
```

## 8.4 附近巴士站

```
GET /v1/bus-stops/nearby?lat=1.2839&lng=103.8607&radius=800&limit=20
```

```json
{
  "data": {
    "items": [
      {
        "bus_stop_code": "65009",
        "description": "Opp Somerset Stn",
        "road_name": "Somerset Rd",
        "latitude": 1.30123,
        "longitude": 103.83712,
        "distance_m": 120,
        "has_arrival_data": true
      }
    ]
  }
}
```

## 8.5 搜索巴士站

```
GET /v1/bus-stops/search?q=marina&limit=20
```

搜索排序建议：精确 BusStopCode 匹配 > 站点描述前缀匹配 > 道路名匹配 > 模糊匹配 > 距离加权。

## 8.6 首页聚合

```
GET /v1/home?lat=1.2839&lng=103.8607
```

```json
{
  "data": {
    "location_label": "Marina Bay, Singapore",
    "favorite_groups": [
      {
        "id": "uuid",
        "name": "Home",
        "emoji": "🏠",
        "items": [
          {
            "bus_stop_code": "65009",
            "service_no": "36",
            "arrivals": [
              {"display": "2m", "load_color": "green"},
              {"display": "12m", "load_color": "yellow"},
              {"display": "24m", "load_color": "green"}
            ]
          }
        ]
      }
    ],
    "nearby_bus_stops": []
  }
}
```

## 8.7 收藏接口

```
POST /v1/favorite-groups
PATCH /v1/favorite-groups/{group_id}
DELETE /v1/favorite-groups/{group_id}

POST /v1/favorites
DELETE /v1/favorites/{favorite_id}
PATCH /v1/favorites/reorder
```

# 9. LTA Client 与数据标准化

## 9.1 LTAClient 规范

```python
class LTAClient:
    BASE_URL = "https://datamall2.mytransport.sg/ltaodataservice"

    def __init__(self, account_key: str, timeout_seconds: float = 5.0):
        self.account_key = account_key
        self.timeout_seconds = timeout_seconds

    async def get_bus_arrival(
        self,
        bus_stop_code: str,
        service_no: str | None = None,
    ) -> dict:
        ...

    async def get_bus_stops(self, skip: int = 0) -> list[dict]:
        ...

    async def get_bus_routes(self, skip: int = 0) -> list[dict]:
        ...

    async def get_bus_services(self, skip: int = 0) -> list[dict]:
        ...
```

## 9.2 请求头

```python
headers = {
    "AccountKey": settings.LTA_ACCOUNT_KEY,
    "accept": "application/json",
}
```

## 9.3 标准化函数

```python
def normalize_arrival_time(estimated_arrival: str | None, now: datetime) -> dict:
    if not estimated_arrival:
        return {
            "display": None,
            "minutes": None,
            "status": "NO_DATA",
        }

    eta = parse_singapore_time(estimated_arrival)
    diff_seconds = max(0, int((eta - now).total_seconds()))
    minutes = diff_seconds // 60

    if minutes < 1:
        return {"display": "Arr", "minutes": 0, "status": "ARRIVING"}

    return {"display": f"{minutes}m", "minutes": minutes, "status": "ESTIMATED"}


def map_load(load: str | None) -> dict:
    mapping = {
        "SEA": ("Seats Available", "green"),
        "SDA": ("Standing Available", "yellow"),
        "LSD": ("Limited Standing", "red"),
    }
    label, color = mapping.get(load or "", ("Unknown", "gray"))
    return {"load": load, "load_label": label, "load_color": color}


def is_wheelchair_accessible(feature: str | None) -> bool:
    return feature == "WAB"
```

## 9.4 车辆类型映射

| LTA Type | 含义 | 返回字段建议 |
| --- | --- | --- |
| SD | Single Deck 单层巴士 | bus_type_label = Single Deck |
| DD | Double Deck 双层巴士 | bus_type_label = Double Deck |
| BD | Bendy 铰接巴士 | bus_type_label = Bendy |

# 10. 核心业务流程

## 10.1 实时到站流程

```
1. 校验 bus_stop_code 是否为 5 位数字。
2. 读取 Redis arrival:{bus_stop_code}。
3. 命中缓存：返回缓存内容。
4. 未命中：请求 LTA /v3/BusArrival。
5. 如果 LTA 成功：
   - 转换 Services 数组。
   - 把 NextBus/NextBus2/NextBus3 转为 arrivals 数组。
   - 计算 display/minutes/status。
   - 映射 load_color、wheelchair、bus_type、monitored。
   - 写 Redis TTL 20 秒。
   - 写 last_good TTL 2-5 分钟。
6. 如果 LTA 失败：
   - 有 last_good：返回 stale=true。
   - 无 last_good：返回 503 或空列表，带错误说明。
```

## 10.2 无数据状态判断

```python
if arrival_data_exists:
    show arrival data
else:
    if is_service_operating_now(bus_stop_code, service_no, now):
        display = "No Est. Available"
        status = "NO_ESTIMATE"
    else:
        display = "Not In Operation"
        status = "NOT_IN_OPERATION"
```

## 10.3 附近站点流程

```sql
SELECT
    bus_stop_code,
    road_name,
    description,
    latitude,
    longitude,
    ST_Distance(location, ST_MakePoint(:lng, :lat)::geography) AS distance_m
FROM bus_stops
WHERE ST_DWithin(location, ST_MakePoint(:lng, :lat)::geography, :radius)
ORDER BY distance_m ASC
LIMIT :limit;
```

## 10.4 每日同步流程

```
03:00 Singapore Time
  -> sync_bus_stops()
      -> loop $skip=0,500,1000...
      -> upsert bus_stops
  -> sync_bus_routes()
      -> loop $skip=0,500,1000...
      -> upsert bus_routes
  -> sync_bus_services()
      -> loop $skip=0,500,1000...
      -> upsert bus_services
  -> log sync counts and failures
```

# 11. 项目目录结构

```
bus-arrival-backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── v1/
│   │       ├── arrivals.py
│   │       ├── bus_stops.py
│   │       ├── favorites.py
│   │       └── home.py
│   ├── clients/
│   │   └── lta_client.py
│   ├── core/
│   │   ├── cache.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── errors.py
│   │   ├── logging.py
│   │   └── security.py
│   ├── models/
│   │   ├── bus_route.py
│   │   ├── bus_service.py
│   │   ├── bus_stop.py
│   │   ├── favorite.py
│   │   └── user.py
│   ├── schemas/
│   │   ├── arrival.py
│   │   ├── bus_stop.py
│   │   ├── common.py
│   │   ├── favorite.py
│   │   └── home.py
│   ├── services/
│   │   ├── arrival_service.py
│   │   ├── favorite_service.py
│   │   ├── home_service.py
│   │   ├── nearby_service.py
│   │   └── search_service.py
│   ├── tasks/
│   │   ├── scheduler.py
│   │   └── sync_lta_data.py
│   └── utils/
│       ├── geo.py
│       └── time_utils.py
├── migrations/
├── tests/
│   ├── test_arrivals.py
│   ├── test_bus_stops.py
│   ├── test_lta_client.py
│   └── test_normalizers.py
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── .env.example
└── README.md
```

# 12. 配置与环境变量

```
APP_ENV=development
APP_NAME=Singapore Bus Arrival API
APP_VERSION=0.1.0

DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/bus_app
REDIS_URL=redis://redis:6379/0

LTA_ACCOUNT_KEY=replace_with_real_key
LTA_BASE_URL=https://datamall2.mytransport.sg/ltaodataservice
LTA_TIMEOUT_SECONDS=5

DEFAULT_ARRIVAL_CACHE_TTL_SECONDS=20
DEFAULT_LAST_GOOD_CACHE_TTL_SECONDS=300
DEFAULT_NEARBY_CACHE_TTL_SECONDS=60

JWT_SECRET=replace_me
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
LOG_LEVEL=INFO
```

## 12.1 配置规范

- 不得把 LTA_ACCOUNT_KEY 写入代码或提交 GitHub。
- .env.example 只放占位符。
- 生产环境的密钥使用云平台 Secret Manager 或环境变量。
- FastAPI 文档在生产环境可限制访问或关闭。

# 13. Docker 与本地开发

```yaml
version: "3.9"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_DB: bus_app
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

## 13.1 本地启动命令

```bash
cp .env.example .env
# 填入 LTA_ACCOUNT_KEY

docker compose up -d
alembic upgrade head
python -m app.tasks.sync_lta_data
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

# 14. 测试策略

| 测试类型 | 工具 | 覆盖内容 |
| --- | --- | --- |
| 单元测试 | pytest | 时间计算、Load 映射、Feature 映射、首末班判断。 |
| HTTP Mock | respx | 模拟 LTA 成功、超时、5xx、空数据。 |
| 接口测试 | httpx AsyncClient | /arrivals、/nearby、/search、/home。 |
| 数据库测试 | pytest + test database | PostGIS 附近查询、upsert 同步。 |
| 缓存测试 | fakeredis 或测试 Redis | 缓存命中、miss、last_good fallback。 |
| 集成测试 | Docker Compose | API + Postgres + Redis 全链路。 |

## 14.1 必测用例

- EstimatedArrival 距离当前 59 秒时返回 Arr。
- EstimatedArrival 距离当前 119 秒时返回 1m。
- Load=SEA 返回 green，SDA 返回 yellow，LSD 返回 red。
- Feature=WAB 返回 wheelchair=true。
- NextBus3 为空时，arrivals 数组不应包含空对象。
- LTA 超时时，有 last_good 缓存应返回 stale=true。
- BusStopCode 非 5 位数字时返回 422。
- 附近站点按 distance_m 从小到大排序。
- 搜索 83139 应优先返回 BusStopCode 精确匹配。

# 15. 安全与稳定性规范

## 15.1 安全规范

- LTA AccountKey 只存在服务端环境变量中。
- 所有移动端请求必须走 HTTPS。
- 收藏接口需要用户身份；MVP 可用匿名 device_id，正式版接入 Apple/Google 登录。
- 对高频接口做 IP/device 级限流，例如每分钟 60-120 次。
- 日志不得打印 AccountKey、Authorization header、用户精确长期轨迹。

## 15.2 稳定性规范

- LTA 外部请求必须设置 timeout，推荐 5 秒以内。
- LTA 5xx 或网络失败时使用 last_good 缓存兜底。
- Redis 不可用时仍可请求 LTA，但需要限流保护。
- 数据库不可用时，实时到站接口可部分可用；附近站点和收藏不可用。
- 所有错误返回统一 error_code 和 message。

## 15.3 错误响应格式

```json
{
  "error": {
    "code": "LTA_TIMEOUT",
    "message": "LTA service timed out. Please try again later.",
    "request_id": "req_abc123"
  }
}
```

# 16. 部署流程

## 16.1 推荐部署组合

| 组件 | 早期推荐 | 正式推荐 |
| --- | --- | --- |
| API | Railway / Render / Fly.io | AWS ECS / GCP Cloud Run |
| PostgreSQL | Supabase / Neon | AWS RDS PostgreSQL + PostGIS |
| Redis | Upstash Redis | Elasticache / Memorystore |
| 日志 | 平台日志 + Sentry | Sentry + OpenTelemetry |
| 域名/CDN | Cloudflare | Cloudflare + WAF |

## 16.2 CI/CD 基本流程

```
on push to main:
  - install dependencies
  - run ruff/black/mypy
  - run pytest
  - build Docker image
  - push image
  - run database migrations
  - deploy API
  - run smoke test /health
```

# 17. Codex 开发任务拆分

下面任务可以逐条交给 Codex。每个任务都应要求 Codex 生成代码、测试和必要的 README 说明。

| 任务编号 | 任务名称 | 交付物 |
| --- | --- | --- |
| T01 | 初始化 FastAPI 项目 | 项目目录、pyproject.toml、main.py、/health、README。 |
| T02 | 配置系统 | Pydantic Settings、.env.example、日志配置。 |
| T03 | 数据库模型 | SQLAlchemy models、Alembic migration、PostGIS extension。 |
| T04 | Redis Cache 封装 | get/set/json helpers、TTL、异常处理。 |
| T05 | LTAClient | BusArrival/BusStops/BusRoutes/BusServices 请求方法、timeout、retry、测试。 |
| T06 | Arrival 标准化 | NextBus 转 arrivals、时间计算、Load/Feature/Type 映射、测试。 |
| T07 | 实时到站接口 | /v1/bus-stops/{code}/arrivals、缓存、fallback。 |
| T08 | 静态数据同步 | 分页 $skip 拉取、upsert、命令行任务。 |
| T09 | 附近站点接口 | PostGIS 查询、距离排序、缓存。 |
| T10 | 搜索接口 | BusStopCode 精确匹配、文本搜索、排序。 |
| T11 | 收藏分组 | 用户、分组、收藏 CRUD。 |
| T12 | 首页聚合 | /v1/home 聚合收藏和附近站点。 |
| T13 | 首末班判断 | 基于 BusRoutes 返回 No Est. Available / Not In Operation。 |
| T14 | 测试补齐 | 单元、接口、缓存、LTA mock、数据库测试。 |
| T15 | Docker 与部署 | Dockerfile、docker-compose、部署说明、健康检查。 |

## 17.1 给 Codex 的总提示词

```
你是资深 Python 后端工程师。请根据本文档开发新加坡实时公交到站 App 的服务端。
技术栈必须使用 FastAPI、SQLAlchemy 2.x Async、PostgreSQL/PostGIS、Redis、httpx、Pydantic v2、pytest。
请严格遵守以下要求：
1. 不要在代码中硬编码 LTA AccountKey，必须从环境变量读取。
2. Flutter 客户端不得直接依赖 LTA 原始字段，服务端必须返回标准化 JSON。
3. Bus Arrival 接口必须使用 Redis 缓存，TTL 默认 20 秒。
4. LTA 超时或失败时，优先返回 last_good 缓存并设置 stale=true。
5. 所有外部请求必须有 timeout、错误处理和日志。
6. 所有核心逻辑必须有测试，包括时间取整、Load 颜色映射、WAB、空 NextBus、缓存 fallback。
7. 代码需要类型标注，目录结构按本文档执行。
8. 每完成一个模块，请更新 README 和测试。
```

# 18. 验收标准

## 18.1 MVP 功能验收

- 访问 /health 返回 ok，并能检查数据库和 Redis。
- 访问 /v1/bus-stops/83139/arrivals 能返回标准化到站数据。
- 同一站点 20 秒内重复请求应命中 Redis，不重复请求 LTA。
- 能同步 BusStops 到 PostgreSQL，并支持附近站点查询。
- 搜索 marina、orchard、83139 能返回合理站点。
- 能创建 Home / Work 收藏分组并添加线路。
- /v1/home 能一次返回收藏卡片和附近站点。

## 18.2 质量验收

- pytest 全部通过。
- ruff/black/mypy 无关键错误。
- 接口响应时间：缓存命中 P95 < 150ms；缓存 miss P95 < 1000ms。
- LTA 失败时不会导致 App 首页完全空白。
- 所有密钥不出现在 Git 历史、日志、README 示例中。

# 19. 附录：UI 参考与关键规则

## 19.1 UI 参考截图

## 19.1 UI 参考截图
文档版包含用户提供的两张 UI 参考截图。

## 19.2 UI 展示规则给后端的要求

| UI 元素 | 后端返回字段 | 备注 |
| --- | --- | --- |
| Arr / 2m / 12m | arrivals[].display | 前端不再自行计算。 |
| 绿色/黄色/红色圆点 | arrivals[].load_color | 统一由服务端映射。 |
| 星标 | is_favorite | 根据用户收藏数据返回。 |
| 轮椅/巴士小图标 | wheelchair、bus_type | UI 可按需展示。 |
| 展开站点列表 | services[] | 每个站点返回所有服务。 |
| 距离 120m | distance_m | PostGIS 计算。 |

## 19.3 未来扩展建议

- 到站提醒：用户选择某线路某站，服务端定时检查 ETA，小于阈值时推送。
- MRT 异常：接入 Train Service Alerts，在首页顶部展示服务中断。
- 地图车辆位置：使用 Bus Arrival 的 Latitude/Longitude 展示车辆。
- 乘客量分析：后期可接入 Passenger Volume 数据做站点热度。
- 多语言：服务端 status_code 保持英文枚举，前端做 i18n 文案。

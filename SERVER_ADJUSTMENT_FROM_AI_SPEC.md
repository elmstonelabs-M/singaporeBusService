# 服务端与前端开发调整文档：对比外部实时巴士 App 规格

本文基于外部文档 `sg_bus_app_ai_development_spec.md`，对比当前 `singaporeBusService` 服务端实现后，整理出服务端需要调整的部分，以及 Flutter 前端开发时必须遵守的数据边界。

这份文档可以直接交给前端开发使用。核心原则是：

- 实时到站数据走服务端，服务端隐藏 LTA AccountKey，并做缓存、标准化和降级兜底。
- 用户数据留在客户端，包括收藏、提醒、最近搜索、用户设置和实时位置相关状态。
- 静态公交数据放在客户端，包括站点、线路、线路站点关系；MVP 打包进 App，后续可通过服务端更新包升级。
- 服务端现有 search、nearby、favorite、alias 能力只作为兼容或历史能力，不作为新 Flutter MVP 的主路径。

## 结论摘要

当前服务端已经覆盖了 FastAPI、LTA DataMall 代理、Redis 缓存、静态数据同步、到站标准化、无实时数据状态判断、收藏/别名、首页聚合和生产部署基础。整体方向是可用的，不需要重写。

真正需要调整的是五类：

1. 补齐规格明确要求但当前缺失的批量到站接口。
2. 统一静态数据 API 命名和包格式，避免 Flutter 端按 `/dataset` 对接时产生偏差。
3. 修复静态数据版本 checksum 在缺少 `StaticDataState` 时的递归风险。
4. 明确收藏、提醒、最近搜索、位置等用户数据全部放客户端。
5. 明确静态公交数据全部放客户端，MVP 随 App 打包内置，服务端只负责生成和提供后续更新包。

## 最终职责边界

### Flutter 客户端负责

以下数据和逻辑必须保存在客户端本地，不依赖服务端：

| 类型 | 客户端职责 | 推荐存储 |
|---|---|---|
| 站点静态数据 | `bus_stops` 查询、搜索、附近站计算、站点详情基础信息 | SQLite / Drift |
| 线路静态数据 | `bus_services`、线路方向、运营商、频率、首末站 | SQLite / Drift |
| 线路站点关系 | `bus_routes`、线路经过站点、顺序、首末班时间 | SQLite / Drift |
| 收藏分组 | Home、Work、自定义分组 | SQLite / Drift |
| 收藏项目 | 某站点的某条线路，例如 `83139 + 36` | SQLite / Drift |
| 最近搜索 | 搜索关键词、最近查看站点 | SQLite / Drift 或轻量本地存储 |
| 到站提醒 | 提前 1/3/5 分钟提醒规则、是否已触发 | SQLite / Drift |
| 下车提醒 | 目的地站点、提醒距离、GPS 命中次数、是否已触发 | SQLite / Drift |
| 用户位置 | 当前定位、下车提醒定位监听 | 不上传服务端，仅本地运行时使用 |
| 用户设置 | 主题、语言、默认提醒距离等 | shared_preferences 或同类轻量存储 |

### FastAPI 服务端负责

服务端只负责以下能力：

| 类型 | 服务端职责 |
|---|---|
| LTA 代理 | 客户端不直接请求 LTA，不暴露 `LTA_ACCOUNT_KEY` |
| 实时到站 | 单站、指定线路、批量线路到站查询 |
| Redis 缓存 | 缓存 LTA 到站结果，减少重复请求 |
| 数据标准化 | 统一 ETA、拥挤度、无障碍、车型、实时定位状态 |
| 旧缓存兜底 | LTA 失败时尽量返回 `last_good` 缓存，并标记 `stale = true` |
| 静态数据生成 | 从 LTA 同步 `bus_stops`、`bus_routes`、`bus_services` |
| 初始 SQLite 包 | 生成 `sg_bus_initial.db` 给 Flutter 打包 |
| 后续更新包 | 生成 `.db.zip`，提供版本检查、下载、sha256 |
| 健康检查 | `/health` |
| 反馈 | 可选保留 `/v1/feedback` |

服务端不应该负责：

- 保存用户收藏。
- 保存到站提醒规则。
- 保存下车提醒规则。
- 保存最近搜索。
- 保存用户实时位置。
- 根据用户位置做下车提醒。
- 给 MVP 做 FCM/APNs 推送。

## 当前实现与规格对比

| 模块 | 外部规格要求 | 当前服务端状态 | 判断 |
|---|---|---|---|
| 健康检查 | `GET /health` | 已实现，且检查 DB/Redis | 保留 |
| 单站到站 | `GET /v1/bus-stops/{code}/arrivals` | 已实现，含站点元数据、收藏状态、别名 | 保留，但可降低对 `user_device_id` 的强依赖 |
| 批量到站 | `POST /v1/arrivals/batch` | 未发现业务接口 | 需要补齐 |
| LTA Client | timeout、retry、错误处理 | 已实现 timeout/retry，失败时 arrival service 使用 last_good | 保留，补充日志更好 |
| Redis 缓存 | 15-20 秒，按站点/线路 key | 已实现 `arrival:{code}` / `arrival:{code}:{service}` | 保留 |
| 到站标准化 | `Arr`、`Xm`、load、WAB、bus type、monitored | 已实现 | 保留 |
| 无实时数据状态 | `NO_ESTIMATE` / `NOT_IN_OPERATION` | 已结合运营时间判断 | 保留 |
| 静态数据版本 | `GET /v1/dataset/version` | 当前是 `GET /v1/static-data/version` | 需要兼容或改名 |
| 静态数据下载 | SQLite zip 或下载 URL | 当前返回完整 JSON package | 需要规划 SQLite zip，短期可保留 JSON |
| 客户端本地搜索/附近 | 由客户端 SQLite 完成 | 后端仍提供 search/nearby | 作为兼容 fallback 保留 |
| 收藏 | 客户端本地保存 | 后端已有 favorite group/item | 新 Flutter MVP 不使用，作为兼容/历史能力保留 |
| 到站提醒 | 客户端本地轮询 + 本地通知 | 后端未做提醒 | 符合规格，不应新增服务端提醒 |
| 下车提醒 | 客户端本地 GPS + 本地通知 | 后端未做提醒 | 符合规格，不应上传位置 |

## P0：必须调整

### 1. 新增批量到站接口，并明确缓存优先策略

新增：

```http
POST /v1/arrivals/batch
```

请求：

```json
{
  "items": [
    { "bus_stop_code": "83139", "service_no": "36" },
    { "bus_stop_code": "83139", "service_no": "106" },
    { "bus_stop_code": "02151", "service_no": "97" }
  ]
}
```

建议实现方式：

- 新建 `app/api/v1/arrivals.py`。
- 新增 `BatchArrivalRequest`、`BatchArrivalItemRequest`、`BatchArrivalPayload` schema。
- 在 service 层按 `bus_stop_code` 聚合请求。
- 同一站点的一条或多条线路，优先读取站点级缓存。
- 如果站点级缓存存在，直接从缓存结果中过滤客户端要求的 `service_no`。
- 如果站点级缓存不存在，再请求 LTA 的站点级 BusArrival。
- 请求 LTA 后，将站点级完整结果写入 Redis，再过滤出目标线路返回。
- 单个 item 失败不要让整批失败，item 级返回 `status` 和可选 `error_code`。
- 限制批量大小，例如最多 50 个 item，避免客户端一次刷太多收藏造成 LTA 压力。

#### 缓存查询规则

服务端实时到站缓存必须以“站点级缓存优先”为主：

```text
用户请求：83139 站的 36、106、111 三条线路

1. 先查 Redis key: arrival:83139
2. 如果存在：
   - 不请求 LTA
   - 从缓存中的 services 过滤出 36、106、111
   - 返回给客户端
3. 如果不存在：
   - 请求 LTA /BusArrival?BusStopCode=83139
   - 标准化完整站点结果
   - 写入 Redis key: arrival:83139，TTL 15-20 秒
   - 写入 last_good key: arrival:last_good:83139
   - 从完整结果中过滤出 36、106、111
   - 返回给客户端
```

当用户只查询单条线路时，也优先使用站点级缓存：

```text
用户请求：83139 站的 36 路

1. 先查 Redis key: arrival:83139
2. 命中则过滤 36 路返回
3. 未命中才请求 LTA
```

这样做的原因：

- LTA 对一个站点一次返回多条线路，站点级缓存利用率最高。
- 收藏卡片通常是同一站点多条线路，站点级缓存可以显著减少 LTA 请求。
- 避免 `arrival:83139:36`、`arrival:83139:106` 这种线路级缓存重复存储同一站点数据。

#### Redis key 建议

主缓存：

```text
arrival:{bus_stop_code}
```

示例：

```text
arrival:83139
```

旧缓存兜底：

```text
arrival:last_good:{bus_stop_code}
```

示例：

```text
arrival:last_good:83139
```

线路级 key `arrival:{bus_stop_code}:{service_no}` 可作为兼容保留，但新逻辑不应优先写入它。

#### 单站接口也要复用同一缓存策略

现有：

```http
GET /v1/bus-stops/{bus_stop_code}/arrivals?service_no=36
```

也应该采用相同流程：

- 先查 `arrival:{bus_stop_code}`。
- 命中则过滤 `service_no`。
- 未命中则请求 LTA 站点级数据。

不要因为传了 `service_no` 就直接请求 LTA 的线路过滤接口。服务端内部可以统一拿站点级数据，减少缓存碎片。

推荐返回保持项目现有 envelope：

```json
{
  "data": {
    "updated_at": "2026-05-24T20:30:00+08:00",
    "items": [
      {
        "bus_stop_code": "83139",
        "service_no": "36",
        "status": "OK",
        "arrivals": []
      }
    ]
  },
  "meta": {
    "stale": false
  }
}
```

### 2. 修复静态数据 checksum 递归风险

当前 `StaticDataService._version_info()` 在没有 `StaticDataState("current")` 时会调用 `_package_checksum()`；而 `_package_checksum()` 又调用 `get_package_payload()`，后者再次进入 `_version_info()`。这在无 state 的新环境中存在递归风险。

建议：

- 将 package 构建拆成不依赖 `_version_info()` 的私有方法，例如 `_build_package(version, generated_at)`。
- `_package_checksum(version, generated_at)` 直接基于 `_build_package()` 计算 hash。
- 加测试覆盖“数据库没有 `StaticDataState` 记录时 `/v1/static-data/version` 能正常返回”。

### 3. 兼容 `/v1/dataset/*` API

外部规格写的是：

- `GET /v1/dataset/version`
- `GET /v1/dataset/download`

当前实现是：

- `GET /v1/static-data/version`
- `GET /v1/static-data/package`

建议短期不要破坏现有接口，而是增加兼容路由：

- `/v1/dataset/version` 复用 `static-data/version`。
- `/v1/dataset/download` 短期可返回 JSON package 或重定向到 `/v1/static-data/package`。
- 文档中明确 canonical endpoint，避免 Flutter 团队混用。

## P1：应尽快调整

### 4. 静态数据必须客户端本地化，MVP 打包内置 SQLite

外部规格推荐客户端内置 SQLite 数据库。结合当前产品目标，MVP 应采用以下方案：

```text
Flutter assets 内置:
assets/database/sg_bus_initial.db
```

首次启动流程：

```text
1. Flutter 检查 App 本地 documents/database 目录是否已有业务数据库。
2. 如果没有，则从 assets/database/sg_bus_initial.db 复制到本地目录。
3. 后续所有静态查询都读本地 SQLite。
4. 如果服务端版本检查发现有新数据包，再下载新包并安全替换。
```

客户端本地 SQLite 至少包含：

```sql
CREATE TABLE bus_stops (
    bus_stop_code TEXT PRIMARY KEY,
    road_name TEXT NOT NULL,
    description TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    search_text TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE bus_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_no TEXT NOT NULL,
    operator TEXT,
    direction INTEGER,
    stop_sequence INTEGER,
    bus_stop_code TEXT NOT NULL,
    distance_km REAL,
    wd_first_bus TEXT,
    wd_last_bus TEXT,
    sat_first_bus TEXT,
    sat_last_bus TEXT,
    sun_first_bus TEXT,
    sun_last_bus TEXT
);

CREATE TABLE bus_services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_no TEXT NOT NULL,
    operator TEXT,
    direction INTEGER,
    category TEXT,
    origin_code TEXT,
    destination_code TEXT,
    am_peak_freq TEXT,
    am_offpeak_freq TEXT,
    pm_peak_freq TEXT,
    pm_offpeak_freq TEXT,
    loop_desc TEXT
);
```

推荐索引：

```sql
CREATE INDEX idx_bus_stops_search_text ON bus_stops(search_text);
CREATE INDEX idx_bus_routes_service_no ON bus_routes(service_no);
CREATE INDEX idx_bus_routes_bus_stop_code ON bus_routes(bus_stop_code);
CREATE INDEX idx_bus_routes_service_stop ON bus_routes(service_no, bus_stop_code);
CREATE INDEX idx_bus_services_service_no ON bus_services(service_no);
```

前端必须使用本地 SQLite 完成：

- 站点编号搜索。
- 道路名搜索。
- 站点名搜索。
- 附近站点计算。
- 线路详情。
- 某站点有哪些线路。
- 某线路经过哪些站点。
- 首末班和运营时间辅助判断。

服务端需要提供给前端打包使用的数据库文件：

```text
sg_bus_initial.db
sg_bus_YYYY_MM_DD.db.zip
```

建议服务端新增或完善离线生成脚本：

```text
python -m app.tasks.generate_sqlite_dataset
```

生成内容：

- `datasets/sg_bus_initial.db`
- `datasets/sg_bus_YYYY_MM_DD.db.zip`
- `datasets/manifest.json`

`manifest.json` 示例：

```json
{
  "version": "2026-05-24",
  "database_file": "sg_bus_2026_05_24.db.zip",
  "sha256": "xxxx",
  "generated_at": "2026-05-24T03:00:00+08:00",
  "force_update": false
}
```

当前 `/v1/static-data/package` 返回完整 JSON，适合作为调试和过渡，但不作为 Flutter MVP 主路径。建议：

- 保留 JSON package 作为调试和兼容接口。
- 新增离线生成 SQLite 数据包脚本，来源为 PostgreSQL 中的 `bus_stops`、`bus_routes`、`bus_services`。
- 新增 `DATASET_STORAGE_DIR` 配置，用于保存生成后的 `.db.zip`。
- `version` 响应补齐外部规格字段：`database_url` 或 `download_url`、`sha256`、`force_update`、`updated_at`。
- 下载接口返回文件流，设置合理的 `ETag`、`Cache-Control`。

推荐版本接口：

```http
GET /v1/dataset/version
```

返回：

```json
{
  "data": {
    "version": "2026-05-24",
    "database_url": "/v1/dataset/download",
    "sha256": "xxxx",
    "force_update": false,
    "updated_at": "2026-05-24T03:00:00+08:00"
  },
  "meta": {
    "updated_at": "2026-05-24T03:00:00+08:00",
    "stale": false
  }
}
```

推荐下载接口：

```http
GET /v1/dataset/download
```

返回：

- `application/zip`
- 文件内容为最新的 `sg_bus_YYYY_MM_DD.db.zip`

Flutter 校验流程：

```text
1. 下载 zip 到临时目录。
2. 计算 sha256。
3. 与 `/v1/dataset/version` 返回的 sha256 比对。
4. 校验通过后解压到临时数据库文件。
5. 打开数据库做基本完整性检查。
6. 关闭当前数据库连接。
7. 原子替换旧数据库。
8. 保存本地 version。
9. 如果任何步骤失败，继续使用旧数据库。
```

### 5. 调整到站接口对 `user_device_id` 的要求

外部规格的单站到站接口没有要求登录或设备 ID。当前 `GET /v1/bus-stops/{code}/arrivals` 强制要求 `user_device_id`，主要是为了注入别名和收藏状态。

建议：

- 将 `user_device_id` 改为可选。
- 未传时只返回公共到站数据和官方站点名。
- 传入时继续返回 `display_name`、`is_favorite`、`favorite_id` 等用户态字段。

这样更符合“客户端本地收藏、不强制登录”的 MVP 方向，也方便第三方或 Flutter 首屏快速调用。

### 6. 用户收藏、提醒等数据全部放客户端

外部规格要求收藏保存在手机本地；当前后端已实现设备态收藏、分组、别名，并通过 `user_device_id` 识别用户。

为了让 Flutter MVP 简单、稳定、低成本，并避免引入半账号系统，新的前端开发应按以下规则执行：

- 收藏分组全部保存在客户端。
- 收藏站点和线路全部保存在客户端。
- 到站提醒全部保存在客户端。
- 下车提醒全部保存在客户端。
- 最近搜索全部保存在客户端。
- 用户位置只在客户端运行时使用，不上传服务端。
- 服务端 favorite / alias API 不作为新 Flutter MVP 的主路径。

前端推荐本地表：

```sql
CREATE TABLE favorite_groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    emoji TEXT,
    display_order INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE favorite_items (
    id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL,
    bus_stop_code TEXT NOT NULL,
    service_no TEXT NOT NULL,
    display_order INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE bus_arrival_reminders (
    id TEXT PRIMARY KEY,
    bus_stop_code TEXT NOT NULL,
    service_no TEXT NOT NULL,
    remind_before_minutes INTEGER NOT NULL,
    enabled INTEGER DEFAULT 1,
    triggered INTEGER DEFAULT 0,
    last_estimated_arrival TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE destination_reminders (
    id TEXT PRIMARY KEY,
    destination_bus_stop_code TEXT NOT NULL,
    destination_name TEXT NOT NULL,
    road_name TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    remind_distance_m INTEGER DEFAULT 500,
    enabled INTEGER DEFAULT 1,
    triggered INTEGER DEFAULT 0,
    nearby_hit_count INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE recent_searches (
    id TEXT PRIMARY KEY,
    query TEXT,
    bus_stop_code TEXT,
    display_name TEXT,
    created_at TEXT
);
```

默认收藏分组：

```text
Home
Work
```

到站提醒逻辑：

```text
1. 用户在站点详情页选择某条线路。
2. 设置提前 1/3/5 分钟提醒。
3. 客户端本地保存规则。
4. 当前页面或短时间后台轮询服务端实时到站接口。
5. 如果 arrival_minutes > 0 且 arrival_minutes <= remind_before_minutes：
   - 触发本地通知。
   - 将 triggered 标记为 true。
6. 不调用服务端保存提醒。
```

下车提醒逻辑：

```text
1. 用户选择目的地站点。
2. 客户端从本地 bus_stops 获取目的地经纬度。
3. 用户选择提醒距离，例如 300m / 500m / 800m。
4. 客户端本地保存规则。
5. 客户端监听 GPS。
6. 连续 2 次距离 <= remind_distance_m 后触发本地通知。
7. 标记 triggered = true 并停止该提醒。
8. 不上传 GPS 到服务端。
```

不建议继续扩展服务端收藏同步、登录、推送提醒，除非进入后续版本。

## P2：可延后

### 7. Search / nearby 降级为兼容 fallback

外部规格要求搜索和附近站在客户端 SQLite 完成。当前后端 `search`、`nearby` 可以保留，但新 Flutter MVP 不应该作为主路径调用。

- 文档标注为 fallback endpoint。
- 前端完成本地 SQLite 后，不再作为主路径调用。
- 后端保留用于调试、低版本客户端和无本地数据时兜底。

前端搜索主路径：

```sql
SELECT *
FROM bus_stops
WHERE search_text LIKE '%' || ? || '%'
LIMIT 50;
```

如果输入是 5 位数字：

```sql
SELECT *
FROM bus_stops
WHERE bus_stop_code = ?
LIMIT 1;
```

前端附近站主路径：

```text
1. 获取当前 GPS。
2. 从本地 bus_stops 读取候选站点。
3. 可先用经纬度 bounding box 粗筛。
4. 使用 Haversine 或 Geolocator.distanceBetween 计算距离。
5. 按距离排序。
6. 取最近 20 个。
```

### 8. 补充静态数据分片或 delta

如果完整 JSON 或 SQLite 包变大，可后续新增：

- `GET /v1/static-data/bus-stops`
- `GET /v1/static-data/bus-routes`
- `GET /v1/static-data/bus-services`
- `GET /v1/static-data/delta?since_version=...`

MVP 不需要 delta，完整包替换更简单稳定。

### 9. 增强 LTA 错误日志与可观测性

当前 LTA client 有 retry，但建议补充：

- LTA HTTP 状态码日志。
- timeout / transport error 分类日志。
- cache hit / miss 指标。
- stale fallback 计数。
- 批量接口的聚合请求数量和节省的 LTA 请求数。

## 不建议服务端实现的内容

以下内容应留在 Flutter 客户端：

- 到站提醒规则保存。
- 到站提醒本地通知。
- 下车提醒规则保存。
- 下车提醒 GPS 判断。
- 用户实时位置上传。
- 服务端长期下车提醒。
- 服务端收藏同步。
- 服务端最近搜索。

原因是外部规格已经明确 MVP 不做服务端推送和位置保存；这也是隐私、成本和复杂度上更稳的选择。

## 建议实施顺序

1. 修复 `StaticDataService` checksum 递归风险，并补测试。
2. 调整 arrival 缓存策略为站点级缓存优先，单条线路也从站点级缓存过滤。
3. 新增 `/v1/arrivals/batch`，复用现有 arrival normalize/cache/stale fallback。
4. 增加 `/v1/dataset/version`、`/v1/dataset/download` 兼容路由。
5. 将 arrivals 的 `user_device_id` 改为可选。
6. 新增 SQLite 静态数据生成脚本，产出 `sg_bus_initial.db` 给 Flutter 打包。
7. 新增 SQLite zip 更新包生成和下载，保留现有 JSON package 作为调试接口。
8. 更新 `FRONTEND_HANDOFF.md`，明确哪些接口是主路径、哪些是 fallback。
9. 前端实现本地 SQLite 查询、收藏、提醒、附近站、最近搜索。

## 验收清单

- `GET /health` 正常。
- `GET /v1/bus-stops/83139/arrivals` 不传 `user_device_id` 也能返回公共到站数据。
- `GET /v1/bus-stops/83139/arrivals?service_no=36` 优先读取 `arrival:83139` 站点级缓存，并过滤 36 路。
- `POST /v1/arrivals/batch` 对同一站点多个线路只触发一次站点级查询。
- LTA 失败且存在 last_good cache 时，批量和单站接口都能返回 `meta.stale = true`。
- `GET /v1/dataset/version` 与 `/v1/static-data/version` 返回兼容的版本信息。
- 无 `StaticDataState` 记录的新数据库环境中，静态数据版本接口不递归报错。
- Flutter 可按服务端返回的 `sha256` 校验静态数据包。
- Flutter 安装包内置 `assets/database/sg_bus_initial.db`。
- Flutter 断网时仍可搜索站点、查看线路静态信息、计算附近站。
- Flutter 收藏、到站提醒、下车提醒关闭 App 后仍在本地存在。
- 服务端数据库中不新增用户位置、提醒规则、最近搜索等 MVP 用户态表。

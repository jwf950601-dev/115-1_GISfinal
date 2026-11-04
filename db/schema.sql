-- Supabase（PostgreSQL）資料表：在 Supabase 的 SQL Editor 執行一次即可。
-- 只存「尖峰時段的快照」，App 用它算 15 分鐘預估與可靠度；住家或使用者輸入的地址不存。

-- YouBike 即時車位快照（GitHub Actions 尖峰每 15 分鐘寫入一次）
create table if not exists bike_snapshot (
    fetched_at      timestamptz not null,          -- 我們呼叫 TDX 的時間
    station_uid     text        not null,          -- TDX StationUID
    rent            smallint,                      -- 可借車數 AvailableRentBikes（含電輔車）
    rent_e          smallint,                      -- 其中電輔車 AvailableRentBikesDetail.ElectricBikes
    ret             smallint,                      -- 可還空位 AvailableReturnBikes
    service_status  smallint,                      -- ServiceStatus：0 停止營運、1 正常營運、2 暫停營運
    update_time     timestamptz,                   -- TDX 的 UpdateTime
    primary key (fetched_at, station_uid)
);
create index if not exists bike_snapshot_uid_time on bike_snapshot (station_uid, fetched_at desc);

-- 雨量快照（同一支排程一起寫入）
create table if not exists rain_snapshot (
    fetched_at  timestamptz not null,
    station_id  text        not null,              -- 氣象署測站代碼
    lat         double precision,
    lon         double precision,
    rain_mm     real,                              -- 過去 1 小時雨量（欄位以實際資料確認）
    primary key (fetched_at, station_id)
);

-- API 呼叫紀錄：每週和 TDX 會員中心的使用統計對帳
create table if not exists api_log (
    called_at  timestamptz not null default now(),
    source     text        not null,               -- tdx / cwa
    path       text        not null,
    n_records  integer,
    bytes      integer                             -- 解壓縮後的大小；gzip 傳輸量約為 1/5
);

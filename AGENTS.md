# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

双色球智能预测系统 — Flask web app that scrapes Chinese lottery (双色球/SSQ) historical data, performs statistical analysis, generates weighted random predictions with ECharts visualizations, and supports user pick tracking with automatic prize comparison.

## Deployment

Docker Compose 运行，对外端口 6888。

```bash
# 上传文件后必须重建镜像（模板和代码都在镜像内，不是挂载卷）
scp <changed_files> <user>@<your-server>:/opt/SSQ/
ssh <user>@<your-server> "cd /opt/SSQ && docker compose up -d --build"

# 只有 data/ 目录是挂载卷，改模板或 Python 代码必须 rebuild
# 仅改 data/ 下的内容不需要 rebuild
```

Local dev:
```bash
pip install -r requirements.txt
python app.py                 # starts on http://localhost:5000
```

No test suite exists.

## Architecture

Four Python modules, single-process Flask app:

- **app.py** — Flask routes + APScheduler cron job (21:35 Asia/Shanghai daily). On startup: init DB → fetch all history → run prediction → check picks → start scheduler. Contains prize comparison logic (`get_prize`, `check_picks`).
- **scraper.py** — Data ingestion with two sources: primary `17500.cn` (plain text, overseas-friendly), fallback `cwl.gov.cn` API. `fetch_all_history()` does initial bulk load; `fetch_latest()` does incremental updates.
- **predictor.py** — Multi-dimensional analysis (frequency, missing values, zone distribution 1-11/12-22/23-33, odd/even, sum trend) then weighted random ball selection via `weighted_pick()`.
- **database.py** — SQLite (`data/ssq.db`) with `results`, `predictions`, and `my_picks` tables. Batch inserts use `INSERT OR IGNORE` for idempotency.

Templates use Tailwind CSS (CDN) + ECharts for charts. No frontend build step.

## Key Data Flow

1. Startup: `fetch_all_history()` → `data/ssq.db` → `do_predict()` → `check_picks()`
2. Cron (21:35): `fetch_latest()` → if new data, auto-predict → auto-compare picks
3. User clicks "重新预测": `/api/predict` → saves to `predictions` table → reload page
4. Manual refresh: `/api/refresh` checks for new lottery results + triggers pick comparison

## API Endpoints

| Route | Purpose |
|---|---|
| `/` | Main page: prediction + charts + recent 30 draws |
| `/history` | Paginated all results (50/page) |
| `/my-picks` | User pick input page (ball selector + pick list with results) |
| `/api/latest` | JSON: latest 10 results |
| `/api/predict` | JSON: generate new prediction |
| `/api/refresh` | JSON: check for new data + compare picks |
| `/api/pick` | POST JSON: submit a pick `{issue, reds[], blue}` |
| `/api/pick/delete` | POST JSON: delete a pick `{id}` |

## Data Model

SQLite tables in `data/ssq.db`:
- **results**: issue (期号, UNIQUE), date, red1-red6 (1-33), blue (1-16), sales, pool_money
- **predictions**: issue, date, red1-red6, blue, analysis (JSON string)
- **my_picks**: issue, red1-red6, blue, prize (nullable, filled after draw), matched_reds (comma-separated string), matched_blue (0 or 1)

## Prize Rules (双色球中奖规则)

一等奖 6红+1蓝、二等奖 6红+0蓝、三等奖 5红+1蓝、四等奖 5红+0蓝 或 4红+1蓝、五等奖 4红+0蓝 或 3红+1蓝、六等奖 2红+1蓝 或 1红+1蓝 或 0红+1蓝。

## Known Gotchas

- JSON round-trip converts dict keys to strings. Template lookups must use `i|string` filter when iterating with `range()`. Affects `missing_analysis` and any dict with integer keys passed through `json.dumps` → `json.loads`.
- Flask `debug=False` caches templates. Must restart container after template changes (and since templates are inside the Docker image, must rebuild).

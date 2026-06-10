<div align="center">

# 🎱 双色球智能预测系统

**基于多维统计分析的福彩双色球预测与可视化平台**

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-green.svg)](https://flask.palletsprojects.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[功能演示](#-功能演示) · [预测算法](#-预测算法) · [快速部署](#-快速部署)

</div>

---

## 📸 功能演示

系统包含三大核心页面：

- **首页** — AI 预测推荐 + 多维度 ECharts 可视化图表 + 近 30 期开奖速览
- **历史数据** — 全量开奖记录分页浏览（每页 50 期）
- **自选号码** — 可视化球盘选号，支持单期投注与长期跟踪，开奖后自动比对中奖等级

## 🧠 预测算法

本系统采用**多维度加权随机模型（Multi-Dimensional Weighted Random Model）**，从历史开奖数据中提取五个正交分析维度，构建综合权重矩阵，通过加权随机采样生成推荐号码。

### 1. 频率热度分析（Frequency Thermal Analysis）

对全量历史开奖数据进行遍历，统计每个红球（1-33）和蓝球（1-16）的累计出现频次，识别**热号**（高频号码）与**冷号**（低频号码）。在权重计算中，频率贡献占比 **50%**，高频率号码获得更大选中概率。

### 2. 遗漏值回归分析（Missing Value Regression Analysis）

计算每个号码连续未出现的期数（遗漏值），基于**均值回归理论**——长期未出现的号码在未来开奖中出现的概率具有补偿性上升趋势。遗漏贡献占比 **30%**，遗漏值越大的号码权重越高，引导模型向"遗漏回补"方向倾斜。

### 3. 三区间均衡模型（Tri-Zone Equilibrium Model）

将红球 1-33 划分为三个等距区间：第一区间（1-11）、第二区间（12-22）、第三区间（23-33），统计历史开奖号码在各区间的分布密度。通过区间平衡因子（权重 **10%**）引导预测结果呈现合理的区间分散特征，避免号码过度集中于单一区间。

### 4. 奇偶比约束（Odd-Even Ratio Constraint）

对历史红球开奖数据的奇偶比例进行统计分析，为后续号码筛选提供奇偶平衡参考，确保预测号码的奇偶分布符合历史规律。

### 5. 和值趋势分析（Sum Trend Analysis）

计算近 100 期红球和值序列，统计均值、极值范围与波动趋势，为预测号码的整体大小分布提供趋势参考。

### 综合权重计算

```
W(n) = Freq(n)/MaxFreq × 50    （频率权重）
     + Miss(n)/50 × 30          （遗漏权重）
     + Zone(n)/ZoneTotal × 10   （区间平衡）
     + Random(5, 15)            （随机扰动，防止过拟合）
```

最终通过**加权放回采样（Weighted Sampling with Replacement）**从权重池中抽取 6 个不重复红球和 1 个蓝球，生成预测组合。

> ⚠️ **免责声明**：双色球开奖为随机事件，任何基于历史数据的统计分析均无法保证预测准确性。本系统仅供学习研究使用，不构成任何投注建议。

## 🏗️ 系统架构

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  scraper.py │────▶│  database.py │────▶│ predictor.py │
│  数据采集层  │     │   数据持久层   │     │   分析预测层   │
│  双源容灾    │     │   SQLite 3表  │     │   5维分析     │
└─────────────┘     └──────┬───────┘     └──────┬───────┘
                           │                     │
                    ┌──────▼─────────────────────▼──────┐
                    │            app.py                   │
                    │         Flask + APScheduler         │
                    │    路由 │ 定时任务 │ 开奖比对        │
                    └──────────────┬─────────────────────┘
                                   │
                    ┌──────────────▼─────────────────────┐
                    │        templates/ (Jinja2)          │
                    │   Tailwind CSS + ECharts 可视化      │
                    └────────────────────────────────────┘
```

**数据流：** 启动时全量抓取 → 多维分析预测 → 用户选号录入 → 每日 21:35 定时检测开奖 → 自动比对中奖结果

**数据源容灾：** 主源 `17500.cn`（纯文本格式，海外可访问） → 备源 福彩官网 API，自动切换。

## 🚀 快速部署

### 本地运行

```bash
git clone https://github.com/wssXzzzz/shuangseqiu666.git
cd shuangseqiu666
pip install -r requirements.txt
python app.py
```

访问 http://localhost:5000

### Docker 部署

```bash
docker compose up -d --build
```

对外端口 `6888`，数据持久化到 `./data/` 目录。

## 📊 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python Flask, APScheduler |
| 数据库 | SQLite 3 |
| 前端 | Tailwind CSS (CDN), ECharts |
| 部署 | Docker Compose |
| 数据源 | 17500.cn, 福彩官网 API |

## 📄 许可证

MIT License

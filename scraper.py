import requests
import re
import time
import logging
from database import insert_results_batch, get_latest_issue, get_result_count

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

# 主要数据源：17500.cn 纯文本格式，海外可访问
DATA_URL = 'http://www.17500.cn/getData/ssq.TXT'

# 备用数据源
CWL_API = 'https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice'


def fetch_from_17500():
    """从 17500.cn 获取全部历史数据（纯文本，海外友好）"""
    try:
        resp = requests.get(DATA_URL, headers={'User-Agent': UA}, timeout=30)
        resp.raise_for_status()
        text = resp.text
        items = []
        for line in text.strip().split('\n'):
            parts = line.strip().split()
            if len(parts) < 9:
                continue
            issue = parts[0]
            date = parts[1]
            reds = []
            for i in range(2, 8):
                try:
                    reds.append(int(parts[i]))
                except ValueError:
                    break
            blue = 0
            try:
                blue = int(parts[8])
            except (ValueError, IndexError):
                continue

            if len(reds) != 6 or blue == 0:
                continue

            items.append((issue, date, reds[0], reds[1], reds[2],
                          reds[3], reds[4], reds[5], blue, '', ''))
        return items
    except Exception as e:
        logger.warning(f'17500.cn 数据获取失败: {e}')
        return []


def fetch_from_cwl(page_no=1, page_size=100):
    """福彩官网 API（备用）"""
    try:
        s = requests.Session()
        s.headers.update({'User-Agent': UA})
        s.get('https://www.cwl.gov.cn/', timeout=10)
        time.sleep(0.3)
        resp = s.get(CWL_API, params={
            'name': 'ssq', 'issueCount': '', 'issueStart': '', 'issueEnd': '',
            'dayStart': '2003-02-16', 'dayEnd': '2099-12-31',
            'pageNo': page_no, 'pageSize': page_size, 'systemType': 'PC',
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        items = []
        for item in data.get('result', []):
            red_str = str(item.get('red', ''))
            blue_str = str(item.get('blue', ''))
            reds = sorted([int(x) for x in red_str.split(',') if x.strip().isdigit()])
            blue = int(blue_str) if blue_str.strip().isdigit() else 0
            if len(reds) != 6 or blue == 0:
                continue
            issue = str(item.get('code', '') or item.get('issue', ''))
            date_str = re.sub(r'[（(].+?[）)]', '', str(item.get('date', ''))).strip()
            items.append((issue, date_str, reds[0], reds[1], reds[2],
                          reds[3], reds[4], reds[5], blue, '', ''))
        return items, data.get('total', 0)
    except Exception as e:
        logger.warning(f'福彩官网 API 失败: {e}')
        return [], 0


def fetch_all_history():
    """全量抓取历史数据"""
    count = get_result_count()
    if count > 3000:
        logger.info(f'已有 {count} 期数据，跳过全量抓取')
        return True

    logger.info('开始全量抓取历史数据...')

    # 方案 1: 17500.cn
    items = fetch_from_17500()
    if items:
        insert_results_batch(items)
        logger.info(f'从 17500.cn 导入 {len(items)} 期数据')
        return True

    # 方案 2: 福彩官网 API
    logger.info('尝试福彩官网 API 备用源...')
    all_items, total = fetch_from_cwl(page_no=1, page_size=100)
    if all_items:
        page = 1
        while len(all_items) < total:
            page += 1
            time.sleep(0.5)
            page_items, _ = fetch_from_cwl(page_no=page, page_size=100)
            if not page_items:
                break
            all_items.extend(page_items)
        insert_results_batch(all_items)
        logger.info(f'从福彩官网导入 {len(all_items)} 期数据')
        return True

    logger.error('所有数据源均失败')
    return False


def fetch_latest():
    """增量更新：获取最新数据"""
    # 重新下载全量数据，只插入新的
    items = fetch_from_17500()
    if items:
        latest_remote = items[-1][0]
        current = get_latest_issue()
        if latest_remote != current:
            # 找出新增的记录
            new_items = []
            for item in reversed(items):
                if item[0] == current:
                    break
                new_items.append(item)
            if new_items:
                new_items.reverse()
                insert_results_batch(new_items)
                logger.info(f'新增 {len(new_items)} 期数据，最新: {latest_remote}')
                return True
        return False

    # 备用: 福彩官网
    items, _ = fetch_from_cwl(page_no=1, page_size=3)
    if items:
        latest = items[0]
        current = get_latest_issue()
        if latest[0] != current:
            insert_results_batch([latest])
            logger.info(f'新数据: 第 {latest[0]} 期')
            return True
    return False

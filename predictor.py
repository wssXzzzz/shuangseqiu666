import random
from collections import Counter
from database import get_all_red_blue, get_recent_results, get_result_count


def frequency_analysis(reds, blues):
    """频率分析：统计每个号码出现次数"""
    red_freq = Counter(reds)
    blue_freq = Counter(blues)

    red_sorted = sorted(red_freq.items(), key=lambda x: x[1], reverse=True)
    blue_sorted = sorted(blue_freq.items(), key=lambda x: x[1], reverse=True)

    hot_reds = [n for n, _ in red_sorted[:10]]
    cold_reds = [n for n, _ in red_sorted[-10:]]
    hot_blues = [n for n, _ in blue_sorted[:5]]
    cold_blues = [n for n, _ in blue_sorted[-5:]]

    return {
        'red_freq': dict(red_freq),
        'blue_freq': dict(blue_freq),
        'hot_reds': hot_reds,
        'cold_reds': cold_reds,
        'hot_blues': hot_blues,
        'cold_blues': cold_blues,
    }


def missing_analysis(limit=50):
    """遗漏值分析：计算每个号码连续未出现的期数"""
    recent = get_recent_results(limit)
    if not recent:
        return {'red_missing': {}, 'blue_missing': {}}

    # recent 按 DESC 排序（最新在前），idx 即为遗漏期数
    red_missing = {i: limit for i in range(1, 34)}
    blue_missing = {i: limit for i in range(1, 17)}

    for idx, r in enumerate(recent):
        draw_reds = [r['red1'], r['red2'], r['red3'], r['red4'], r['red5'], r['red6']]
        draw_blue = r['blue']

        for n in draw_reds:
            if red_missing.get(n) == limit:
                red_missing[n] = idx
        if blue_missing.get(draw_blue) == limit:
            blue_missing[draw_blue] = idx

    return {
        'red_missing': red_missing,
        'blue_missing': blue_missing,
    }


def zone_analysis(reds):
    """区间分布：红球按 1-11, 12-22, 23-33 三个区间统计"""
    zones = {'1-11': 0, '12-22': 0, '23-33': 0}
    for r in reds:
        if r <= 11:
            zones['1-11'] += 1
        elif r <= 22:
            zones['12-22'] += 1
        else:
            zones['23-33'] += 1
    return zones


def odd_even_analysis(reds):
    """奇偶比分析"""
    odd = sum(1 for r in reds if r % 2 == 1)
    even = len(reds) - odd
    ratio = f'{odd}:{even}'
    return {'odd': odd, 'even': even, 'ratio': ratio}


def sum_analysis(limit=100):
    """和值分析：最近 N 期红球和值的分布"""
    recent = get_recent_results(limit)
    sums = []
    for r in recent:
        s = r['red1'] + r['red2'] + r['red3'] + r['red4'] + r['red5'] + r['red6']
        sums.append(s)

    if not sums:
        return {'sums': [], 'avg': 0, 'range': (0, 0)}

    return {
        'sums': sums,
        'avg': round(sum(sums) / len(sums), 1),
        'min': min(sums),
        'max': max(sums),
    }


def weighted_pick(candidates, weights, count):
    """按权重随机选择"""
    pool = []
    for num, w in zip(candidates, weights):
        pool.extend([num] * max(1, int(w)))
    random.shuffle(pool)
    picked = []
    for p in pool:
        if p not in picked:
            picked.append(p)
        if len(picked) >= count:
            break
    # 不够则从候选中随机补
    while len(picked) < count:
        n = random.choice(candidates)
        if n not in picked:
            picked.append(n)
    return sorted(picked)


def predict():
    """综合预测：多维度加权生成推荐号码"""
    reds, blues = get_all_red_blue()
    if not reds:
        return None

    total = get_result_count()
    freq = frequency_analysis(reds, blues)
    missing = missing_analysis(50)
    zones = zone_analysis(reds)
    odd_even = odd_even_analysis(reds)
    sums = sum_analysis(100)

    # 红球预测：综合频率和遗漏值
    red_candidates = list(range(1, 34))
    red_weights = []
    red_freq = freq['red_freq']
    red_miss = missing['red_missing']
    max_freq = max(red_freq.values()) if red_freq else 1

    for n in red_candidates:
        f = red_freq.get(n, 0) / max_freq * 50
        m = min(red_miss.get(n, 0) / 50, 1.0) * 30
        # 区间平衡加分
        zone = (n - 1) // 11
        zone_total = sum(zones.values()) if sum(zones.values()) > 0 else 1
        z = (zones.get(['1-11', '12-22', '23-33'][zone], 0) / zone_total) * 10
        # 随机扰动
        r = random.uniform(5, 15)
        red_weights.append(f + m + z + r)

    predicted_reds = weighted_pick(red_candidates, red_weights, 6)

    # 蓝球预测
    blue_candidates = list(range(1, 17))
    blue_weights = []
    blue_freq = freq['blue_freq']
    blue_miss = missing['blue_missing']
    max_blue_freq = max(blue_freq.values()) if blue_freq else 1

    for n in blue_candidates:
        f = blue_freq.get(n, 0) / max_blue_freq * 50
        m = min(blue_miss.get(n, 0) / 50, 1.0) * 30
        r = random.uniform(5, 20)
        blue_weights.append(f + m + r)

    predicted_blue = weighted_pick(blue_candidates, blue_weights, 1)[0]

    return {
        'reds': predicted_reds,
        'blue': predicted_blue,
        'total_periods': total,
        'analysis': {
            'frequency': {
                'red_freq': dict(sorted(freq['red_freq'].items())),
                'blue_freq': dict(sorted(freq['blue_freq'].items())),
                'hot_reds': freq['hot_reds'],
                'cold_reds': freq['cold_reds'],
                'hot_blues': freq['hot_blues'],
                'cold_blues': freq['cold_blues'],
            },
            'missing': missing,
            'zones': zones,
            'odd_even': odd_even,
            'sums': sums,
        }
    }

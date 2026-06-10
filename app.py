import json
from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from database import (
    init_db, get_recent_results, get_all_results, get_result_count,
    save_prediction, get_latest_prediction,
    save_pick, get_picks, get_normal_picks, get_persistent_picks,
    get_persistent_results, get_unchecked_picks, update_pick_result, delete_pick,
    get_latest_result, has_persistent_result, save_persistent_result,
    get_conn
)
from scraper import fetch_all_history, fetch_latest
from predictor import predict

app = Flask(__name__)
scheduler = BackgroundScheduler()

data_loaded = False

PRIZE_RULES = [
    (6, 1, '一等奖'), (6, 0, '二等奖'), (5, 1, '三等奖'),
    (5, 0, '四等奖'), (4, 1, '四等奖'),
    (4, 0, '五等奖'), (3, 1, '五等奖'),
    (2, 1, '六等奖'), (1, 1, '六等奖'), (0, 1, '六等奖'),
]


def get_prize(red_match, blue_match):
    for r, b, name in PRIZE_RULES:
        if red_match == r and blue_match == b:
            return name
    return None


def check_picks():
    """开奖后自动比对自选号码"""
    # 1. 单期号码（现有逻辑）
    picks = get_unchecked_picks()
    if picks:
        conn = get_conn()
        for pick in picks:
            row = conn.execute(
                'SELECT * FROM results WHERE issue = ?', (pick['issue'],)
            ).fetchone()
            if not row:
                continue
            draw_reds = [row['red1'], row['red2'], row['red3'],
                         row['red4'], row['red5'], row['red6']]
            draw_blue = row['blue']
            pick_reds = [pick['red1'], pick['red2'], pick['red3'],
                         pick['red4'], pick['red5'], pick['red6']]
            pick_blue = pick['blue']

            red_match = len(set(pick_reds) & set(draw_reds))
            blue_match = 1 if pick_blue == draw_blue else 0

            prize = get_prize(red_match, blue_match)
            matched = sorted(set(pick_reds) & set(draw_reds))
            matched_str = ','.join(str(n) for n in matched)
            update_pick_result(pick['id'], prize or '未中奖', matched_str, blue_match)
        conn.close()

    # 2. 持续跟踪号码
    latest = get_latest_result()
    if not latest:
        return
    persistent = get_persistent_picks()
    for pp in persistent:
        if has_persistent_result(pp['id'], latest['issue']):
            continue
        pick_reds = [pp['red1'], pp['red2'], pp['red3'],
                     pp['red4'], pp['red5'], pp['red6']]
        pick_blue = pp['blue']
        draw_reds = [latest['red1'], latest['red2'], latest['red3'],
                     latest['red4'], latest['red5'], latest['red6']]
        draw_blue = latest['blue']

        red_match = len(set(pick_reds) & set(draw_reds))
        blue_match = 1 if pick_blue == draw_blue else 0

        prize = get_prize(red_match, blue_match)
        matched = sorted(set(pick_reds) & set(draw_reds))
        matched_str = ','.join(str(n) for n in matched)
        save_persistent_result(pp['id'], latest['issue'], pick_reds, pick_blue,
                               prize or '未中奖', matched_str, blue_match)


def load_data():
    global data_loaded
    try:
        fetch_all_history()
        data_loaded = True
    except Exception as e:
        print(f'数据加载失败: {e}')


def scheduled_update():
    try:
        new_data = fetch_latest()
        if new_data:
            do_predict()
            check_picks()
    except Exception as e:
        print(f'定时更新失败: {e}')


def do_predict():
    result = predict()
    if result:
        from database import get_latest_issue
        issue = get_latest_issue()
        next_issue = str(int(issue) + 1) if issue else ''
        save_prediction(
            issue=next_issue,
            date='',
            reds=result['reds'],
            blue=result['blue'],
            analysis=json.dumps(result['analysis'], ensure_ascii=False)
        )
    return result


@app.route('/')
def index():
    results = get_recent_results(30)
    total = get_result_count()
    prediction = get_latest_prediction()

    analysis = {}
    if prediction and prediction.get('analysis'):
        try:
            analysis = json.loads(prediction['analysis'])
        except (json.JSONDecodeError, TypeError):
            analysis = {}

    return render_template('index.html',
                           results=results,
                           total=total,
                           prediction=prediction,
                           analysis=analysis,
                           data_loaded=data_loaded)


@app.route('/history')
def history():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    results, total = get_all_results(page, per_page)
    total_pages = (total + per_page - 1) // per_page
    return render_template('history.html',
                           results=results,
                           page=page,
                           total_pages=total_pages,
                           total=total)


@app.route('/api/latest')
def api_latest():
    results = get_recent_results(10)
    return jsonify({'code': 200, 'data': results, 'total': get_result_count()})


@app.route('/api/refresh')
def api_refresh():
    new_data = fetch_latest()
    if new_data:
        check_picks()
    return jsonify({'code': 200, 'new_data': new_data})


@app.route('/my-picks')
def my_picks():
    from database import get_latest_issue
    latest = get_latest_issue()
    next_issue = str(int(latest) + 1) if latest else ''
    normal_picks = get_normal_picks()
    persistent = get_persistent_picks()
    # 为每个持续跟踪号码附带其所有子记录
    for pp in persistent:
        pp['results'] = get_persistent_results(pp['id'])
    return render_template('my_picks.html',
                           next_issue=next_issue,
                           picks=normal_picks,
                           persistent_picks=persistent)


@app.route('/api/pick', methods=['POST'])
def api_add_pick():
    data = request.get_json()
    issue = data.get('issue', '').strip()
    reds = data.get('reds', [])
    blue = data.get('blue')
    persistent = data.get('persistent', False)

    if len(reds) != 6 or not blue:
        return jsonify({'code': 400, 'message': '参数不完整'})

    reds = sorted(int(r) for r in reds)
    blue = int(blue)

    if persistent:
        save_pick('', reds, blue, persistent=True)
    else:
        if not issue:
            return jsonify({'code': 400, 'message': '请输入期号'})
        save_pick(issue, reds, blue)

    return jsonify({'code': 200})


@app.route('/api/pick/delete', methods=['POST'])
def api_delete_pick():
    data = request.get_json()
    pick_id = data.get('id')
    if pick_id:
        delete_pick(pick_id)
        return jsonify({'code': 200})
    return jsonify({'code': 400, 'message': '缺少 id'})


if __name__ == '__main__':
    init_db()
    load_data()
    do_predict()
    check_picks()

    # 每天北京时间 21:35 自动检查更新（周二/四/日开奖）
    scheduler.add_job(scheduled_update, 'cron', hour=21, minute=35,
                      timezone='Asia/Shanghai')
    scheduler.start()

    app.run(host='0.0.0.0', port=5000, debug=False)

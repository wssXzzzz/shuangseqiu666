import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'ssq.db')


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue TEXT UNIQUE NOT NULL,
            date TEXT,
            red1 INTEGER, red2 INTEGER, red3 INTEGER,
            red4 INTEGER, red5 INTEGER, red6 INTEGER,
            blue INTEGER,
            sales TEXT,
            pool_money TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue TEXT,
            date TEXT,
            red1 INTEGER, red2 INTEGER, red3 INTEGER,
            red4 INTEGER, red5 INTEGER, red6 INTEGER,
            blue INTEGER,
            analysis TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS my_picks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue TEXT NOT NULL,
            red1 INTEGER, red2 INTEGER, red3 INTEGER,
            red4 INTEGER, red5 INTEGER, red6 INTEGER,
            blue INTEGER,
            prize TEXT,
            matched_reds TEXT,
            matched_blue INTEGER DEFAULT 0
        )
    ''')
    # 迁移：为旧表添加新列
    try:
        conn.execute('ALTER TABLE my_picks ADD COLUMN persistent INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute('ALTER TABLE my_picks ADD COLUMN parent_id INTEGER DEFAULT NULL')
    except sqlite3.OperationalError:
        pass
    # 迁移：为 predictions 表添加开奖对比字段
    for col in [
        'ALTER TABLE predictions ADD COLUMN matched_reds TEXT',
        'ALTER TABLE predictions ADD COLUMN matched_blue INTEGER DEFAULT 0',
        'ALTER TABLE predictions ADD COLUMN prize TEXT',
    ]:
        try:
            conn.execute(col)
        except sqlite3.OperationalError:
            pass
    # 迁移：清理同一期的重复预测（保留最新一条，与首页展示一致），并加唯一索引防止再次重复
    conn.execute('''
        DELETE FROM predictions
        WHERE id NOT IN (SELECT MAX(id) FROM predictions GROUP BY issue)
    ''')
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_predictions_issue ON predictions(issue)')
    conn.commit()
    conn.close()


def insert_result(issue, date, reds, blue, sales='', pool_money=''):
    conn = get_conn()
    try:
        conn.execute(
            '''INSERT OR IGNORE INTO results
               (issue, date, red1, red2, red3, red4, red5, red6, blue, sales, pool_money)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (issue, date, *reds, blue, sales, pool_money)
        )
        conn.commit()
    finally:
        conn.close()


def insert_results_batch(data):
    conn = get_conn()
    try:
        conn.executemany(
            '''INSERT OR IGNORE INTO results
               (issue, date, red1, red2, red3, red4, red5, red6, blue, sales, pool_money)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            data
        )
        conn.commit()
    finally:
        conn.close()


def get_latest_issue():
    conn = get_conn()
    row = conn.execute('SELECT issue FROM results ORDER BY id DESC LIMIT 1').fetchone()
    conn.close()
    return row['issue'] if row else None


def get_recent_results(limit=30):
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM results ORDER BY id DESC LIMIT ?', (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_results(page=1, per_page=50):
    conn = get_conn()
    offset = (page - 1) * per_page
    rows = conn.execute(
        'SELECT * FROM results ORDER BY id DESC LIMIT ? OFFSET ?',
        (per_page, offset)
    ).fetchall()
    total = conn.execute('SELECT COUNT(*) as cnt FROM results').fetchone()['cnt']
    conn.close()
    return [dict(r) for r in rows], total


def get_all_red_blue():
    conn = get_conn()
    rows = conn.execute(
        'SELECT red1,red2,red3,red4,red5,red6,blue FROM results ORDER BY id'
    ).fetchall()
    conn.close()
    reds = []
    blues = []
    for r in rows:
        reds.extend([r['red1'], r['red2'], r['red3'], r['red4'], r['red5'], r['red6']])
        blues.append(r['blue'])
    return reds, blues


def get_result_count():
    conn = get_conn()
    cnt = conn.execute('SELECT COUNT(*) as cnt FROM results').fetchone()['cnt']
    conn.close()
    return cnt


def save_prediction(issue, date, reds, blue, analysis=''):
    """一期只保留一条预测：该期已有预测时忽略，重启不会重复生成"""
    conn = get_conn()
    conn.execute(
        '''INSERT OR IGNORE INTO predictions
           (issue, date, red1, red2, red3, red4, red5, red6, blue, analysis)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (issue, date, *reds, blue, analysis)
    )
    conn.commit()
    conn.close()


def get_latest_prediction():
    conn = get_conn()
    row = conn.execute(
        'SELECT * FROM predictions ORDER BY id DESC LIMIT 1'
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_pick(issue, reds, blue, persistent=False):
    conn = get_conn()
    conn.execute(
        '''INSERT INTO my_picks (issue, red1, red2, red3, red4, red5, red6, blue, persistent)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (issue, *reds, blue, 1 if persistent else 0)
    )
    conn.commit()
    conn.close()


def get_picks():
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM my_picks WHERE parent_id IS NULL ORDER BY id DESC'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_normal_picks():
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM my_picks WHERE (persistent = 0 OR persistent IS NULL) AND parent_id IS NULL ORDER BY id DESC'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_persistent_picks():
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM my_picks WHERE persistent = 1 AND parent_id IS NULL ORDER BY id DESC'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_persistent_results(parent_id):
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM my_picks WHERE parent_id = ? ORDER BY issue DESC',
        (parent_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unchecked_picks():
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM my_picks WHERE prize IS NULL AND (persistent = 0 OR persistent IS NULL) AND parent_id IS NULL ORDER BY id'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_result():
    conn = get_conn()
    row = conn.execute(
        'SELECT * FROM results ORDER BY id DESC LIMIT 1'
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def has_persistent_result(parent_id, issue):
    conn = get_conn()
    row = conn.execute(
        'SELECT id FROM my_picks WHERE parent_id = ? AND issue = ?',
        (parent_id, issue)
    ).fetchone()
    conn.close()
    return row is not None


def save_persistent_result(parent_id, issue, reds, blue, prize, matched_reds, matched_blue):
    conn = get_conn()
    conn.execute(
        '''INSERT INTO my_picks (issue, red1, red2, red3, red4, red5, red6, blue, prize, matched_reds, matched_blue, parent_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (issue, *reds, blue, prize, matched_reds, matched_blue, parent_id)
    )
    conn.commit()
    conn.close()


def update_pick_result(pick_id, prize, matched_reds, matched_blue):
    conn = get_conn()
    conn.execute(
        'UPDATE my_picks SET prize=?, matched_reds=?, matched_blue=? WHERE id=?',
        (prize, matched_reds, matched_blue, pick_id)
    )
    conn.commit()
    conn.close()


def delete_pick(pick_id):
    conn = get_conn()
    conn.execute('DELETE FROM my_picks WHERE parent_id=?', (pick_id,))
    conn.execute('DELETE FROM my_picks WHERE id=?', (pick_id,))
    conn.commit()
    conn.close()


def get_unchecked_predictions():
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM predictions WHERE prize IS NULL ORDER BY id'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_prediction_result(prediction_id, prize, matched_reds, matched_blue):
    conn = get_conn()
    conn.execute(
        'UPDATE predictions SET prize=?, matched_reds=?, matched_blue=? WHERE id=?',
        (prize, matched_reds, matched_blue, prediction_id)
    )
    conn.commit()
    conn.close()


def get_all_predictions(page=1, per_page=20):
    conn = get_conn()
    offset = (page - 1) * per_page
    rows = conn.execute(
        'SELECT * FROM predictions ORDER BY id DESC LIMIT ? OFFSET ?',
        (per_page, offset)
    ).fetchall()
    total = conn.execute('SELECT COUNT(*) as cnt FROM predictions').fetchone()['cnt']
    conn.close()
    return [dict(r) for r in rows], total

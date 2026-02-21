# db.py
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "data.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # 取引テーブル
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            y INTEGER NOT NULL,
            m INTEGER NOT NULL,
            d INTEGER NOT NULL,
            code INTEGER NOT NULL,
            description TEXT NOT NULL,
            amount INTEGER NOT NULL,
            direction TEXT NOT NULL CHECK(direction IN ('in','out')),
            created_at TEXT NOT NULL,
            is_reflected INTEGER NOT NULL DEFAULT 0
        );
    """)

    # 調整用テーブル
    cur.execute("""
        CREATE TABLE IF NOT EXISTS adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            y INTEGER NOT NULL,
            m INTEGER NOT NULL,
            item TEXT NOT NULL,
            amount INTEGER NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            is_reflected INTEGER NOT NULL DEFAULT 0,
            UNIQUE(y, m, item)
        );
    """)

    conn.commit()
    conn.close()


# ------------------------
# 取引追加（売上・経費共通）
# ------------------------
def add_transaction(
    *,
    y: int,
    m: int,
    d: int,
    code: int,
    description: str,
    amount: int,
    direction: str,
    force: bool = False,
):
    description = (description or "").strip()

    if not description:
        return False, "摘要が空です"

    if amount <= 0:
        return False, "金額は1円以上にしてください"

    if direction not in ("in", "out"):
        return False, "directionが不正です"

    conn = get_conn()
    cur = conn.cursor()

    # 重複チェック（完全一致）
    cur.execute(
        """
        SELECT COUNT(1)
        FROM transactions
        WHERE y=? AND m=? AND d=? AND code=? AND description=? AND amount=? AND direction=?;
        """,
        (y, m, d, code, description, amount, direction),
    )
    exists = cur.fetchone()[0] > 0

    if exists and not force:
        conn.close()
        return False, "⚠️ 同じ内容が既にあります（重複）。チェックを入れると登録できます"

    try:
        cur.execute(
            """
            INSERT INTO transactions
            (y, m, d, code, description, amount, direction, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (y, m, d, code, description, amount, direction, now_iso()),
        )
        conn.commit()
        return True, None
    finally:
        conn.close()


# ------------------------
# 調整用：月ごとに上書き保存（y,m,itemで1件）
# ------------------------
def upsert_adjustment(
    *,
    y: int,
    m: int,
    item: str,
    amount: int,
    note: str = "",
):
    item = (item or "").strip()
    note = (note or "").strip()

    if not item:
        raise ValueError("itemが空です")

    if amount < 0:
        raise ValueError("金額は0以上にしてください")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO adjustments (y, m, item, amount, note, created_at, is_reflected)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        ON CONFLICT(y, m, item) DO UPDATE SET
            amount=excluded.amount,
            note=excluded.note,
            created_at=excluded.created_at,
            is_reflected=0;
        """,
        (y, m, item, amount, note, now_iso()),
    )

    conn.commit()
    conn.close()


# ------------------------
# 反映用：未反映取引の取得/反映済み更新
# ------------------------
def get_unreflected_transactions(*, y: int, m: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, y, m, d, code, description, amount, direction
        FROM transactions
        WHERE y=? AND m=? AND is_reflected=0
        ORDER BY d ASC, id ASC;
        """,
        (y, m),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def mark_transactions_reflected(ids):
    if not ids:
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.executemany(
        "UPDATE transactions SET is_reflected=1 WHERE id=?;",
        [(int(i),) for i in ids],
    )
    conn.commit()
    conn.close()

# ------------------------
# 売上：同じ日・同じ摘要なら上書き（UPDATE）
# code=1, direction='in' 固定
# ------------------------
def upsert_sales(
    *,
    y: int,
    m: int,
    d: int,
    description: str,
    amount: int,
):
    description = (description or "").strip()

    if not description:
        return False, "摘要が空です"
    if amount <= 0:
        return False, "金額は1円以上にしてください"

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id FROM transactions
        WHERE y=? AND m=? AND d=? AND code=1 AND description=? AND direction='in'
        ORDER BY id DESC LIMIT 1;
        """,
        (y, m, d, description),
    )
    row = cur.fetchone()

    if row:
        cur.execute(
            """
            UPDATE transactions
            SET amount=?, created_at=?, is_reflected=0
            WHERE id=?;
            """,
            (amount, now_iso(), int(row["id"])),
        )
        conn.commit()
        conn.close()
        return True, "上書きしました"

    cur.execute(
        """
        INSERT INTO transactions
        (y, m, d, code, description, amount, direction, created_at)
        VALUES (?, ?, ?, 1, ?, ?, 'in', ?);
        """,
        (y, m, d, description, amount, now_iso()),
    )
    conn.commit()
    conn.close()
    return True, "登録しました"


# ------------------------
# 売上：指定月・指定摘要の最新金額を取得（UI初期表示用）
# direction='in'
# ------------------------
def get_sales_amount(*, y: int, m: int, description: str):
    description = (description or "").strip()
    if not description:
        return None

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT amount
        FROM transactions
        WHERE y=? AND m=? AND description=? AND direction='in'
        ORDER BY id DESC
        LIMIT 1;
        """,
        (y, m, description),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return None
    return int(row["amount"])


# ------------------------
# 固定費：同じ月・同じ項目なら上書き（UPDATE）
# direction='out'
# ------------------------
def upsert_fixed_cost(
    *,
    y: int,
    m: int,
    d: int,
    code: int,
    item: str,
    amount: int,
):
    item = (item or "").strip()

    if not item:
        return False, "項目が空です"
    if amount <= 0:
        return False, "金額は1円以上にしてください"

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id FROM transactions
        WHERE y=? AND m=? AND code=? AND description=? AND direction='out'
        ORDER BY id DESC LIMIT 1;
        """,
        (y, m, code, item),
    )
    row = cur.fetchone()

    if row:
        cur.execute(
            """
            UPDATE transactions
            SET d=?, amount=?, created_at=?, is_reflected=0
            WHERE id=?;
            """,
            (d, amount, now_iso(), int(row["id"])),
        )
        conn.commit()
        conn.close()
        return True, "上書きしました"

    cur.execute(
        """
        INSERT INTO transactions
        (y, m, d, code, description, amount, direction, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'out', ?);
        """,
        (y, m, d, code, item, amount, now_iso()),
    )
    conn.commit()
    conn.close()
    return True, "登録しました"
def get_fixed_cost_items_for_month(*, y: int, m: int, items: list[str]) -> set:
    """
    指定年月で、固定費テンプレ(items)に含まれる description だけを「登録済み」として数える。
    """
    items = [((s or "").strip()) for s in items if (s or "").strip()]
    if not items:
        return set()

    conn = get_conn()
    cur = conn.cursor()

    placeholders = ",".join(["?"] * len(items))
    sql = f"""
        SELECT DISTINCT description
        FROM transactions
        WHERE y=? AND m=? AND direction='out' AND description IN ({placeholders})
    """
    cur.execute(sql, (y, m, *items))
    rows = cur.fetchall()
    conn.close()

    out = set()
    for r in rows:
        if isinstance(r, dict):
            v = r.get("description")
        else:
            v = r[0]
        if v not in (None, ""):
            out.add(v)
    return out

if __name__ == "__main__":
    init_db()
    print("DB initialized:", DB_PATH)

"""資料庫連線（Supabase／PostgreSQL）。沒有設定 DATABASE_URL 時，App 仍可運作，只是沒有歷史資料。"""
import psycopg

from . import config


def enabled():
    return bool(config.DATABASE_URL)


def query(sql, params=None):
    """執行查詢並回傳所有列（list of tuple）。"""
    with psycopg.connect(config.DATABASE_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()


def execute_many(sql, rows):
    """一次寫入多列。"""
    with psycopg.connect(config.DATABASE_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        conn.commit()

"""品牌词数据操作"""
from database.core import get_db, now

def get_brand_words():
    conn = get_db()
    rows = conn.execute("SELECT word FROM brand_words ORDER BY id").fetchall()
    conn.close()
    return [r["word"] for r in rows]

def add_brand_word(word: str):
    conn = get_db()
    try:
        conn.execute("INSERT INTO brand_words (word, created_at) VALUES (?,?)", (word, now()))
        conn.commit()
    except: pass
    rows = conn.execute("SELECT word FROM brand_words ORDER BY id").fetchall()
    conn.close()
    return [r["word"] for r in rows]

def delete_brand_word(word: str):
    conn = get_db()
    conn.execute("DELETE FROM brand_words WHERE word=?", (word,))
    conn.commit()
    rows = conn.execute("SELECT word FROM brand_words ORDER BY id").fetchall()
    conn.close()
    return [r["word"] for r in rows]

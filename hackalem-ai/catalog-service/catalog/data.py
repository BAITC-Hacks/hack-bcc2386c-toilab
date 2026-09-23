import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from .models import Item

class Store:
    """Single-process SQLite repository. Replace behind this interface for replicas."""
    def __init__(self, path):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY, body TEXT NOT NULL); CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT); CREATE TABLE IF NOT EXISTS cart(session TEXT,product TEXT,qty INTEGER,PRIMARY KEY(session,product));")
    def items(self):
        with self.lock:
            return [Item.model_validate_json(r[0]) for r in self.db.execute("SELECT body FROM products ORDER BY id")]
    def replace(self, items):
        with self.lock, self.db:
            self.db.execute("DELETE FROM products")
            self.db.executemany("INSERT INTO products VALUES(?,?)", [(x.id,x.model_dump_json()) for x in items])
            self.db.execute("INSERT OR REPLACE INTO meta VALUES('last_sync',?)", (datetime.now(timezone.utc).isoformat(),))
    def last_sync(self):
        with self.lock:
            row=self.db.execute("SELECT v FROM meta WHERE k='last_sync'").fetchone()
            return row[0] if row else "1970-01-01T00:00:00+00:00"
    def cart(self, session):
        with self.lock:
            return [{"product_id":r[0],"qty":r[1]} for r in self.db.execute("SELECT product,qty FROM cart WHERE session=? ORDER BY product",(session,))]
    def set_qty(self, session, product, qty):
        with self.lock, self.db:
            self.db.execute("INSERT INTO cart VALUES(?,?,?) ON CONFLICT(session,product) DO UPDATE SET qty=excluded.qty", (session,product,qty))

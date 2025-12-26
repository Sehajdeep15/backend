import aiosqlite
import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class Storage:
    def __init__(self, db_url: str):
        # Handle sqlite:////data/app.db format
        # aiosqlite needs the file path directly.
        self.db_path = self._parse_db_url(db_url)

    def _parse_db_url(self, db_url: str) -> str:
        # Simple parser for sqlite:///path or sqlite:////path
        match = re.match(r"sqlite:\/\/\/(.+)", db_url)
        if match:
            return match.group(1)
        return db_url # Fallback if not matching expected pattern

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    from_msisdn TEXT NOT NULL,
                    to_msisdn TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    text TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            # Indices for performance
            await db.execute("CREATE INDEX IF NOT EXISTS idx_ts ON messages (ts)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_from ON messages (from_msisdn)")
            await db.commit()

    async def check_connection(self) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def insert_message(self, message_id: str, sender: str, receiver: str, ts: datetime, text: Optional[str]) -> bool:
        """
        Returns True if inserted, False if duplicate.
        """
        now = datetime.now(timezone.utc).isoformat()
        ts_str = ts.isoformat() if isinstance(ts, datetime) else ts
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO messages (message_id, from_msisdn, to_msisdn, ts, text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (message_id, sender, receiver, ts_str, text, now)
                )
                await db.commit()
                return True
        except aiosqlite.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                return False
            raise e

    async def query_messages(self, limit: int, offset: int, from_filter: Optional[str], since: Optional[datetime], q: Optional[str]) -> Tuple[List[Dict[str, Any]], int]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            base_query = "FROM messages WHERE 1=1"
            params = []
            
            if from_filter:
                base_query += " AND from_msisdn = ?"
                params.append(from_filter)
            
            if since:
                base_query += " AND ts >= ?"
                params.append(since.isoformat() if isinstance(since, datetime) else since)
                
            if q:
                base_query += " AND text LIKE ?"
                params.append(f"%{q}%")

            # Count total
            async with db.execute(f"SELECT COUNT(*) {base_query}", params) as cursor:
                total_row = await cursor.fetchone()
                total = total_row[0]

            # Fetch data
            data_query = f"SELECT * {base_query} ORDER BY ts ASC, message_id ASC LIMIT ? OFFSET ?"
            data_params = params + [limit, offset]
            
            async with db.execute(data_query, data_params) as cursor:
                rows = await cursor.fetchall()
                
            data = []
            for row in rows:
                data.append({
                    "message_id": row["message_id"],
                    "from": row["from_msisdn"],
                    "to": row["to_msisdn"],
                    "ts": row["ts"],
                    "text": row["text"]
                })
            return data, total

    async def compute_stats(self) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            stats = {}
            
            # Total messages
            async with db.execute("SELECT COUNT(*) FROM messages") as cursor:
                row = await cursor.fetchone()
                stats["total_messages"] = row[0]
            
            # Senders count
            async with db.execute("SELECT COUNT(DISTINCT from_msisdn) FROM messages") as cursor:
                row = await cursor.fetchone()
                stats["senders_count"] = row[0]
                
            # First/Last ts
            async with db.execute("SELECT MIN(ts), MAX(ts) FROM messages") as cursor:
                row = await cursor.fetchone()
                stats["first_message_ts"] = row[0]
                stats["last_message_ts"] = row[1]
                
            # Top 10 senders
            async with db.execute("""
                SELECT from_msisdn, COUNT(*) as cnt 
                FROM messages 
                GROUP BY from_msisdn 
                ORDER BY cnt DESC 
                LIMIT 10
            """) as cursor:
                rows = await cursor.fetchall()
                stats["messages_per_sender"] = {row[0]: row[1] for row in rows}
                
            return stats
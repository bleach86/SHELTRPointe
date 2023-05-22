import json
import asyncio
import concurrent.futures
import plyvel
import aiosqlite


class Database:
    """Class for doing Async sqlite3 database oporations."""

    def __init__(self):
        self.conn = None
        self.dbPath = "sheltrPointe.db"
        self.tableList = []

    async def initDB(self):
        """Check that our tables exist, and create them if not."""
        if self.conn is not None:
            print("Database connection already started.")
            return
        try:
            async with aiosqlite.connect(self.dbPath) as conn:
                self.conn = conn
                self.cursor = await self.conn.cursor()
                await self.cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table';"
                )
                tables = await self.cursor.fetchall()
                for i in tables:
                    self.tableList.append(i[0])
                if "vinDetailAsync" not in self.tableList:
                    await self.initVinDetail()
        except Exception as e:
            print(f"Error connecting to database: {e}")
            raise

    async def initVinDetail(self):
        """Create the vin detail table."""
        await self.cursor.execute(
            """CREATE TABLE vinDetailAsync (
                                txid text primary key unique,
                                vinDetail text,
                                timestamp integer
                            )"""
        )
        await self.conn.commit()

    async def newVinDetail(self, txid, vinDetail, timestamp):
        """Adds a new vin detail to the db."""
        async with aiosqlite.connect(self.dbPath) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """INSERT OR IGNORE INTO vinDetailAsync VALUES (?, ?, ?)""",
                    (txid, vinDetail, timestamp),
                )
                await conn.commit()

    async def getVinDetail(self, txid):
        """Retruns the vin detail for a given TXID"""
        async with aiosqlite.connect(self.dbPath) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """SELECT * FROM vinDetailAsync WHERE txid=:txid""", {"txid": txid}
                )
                existing = await cursor.fetchone()
                if existing is None:
                    return None

                assert txid == existing[0]
                return json.loads(existing[1])

    async def getAllVinDetail(self):
        """Retruns all rows in the vin detail table."""
        async with aiosqlite.connect(self.dbPath) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""SELECT * FROM vinDetailAsync""")
                existing = await cursor.fetchall()
                return existing

    async def removeVinDetail(self, txid):
        """Removes vin detail entry for a given TXID"""
        async with aiosqlite.connect(self.dbPath) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """DELETE from vinDetailAsync WHERE txid=?""", (txid,)
                )
                await conn.commit()


class AsyncLvldb:
    """Async wrapper class for plyvel"""

    def __init__(self):
        self.lvldb = plyvel.DB("sheltrPointLVL.db", create_if_missing=True)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.loop = asyncio.get_running_loop()

    async def get(self, key):
        """Async wrapper for plyvel's get method. Runs in an awaitable thread"""
        return await self.loop.run_in_executor(self.executor, self.lvldb.get, key)

    async def put(self, key, value):
        """Async wrapper for plyvel's put method. Runs in an awaitable thread"""
        return await self.loop.run_in_executor(
            self.executor, self.lvldb.put, key, value
        )

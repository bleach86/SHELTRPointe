import aiosqlite
import json
import time
import random
from datetime import datetime
import asyncio
import plyvel

class Database:
    def __init__(self):
        self.conn = None
        self.tableList = []

    async def connect(self):
        if self.conn is None:
            try:
                self.conn = await aiosqlite.connect("sheltrPointe.db")
            except RuntimeError:
                print("Database connection already started.")
                return


        self.cursor = await self.conn.cursor()
        await self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = await self.cursor.fetchall()
        for i in tables:
            self.tableList.append(i[0])

        if 'vinDetailAsync' not in self.tableList:
            await self.initVinDetail()

    async def close(self):
        await self.conn.close()

    async def initVinDetail(self):

        await self.cursor.execute("""CREATE TABLE vinDetailAsync (
                                txid text primary key unique,
                                vinDetail text,
                                timestamp integer
                            )""")
        await self.conn.commit()

    async def inittxCache(self):
        await self.cursor.execute("""CREATE TABLE txCache (
                                txid text,
                                txdetail text,
                                height integer
                            )""")
        await self.conn.commit()

    async def initsheltrMQ(self):
        await self.cursor.execute("""CREATE TABLE sheltrMQ (
                                id INTEGER PRIMARY KEY,
                                data text
                            )""")
        await self.conn.commit()

    async def newVinDetail(self, txid, vinDetail, timestamp):
        await self.cursor.execute(
            """INSERT OR IGNORE INTO vinDetailAsync VALUES (?, ?, ?)""",
            (txid, vinDetail, timestamp))
        await self.conn.commit()

    async def isVinDetailExisting(self, txid):
        await self.cursor.execute("""SELECT * FROM vinDetailAsync WHERE txid=?""", (txid,))
        existing = await self.cursor.fetchone()
        if existing == None:
            return False
        else:
            return True

    async def getVinDetail(self, txid):
        await self.cursor.execute("""SELECT * FROM vinDetailAsync WHERE txid=?""", (txid,))
        existing = await self.cursor.fetchone()
        if existing == None:
            return None
        else:
            return json.loads(existing[1])

    async def getAllVinDetail(self):
        await self.cursor.execute("""SELECT * FROM vinDetailAsync""")
        existing = await self.cursor.fetchall()
        return existing

    async def removeVinDetail(self, txid):
        await self.cursor.execute(f"""DELETE from vinDetailAsync WHERE txid=?""", (txid,))
        await self.conn.commit()


class AsyncLvldb:
    def __init__(self):
        self.lvldb = plyvel.DB('sheltrPointLVL.db', create_if_missing=True)
    
    async def get(self, key):
        return await asyncio.to_thread(self.lvldb.get, key)

    async def put(self, key, value):
        return await asyncio.to_thread(self.lvldb.put, key, value)


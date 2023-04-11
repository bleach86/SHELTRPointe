import sqlite3, json, time, random
from datetime import datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect("sheltrPointe.db", check_same_thread=False)
        self.cursor = self.conn.cursor()

        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = self.cursor.fetchall()
        #self.cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_txid'")
        #txindex = self.cursor.fetchone()
        #self.cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_vin'")
        #vinindex = self.cursor.fetchone()

        self.tableList = []
        for i in tables:
            self.tableList.append(i[0])


        if 'vinDetail' not in self.tableList:
            self.initVinDetail()

        if 'txCache' not in self.tableList:
            self.inittxCache()

        if 'sheltrMQ' not in self.tableList:
            self.initsheltrMQ()

        #if not txindex:
        #    self.initTxIndex()

        #if not vinindex:
        #    self.initVinIndex()


    def initVinDetail(self):
        with self.conn:
            self.cursor.execute("""CREATE TABLE vinDetail (
                                   txid text,
                                   vinDetail text,
                                   timestamp integer
                                )""")

    def inittxCache(self):
        with self.conn:
            self.cursor.execute("""CREATE TABLE txCache (
                                   txid text,
                                   txdetail text,
                                   height integer
                                )""")

    def initsheltrMQ(self):
        with self.conn:
            self.cursor.execute("""CREATE TABLE sheltrMQ (
                                   id INTEGER PRIMARY KEY,
                                   data text
                                )""")

    def initTxIndex(self):
        with self.conn:
            self.cursor.execute("CREATE INDEX idx_txid ON txCache(height DESC)")

    def initVinIndex(self):
        with self.conn:
            self.cursor.execute("CREATE INDEX idx_vin ON vinDetail(txid)")

    def newVinDetail(self, txid, vinDetail, timestamp):
        if not self.isVinDetailExisting(txid):
            with self.conn:
                self.cursor.execute(
                    """INSERT INTO vinDetail VALUES (:txid, :vinDetail, :timestamp)""",
                    {'txid': txid, 'vinDetail': vinDetail, "timestamp": timestamp})
    
    def isVinDetailExisting(self, txid):
        self.cursor.execute("""SELECT * FROM vinDetail WHERE txid=:txid""", {'txid': txid})
        existing = self.cursor.fetchone()
        if existing == None:
            return False
        else:
            return True

    def getVinDetail(self, txid):
        self.cursor.execute("""SELECT * FROM vinDetail WHERE txid=:txid""", {'txid': txid})
        existing = self.cursor.fetchone()
        if existing == None:
            return None
        else:
            return json.loads(existing[1])

    def getAllVinDetail(self):
        self.cursor.execute("""SELECT * FROM vinDetail""")
        existing = self.cursor.fetchall()
        return existing

    def removeVinDetail(self, txid):
        with self.conn:
            self.cursor.execute(f"""DELETE from vinDetail WHERE txid=:txid""", {"txid": txid})


    def newtxCache(self, txid, txdetail, height):
        if not self.istxCacheExisting(txid):
            with self.conn:
                self.cursor.execute(
                    """INSERT INTO txCache VALUES (:txid, :txdetail, :height)""",
                    {'txid': txid, 'txdetail': txdetail, "height": height})
    
    def istxCacheExisting(self, txid):
        self.cursor.execute("""SELECT * FROM txCache INDEXED BY idx_txid WHERE txid=:txid""", {'txid': txid})
        existing = self.cursor.fetchone()
        if existing == None:
            return False
        else:
            return True

    def gettxCache(self, txid):
        self.cursor.execute("""SELECT * FROM txCache INDEXED BY idx_txid WHERE txid=:txid""", {'txid': txid})
        existing = self.cursor.fetchone()
        if existing == None:
            return None
        else:
            return json.loads(existing[1])
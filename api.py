from quart import Quart, render_template, request, jsonify, websocket
from quart_cors import cors
import socketio

import ssl

import time, json
from util import callrpc
import asyncio
import uvicorn

from binascii import unhexlify

import threading, asyncio, random
import queue
import zmq
import plyvel

from threading import Thread
from functools import wraps
from database import Database

db = Database()

lvldb = plyvel.DB('sheltrPointLVL.db', create_if_missing=True)

from zmq_sub import ZMQHandler

PORT = 51725

CORS_ALLOWED_ORIGINS = "*"

VERSION = "0.1"

class QuartSIO:
    def __init__(self) -> None:
        self._sio = socketio.AsyncServer(
            async_mode="asgi", cors_allowed_origins=CORS_ALLOWED_ORIGINS
        )
        self._quart_app = Quart(__name__, template_folder="templates")
        self._quart_app = cors(self._quart_app, allow_origin=CORS_ALLOWED_ORIGINS)
        self._quart_app.config['SECRET_KEY'] = 'secret!'
        self._quart_app.config['JSON_SORT_KEYS'] = False
        self._sio_app = socketio.ASGIApp(self._sio, self._quart_app)
        self.route = self._quart_app.route
        self.on = self._sio.on
        self.enter_room = self._sio.enter_room
        self.emit = self._sio.emit

    async def _run(self, host: str, port: int):
        try:
            uvconfig = uvicorn.Config(self._sio_app, host=host, port=port)
            server = uvicorn.Server(config=uvconfig)
            await server.serve()
        except KeyboardInterrupt:
            print("Shutting down")
        finally:
            print("Bye!")

    def run(self, host: str, port: int):
        asyncio.run(self._run(host, port))


app = QuartSIO()


def api_required(func):
    @wraps(func)
    async def decorator(*args, **kwargs):
        if json.loads(await request.get_data()):
            return await func(*args, **kwargs)
    return decorator


@app._quart_app.after_request
async def after_request(response):
  response.headers.add('Access-Control-Allow-Origin', '*')
  response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
  response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
  return response

@app.route('/', methods=["POST", "GET"]) 
async def index():
    return await render_template('template.html', content=request.method)

@app.route('/ping/', methods=["POST", "GET"]) 
async def ping():
    return await render_template('template.html', content="Pong!")

@app.route('/getblockcount/', methods=["GET"])
async def getBlockCount():
    return jsonify(callrpc(PORT, "getblockcount"))

@app.route('/api/block/<blockHash>/', methods=["GET"])
async def getBlock(blockHash):
    return jsonify(callrpc(PORT, "getblock", [blockHash]))

@app.route('/api/block-index/<blockIndex>/', methods=["GET"])
async def getBlockHash(blockIndex):
    blockHash = {"blockHash": callrpc(PORT, "getblockhash", [int(blockIndex)])}
    return jsonify(blockHash)

@app.route('/api/tx/<txid>/', methods=["GET"])
async def getTx(txid, standalone=False):
    tx = lvldb.get(bytes(txid, 'utf-8'))
    if tx:
        tx = json.loads(tx)   
        isCache = True
    else:
        isCache = False
        tx = callrpc(PORT, "getrawtransaction", [txid, True])

        isCoinStake = True if unhexlify(tx['hex'])[1] == 0x02 else False
        tx['isCoinStake'] = isCoinStake
        if isCoinStake:
            rewardDetails = callrpc(PORT, "getblockreward", [int(tx['height'])])

            tx['reward'] = float(rewardDetails['blockreward'])
            tx['rewardSat'] = convertToSat(rewardDetails['blockreward'])

            if "gvrreward" in rewardDetails:
                tx['isAGVR'] = True
                tx['rewardAGVR'] = float(rewardDetails['gvrreward'])
                tx['rewardAGVRSat'] = convertToSat(rewardDetails['gvrreward'])
            else:
                tx['isAGVR'] = False 

        tx['vin'] = getInputDetails(tx['vin'], txid)
    
    if 'time' not in tx:
        tx['time'] = int(time.time())
    if "confirmations" in tx:
        currHeight = callrpc(PORT, "getblockcount") + 1
        tx['confirmations'] = currHeight - tx['height']
    if not isCache:
        if "confirmations" in tx and tx['confirmations'] >= 100:
            if db.getVinDetail(txid):
                db.removeVinDetail(txid)
            lvldb.put(bytes(txid, 'utf-8'), json.dumps(tx, indent=2).encode('utf-8'))

    del tx['hex']
    if standalone:
        return tx
    return jsonify(tx)


@app.route('/api/addrs/<addrs>/txs/', methods=["GET"])
async def getTxHistory(addrs):
    addrs = removeBlank(addrs.split(','))

    txids = callrpc(PORT, "getaddresstxids", [{"addresses": addrs}])
    txHistory = []
    
    fromIdx = 0
    toIdx = 10

    if request.args.get("from"):
        fromIdx = int(request.args.get("from"))
    
    if request.args.get("to"):
        toIdx = int(request.args.get("to"))
    
    mempool = callrpc(PORT, "getaddressmempool", [{"addresses": addrs}])

    if mempool:
        memTxs = []
        for mem in mempool:
            if mem['txid'] not in memTxs:
                memTxs.append(mem['txid'])
        
        txids += memTxs
    
    resp = getAddrHist(txids, fromIdx, toIdx)

    return jsonify(resp)

@app.route('/api/addrs/txs/', methods=["POST"])
async def getTxHistoryPost():
    reqJson = json.loads(await request.get_data())

    if 'addrs' in reqJson:
        addrs = reqJson['addrs']
        addrs = removeBlank(addrs.split(','))
    else:
        return "Missing Addresses"

    txids = callrpc(PORT, "getaddresstxids", [{"addresses": addrs}])
    txHistory = []
    
    fromIdx = 0
    toIdx = 10

    if "from" in reqJson:
        fromIdx = int(reqJson['from'])
    
    if "to" in reqJson:
        toIdx = int(reqJson['to'])
    
    mempool = callrpc(PORT, "getaddressmempool", [{"addresses": addrs}])

    if mempool:
        memTxs = []
        for mem in mempool:
            if mem['txid'] not in memTxs:
                memTxs.append(mem['txid'])
        
        txids += memTxs
    
    resp = getAddrHist(txids, fromIdx, toIdx)

    return jsonify(resp)


@app.route('/api/addr/<addr>/utxo/', methods=["GET"])
async def getUtxo(addr):
    utxo = getUTXOs(addr)

    return jsonify(sorted(utxo, key=lambda d: d['confirmations']))

@app.route('/api/tx/send/', methods=["POST"])
async def sendTx():
    req = json.loads(await request.get_data())

    if "rawtx" not in req:
        return "Missing Transaction data."
    
    try:
        int(req['rawtx'], 16)
    except ValueError:
        return jsonify({"reject-reason": "Invalid Hex"})
    try:
        testMemPool = callrpc(PORT, "testmempoolaccept", [[req['rawtx']]])
    except:
        return jsonify({"reject-reason": "Invalid Transaction"})
    if not testMemPool[0]['allowed']:
        return jsonify({"reject-reason": testMemPool[0]['reject-reason']})
    
    txid = callrpc(PORT, "sendrawtransaction", [req['rawtx']])

    return jsonify({"txid": txid})


@app.route('/api/addrs/utxo/', methods=["POST"])
@api_required
async def getUtxoMultiGet():
    reqJson = json.loads(await request.get_data())

    if 'addrs' in reqJson:
        addrs = reqJson['addrs']
    else:
        return "Missing Addresses"
    
    utxo = getUTXOs(addrs)

    return jsonify(sorted(utxo, key=lambda d: d['confirmations']))


def getUTXOs(addr):

    addr = removeBlank(addr.split(','))

    currHeight = callrpc(PORT, "getblockcount") + 1
    utxo = callrpc(PORT, "getaddressutxos", [{"addresses": addr}])

    for i in utxo:
        i['confirmations'] = currHeight - int(i['height'])

    mempool = callrpc(PORT, "getaddressmempool", [{"addresses": addr}])

    if mempool:
        for memUTXO in mempool.copy():
            if "prevtxid" in memUTXO:
                for unspentTx in utxo.copy():
                    if unspentTx['txid'] == memUTXO['prevtxid'] and unspentTx['outputIndex'] == memUTXO['prevout']:
                        utxo.remove(unspentTx)
                mempool.remove(memUTXO)

            else:
                tx = callrpc(PORT, "getrawtransaction", [memUTXO['txid'], True])
                memUTXO['script'] = tx['vout'][memUTXO['index']]['scriptPubKey']['hex']
                memUTXO['outputIndex'] = memUTXO['index']
                memUTXO['confirmations'] = 0

                del memUTXO['index']
        
        utxo = utxo + mempool

    return utxo


def getInputDetails(inputs, txid):
    
    existing = db.getVinDetail(txid)
    
    if existing:
        return existing

    for vin in inputs:
        addr = None
        amount = None
        amountSats = None
        
        if "type" in vin and vin['type'] in ['anon', 'blind']:
            vin['type'] = vin['type']
            vin['addr'] = addr
            vin['value'] = amount
            vin['valueSat'] = amountSats
        else:
            inTX = lvldb.get(bytes(vin['txid'], 'utf-8'))
            if not inTX:
                inTX = callrpc(PORT, "getrawtransaction", [vin['txid'], True])
            else:
                inTX = json.loads(inTX)
            txType = inTX['vout'][vin['vout']]['type'] if "type" in inTX['vout'][vin['vout']] else "standard"

            if txType not in ['anon', 'blind']:
                addr = inTX['vout'][vin['vout']]['scriptPubKey']['addresses'][0]
                amount = inTX['vout'][vin['vout']]['value']
                amountSats = inTX['vout'][vin['vout']]['valueSat']
            
            vin['type'] = txType
            vin['addr'] = addr
            vin['value'] = amount
            vin['valueSat'] = amountSats

    db.newVinDetail(txid, json.dumps(inputs), int(time.time()))
    return inputs


def getAddrHist(txids, fromIdx, toIdx):
    txHistory = []
    txids.reverse()
    
    if fromIdx < 0:
        fromIdx = 0
    
    if toIdx > len(txids):
        toIdx = len(txids)

    if fromIdx > len(txids):
        fromIdx = len(txids) - 1
    
    if (toIdx - fromIdx) > 50:
        toIdx = fromIdx + 50
    
    if fromIdx > toIdx:
        toIdx = fromIdx + 10

    currHeight = callrpc(PORT, "getblockcount") + 1

    for txid in txids[fromIdx:toIdx]:
        tx = lvldb.get(bytes(txid, 'utf-8'))
        if tx:
            tx = json.loads(tx)   
            isCache = True
        else:
            isCache = False
            tx = callrpc(PORT, "getrawtransaction", [txid, True]) 
        
        if 'addr' not in tx['vin'][0]:
            isCoinStake = True if unhexlify(tx['hex'])[1] == 0x02 else False
            tx['isCoinStake'] = isCoinStake
            if isCoinStake:
                rewardDetails = callrpc(PORT, "getblockreward", [int(tx['height'])])

                tx['reward'] = float(rewardDetails['blockreward'])
                tx['rewardSat'] = convertToSat(rewardDetails['blockreward'])

                if "gvrreward" in rewardDetails:
                    tx['isAGVR'] = True
                    tx['rewardAGVR'] = float(rewardDetails['gvrreward'])
                    tx['rewardAGVRSat'] = convertToSat(rewardDetails['gvrreward'])
                else:
                    tx['isAGVR'] = False
            detailedVin = getInputDetails(tx['vin'], txid)
            tx["vin"] = detailedVin
        
        if "confirmations" in tx:
            tx['confirmations'] = currHeight - tx['height']
        if not isCache:
            if "confirmations" in tx and tx['confirmations'] >= 100:
                if db.getVinDetail(txid):
                    db.removeVinDetail(txid)
                lvldb.put(bytes(txid, 'utf-8'), json.dumps(tx, indent=2).encode('utf-8'))
        del tx['hex']
        txHistory.append(tx)
    
    resp = {
        "totalItems": len(txids),
        "from": fromIdx,
        "to": toIdx,
        "items": txHistory
    }

    return resp


def removeBlank(addrLst):
    if addrLst[0] == '':
        addrLst = addrLst[1:]
    
    if addrLst[-1] == '':
        addrLst = addrLst[:-1]
    
    return addrLst

def convertFromSat(value):
        sat_readable = value / 10**8
        return sat_readable

def convertToSat(value):
    sat_readable = value * 10**8
    return round(sat_readable)


@app.on('my event')
async def test_message(message):
    await app.emit('my response', {'data': message['data']})


@app.on('my broadcast event')
async def test_message(message):
    await app.emit('my response', {'data': message['data']}, broadcast=True)


@app.on('connect')
async def test_connect(sid, environ):
    await app.emit('', {'data': 'Connected'})

@app.on('disconnect')
async def test_disconnect(sid):
    print('Client disconnected')



@app.on('join')
async def on_join(sid, data):
    username = data['username']
    room = data['room']
    app.enter_room(sid, room)
    
    # await app.emit("server_response", f'{username} has entered the room. {room}', room=room, to=sid)


@app.on('leave')
async def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)


@app.on('client_message')
async def handle_client_message(message):
    print('Received message from client:', message)
    
    if "txid" in message:
        await app.emit('server_response', getTx(message['txid'], standalone=True))
        return
    
    # Send a response back to the client
    await app.emit('server_response', {'data': 'Response from server'})


async def newTx(msg):
    await app.emit("room_message", msg, room="tx")
    

@app._quart_app.before_serving
async def startup():
    loop = asyncio.get_event_loop()
    daemon = ZMQHandler(PORT, loop, app)
    app._quart_app.add_background_task(daemon.start())
    
@app._quart_app.after_serving
async def shutdown():
    app.smtp_server.close()

def requestUpnp():
    import miniupnpc

    upnp = miniupnpc.UPnP()

    upnp.discoverdelay = 200
    upnp.discover()
    upnp.selectigd()
    port = 52555

    # addportmapping(external-port, protocol, internal-host, internal-port, description, remote-host)
    try:
        upnp.addportmapping(port, 'TCP', upnp.lanaddr, 3001, 'Sheltr Servr', '')
    except Exception as e:
        print(e)


def vinDetailCleanup():
    while True:
        vinDetail = db.getAllVinDetail()
        for item in vinDetail:
            tx = callrpc(PORT, "getrawtransaction", [item[0], True])
            if "confirmations" in tx and tx['confirmations'] > 100:
                if not lvldb.get(bytes(item[0], "utf-8")):
                    currHeight = callrpc(PORT, "getblockcount") + 1
                    isCoinStake = True if unhexlify(tx['hex'])[1] == 0x02 else False
                    tx['isCoinStake'] = isCoinStake
                    if isCoinStake:
                        rewardDetails = callrpc(PORT, "getblockreward", [int(tx['height'])])

                        tx['reward'] = float(rewardDetails['blockreward'])
                        tx['rewardSat'] = convertToSat(rewardDetails['blockreward'])

                        if "gvrreward" in rewardDetails:
                            tx['isAGVR'] = True
                            tx['rewardAGVR'] = float(rewardDetails['gvrreward'])
                            tx['rewardAGVRSat'] = convertToSat(rewardDetails['gvrreward'])
                        else:
                            tx['isAGVR'] = False
                    detailedVin = getInputDetails(tx['vin'], item[0])
                    tx["vin"] = detailedVin
                    
                    tx['confirmations'] = currHeight - tx['height']
                    lvldb.put(bytes(item[0], 'utf-8'), json.dumps(tx, indent=2).encode('utf-8'))
                
                db.removeVinDetail(item[0])
        
        time.sleep(300)


if __name__ == '__main__':
    # requestUpnp()
    t = Thread(target=vinDetailCleanup, daemon=True)
    t.start()
    app.run("0.0.0.0", 52555)

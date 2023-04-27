#!/usr/bin/env python3
# Copyright (c) 2014-2018 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

"""
    ZMQ example using python3's asyncio

    Bitcoin should be started with the command line arguments:
        bitcoind -testnet -daemon \
                -zmqpubrawtx=tcp://127.0.0.1:28332 \
                -zmqpubrawblock=tcp://127.0.0.1:28332 \
                -zmqpubhashtx=tcp://127.0.0.1:28332 \
                -zmqpubhashblock=tcp://127.0.0.1:28332 \
                -zmqpubsequence=tcp://127.0.0.1:28332

    We use the asyncio library here.  `self.handle()` installs itself as a
    future at the end of the function.  Since it never returns with the event
    loop having an empty stack of futures, this creates an infinite loop.  An
    alternative is to wrap the contents of `handle` inside `while True`.

    A blocking example using python 2.7 can be obtained from the git history:
    https://github.com/bitcoin/bitcoin/blob/37a7fe9e440b83e2364d5498931253937abe9294/contrib/zmq/zmq_sub.py
"""

import binascii
import asyncio
import time

import zmq
import zmq.asyncio
import signal
import struct
import sys
import json
import socketio

from util import callrpc


if (sys.version_info.major, sys.version_info.minor) < (3, 5):
    print("This example only works with Python 3.5 and greater")
    sys.exit(1)

port = 28332

class ZMQHandler():
    def __init__(self, rpcPort, loop, app):
        self.loop = loop
        self.zmqContext = zmq.asyncio.Context()

        self.zmqSubSocket = self.zmqContext.socket(zmq.SUB)
        self.zmqSubSocket.setsockopt(zmq.RCVHWM, 0)
        self.zmqSubSocket.setsockopt_string(zmq.SUBSCRIBE, "hashblock")
        self.zmqSubSocket.setsockopt_string(zmq.SUBSCRIBE, "hashtx")
        self.zmqSubSocket.setsockopt_string(zmq.SUBSCRIBE, "rawblock")
        self.zmqSubSocket.setsockopt_string(zmq.SUBSCRIBE, "rawtx")
        self.zmqSubSocket.setsockopt_string(zmq.SUBSCRIBE, "sequence")
        self.zmqSubSocket.connect("tcp://127.0.0.1:%i" % port)
        self.rpcPort = rpcPort
        self.app = app

        self.sentTxInfo = []

    async def handle(self) :
        topic, body, seq = await self.zmqSubSocket.recv_multipart()
        sequence = "Unknown"
        if len(seq) == 4:
            sequence = str(struct.unpack('<I', seq)[-1])
        if topic == b"hashblock":
            pass
        elif topic == b"hashtx":
            pass
        elif topic == b"rawblock":
            pass
        elif topic == b"rawtx":
            try:
                await self.processTx(binascii.hexlify(body).decode("utf-8"), body[1] == 0x02)
            except Exception as e:
                print(e)

        # schedule ourselves to receive the next message
        asyncio.ensure_future(self.handle())

    async def processTx(self, rawTx, isCoinStake):
        decodeTx = callrpc(self.rpcPort, "decoderawtransaction", [rawTx])
        
        if decodeTx['txid'] in self.sentTxInfo:
            self.sentTxInfo.remove(decodeTx['txid'])
            
            return
        
        inputs = await self.getInputs(decodeTx['vin'])
        outputs = {
            "addrs": {},
            "outputAmount": 0
        }

        for txOut in decodeTx['vout']:
            if "type" in txOut and txOut['type'] in ["blind", "anon"]:
                if "anon" in inputs['addrs']:
                    continue
                else:
                    outputs['addrs']['anon'] = 0
                    continue
            elif "type" in txOut and txOut['type'] in ["data"]:
                continue

            addr = txOut['scriptPubKey']['addresses'][0]

            if addr in outputs['addrs']:
                outputs['addrs'][addr] += txOut['value']
            else:
                outputs['addrs'][addr] = txOut['value']

            outputs['outputAmount'] += txOut['value']

        txInfo = {
            "txid": decodeTx['txid'],
            "time": int(time.time()),
            "inputs": inputs['addrs'],
            "outputs": outputs['addrs'],
            "totalTxValue": outputs['outputAmount'] - inputs['inputAmount'],
            "isCoinStake": isCoinStake
        }

        await self.app.emit('room_message', txInfo, room="tx")

        if not isCoinStake:
            self.sentTxInfo.append(decodeTx['txid'])

    async def getInputs(self, vin):
        inputs = {
            "addrs": {},
            "inputAmount": 0
        }

        for txIn in vin:
            if "type" in txIn and txIn['type'] in ["blind", "anon"]:
                if "anon" in inputs['addrs']:
                    continue
                else:
                    inputs['addrs']['anon'] = 0
                    continue
            utxo = callrpc(self.rpcPort, "getrawtransaction", [txIn['txid'], True])["vout"][txIn['vout']]

            addr = utxo['scriptPubKey']['addresses'][0]

            if addr in inputs['addrs']:
                if "value" in utxo:
                    inputs['addrs'][addr] += utxo['value']
                    inputs['inputAmount'] += utxo['value']
            else:
                if "value" in utxo:
                    inputs['addrs'][addr] = utxo['value']
                    inputs['inputAmount'] += utxo['value']

        return inputs

    async def cleanUpTxid(self):

        while True:

            for txid in self.sentTxInfo.copy():
                
                try:
                    tx = callrpc(self.rpcPort, "getrawtransaction", [txid, True])

                    if "confirmations" in tx and (tx['confirmations'] < 0 or tx['confirmations'] > 0):
                        self.sentTxInfo.remove(txid)
                except:
                    self.sentTxInfo.remove(txid)
                    
            await asyncio.sleep(600)

    def start(self):
        #self.loop.add_signal_handler(signal.SIGINT, self.stop)
        self.loop.create_task(self.handle())
        self.loop.create_task(self.cleanUpTxid())

    def stop(self):
        self.loop.stop()
        self.zmqContext.destroy()


if __name__ == "__main__":
    daemon = ZMQHandler()
    daemon.start()

from util import callrpc
from binascii import unhexlify
import json, time
import random
import asyncio

from database import AsyncLvldb

PORT = 51725



class PreCache:
    def __init__(self, lvldb):
        self.lvldb = lvldb

    async def getInputDetails(self, inputs, txid):

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
                inTX = await self.lvldb.get(bytes(vin['txid'], "utf-8"))
                if not inTX:
                    inTX = await callrpc(PORT, "getrawtransaction", [vin['txid'], True])
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

        return inputs


    async def itterBlocks(self):

        bestBlock = await self.lvldb.get(b"bestBlock")
        currHeight = await callrpc(PORT, "getblockcount") + 1
        start = time.time()
        
        for i in range(int(bestBlock) if bestBlock else 1, currHeight):
            
            blockHash = await callrpc(PORT, "getblockhash", [i])

            block = await callrpc(PORT, "getblock", [blockHash, 2])
            

            for tx in block['tx']:
                if await self.lvldb.get(bytes(tx['txid'], 'utf-8')):
                    continue

                isCoinStake = True if unhexlify(tx['hex'])[1] == 0x02 else False
                tx['isCoinStake'] = isCoinStake
                if isCoinStake:
                    rewardDetails = await callrpc(PORT, "getblockreward", [int(block['height'])])

                    tx['reward'] = float(rewardDetails['blockreward'])
                    tx['rewardSat'] = convertToSat(rewardDetails['blockreward'])

                    if "gvrreward" in rewardDetails and rewardDetails['blockreward'] > 0:
                        tx['isAGVR'] = True
                        tx['rewardAGVR'] = float(rewardDetails['gvrreward'])
                        tx['rewardAGVRSat'] = convertToSat(rewardDetails['gvrreward'])
                    else:
                        tx['isAGVR'] = False
                
                tx["blockhash"] = block['hash']
                tx["height"] = block['height']
                tx["confirmations"] = block['confirmations']
                tx["time"] = block['time']
                tx["blocktime"] = block['time']

                tx['vin'] = await self.getInputDetails(tx['vin'], tx['txid'])

                if block['confirmations'] >= 100:
                    await self.lvldb.put(bytes(tx['txid'], 'utf-8'), json.dumps(tx, indent=2).encode('utf-8'))
            
            if (i % 1_000) == 0:
                print(f"{i} Blocks processed in {time.time() - start} seconds")
                start = time.time()
            await self.lvldb.put(b"bestBlock", bytes(str(i), 'utf-8'))

def convertFromSat(value):
        sat_readable = value / 10**8
        return sat_readable

def convertToSat(value):
    sat_readable = value * 10**8
    return round(sat_readable)

async def main():
    lvldb = AsyncLvldb()
    pre_cache = PreCache(lvldb)
    await pre_cache.itterBlocks()
    
if __name__ == '__main__':
    asyncio.run(main())



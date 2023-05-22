import asyncio
import json
from web3 import Web3, AsyncWeb3, AsyncHTTPProvider
from web3.middleware import async_geth_poa_middleware
from eth_account.messages import encode_defunct
import secrets


class EvmUtils:
    """Class that sets up the RPC connection to the EVM"""

    def __init__(self):
        self.url = "https://endpoints.omniatech.io/v1/matic/mumbai/2e801aa53f7e4c049c329ca905671c69"
        self.w3 = AsyncWeb3(AsyncHTTPProvider(self.url))
        self.w3.middleware_onion.inject(async_geth_poa_middleware, layer=0)
        self.solidity_keccak = Web3.solidity_keccak


class WghostUtils(EvmUtils):
    """Set of utilities for interaction with wghsot."""

    def __init__(self):
        super().__init__()
        with open("abi.json", "r", encoding="utf-8") as abi_file:
            self.abi = json.load(abi_file)
        self.token_address = "0x06514C2321A5235871e460e5a361F29AEeCe70Cc"
        self.contract = self.w3.eth.contract(address=self.token_address, abi=self.abi)
        self.func = self.contract.functions

        self.burn_filter = None

    async def get_token_info(self):
        """Returns basic toking information."""
        info = {
            "name": await self.func.name().call(),
            "symbol": await self.func.symbol().call(),
            "decimals": (dec := await self.func.decimals().call()),
            "totalSupply": await self.get_total_supply() / 10**dec,
            "owner": (owner := await self.func.owner().call()),
            "balanceOfOwner": await self.get_balance(owner) / 10**dec,
        }
        # print(info)
        return info

    async def get_paused(self):
        """Returns if contract is paused"""
        return await self.func.paused().call()

    async def get_total_supply(self):
        """Retruns the total supply of the Contract."""
        return await self.func.totalSupply().call()

    async def get_balance(self, address):
        """Returns token balance of given address."""
        return await self.func.balanceOf(address).call()

    async def get_burn_filter(self):
        """Sets the burn filter is none is set."""
        if not self.burn_filter or self.burn_filter.stopped:
            burn_filter = await self.contract.events.WGhostBurnt.create_filter(
                fromBlock=35181092
            )
            self.burn_filter = burn_filter

    async def get_new_burn(self):
        """Gets Burn events since last event check."""
        await self.get_burn_filter()

        # events = await self.contract.events.Transfer.get_logs(fromBlock=35181092)
        # print(events)
        try:
            resp = await self.burn_filter.get_new_entries()
        except:
            self.burn_filter = None
            await self.get_burn_filter()
            resp = await self.burn_filter.get_new_entries()

        thing = {
            "height": 745120,
            "lock_addr_balance": 1234123345724234,
            "txid": "5d6580b867b3b58ba8dde3e794fe92c449d4bcc5f8f4d7a774f4bfd9b2817222",
            "mint_amount": 69420,
            "address": "0x3C02AC46a959fE8aA00c59dC67affe43dc6d527d",
            "timestamp": 12345678,
        }

        print(
            self.w3.to_hex(
                self.solidity_keccak(
                    ["address", "uint256", "uint32", "uint256", "string", "uint256"],
                    [
                        thing["address"],
                        thing["mint_amount"],
                        thing["height"],
                        thing["lock_addr_balance"],
                        thing["txid"],
                        thing["timestamp"],
                    ],
                )
            )
        )

        return resp

    async def get_burn(self):
        """Async background task to get burn events."""
        while True:
            results = await self.get_new_burn()

            if results:
                for i in results:
                    print(f"{i['args']['ghostAddr']}: {i['args']['amount']}")
            else:
                print("no new events")

            print(await self.get_balance("0x3C02AC46a959fE8aA00c59dC67affe43dc6d527d"))
            print(await self.w3.eth.chain_id)

            await asyncio.sleep(10)

    async def sign_message(self, acct):
        # acct = self.w3.eth.account.from_key(
        #    "0x503f38a9c967ed597e47fe25643985f032b072db8075426a92110f82df48dfcb"
        # )

        msg = "0xdac013729686e7f7cdf7e51f360232e66500278a6ea36c39b9b44c5a01519d1d"

        hashthing = self.solidity_keccak(["bytes32"], [msg])
        print(f"the hash thing {self.w3.to_hex(hashthing)}")

        message = encode_defunct(hexstr=msg)

        signed_message = self.w3.eth.account.sign_message(message, private_key=acct.key)

        print(signed_message)

        ec_recover_args = (msghash, v, r, s) = (
            self.w3.to_hex(signed_message.messageHash),
            signed_message.v,
            self.to_32byte_hex(signed_message.r),
            self.to_32byte_hex(signed_message.s),
        )

        print(ec_recover_args)
        print(acct.address)

    def to_32byte_hex(self, val):
        return self.w3.to_hex(self.w3.to_bytes(val).rjust(32, b"\0"))

    async def transfer_wghost(self):
        acct = self.w3.eth.account.from_key(
            "0x61ba05a1a3d8c4eccb0a48b6201bf065943f80947831975929153ab3162a2faa"
        )
        print(acct.address)
        est_gas = await self.contract.functions.transfer(
            "0x9Cce462D03c81bEB1b793093d44DcA51C4A88262", 12
        ).estimate_gas({"from": acct.address})

        nonce = await self.w3.eth.get_transaction_count(
            "0x3C02AC46a959fE8aA00c59dC67affe43dc6d527d"
        )

        wghost_tx = await self.contract.functions.transfer(
            "0x9Cce462D03c81bEB1b793093d44DcA51C4A88262", 12
        ).build_transaction(
            {
                "chainId": await self.w3.eth.chain_id,
                "gas": est_gas,
                "gasPrice": self.w3.to_wei("2", "gwei"),
                "nonce": nonce,
            }
        )

        print(wghost_tx)

        signed = acct.sign_transaction(wghost_tx)

        print(signed)
        print(self.w3.to_hex(self.w3.keccak(signed.rawTransaction)))

        print(
            self.w3.to_hex(
                await self.w3.eth.send_raw_transaction(signed.rawTransaction)
            )
        )

    async def create_account_from_key(self):
        priv = secrets.token_hex(32)
        private_key = "0x" + priv
        print("SAVE BUT DO NOT SHARE THIS:", private_key)
        acct = self.w3.eth.account.from_key(private_key)
        print("Address:", acct.address)

    async def create_account_from_mnemonic(self, mnemonic, index=0):
        self.w3.eth.account.enable_unaudited_hdwallet_features()
        account = self.w3.eth.account.from_mnemonic(
            mnemonic,
            account_path=f"m/44'/60'/0'/0/{index}",
        )

        return account


class MaticUtils(EvmUtils):
    """Set of utilities for interaction with matic."""

    async def get_best_matic_block(self):
        """returns best matic block"""
        return await self.w3.eth.block_number

    async def get_balance(self, address):
        """Returns matic balance for given address"""
        balance = await self.w3.eth.get_balance(address)
        return self.w3.from_wei(balance, "ether")


async def main():
    """Sets up the main function"""
    info = await wghost_util.get_token_info()
    print("Token info: ")
    print(info)

    print(await matic_util.get_best_matic_block())

    print(await wghost_util.get_paused())
    # await wghost_util.get_burn()
    # await wghost_util.transfer_wghost()
    acct = await wghost_util.create_account_from_mnemonic(
        "orbit salad flip high pool off clip dinner butter adjust caught case", 0
    )

    print(acct.address)

    await wghost_util.sign_message(acct)


if __name__ == "__main__":
    wghost_util = WghostUtils()
    matic_util = MaticUtils()
    asyncio.run(main())

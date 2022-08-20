#!/usr/bin/env python3
from pyteal import *
from beaker import *
import os
import json
from typing import Final

ARGS = Txn.application_args

# Global Bytes (4)
OWNER = Bytes("owner")
ROYALTY_ADDR = Bytes("royaltyAddress")
HIGHEST_BIDDER = Bytes("highestBidder")
METADATA = Bytes("metadata")

# Global Ints (7)
AUCTION_END = Bytes("auctionEnd")
SALE_PRICE = Bytes("salePrice")
HIGHEST_BID = Bytes("highestBid")
ROYALTY_PERCENT = Bytes("royaltyPercent")
ALLOW_TRANSFER = Bytes("allowTransfer")
ALLOW_SALE = Bytes("allowSale")
ALLOW_AUCTION = Bytes("allowAuction")
ASA_ID = Bytes("asaID")


def set(key, value):
    if type(value) == str:
        value = Bytes(value)
    elif type(value) == int:
        value = Int(value)

    return App.globalPut(key, value)


def get(key):
    return App.globalGet(key)

class MyApp(Application):
    owner: Final[ApplicationStateValue] = ApplicationStateValue(stack_type=TealType.bytes)
    royalty_address: Final[ApplicationStateValue] = ApplicationStateValue(stack_type=TealType.bytes, key=ROYALTY_ADDR)
    highest_bidder: Final[ApplicationStateValue] = ApplicationStateValue(stack_type=TealType.bytes, key=HIGHEST_BIDDER)
    metadata: Final[ApplicationStateValue] = ApplicationStateValue(stack_type=TealType.bytes)

    auction_end: Final[ApplicationStateValue] = ApplicationStateValue(stack_type=TealType.uint64, key=AUCTION_END)
    sale_price: Final[ApplicationStateValue] = ApplicationStateValue(stack_type=TealType.uint64, key=SALE_PRICE)
    highest_bid: Final[ApplicationStateValue] = ApplicationStateValue(stack_type=TealType.uint64, key=HIGHEST_BID)
    royalty_percent: Final[ApplicationStateValue] = ApplicationStateValue(stack_type=TealType.uint64, key=ROYALTY_PERCENT)
    allow_transfer: Final[ApplicationStateValue] = ApplicationStateValue(stack_type=TealType.uint64, key=ALLOW_TRANSFER)
    allow_sale: Final[ApplicationStateValue] = ApplicationStateValue(stack_type=TealType.uint64, key=ALLOW_SALE)
    allow_auction: Final[ApplicationStateValue] = ApplicationStateValue(stack_type=TealType.uint64, key=ALLOW_AUCTION)
    asa_id: Final[ApplicationStateValue] = ApplicationStateValue(stack_type=TealType.uint64, key=ASA_ID)

    @internal(TealType.none)
    def clawback_asa(self):
        asa_id = get(ASA_ID)
        highest_bidder = get(HIGHEST_BIDDER)

        clawback_txn = Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.receiver: Global.current_application_address(),
                    TxnField.amount: Int(1),
                    TxnField.asset_sender: highest_bidder,
                    TxnField.xfer_asset: asa_id,
                }
            ),
        )

        clawback_seq = Seq(
            contract_holding := AssetHolding.balance(highest_bidder, asa_id),
            If(contract_holding.value(), clawback_txn),
        )

        return If(asa_id != Int(0), clawback_seq)


    @external
    def claim_asa(self):
        asa_id = get(ASA_ID)
        owner = get(OWNER)

        return Seq(
            Assert(asa_id),
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.receiver: owner,
                    TxnField.amount: Int(1),
                    TxnField.asset_sender: Global.current_application_address(),
                    TxnField.xfer_asset: asa_id,
                }
            ),
        )


    @create
    def create():
        return Approve()

    @external(authorize=Authorize.only(Global.creator_address()))
    def initialize(self, 
        royalty_addr: abi.Address, 
        royalty_percent: abi.Uint64,
        metadata: abi.String,
        allow_transfer: abi.Bool,
        allow_sale: abi.Bool,
        allow_auction: abi.Bool,
        asa_id: abi.Uint64
    ):
        return Seq(
            # Set global bytes
            set(ROYALTY_ADDR, royalty_addr.get()),
            set(OWNER, Txn.sender()),
            set(HIGHEST_BIDDER, ""),
            set(METADATA, metadata.get()),
            # Set global ints
            set(ROYALTY_PERCENT, royalty_percent.get()),
            set(AUCTION_END, 0),
            set(ALLOW_TRANSFER, allow_transfer.get()),
            set(ALLOW_SALE, allow_sale.get()),
            set(ALLOW_AUCTION, allow_auction.get()),
            set(SALE_PRICE, 0),
            set(HIGHEST_BID, 0),
            set(ASA_ID, asa_id.get()),
        )


    @external
    def buy(self):
        royalty_payment = Gtxn[Txn.group_index() + Int(2)]
        payment = Gtxn[Txn.group_index() + Int(1)]

        sale_price = get(SALE_PRICE)
        royalty_percent = get(ROYALTY_PERCENT)
        royalty_address = get(ROYALTY_ADDR)
        owner = get(OWNER)

        royalty_amt = sale_price * royalty_percent / Int(100)
        purchase_amt = sale_price - royalty_amt

        return Seq(
            Assert(sale_price > Int(0)),
            # Verify senders are all the same
            Assert(royalty_payment.sender() == payment.sender()),
            Assert(Txn.sender() == payment.sender()),
            # Verify receivers are correct
            Assert(royalty_payment.receiver() == royalty_address),
            Assert(payment.receiver() == owner),
            # Verify amounts are correct
            Assert(royalty_payment.amount() == royalty_amt),
            Assert(payment.amount() == purchase_amt),
            # Update global state
            set(OWNER, Txn.sender()),
            set(SALE_PRICE, 0),
            self.clawback_asa(),
        )


    @external
    def start_sale(self, price: abi.Uint64):
        allow_sale = get(ALLOW_SALE)
        owner = get(OWNER)
        auction_end = get(AUCTION_END)

        return Seq(
            Assert(allow_sale),
            Assert(auction_end == Int(0)),
            Assert(Txn.sender() == owner),
            set(SALE_PRICE, price.get()),
        )


    @external
    def end_sale():
        owner = get(OWNER)

        return Seq(Assert(Txn.sender() == owner), set(SALE_PRICE, 0))


    @external
    def transfer(self, receiver: abi.Address):
        allow_transfer = get(ALLOW_TRANSFER)
        owner = get(OWNER)
        auction_end = get(AUCTION_END)

        return Seq(
            Assert(allow_transfer),
            Assert(auction_end == Int(0)),
            Assert(Txn.sender() == owner),
            set(OWNER, receiver.get()),
            self.clawback_asa(),
        )


    @external
    def start_auction(self, starting_price: abi.Uint64, length: abi.Uint64):
        payment = Gtxn[Txn.group_index() + Int(1)]

        allow_auction = get(ALLOW_AUCTION)

        return Seq(
            Assert(allow_auction),
            # Verify payment txn
            Assert(payment.receiver() == Global.current_application_address()),
            Assert(payment.amount() == Int(100_000)),
            # Set global state
            set(AUCTION_END, Global.latest_timestamp() + length.get()),
            set(HIGHEST_BID, starting_price.get()),
        )


    @internal(TealType.none)
    def pay(self, receiver: Expr, amount: Expr):
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.receiver: receiver,
                    TxnField.amount: amount - Global.min_txn_fee(),
                }
            ),
            InnerTxnBuilder.Submit(),
        )


    @external
    def end_auction(self):
        auction_end = get(AUCTION_END)
        highest_bid = get(HIGHEST_BID)
        royalty_percent = get(ROYALTY_PERCENT)
        royalty_amount = highest_bid * royalty_percent / Int(100)
        royalty_address = get(ROYALTY_ADDR)
        owner = get(OWNER)
        highest_bidder = get(HIGHEST_BIDDER)

        return Seq(
            Assert(Global.latest_timestamp() > auction_end),
            # Pay royalty address and owner
            self.pay(royalty_address, royalty_amount),
            self.pay(owner, highest_bid - royalty_amount),
            # Set global state
            set(AUCTION_END, 0),
            set(OWNER, highest_bidder),
            set(HIGHEST_BIDDER, ""),
            self.clawback_asa(),
        )


    @external
    def bid(self):
        payment = Gtxn[Txn.group_index() + Int(1)]

        auction_end = get(AUCTION_END)
        highest_bidder = get(HIGHEST_BIDDER)
        highest_bid = get(HIGHEST_BID)

        return Seq(
            Assert(Global.latest_timestamp() < auction_end),
            # Verify payment transaction
            Assert(payment.amount() > highest_bid),
            Assert(Txn.sender() == payment.sender()),
            # Return previous bid
            If(highest_bidder != Bytes(""), self.pay(highest_bidder, highest_bid)),
            # Set global state
            set(HIGHEST_BID, payment.amount()),
            set(HIGHEST_BIDDER, payment.sender()),
        )


if __name__ == "__main__":
    app = MyApp()

    if os.path.exists("approval.teal"):
        os.remove("approval.teal")

    if os.path.exists("approval.teal"):
        os.remove("clear.teal")

    if os.path.exists("abi.json"):
        os.remove("abi.json")

    with open("approval.teal", "w") as f:
        f.write(app.approval_program)

    with open("clear.teal", "w") as f:
        f.write(app.clear_program)

    with open("abi.json", "w") as f:
        f.write(json.dumps(app.contract.dictify(), indent=4))

acct = sandbox.get_accounts().pop()

app_client = client.ApplicationClient(
    client=sandbox.get_algod_client(), 
    app=MyApp(version=6), 
    signer=acct.signer
)

app_client.create()
app_client.call(
    MyApp.initialize,
    royalty_addr = acct.address, 
    royalty_percent = 10,
    metadata = "Hello World",
    allow_transfer = True,
    allow_sale = True,
    allow_auction = True,
    asa_id = 0
    )

print(app_client.get_application_state())

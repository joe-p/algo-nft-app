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
        asa_id = self.asa_id.get()
        highest_bidder = self.highest_bidder.get()

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
        asa_id = self.asa_id.get()
        owner = self.owner.get()

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
            self.royalty_address.set(royalty_addr.get()),
            self.owner.set(Txn.sender()),
            self.highest_bidder.set(Bytes("")),
            self.metadata.set(metadata.get()),
            self.royalty_percent.set(royalty_percent.get()),
            self.auction_end.set(Int(0)),
            self.allow_transfer.set(allow_transfer.get()),
            self.allow_sale.set(allow_sale.get()),
            self.allow_auction.set(allow_auction.get()),
            self.sale_price.set(Int(0)),
            self.highest_bid.set(Int(0)),
            self.asa_id.set(asa_id.get()),
        )


    @external
    def buy(self):
        royalty_payment = Gtxn[Txn.group_index() + Int(2)]
        payment = Gtxn[Txn.group_index() + Int(1)]

        sale_price = self.sale_price.get()
        royalty_percent = self.royalty_percent.get()
        royalty_address = self.royalty_address.get()
        owner = self.owner.get()

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
            self.owner.set(Txn.sender()),
            self.sale_price.set(Int(0)),
            self.clawback_asa(),
        )


    @external
    def start_sale(self, price: abi.Uint64):
        allow_sale = self.allow_sale.get()
        owner = self.owner.get()
        auction_end = self.auction_end.get()

        return Seq(
            Assert(allow_sale),
            Assert(auction_end == Int(0)),
            Assert(Txn.sender() == owner),
            self.sale_price.set(price.get()),
        )


    @external
    def end_sale(self):
        owner = self.owner.get()

        return Seq(Assert(Txn.sender() == owner), self.sale_price.set(Int(0)))


    @external
    def transfer(self, receiver: abi.Address):
        allow_transfer = self.allow_transfer.get()
        owner = self.owner.get()
        auction_end = self.auction_end.get()

        return Seq(
            Assert(allow_transfer),
            Assert(auction_end == Int(0)),
            Assert(Txn.sender() == owner),
            self.owner.set(receiver.get()),
            self.clawback_asa(),
        )


    @external
    def start_auction(self, starting_price: abi.Uint64, length: abi.Uint64):
        payment = Gtxn[Txn.group_index() + Int(1)]

        allow_auction = self.allow_auction.get()

        return Seq(
            Assert(allow_auction),
            # Verify payment txn
            Assert(payment.receiver() == Global.current_application_address()),
            Assert(payment.amount() == Int(100_000)),
            # Set global state
            self.auction_end.set(Global.latest_timestamp() + length.get()),
            self.highest_bid.set(starting_price.get()),
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
        auction_end = self.auction_end.get()
        highest_bid = self.highest_bid.get()
        royalty_percent = self.royalty_percent.get()
        royalty_amount = highest_bid * royalty_percent / Int(100)
        royalty_address = self.royalty_address.get()
        owner = self.owner.get()
        highest_bidder = self.highest_bidder.get()

        return Seq(
            Assert(Global.latest_timestamp() > auction_end),
            # Pay royalty address and owner
            self.pay(royalty_address, royalty_amount),
            self.pay(owner, highest_bid - royalty_amount),
            # Set global state
            self.auction_end.set(Int(0)),
            self.owner.set(highest_bidder),
            self.highest_bidder.set(Bytes("")),
            self.clawback_asa(),
        )


    @external
    def bid(self):
        payment = Gtxn[Txn.group_index() + Int(1)]

        auction_end = self.auction_end.get()
        highest_bidder = self.highest_bidder.get()
        highest_bid = self.highest_bid.get()

        return Seq(
            Assert(Global.latest_timestamp() < auction_end),
            # Verify payment transaction
            Assert(payment.amount() > highest_bid),
            Assert(Txn.sender() == payment.sender()),
            # Return previous bid
            If(highest_bidder != Bytes(""), self.pay(highest_bidder, highest_bid)),
            # Set global state
            self.highest_bid.set(payment.amount()),
            self.highest_bidder.set(payment.sender()),
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

#!/usr/bin/env python3
from pyteal import *
import os

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


@Subroutine(TealType.none)
def clawback_asa():
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


def claim_asa():
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
        Approve(),
    )


def init():
    royalty_addr = ARGS[0]
    royalty_percent = Btoi(ARGS[1])
    metadata = ARGS[2]
    allow_transfer = Btoi(ARGS[3])
    allow_sale = Btoi(ARGS[4])
    allow_auction = Btoi(ARGS[5])
    asa_id = Btoi(ARGS[6])

    return Seq(
        # Set global bytes
        set(ROYALTY_ADDR, royalty_addr),
        set(OWNER, Txn.sender()),
        set(HIGHEST_BIDDER, ""),
        set(METADATA, metadata),
        # Set global ints
        set(ROYALTY_PERCENT, royalty_percent),
        set(AUCTION_END, 0),
        set(ALLOW_TRANSFER, allow_transfer),
        set(ALLOW_SALE, allow_sale),
        set(ALLOW_AUCTION, allow_auction),
        set(SALE_PRICE, 0),
        set(HIGHEST_BID, 0),
        set(ASA_ID, asa_id),
        Approve(),
    )


def buy():
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
        clawback_asa(),
        Approve(),
    )


def start_sale():
    price = Btoi(ARGS[1])

    allow_sale = get(ALLOW_SALE)
    owner = get(OWNER)

    return Seq(
        Assert(allow_sale),
        Assert(Txn.sender() == owner),
        set(SALE_PRICE, price),
        Approve(),
    )


def end_sale():
    owner = get(OWNER)

    return Seq(Assert(Txn.sender() == owner), set(SALE_PRICE, 0), Approve())


def transfer():
    receiver = ARGS[1]

    allow_transfer = get(ALLOW_TRANSFER)
    owner = get(OWNER)

    return Seq(
        Assert(allow_transfer),
        Assert(Txn.sender() == owner),
        set(OWNER, receiver),
        clawback_asa(),
        Approve(),
    )


def start_auction():
    payment = Gtxn[Txn.group_index() + Int(1)]

    starting_price = Btoi(ARGS[1])
    length = Btoi(ARGS[2])

    allow_auction = get(ALLOW_AUCTION)

    return Seq(
        Assert(allow_auction),
        # Verify payment txn
        Assert(payment.receiver() == Global.current_application_address()),
        Assert(payment.amount() == Int(100_000)),
        # Set global state
        set(AUCTION_END, Global.latest_timestamp() + length),
        set(HIGHEST_BID, starting_price),
        Approve(),
    )


def pay(receiver, amount):
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


def end_auction():
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
        pay(royalty_address, royalty_amount),
        pay(owner, highest_bid - royalty_amount),
        # Set global state
        set(AUCTION_END, 0),
        set(OWNER, highest_bidder),
        set(HIGHEST_BIDDER, ""),
        clawback_asa(),
        Approve(),
    )


def bid():
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
        If(highest_bidder != Bytes(""), pay(highest_bidder, highest_bid)),
        # Set global state
        set(HIGHEST_BID, payment.amount()),
        set(HIGHEST_BIDDER, payment.sender()),
        Approve(),
    )


def approval():
    fcn = ARGS[0]

    return Cond(
        [Txn.application_id() == Int(0), init()],
        # Delete only for debugging sake
        # TODO: Implement delete function that requires input from owner and creator
        [Txn.on_completion() == OnComplete.DeleteApplication, Approve()],
        [fcn == Bytes("start_auction"), start_auction()],
        [fcn == Bytes("start_sale"), start_sale()],
        [fcn == Bytes("end_sale"), start_sale()],
        [fcn == Bytes("bid"), bid()],
        [fcn == Bytes("end_auction"), end_auction()],
        [fcn == Bytes("transfer"), transfer()],
        [fcn == Bytes("buy"), buy()],
        [fcn == Bytes("claim_asa"), claim_asa()],
    )


def clear():
    return Approve()


if __name__ == "__main__":
    if os.path.exists("approval.teal"):
        os.remove("approval.teal")

    if os.path.exists("approval.teal"):
        os.remove("clear.teal")

    compiled_approval = compileTeal(approval(), mode=Mode.Application, version=5)

    with open("approval.teal", "w") as f:
        f.write(compiled_approval)

    compiled_clear = compileTeal(clear(), mode=Mode.Application, version=5)

    with open("clear.teal", "w") as f:
        f.write(compiled_clear)

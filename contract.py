#!/usr/bin/env python3
from pyteal import *
import os

ARGS = Txn.application_args
FEE = Int(1000)

# Global Bytes (4)
OWNER = Bytes("owner")
ROYALTY_ADDR = Bytes("royaltyAddress")
HIGHEST_BIDDER = Bytes("highestBidder")
METADATA = Bytes("metadata")

# Global Ints (5)
AUCTION_END = Bytes("auctionEnd")
TX_METHODS = Bytes("txMethods")
SALE_PRICE = Bytes("salePrice")
HIGHEST_BID = Bytes("highestBid")
ROYALTY_PERCENT = Bytes("royaltyPercent")

# TX_METHODS is a 3-bit bitmask for allowed ways to transfer ownership. 
# bit[2](MSB) = auction, bit[1] = sell, bit[0](LSB) = transfer

def set(key, value):
    if (type(value) == str):
        value = Bytes(value)
    elif(type(value) == int):
        value = Int(value)

    return App.globalPut(key, value)

def get(key):
    return App.globalGet(key)


def init():
    royalty_addr = ARGS[0]
    royalty_percent = Btoi(ARGS[1])
    metadata = ARGS[2]
    tx_methods = Btoi(ARGS[3]) # see comment on TX_METHODS for explanation

    return Seq(
        # Set global bytes
        set(ROYALTY_ADDR, royalty_addr), #b1
        set(OWNER, Txn.sender()), #b2
        set(HIGHEST_BIDDER, ""), #b3
        set(METADATA, metadata), #b4
        
        # Set global ints
        set(ROYALTY_PERCENT, royalty_percent), #i1
        set(AUCTION_END, Int(0)), #i2
        set(TX_METHODS, tx_methods), #i3
        set(SALE_PRICE, Int(0)), # i4
        set(HIGHEST_BID, Int(0)), # i5

        Approve()
    )

def buy():
    royalty_payment = Gtxn[2]
    payment = Gtxn[1]

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

        set(OWNER, Txn.sender()),
        set(SALE_PRICE, 0),
        Approve()
    )

def start_sale():
    price = Btoi(ARGS[1])

    tx_methods = get(TX_METHODS)
    owner = get(OWNER)
    
    return Seq(
        Assert(tx_methods & Int(2)), # TX_METHODS bit[1] is set
        Assert(Txn.sender() == owner),
        set(SALE_PRICE, price),
        Approve()
    )

def end_sale():
    owner = get(OWNER)

    return Seq(
        Assert(Txn.sender() == owner),
        set(SALE_PRICE, Int(0)),
        Approve()
    )

def transfer():
    receiver = ARGS[1]

    tx_methods = get(TX_METHODS)
    owner = get(OWNER)

    return Seq(
        Assert(tx_methods & Int(1)), # TX Methods bit[0] is set
        Assert(Txn.sender() == owner),
        set(OWNER, receiver),
        Approve()
    )

def start_auction():
    payment = Gtxn[1]

    starting_price = Btoi(ARGS[1])
    length = Btoi(ARGS[2])
    
    tx_methods = get(TX_METHODS)

    return Seq(
        Assert(tx_methods & Int(4) ), # TX Methods bit[2] is set
        Assert(payment.receiver() == Global.current_application_address()),
        Assert(payment.amount() == Int(100000)),
        set(AUCTION_END, Global.latest_timestamp() + length),
        set(HIGHEST_BID, starting_price),
        Approve()
    )

def pay(receiver, amount):
    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver: receiver,
            TxnField.amount: amount - FEE
        }),
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
        Assert( Global.latest_timestamp() > auction_end ),
        pay(royalty_address, royalty_amount),
        pay(owner, highest_bid - royalty_amount),
        set(AUCTION_END, Int(0)),
        set(OWNER, highest_bidder),
        set(HIGHEST_BIDDER, Bytes("")),
        Approve()
    )

def bid():
    payment = Gtxn[1]
    app_call = Gtxn[0]

    auction_end = get(AUCTION_END)
    highest_bidder = get(HIGHEST_BIDDER)
    highest_bid = get(HIGHEST_BID)

    return Seq(
        Assert(Global.latest_timestamp() < auction_end ),
        Assert(payment.amount() > highest_bid),
        Assert(app_call.sender() == payment.sender()),
        If( highest_bidder != Bytes(""), pay(highest_bidder, highest_bid) ),
        set(HIGHEST_BID, payment.amount()),
        set(HIGHEST_BIDDER, payment.sender()),
        Approve()
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
        [fcn == Bytes('transfer'), transfer()], 
        [fcn == Bytes('buy'), buy()]
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

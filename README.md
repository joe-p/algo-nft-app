This repository contains an algorand smart contract that acts as an NFT. 


# Global Storage

| Key             | Type    | Description                                                                           |
|-----------------|---------|---------------------------------------------------------------------------------------|
| owner           | Account | Owner of the NFT. This is the person that can initiate auctions, sales, or transfers. |
| royaltyAddress  | Account | Account that receives royalties from auctions and sales                               |
| royaltyPercent  | Integer | The percent the royalty address receives from sales and auctions                      |
| metadata        | Bytes   | Arbitrary metadata set by the creator of the NFT                                      |
| highestBidder   | Account | Account with the highest bid if an auction is taking place                            |
| highestBid      | Integer | The highest bid if an auction is taking place                                         |
| auctionEnd      | Integer | The end time for an ongoing auction                                                   |
| salePrice       | Integer | The price of the token if the owner is selling                                        |
| txMethods       | Integer | A bit mask indicating if the NFT can be auctioned, sold, and/or transferred           |

# Why not use ASA?
ASAs lack the programmability that is possible with smart contracts. The main goal I wanted to accomplish here was **on-chain** enforcement of royalties, which just isn't possible with ASAs. 

# Future Work

## Implement Security and Input Validation

Right now there is very little input validation and likely a lot of exploits. This should eventually be implemented before being used on mainnet.

## Implement a Controlled ASA
To conform with ARC3 standards, it would be useful to have the smart contract control an ASA that is associated with ownership of a contract. 

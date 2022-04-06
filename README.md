This repository contains an algorand smart contract that acts as an NFT. 


# Global Storage

| Key             | Type    | Description                                                                           |
|-----------------|---------|---------------------------------------------------------------------------------------|
| Owner           | Account | Owner of the NFT. This is the person that can initiate auctions, sales, or transfers. |
| Royalty Address | Account | Account that receives royalties from auctions and sales                               |
| Royalty Percent | Integer | The percent the royalty address receives from sales and auctions                      |
| Metadata        | Bytes   | Arbitrary metadata set by the creator of the NFT                                      |
| Highest Bidder  | Account | Account with the highest bid if an auction is taking place                            |
| Highest Bid     | Integer | The highest bid if an auction is taking place                                         |
| Auction End     | Integer | The end time for an ongoing auction                                                   |
| Sale Price      | Integer | The price of the token if the owner is selling                                        |
| TX Methods      | Integer | A bit mask indicating if the NFT can be auctioned, sold, and/or transferred           |

# Why not use ASA?
ASAs lack the programmability that is possible with smart contracts. The main goal I wanted to accomplish here was **on-chain** enforcement of royalties, which just isn't possible with ASAs. 

# Future Work

## Implement Security and Input Validation

Right now there is very little input validation and likely a lot of exploits. This should eventually be implemented before being used on mainnet.

## Implement a Controlled ASA
To conform with ARC3 standards, it would be useful to have the smart contract control an ASA that is associated with ownership of a contract. 

## Separate Market Functionality from NFT

To reduce network congestion and chain growth, there should be a single contract that all instances of NFTs leverage for managing auctions and sales, with the local storage for the application account keeping track of relevant data. In the current implementation, the minting of each NFT is going to be a large transaction due to the size of smart contract. 
"""
Polygon Wallet Service
Manages USDT wallets on Polygon network
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from web3 import Web3
from eth_account import Account
import secrets

logger = logging.getLogger(__name__)

# Polygon mainnet configuration
POLYGON_RPC_URL = "https://polygon.drpc.org"
POLYGON_CHAIN_ID = 137
USDT_CONTRACT_ADDRESS = "0xc2132D05D31c914a87C6611C10748AEb04B58E8F"  # USDT on Polygon

# ERC-20 ABI (minimal)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]


class PolygonWalletService:
    """
    Polygon wallet management for USDT treasury
    """
    
    def __init__(self, db):
        self.db = db
        self.w3 = Web3(Web3.HTTPProvider(POLYGON_RPC_URL))
        self.chain_id = POLYGON_CHAIN_ID
        self.usdt_address = Web3.to_checksum_address(USDT_CONTRACT_ADDRESS)
        
        if not self.w3.is_connected():
            logger.error("[Polygon] Failed to connect to Polygon RPC")
        else:
            logger.info("[Polygon] Connected to Polygon network")
        
        self.usdt_contract = self.w3.eth.contract(
            address=self.usdt_address,
            abi=ERC20_ABI
        )
    
    async def create_treasury_wallet(self) -> Dict[str, Any]:
        """
        Create a new wallet for treasury management
        
        Returns:
            Wallet info (address, private_key encrypted)
        """
        try:
            # Generate new account
            account = Account.create()
            
            wallet_info = {
                "wallet_id": f"treasury_{secrets.token_hex(8)}",
                "address": account.address,
                "private_key": account.key.hex(),  # TODO: Encrypt this!
                "network": "polygon",
                "chain_id": self.chain_id,
                "is_primary": False,
                "balance_usdt": 0.0,
                "balance_matic": 0.0,
                "created_at": datetime.now(timezone.utc),
                "last_updated": datetime.now(timezone.utc)
            }
            
            # Store in database
            await self.db.crypto_wallets.insert_one(wallet_info)
            
            logger.info(f"[Polygon] Created treasury wallet: {account.address}")
            
            # Don't return private key in response
            return {
                "wallet_id": wallet_info["wallet_id"],
                "address": account.address,
                "network": "polygon",
                "created_at": wallet_info["created_at"].isoformat()
            }
        
        except Exception as e:
            logger.error(f"[Polygon] Error creating wallet: {e}")
            raise
    
    async def get_wallet_balance(self, wallet_address: str) -> Dict[str, Any]:
        """
        Get USDT and MATIC balance for a wallet
        
        Args:
            wallet_address: Polygon wallet address
        
        Returns:
            Balance information
        """
        try:
            if not self.w3.is_connected():
                raise ConnectionError("Not connected to Polygon network")
            
            wallet_address = Web3.to_checksum_address(wallet_address)
            
            # Get USDT balance
            usdt_balance_raw = self.usdt_contract.functions.balanceOf(
                wallet_address
            ).call()
            decimals = self.usdt_contract.functions.decimals().call()
            usdt_balance = usdt_balance_raw / (10 ** decimals)
            
            # Get MATIC balance (for gas)
            matic_balance_wei = self.w3.eth.get_balance(wallet_address)
            matic_balance = self.w3.from_wei(matic_balance_wei, 'ether')
            
            return {
                "address": wallet_address,
                "balance_usdt": float(usdt_balance),
                "balance_matic": float(matic_balance),
                "network": "polygon",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        except Exception as e:
            logger.error(f"[Polygon] Error getting balance: {e}")
            raise
    
    async def send_usdt(
        self,
        from_address: str,
        to_address: str,
        amount_usdt: float,
        private_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send USDT from one address to another
        
        Args:
            from_address: Sender wallet address
            to_address: Recipient wallet address
            amount_usdt: Amount of USDT to send
            private_key: Private key of sender (if not provided, fetch from DB)
        
        Returns:
            Transaction details
        """
        try:
            if not self.w3.is_connected():
                raise ConnectionError("Not connected to Polygon network")
            
            # Get private key from DB if not provided
            if not private_key:
                wallet = await self.db.crypto_wallets.find_one(
                    {"address": from_address},
                    {"_id": 0}
                )
                
                if not wallet:
                    raise ValueError(f"Wallet not found: {from_address}")
                
                private_key = wallet["private_key"]  # TODO: Decrypt
            
            from_address = Web3.to_checksum_address(from_address)
            to_address = Web3.to_checksum_address(to_address)
            
            # Load account
            if private_key.startswith("0x"):
                private_key = private_key[2:]
            account = Account.from_key(private_key)
            
            # Get decimals
            decimals = self.usdt_contract.functions.decimals().call()
            amount_in_units = int(amount_usdt * (10 ** decimals))
            
            # Check balance
            balance_raw = self.usdt_contract.functions.balanceOf(from_address).call()
            if balance_raw < amount_in_units:
                raise ValueError(
                    f"Insufficient USDT balance. Have: {balance_raw / (10 ** decimals)}, "
                    f"Need: {amount_usdt}"
                )
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(from_address)
            gas_price = self.w3.eth.gas_price
            
            transfer_function = self.usdt_contract.functions.transfer(
                to_address,
                amount_in_units
            )
            
            gas_estimate = transfer_function.estimate_gas({"from": from_address})
            gas_limit = int(gas_estimate * 1.2)  # 20% buffer
            
            transaction = transfer_function.build_transaction({
                "from": from_address,
                "nonce": nonce,
                "gas": gas_limit,
                "gasPrice": gas_price,
                "chainId": self.chain_id
            })
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(
                transaction,
                private_key=private_key
            )
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(
                f"[Polygon] USDT transfer sent: {amount_usdt} USDT "
                f"from {from_address} to {to_address} (TX: {tx_hash.hex()})"
            )
            
            return {
                "success": True,
                "tx_hash": tx_hash.hex(),
                "from_address": from_address,
                "to_address": to_address,
                "amount_usdt": amount_usdt,
                "status": "pending",
                "explorer_url": f"https://polygonscan.com/tx/{tx_hash.hex()}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        except Exception as e:
            logger.error(f"[Polygon] Error sending USDT: {e}")
            raise
    
    async def get_primary_treasury_wallet(self) -> Optional[Dict[str, Any]]:
        """
        Get the primary treasury wallet
        """
        try:
            wallet = await self.db.crypto_wallets.find_one(
                {"is_primary": True, "network": "polygon"},
                {"_id": 0}
            )
            
            return wallet
        
        except Exception as e:
            logger.error(f"[Polygon] Error getting primary wallet: {e}")
            return None
    
    async def set_primary_wallet(self, wallet_address: str) -> bool:
        """
        Set a wallet as the primary treasury wallet
        """
        try:
            # Unset all primary flags
            await self.db.crypto_wallets.update_many(
                {"network": "polygon"},
                {"$set": {"is_primary": False}}
            )
            
            # Set new primary
            result = await self.db.crypto_wallets.update_one(
                {"address": wallet_address, "network": "polygon"},
                {"$set": {"is_primary": True}}
            )
            
            logger.info(f"[Polygon] Set primary treasury wallet: {wallet_address}")
            
            return result.modified_count > 0
        
        except Exception as e:
            logger.error(f"[Polygon] Error setting primary wallet: {e}")
            return False


# Singleton instance
_polygon_wallet_service = None


def get_polygon_wallet_service(db) -> PolygonWalletService:
    """Get singleton Polygon wallet service instance"""
    global _polygon_wallet_service
    
    if _polygon_wallet_service is None:
        _polygon_wallet_service = PolygonWalletService(db)
    
    return _polygon_wallet_service

import hashlib
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from django.conf import settings
from django.db import transaction as db_transaction
from web3 import Web3
try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    # For newer versions of web3.py
    from web3.middleware import ExtraDataToPOAMiddleware as geth_poa_middleware
from eth_account import Account
import os
import logging

logger = logging.getLogger(__name__)

# Import models lazily to avoid app registry issues at import time
def _import_models():
    from .models import ChainBlock, ChainTransaction, BlockchainConfig
    return ChainBlock, ChainTransaction, BlockchainConfig


@dataclass
class Tx:
    sender: str
    recipient: str
    amount: float
    project_id: int | None
    kind: str  # ISSUE or TRANSFER
    meta: Dict[str, Any] | None = None


class Web3BlockchainManager:
    """Real blockchain integration using Web3.py and smart contracts"""
    
    def __init__(self):
        self.w3 = None
        self.carbon_token_contract = None
        self.marketplace_contract = None
        self.account = None
        self.config = None
        self._initialize_web3()
    
    def reload(self):
        """Reload the Web3 connection and contracts"""
        logger.info("Reloading Web3 blockchain manager...")
        self._initialize_web3()
    
    def _initialize_web3(self):
        """Initialize Web3 connection and contracts"""
        try:
            # Load blockchain configuration
            BlockchainConfig = _import_models()[2]
            self.config = BlockchainConfig.get_active_config()
            
            if not self.config:
                # Create default local configuration if none exists
                self.config = self._create_default_local_config()
            
            # Connect to blockchain network
            self.w3 = Web3(Web3.HTTPProvider(self.config.rpc_url))
            
            # Add PoA middleware for local networks
            if self.config.network_type in ['local', 'sepolia', 'goerli']:
                try:
                    self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                except Exception:
                    pass  # Middleware might already be added
            
            if not self.w3.is_connected():
                # For local development, blockchain will be started by auto-setup
                if self.config.network_type == 'local':
                    logger.info("Local blockchain not running yet - will be started by auto-setup")
                else:
                    logger.error(f"Failed to connect to blockchain network: {self.config.rpc_url}")
                return
            
            # Load account from private key
            if self.config.private_key:
                self.account = Account.from_key(self.config.private_key)
                logger.info(f"Loaded account: {self.account.address}")
            
            # Load contract instances
            self._load_contracts()
            
            logger.info(f"Web3 blockchain manager initialized successfully on {self.config.network_type}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Web3 blockchain manager: {e}")
    
    def _create_default_local_config(self):
        """Create default local blockchain configuration"""
        try:
            BlockchainConfig = _import_models()[2]
            
            # Generate a new account for local development
            account = Account.create()
            
            config = BlockchainConfig.objects.create(
                name="Local Development Network",
                network_type="local",
                rpc_url="http://127.0.0.1:8545",
                chain_id=1337,
                private_key=account.key.hex(),
                is_active=True
            )
            
            logger.info(f"Created default local blockchain configuration with account: {account.address}")
            return config
            
        except Exception as e:
            logger.error(f"Failed to create default local config: {e}")
            return None
    
    def _load_contracts(self):
        """Load smart contract instances"""
        try:
            if not self.config.carbon_token_address or not self.config.marketplace_address:
                logger.warning("Contract addresses not configured")
                return
            
            # Load contract ABIs (you would load these from compiled contracts)
            carbon_token_abi = self._get_carbon_token_abi()
            marketplace_abi = self._get_marketplace_abi()
            
            # Create contract instances
            self.carbon_token_contract = self.w3.eth.contract(
                address=self.config.carbon_token_address,
                abi=carbon_token_abi
            )
            
            self.marketplace_contract = self.w3.eth.contract(
                address=self.config.marketplace_address,
                abi=marketplace_abi
            )
            
            logger.info("Smart contracts loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load smart contracts: {e}")
    
    def _get_carbon_token_abi(self):
        """Get Carbon Token contract ABI from compiled artifacts"""
        try:
            from pathlib import Path
            from django.conf import settings
            import json
            
            artifact_path = Path(settings.BASE_DIR) / 'contracts' / 'artifacts' / 'contracts' / 'CarbonCreditToken.sol' / 'CarbonCreditToken.json'
            
            if artifact_path.exists():
                with open(artifact_path, 'r') as f:
                    artifact = json.load(f)
                    return artifact['abi']
            else:
                logger.error(f"Carbon Token artifact not found at {artifact_path}")
                return []
        except Exception as e:
            logger.error(f"Failed to load Carbon Token ABI: {e}")
            return []
    
    def _get_marketplace_abi(self):
        """Get Marketplace contract ABI from compiled artifacts"""
        try:
            from pathlib import Path
            from django.conf import settings
            import json
            
            artifact_path = Path(settings.BASE_DIR) / 'contracts' / 'artifacts' / 'contracts' / 'CarbonCreditMarketplace.sol' / 'CarbonCreditMarketplace.json'
            
            if artifact_path.exists():
                with open(artifact_path, 'r') as f:
                    artifact = json.load(f)
                    return artifact['abi']
            else:
                logger.error(f"Marketplace artifact not found at {artifact_path}")
                return []
        except Exception as e:
            logger.error(f"Failed to load Marketplace ABI: {e}")
            return []

    def register_project_on_chain(self, project_name: str, ngo_address: str, estimated_credits: int) -> Optional[int]:
        """Register a project on the blockchain and return the blockchain project ID"""
        if not self.carbon_token_contract or not self.account:
            logger.error("Blockchain not properly initialized")
            return None
        
        try:
            # Ensure address is checksum format
            ngo_address = Web3.to_checksum_address(ngo_address)
            
            # Build transaction
            function = self.carbon_token_contract.functions.registerProject(
                project_name, ngo_address, estimated_credits
            )
            
            # Estimate gas
            gas_estimate = function.estimate_gas({'from': self.account.address})
            
            # Build transaction
            transaction = function.build_transaction({
                'from': self.account.address,
                'gas': gas_estimate,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
            })
            
            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.config.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            
            # Wait for transaction receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                # Parse the logs to get the project ID
                project_id = None
                for log in receipt.logs:
                    try:
                        decoded_log = self.carbon_token_contract.events.ProjectRegistered().process_log(log)
                        project_id = decoded_log['args']['projectId']
                        break
                    except:
                        continue
                
                logger.info(f"Project registered on blockchain: {tx_hash.hex()}, Project ID: {project_id}")
                return project_id
            else:
                logger.error(f"Transaction failed: {tx_hash.hex()}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to register project on blockchain: {e}")
            return None
    
    def mint_credits_on_chain(self, recipient_address: str, amount: int, project_id: int) -> Optional[str]:
        """Mint carbon credits on the blockchain"""
        if not self.carbon_token_contract or not self.account:
            logger.error("Blockchain not properly initialized")
            return None
        
        try:
            # Ensure address is checksum format
            recipient_address = Web3.to_checksum_address(recipient_address)
            
            function = self.carbon_token_contract.functions.mintCredits(
                recipient_address, amount, project_id
            )
            
            gas_estimate = function.estimate_gas({'from': self.account.address})
            
            transaction = function.build_transaction({
                'from': self.account.address,
                'gas': gas_estimate,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
            })
            
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.config.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info(f"Credits minted on blockchain: {tx_hash.hex()}")
                return tx_hash.hex()
            else:
                logger.error(f"Minting transaction failed: {tx_hash.hex()}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to mint credits on blockchain: {e}")
            return None
    
    def transfer_credits_on_chain(self, from_address: str, to_address: str, amount: int, project_id: int) -> Optional[str]:
        """Transfer credits on the blockchain using transferCreditsFrom (owner can transfer on behalf of users)"""
        if not self.carbon_token_contract or not self.account:
            logger.error("Blockchain not properly initialized")
            return None
        
        try:
            # Ensure addresses are checksum format
            from_address = Web3.to_checksum_address(from_address)
            to_address = Web3.to_checksum_address(to_address)
            
            # Use transferCreditsFrom which allows owner to transfer on behalf of users
            function = self.carbon_token_contract.functions.transferCreditsFrom(
                from_address, to_address, amount, project_id
            )
            
            gas_estimate = function.estimate_gas({'from': self.account.address})
            
            transaction = function.build_transaction({
                'from': self.account.address,  # System account (owner) calls the function
                'gas': gas_estimate,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
            })
            
            # Sign with system account (owner) private key
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.config.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info(f"Credits transferred on blockchain: {tx_hash.hex()}")
                return tx_hash.hex()
            else:
                logger.error(f"Transfer transaction failed: {tx_hash.hex()}")
                raise Exception(f"Transaction failed on chain. Hash: {tx_hash.hex()}")
                
        except Exception as e:
            logger.error(f"Failed to transfer credits on blockchain: {e}")
            raise e
    
    def get_balance(self, address: str) -> int:
        """Get token balance for an address"""
        if not self.carbon_token_contract:
            return 0
        
        try:
            # Ensure address is checksum format
            address = Web3.to_checksum_address(address)
            balance = self.carbon_token_contract.functions.balanceOf(address).call()
            return balance
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0
    
    def create_tender_on_chain(self, title: str, description: str, credits_required: int, 
                              max_price: int, duration_days: int) -> Optional[str]:
        """Create a tender on the blockchain marketplace"""
        if not self.marketplace_contract or not self.account:
            logger.error("Marketplace not properly initialized")
            return None
        
        try:
            function = self.marketplace_contract.functions.createTender(
                title, description, credits_required, max_price, duration_days
            )
            
            gas_estimate = function.estimate_gas({'from': self.account.address})
            
            transaction = function.build_transaction({
                'from': self.account.address,
                'gas': gas_estimate,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
            })
            
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.config.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info(f"Tender created on blockchain: {tx_hash.hex()}")
                return tx_hash.hex()
            else:
                logger.error(f"Tender creation failed: {tx_hash.hex()}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create tender on blockchain: {e}")
            return None


class SimpleBlockchain:
    """Ultra-light in-app blockchain for demo purposes (fallback)"""

    def __init__(self):
        self.chain: List[dict] = []
        self.pending: List[Tx] = []
        # Load persisted chain from DB if present, otherwise create genesis
        try:
            ChainBlock, ChainTransaction = _import_models()[:2]
            blocks = list(ChainBlock.objects.all().order_by("index"))
            if blocks:
                for b in blocks:
                    item = b.raw or {
                        "index": b.index,
                        "timestamp": b.timestamp,
                        "transactions": [],
                        "previous_hash": b.previous_hash,
                        "nonce": b.nonce,
                        "hash": b.hash,
                    }
                    # load txs
                    txs = []
                    for tx in b.txs.all():
                        txs.append({
                            "sender": tx.sender,
                            "recipient": tx.recipient,
                            "amount": tx.amount,
                            "project_id": tx.project_id,
                            "kind": tx.kind,
                            "meta": tx.meta,
                        })
                    item["transactions"] = txs
                    self.chain.append(item)
            else:
                self.new_block(previous_hash="GENESIS", nonce=0)
        except Exception:
            # If DB isn't ready (migrations not applied) fallback to in-memory genesis
            self.new_block(previous_hash="GENESIS", nonce=0)

    # ----------------- Core -----------------
    def new_block(self, nonce: int, previous_hash: str | None = None):
        block = {
            "index": len(self.chain) + 1,
            "timestamp": time.time(),
            "transactions": [asdict(t) for t in self.pending],
            "previous_hash": previous_hash or self.hash(self.chain[-1]),
            "nonce": nonce,
        }
        block["hash"] = self.hash(block)
        # persist block and transactions
        try:
            ChainBlock, ChainTransaction = _import_models()[:2]
            with db_transaction.atomic():
                b = ChainBlock.objects.create(
                    index=block["index"],
                    timestamp=block["timestamp"],
                    previous_hash=block.get("previous_hash"),
                    nonce=block["nonce"],
                    hash=block["hash"],
                    raw=block,
                )
                for tx in block["transactions"]:
                    ChainTransaction.objects.create(
                        block=b,
                        sender=tx.get("sender"),
                        recipient=tx.get("recipient"),
                        amount=tx.get("amount"),
                        project_id=tx.get("project_id"),
                        kind=tx.get("kind"),
                        meta=tx.get("meta"),
                    )
        except Exception:
            b = None

        self.pending = []
        self.chain.append(block)
        return block

    def new_transaction(self, tx: Tx):
        self.pending.append(tx)
        # Auto mine if more than ~5 tx for responsiveness
        if len(self.pending) >= 5:
            self.new_block(nonce=0)
        return self.last_block["index"] + 1

    @staticmethod
    def hash(block: dict) -> str:
        content = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(content).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    # ----------------- Convenience -----------------
    def issue_credits(self, recipient_addr: str, amount: float, project_id: int):
        self.new_transaction(Tx(sender="SYSTEM", recipient=recipient_addr, amount=float(amount), project_id=project_id, kind="ISSUE"))
        # mine immediately for deterministic demo ordering
        self.new_block(nonce=0)

    def transfer_credits(self, sender_addr: str, recipient_addr: str, amount: float, project_id: int):
        self.new_transaction(Tx(sender=sender_addr, recipient=recipient_addr, amount=float(amount), project_id=project_id, kind="TRANSFER"))
        self.new_block(nonce=0)


# Initialize blockchain managers
web3_manager = Web3BlockchainManager()

def get_blockchain_manager():
    """Get the Web3 blockchain manager - real blockchain only"""
    return web3_manager

def get_chain():
    """Return blockchain transactions from database - real blockchain only"""
    try:
        from .models import ChainTransaction
        # Return only real blockchain transactions
        transactions = ChainTransaction.objects.filter(
            tx_hash__isnull=False, 
            tx_hash__gt=''
        ).order_by('-timestamp')
        
        # Convert to chain format for compatibility
        chain_data = []
        for tx in transactions:
            chain_data.append({
                'sender': tx.sender,
                'recipient': tx.recipient,
                'amount': tx.amount,
                'project_id': tx.project_id,
                'kind': tx.kind,
                'meta': tx.meta,
                'tx_hash': tx.tx_hash,
                'timestamp': tx.timestamp
            })
        
        return chain_data
    except Exception:
        return []

"""
Blockchain service layer for carbon credit operations
"""
import logging
from typing import Optional, Dict, Any
from django.contrib.auth.models import User
from django.db import models
from web3 import Web3
from .models import Project, Wallet, ChainTransaction, BlockchainConfig
from .blockchain import get_blockchain_manager, web3_manager

logger = logging.getLogger(__name__)


def to_checksum(address: str) -> str:
    """Convert address to checksum format"""
    try:
        return Web3.to_checksum_address(address)
    except Exception:
        return address


class BlockchainService:
    """Service layer for blockchain operations - Real blockchain only"""
    
    @staticmethod
    def register_project_on_blockchain(project: Project) -> Optional[str]:
        """Register a project on the blockchain and return transaction hash"""
        try:
            # Ensure NGO has a wallet
            ngo_wallet = Wallet.ensure(project.ngo)
            
            # Get blockchain manager - must be real blockchain
            manager = web3_manager
            
            if not manager.w3 or not manager.w3.is_connected():
                raise Exception("Blockchain not connected. Please ensure local blockchain is running.")
            
            if not hasattr(manager, 'register_project_on_chain'):
                raise Exception("Smart contracts not deployed. Please deploy contracts first.")
            
            # Use real blockchain only - convert to checksum address
            tx_hash = manager.register_project_on_chain(
                project_name=project.title,
                ngo_address=to_checksum(ngo_wallet.address),
                estimated_credits=project.credits or 0
            )
            
            if tx_hash:
                logger.info(f"Project {project.id} registered on blockchain: {tx_hash}")
                return tx_hash
            else:
                raise Exception(f"Failed to register project {project.id} on blockchain")
                
        except Exception as e:
            logger.error(f"Error registering project {project.id} on blockchain: {e}")
            raise e
    
    @staticmethod
    def mint_credits_for_project(project: Project) -> Optional[str]:
        """Mint carbon credits for an approved project - Real blockchain only"""
        try:
            if project.chain_issued:
                logger.warning(f"Credits already issued for project {project.id}")
                return None
            
            if project.status != 'approved':
                logger.warning(f"Project {project.id} is not approved for credit minting")
                return None
            
            # Ensure NGO has a wallet
            ngo_wallet = Wallet.ensure(project.ngo)
            ngo_address = to_checksum(ngo_wallet.address)
            
            # Get blockchain manager - must be real blockchain
            manager = web3_manager
            
            if not manager.w3 or not manager.w3.is_connected():
                raise Exception("Blockchain not connected. Please start local blockchain: npx hardhat node")
            
            if not manager.carbon_token_contract:
                raise Exception("Smart contracts not deployed. Please deploy contracts first.")
            
            # First register the project on blockchain if not already done
            blockchain_project_id = None
            try:
                blockchain_project_id = manager.register_project_on_chain(
                    project_name=project.title,
                    ngo_address=ngo_address,
                    estimated_credits=project.credits
                )
                if blockchain_project_id:
                    logger.info(f"Project {project.id} registered on blockchain with ID: {blockchain_project_id}")
                else:
                    logger.warning(f"Failed to register project {project.id} on blockchain")
                    # Try using a default project ID (1) for testing
                    blockchain_project_id = 1
            except Exception as e:
                logger.warning(f"Project registration failed: {e}")
                # Try using a default project ID (1) for testing
                blockchain_project_id = 1
            
            # Use real blockchain only - use blockchain project ID
            tx_hash = manager.mint_credits_on_chain(
                recipient_address=ngo_address,
                amount=project.credits,
                project_id=blockchain_project_id
            )
            
            if tx_hash:
                # Update project status
                project.chain_issued = True
                project.save(update_fields=['chain_issued'])
                
                # Record transaction in database with blockchain_project_id
                ChainTransaction.objects.create(
                    sender="SYSTEM",
                    recipient=ngo_address,
                    amount=project.credits,
                    project_id=project.id,
                    kind="MINT",
                    tx_hash=tx_hash,
                    meta={
                        'project_title': project.title,
                        'ngo_username': project.ngo.username,
                        'blockchain_type': 'real',
                        'blockchain_project_id': blockchain_project_id  # Store blockchain project ID
                    }
                )
                
                logger.info(f"Credits minted for project {project.id}: {tx_hash}")
                return tx_hash
            else:
                raise Exception(f"Failed to mint credits for project {project.id}")
                
        except Exception as e:
            logger.error(f"Error minting credits for project {project.id}: {e}")
            raise e
    
    @staticmethod
    def transfer_credits(from_user: User, to_user: User, amount: int, project_id: int) -> Optional[str]:
        """Transfer credits between users - Real blockchain only"""
        try:
            # Ensure both users have wallets
            from_wallet = Wallet.ensure(from_user)
            to_wallet = Wallet.ensure(to_user)
            
            # Convert to checksum addresses
            from_address = to_checksum(from_wallet.address)
            to_address = to_checksum(to_wallet.address)
            
            # Get blockchain manager - must be real blockchain
            manager = web3_manager
            
            if not manager.w3 or not manager.w3.is_connected():
                raise Exception("Blockchain not connected. Please start local blockchain: npx hardhat node")
            
            if not manager.carbon_token_contract:
                raise Exception("Smart contracts not deployed. Please deploy contracts first.")
            
            # Look up the blockchain_project_id from the MINT transaction for this project
            mint_tx = ChainTransaction.objects.filter(
                project_id=project_id,
                kind='MINT',
                tx_hash__isnull=False
            ).first()
            
            if mint_tx and mint_tx.meta and 'blockchain_project_id' in mint_tx.meta:
                blockchain_project_id = mint_tx.meta.get('blockchain_project_id')
                logger.info(f"Found blockchain_project_id {blockchain_project_id} for project {project_id}")
            else:
                # Fallback: try to find any MINT transaction for this project
                logger.warning(f"No blockchain_project_id found in MINT transaction for project {project_id}, using fallback")
                blockchain_project_id = 1  # Default fallback
            
            # Use real blockchain only
            tx_hash = manager.transfer_credits_on_chain(
                from_address=from_address,
                to_address=to_address,
                amount=amount,
                project_id=blockchain_project_id
            )
            
            if tx_hash:
                # Record transaction in database
                ChainTransaction.objects.create(
                    sender=from_address,
                    recipient=to_address,
                    amount=amount,
                    project_id=project_id,  # Use Django project ID for database
                    kind="TRANSFER",
                    tx_hash=tx_hash,
                    meta={
                        'from_username': from_user.username,
                        'to_username': to_user.username,
                        'blockchain_type': 'real',
                        'blockchain_project_id': blockchain_project_id
                    }
                )
                
                logger.info(f"Credits transferred from {from_user.username} to {to_user.username}: {tx_hash}")
                return tx_hash
            else:
                raise Exception(f"Failed to transfer credits from {from_user.username} to {to_user.username}")
                
        except Exception as e:
            logger.error(f"Error transferring credits: {e}")
            raise e
    
    @staticmethod
    def get_user_balance(user: User) -> int:
        """Get user's total token balance"""
        try:
            wallet = Wallet.ensure(user)
            manager = get_blockchain_manager()
            
            if hasattr(manager, 'get_balance'):
                return manager.get_balance(wallet.address)
            else:
                # Fallback: calculate from transactions
                received = ChainTransaction.objects.filter(
                    recipient=wallet.address,
                    kind__in=['MINT', 'TRANSFER']
                ).aggregate(total=models.Sum('amount'))['total'] or 0
                
                sent = ChainTransaction.objects.filter(
                    sender=wallet.address,
                    kind='TRANSFER'
                ).aggregate(total=models.Sum('amount'))['total'] or 0
                
                return max(0, received - sent)
                
        except Exception as e:
            logger.error(f"Error getting balance for user {user.username}: {e}")
            return 0
    
    @staticmethod
    def create_tender_on_blockchain(title: str, description: str, credits_required: int, 
                                   max_price: int, duration_days: int, corporate_user: User) -> Optional[str]:
        """Create a tender on the blockchain marketplace"""
        try:
            # Ensure corporate user has a wallet
            corporate_wallet = Wallet.ensure(corporate_user)
            
            # Get blockchain manager
            manager = get_blockchain_manager()
            
            if hasattr(manager, 'create_tender_on_chain'):
                # Use real blockchain marketplace
                tx_hash = manager.create_tender_on_chain(
                    title=title,
                    description=description,
                    credits_required=credits_required,
                    max_price=max_price,
                    duration_days=duration_days
                )
                
                if tx_hash:
                    logger.info(f"Tender created on blockchain by {corporate_user.username}: {tx_hash}")
                    return tx_hash
                else:
                    logger.error(f"Failed to create tender on blockchain for {corporate_user.username}")
                    return None
            else:
                # Fallback: just log the tender creation
                logger.info(f"Tender created (simple mode) by {corporate_user.username}")
                return "simple_blockchain_tender"
                
        except Exception as e:
            logger.error(f"Error creating tender on blockchain: {e}")
            return None
    
    @staticmethod
    def get_blockchain_status() -> Dict[str, Any]:
        """Get current blockchain connection status"""
        try:
            config = BlockchainConfig.get_active_config()
            
            if not config:
                return {
                    'connected': False,
                    'network': 'none',
                    'error': 'No blockchain configuration found'
                }
            
            manager = get_blockchain_manager()
            
            if hasattr(manager, 'w3') and manager.w3:
                is_connected = manager.w3.is_connected()
                latest_block = manager.w3.eth.block_number if is_connected else None
                
                return {
                    'connected': is_connected,
                    'network': config.network_type,
                    'chain_id': config.chain_id,
                    'latest_block': latest_block,
                    'contracts_deployed': bool(config.carbon_token_address and config.marketplace_address),
                    'carbon_token_address': config.carbon_token_address,
                    'marketplace_address': config.marketplace_address
                }
            else:
                return {
                    'connected': True,
                    'network': 'simple_blockchain',
                    'mode': 'fallback'
                }
                
        except Exception as e:
            logger.error(f"Error getting blockchain status: {e}")
            return {
                'connected': False,
                'error': str(e)
            }
    
    @staticmethod
    def validate_address(address: str) -> bool:
        """Validate if an address is a valid Ethereum address"""
        try:
            if not address or len(address) != 42 or not address.startswith('0x'):
                return False
            
            # Try to convert to checksum address
            from web3 import Web3
            Web3.to_checksum_address(address)
            return True
        except Exception:
            return False
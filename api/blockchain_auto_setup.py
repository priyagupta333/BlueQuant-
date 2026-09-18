"""
Auto-setup blockchain when Django starts
"""
import os
import sys
import subprocess
import threading
import time
import logging
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

class BlockchainAutoSetup:
    """Automatically setup blockchain when Django starts"""
    
    def __init__(self):
        self.blockchain_process = None
        self.contracts_deployed = False
        self.setup_complete = False
        
    def start_blockchain_and_deploy(self):
        """Start blockchain and deploy contracts in background"""
        try:
            logger.info("=== BLOCKCHAIN AUTO-SETUP STARTING ===")
            # Run in separate thread to not block Django startup
            thread = threading.Thread(target=self._setup_blockchain_async, daemon=True)
            thread.start()
            logger.info("Blockchain auto-setup thread started successfully")
        except Exception as e:
            logger.error(f"Failed to start blockchain auto-setup thread: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _setup_blockchain_async(self):
        """Async blockchain setup"""
        try:
            logger.info("=== ASYNC BLOCKCHAIN SETUP STARTED ===")
            # Wait a moment for Django to fully start
            logger.info("Waiting for Django to fully initialize...")
            time.sleep(3)
            
            # Check if blockchain is already running
            logger.info("Checking if blockchain is already running...")
            if self._check_blockchain_running():
                logger.info("Blockchain already running, checking contracts...")
                self._deploy_contracts_if_needed()
                return
            
            # Start blockchain
            logger.info("Starting local blockchain...")
            if self._start_local_blockchain():
                logger.info("Local blockchain started successfully")
                
                # Wait longer for blockchain to be fully ready
                logger.info("Waiting for blockchain to be fully ready...")
                time.sleep(10)
                
                # Verify blockchain is responding properly
                ready_count = 0
                for i in range(10):  # Try 10 times
                    if self._check_blockchain_running():
                        ready_count += 1
                        if ready_count >= 3:  # Need 3 consecutive successful checks
                            break
                    time.sleep(2)
                
                if ready_count >= 3:
                    logger.info("Blockchain is stable and ready")
                    
                    # Deploy contracts
                    logger.info("Deploying smart contracts...")
                    if self._deploy_contracts():
                        logger.info("Smart contracts deployed successfully")
                        self._update_django_config()
                        self.setup_complete = True
                        logger.info("=== BLOCKCHAIN AUTO-SETUP COMPLETED SUCCESSFULLY ===")
                    else:
                        logger.error("Failed to deploy smart contracts")
                else:
                    logger.error("Blockchain not stable after startup")
            else:
                logger.error("Failed to start local blockchain")
                
        except Exception as e:
            logger.error(f"Blockchain auto-setup error: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _check_blockchain_running(self):
        """Check if blockchain is already running"""
        try:
            import requests
            response = requests.post(
                'http://127.0.0.1:8545',
                json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
                timeout=2
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def _start_local_blockchain(self):
        """Start local Hardhat blockchain"""
        try:
            logger.info("=== STARTING LOCAL BLOCKCHAIN ===")
            contracts_dir = Path(settings.BASE_DIR) / 'contracts'
            
            if not contracts_dir.exists():
                logger.error(f"Contracts directory not found: {contracts_dir}")
                return False
            
            logger.info(f"Using contracts directory: {contracts_dir}")
            
            # Check if npm dependencies are installed
            node_modules = contracts_dir / 'node_modules'
            if not node_modules.exists():
                logger.info("Installing npm dependencies...")
                result = subprocess.run(
                    'npm install',
                    cwd=contracts_dir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    shell=True
                )
                if result.returncode != 0:
                    logger.error(f"npm install failed: {result.stderr}")
                    return False
                logger.info("npm dependencies installed successfully")
            else:
                logger.info("npm dependencies already installed")
            
            logger.info("Starting Hardhat blockchain node...")
            
            if os.name == 'nt':  # Windows
                # Use 'start' command to open a new minimized window that stays open
                cmd = f'start "Hardhat Blockchain" /MIN cmd /k "cd /d {contracts_dir} && npx hardhat node"'
                logger.info(f"Running: {cmd}")
                result = os.system(cmd)
                logger.info(f"Start command returned: {result}")
            else:  # Unix/Linux
                self.blockchain_process = subprocess.Popen(
                    ['npx', 'hardhat', 'node'],
                    cwd=contracts_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True
                )
            
            logger.info("Blockchain process started")
            
            # Wait for blockchain to start
            for i in range(60):  # Wait up to 60 seconds
                if i % 10 == 0:
                    logger.info(f"Waiting for blockchain to start (attempt {i+1}/60)...")
                if self._check_blockchain_running():
                    logger.info("Blockchain is ready and responding!")
                    return True
                time.sleep(1)
            
            logger.error("Blockchain failed to start within timeout")
            return False
            
        except Exception as e:
            logger.error(f"Error starting blockchain: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _deploy_contracts(self):
        """Deploy smart contracts"""
        try:
            contracts_dir = Path(settings.BASE_DIR) / 'contracts'
            
            logger.info("Deploying smart contracts...")
            
            # Add retry logic for contract deployment
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    result = subprocess.run(
                        ['npx', 'hardhat', 'run', 'scripts/deploy.js', '--network', 'localhost'],
                        cwd=contracts_dir,
                        capture_output=True,
                        text=True,
                        timeout=120,  # Increased timeout
                        shell=True  # Use shell on Windows
                    )
                    
                    if result.returncode == 0:
                        logger.info("Contracts deployed successfully")
                        logger.info(result.stdout)
                        self.contracts_deployed = True
                        return True
                    else:
                        logger.error(f"Contract deployment failed (attempt {attempt + 1}): {result.stderr}")
                        if attempt < max_retries - 1:
                            logger.info(f"Retrying in 5 seconds...")
                            time.sleep(5)
                        
                except subprocess.TimeoutExpired:
                    logger.error(f"Contract deployment timeout (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying in 5 seconds...")
                        time.sleep(5)
            
            logger.error("All contract deployment attempts failed")
            return False
                
        except Exception as e:
            logger.error(f"Error deploying contracts: {e}")
            return False
    
    def _deploy_contracts_if_needed(self):
        """Deploy contracts if not already deployed"""
        try:
            # Check if contracts are already deployed by checking config
            from .models import BlockchainConfig
            config = BlockchainConfig.get_active_config()
            
            if config and config.carbon_token_address and config.marketplace_address:
                logger.info("Contracts already deployed and configured")
                self.contracts_deployed = True
                self.setup_complete = True
                return True
            
            # Deploy contracts
            return self._deploy_contracts()
            
        except Exception as e:
            logger.error(f"Error checking/deploying contracts: {e}")
            return False
    
    def _update_django_config(self):
        """Update Django blockchain configuration with deployed addresses"""
        try:
            contracts_dir = Path(settings.BASE_DIR) / 'contracts'
            deployment_file = contracts_dir / 'deployments' / 'localhost.json'
            
            if deployment_file.exists():
                import json
                with open(deployment_file, 'r') as f:
                    deployment_info = json.load(f)
                
                # Update blockchain config
                from .models import BlockchainConfig
                config, created = BlockchainConfig.objects.get_or_create(
                    name="Local Development Network",
                    defaults={
                        'network_type': 'local',
                        'rpc_url': 'http://127.0.0.1:8545',
                        'chain_id': 1337,
                        'is_active': True
                    }
                )
                
                # Set the private key if not already set (use Hardhat's first account from env)
                if not config.private_key:
                    config.private_key = os.environ.get('HARDHAT_PRIVATE_KEY', '')
                
                config.carbon_token_address = deployment_info.get('carbonToken', '')
                config.marketplace_address = deployment_info.get('marketplace', '')
                config.is_active = True
                config.save()
                
                logger.info(f"Django config updated with contract addresses")
                logger.info(f"Carbon Token: {config.carbon_token_address}")
                logger.info(f"Marketplace: {config.marketplace_address}")
                
                # Reload the Web3 manager to pick up the new contract addresses
                from .blockchain import web3_manager
                web3_manager.reload()
                logger.info("Web3 manager reloaded with new contract addresses")
                
            else:
                logger.warning(f"Deployment file not found: {deployment_file}")
                
        except Exception as e:
            logger.error(f"Error updating Django config: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def stop_blockchain(self):
        """Stop the blockchain process"""
        if self.blockchain_process:
            try:
                self.blockchain_process.terminate()
                self.blockchain_process.wait(timeout=10)
                logger.info("Blockchain process stopped")
            except Exception as e:
                logger.error(f"Error stopping blockchain: {e}")
                try:
                    self.blockchain_process.kill()
                except Exception:
                    pass


# Global instance
blockchain_auto_setup = BlockchainAutoSetup()
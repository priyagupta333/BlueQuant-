"""
Django management command to manually setup blockchain
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Setup blockchain and deploy contracts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force setup even if blockchain is already running',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting blockchain setup...'))
        
        try:
            from api.blockchain_auto_setup import BlockchainAutoSetup
            
            setup = BlockchainAutoSetup()
            
            # Check if blockchain is already running
            if setup._check_blockchain_running() and not options['force']:
                self.stdout.write(
                    self.style.WARNING('Blockchain is already running. Use --force to restart.')
                )
                
                # Still try to deploy contracts if needed
                if setup._deploy_contracts_if_needed():
                    setup._update_django_config()
                    self.stdout.write(self.style.SUCCESS('Contracts deployed and config updated'))
                else:
                    self.stdout.write(self.style.SUCCESS('Contracts already deployed'))
                return
            
            # Start blockchain
            self.stdout.write('Starting local blockchain...')
            if setup._start_local_blockchain():
                self.stdout.write(self.style.SUCCESS('✓ Blockchain started'))
                
                # Deploy contracts
                self.stdout.write('Deploying smart contracts...')
                if setup._deploy_contracts():
                    self.stdout.write(self.style.SUCCESS('✓ Contracts deployed'))
                    
                    # Update Django config
                    setup._update_django_config()
                    self.stdout.write(self.style.SUCCESS('✓ Django config updated'))
                    
                    # Show final status
                    from api.models import BlockchainConfig
                    config = BlockchainConfig.get_active_config()
                    if config:
                        self.stdout.write(f'Carbon Token: {config.carbon_token_address}')
                        self.stdout.write(f'Marketplace: {config.marketplace_address}')
                    
                    self.stdout.write(
                        self.style.SUCCESS('Blockchain setup completed successfully!')
                    )
                else:
                    self.stdout.write(self.style.ERROR('Failed to deploy contracts'))
            else:
                self.stdout.write(self.style.ERROR('Failed to start blockchain'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Setup failed: {e}'))
            logger.exception("Blockchain setup failed")
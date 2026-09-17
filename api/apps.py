from django.apps import AppConfig
import logging
import sys

logger = logging.getLogger(__name__)


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    
    def ready(self):
        """Called when Django app is ready"""
        import os
        
        # Run auto-setup in the main Django process
        # When using runserver with reloader: RUN_MAIN='true' in main process
        # When using runserver --noreload: RUN_MAIN is not set
        run_main = os.environ.get('RUN_MAIN') == 'true'
        is_runserver = 'runserver' in sys.argv
        no_reload = '--noreload' in sys.argv
        
        should_run_setup = (run_main and is_runserver) or (no_reload and is_runserver)
        
        if should_run_setup:
            try:
                logger.info("Django main process detected, starting blockchain auto-setup...")
                from .blockchain_auto_setup import blockchain_auto_setup
                blockchain_auto_setup.start_blockchain_and_deploy()
                logger.info("Blockchain auto-setup initiated successfully")
            except Exception as e:
                logger.error(f"Failed to start blockchain auto-setup: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.info("Skipping blockchain auto-setup (not main process or not runserver)")
        
        # Import signals to ensure they're registered
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass

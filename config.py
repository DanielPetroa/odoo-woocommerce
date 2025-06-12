import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Entorno
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')  # development, staging, production
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    HOST = os.getenv('HOST', '127.0.0.1')
    PORT = int(os.getenv('PORT', 5000))
    
    # Odoo Configuration
    ODOO_URL = os.getenv('ODOO_URL')
    ODOO_DB = os.getenv('ODOO_DB')
    ODOO_USERNAME = os.getenv('ODOO_USERNAME')
    ODOO_API_KEY = os.getenv('ODOO_API_KEY')
    
    # WooCommerce Configuration
    WOO_URL = os.getenv('WOO_URL')
    WOO_CONSUMER_KEY = os.getenv('WOO_CONSUMER_KEY')
    WOO_CONSUMER_SECRET = os.getenv('WOO_CONSUMER_SECRET')
    
    # Webhook Security
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'change-this-secret')
    
    # Sync Configuration
    SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL', 300))  # segundos
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', 50))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/app.log')
    
    @classmethod
    def validate(cls):
        """Validar que todas las variables requeridas estén configuradas"""
        required_vars = [
            'ODOO_URL', 'ODOO_DB', 'ODOO_USERNAME', 'ODOO_API_KEY',
            'WOO_URL', 'WOO_CONSUMER_KEY', 'WOO_CONSUMER_SECRET'
        ]
        
        missing = [var for var in required_vars if not getattr(cls, var)]
        if missing:
            raise ValueError(f"Variables de entorno faltantes: {', '.join(missing)}")
        
        return True
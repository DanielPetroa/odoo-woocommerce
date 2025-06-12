# src/utils/logger.py
import logging
import logging.handlers
import os
from datetime import datetime
from config import Config

def setup_logger():
    """Configurar logging para la aplicación"""
    
    # Crear directorio de logs si no existe
    log_dir = os.path.dirname(Config.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configurar formato de logs
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper()))
    
    # Limpiar handlers existentes
    root_logger.handlers.clear()
    
    # Handler para archivo con rotación
    file_handler = logging.handlers.RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)
    
    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # Logger específico para requests (reducir verbosidad)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    logging.info("Sistema de logging configurado correctamente")

class SyncLogger:
    """Logger específico para operaciones de sincronización"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(f"sync.{name}")
        
    def log_sync_start(self, operation: str, count: int = None):
        """Log inicio de sincronización"""
        msg = f"Iniciando {operation}"
        if count:
            msg += f" ({count} items)"
        self.logger.info(msg)
    
    def log_sync_success(self, operation: str, count: int = None):
        """Log sincronización exitosa"""
        msg = f"✅ {operation} completado"
        if count:
            msg += f" ({count} items procesados)"
        self.logger.info(msg)
    
    def log_sync_error(self, operation: str, error: str):
        """Log error de sincronización"""
        self.logger.error(f"❌ Error en {operation}: {error}")
    
    def log_item_processed(self, item_type: str, item_id: str, success: bool = True):
        """Log procesamiento de item individual"""
        status = "✅" if success else "❌"
        self.logger.info(f"{status} {item_type} {item_id} {'procesado' if success else 'falló'}")
    
    def log_webhook_received(self, webhook_type: str, data: dict):
        """Log recepción de webhook"""
        self.logger.info(f"📥 Webhook recibido: {webhook_type} - {data.get('id', 'unknown')}")
    
    def log_api_call(self, api: str, endpoint: str, method: str, success: bool = True):
        """Log llamada a API"""
        status = "✅" if success else "❌"
        self.logger.debug(f"{status} API {api}: {method} {endpoint}")

def log_function_call(func):
    """Decorador para loggear llamadas a funciones"""
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        logger.debug(f"Llamando función: {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"Función {func.__name__} completada exitosamente")
            return result
        except Exception as e:
            logger.error(f"Error en función {func.__name__}: {e}")
            raise
    return wrapper

def log_performance(operation_name: str):
    """Decorador para medir y loggear performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            start_time = datetime.now()
            
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                logger.info(f"⏱️ {operation_name} completado en {duration:.2f} segundos")
                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error(f"⏱️ {operation_name} falló después de {duration:.2f} segundos: {e}")
                raise
                
        return wrapper
    return decorator
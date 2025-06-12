# app.py
from flask import Flask, request, jsonify
import logging
import hashlib
import hmac
import json
from datetime import datetime
import threading
import schedule
import time

from config import Config
from src.clients.odoo_client import OdooClient
from src.clients.woo_client import WooCommerceClient
from src.services.sync_service import SyncService
from src.utils.logger import setup_logger

# Configurar logging
setup_logger()
logger = logging.getLogger(__name__)

# Crear Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Validar configuración
try:
    Config.validate()
    logger.info("Configuración validada exitosamente")
except ValueError as e:
    logger.error(f"Error en configuración: {e}")
    exit(1)

# Inicializar clientes
odoo_client = OdooClient()
woo_client = WooCommerceClient()
sync_service = SyncService(odoo_client, woo_client)

def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verificar firma del webhook para seguridad"""
    if not Config.WEBHOOK_SECRET:
        logger.warning("WEBHOOK_SECRET no configurado - saltando verificación")
        return True
    
    expected_signature = hmac.new(
        Config.WEBHOOK_SECRET.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected_signature}", signature)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Verificar conexión a Odoo
        odoo_status = odoo_client.authenticate()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'odoo_connection': odoo_status,
            'environment': Config.ENVIRONMENT
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/webhook/order', methods=['POST'])
def webhook_order():
    """Webhook para nuevas órdenes de WooCommerce"""
    try:
        # Verificar firma
        signature = request.headers.get('X-WC-Webhook-Signature', '')
        if not verify_webhook_signature(request.data, signature):
            logger.warning("Webhook signature verification failed")
            return jsonify({'error': 'Invalid signature'}), 403
        
        # Obtener datos de la orden
        order_data = request.get_json()
        
        if not order_data:
            return jsonify({'error': 'No data provided'}), 400
        
        logger.info(f"Recibida orden #{order_data.get('number', 'unknown')}")
        
        # Procesar orden de forma asíncrona
        threading.Thread(
            target=sync_service.process_woo_order,
            args=(order_data,)
        ).start()
        
        return jsonify({
            'status': 'success',
            'message': 'Order received and will be processed'
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/webhook/customer', methods=['POST'])
def webhook_customer():
    """Webhook para clientes de WooCommerce"""
    try:
        signature = request.headers.get('X-WC-Webhook-Signature', '')
        if not verify_webhook_signature(request.data, signature):
            return jsonify({'error': 'Invalid signature'}), 403
        
        customer_data = request.get_json()
        
        if not customer_data:
            return jsonify({'error': 'No data provided'}), 400
        
        logger.info(f"Recibido cliente: {customer_data.get('email', 'unknown')}")
        
        # Procesar cliente
        threading.Thread(
            target=sync_service.process_woo_customer,
            args=(customer_data,)
        ).start()
        
        return jsonify({
            'status': 'success',
            'message': 'Customer received and will be processed'
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing customer webhook: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/sync/manual', methods=['POST'])
def manual_sync():
    """Endpoint para sincronización manual"""
    try:
        sync_type = request.json.get('type', 'all') if request.is_json else 'all'
        hours = request.json.get('hours', 24) if request.is_json else 24
        
        logger.info(f"Iniciando sincronización manual: {sync_type}")
        
        if sync_type in ['all', 'orders']:
            # Sincronizar órdenes recientes
            bookings = woo_client.get_recent_bookings(hours=hours)
            for booking in bookings:
                sync_service.sync_booking_to_odoo(booking)
        
        if sync_type in ['all', 'customers']:
            # Sincronizar clientes
            customers = woo_client.get_customers(per_page=100)
            for customer in customers:
                sync_service.process_woo_customer(customer)
        
        return jsonify({
            'status': 'success',
            'message': f'Manual sync completed for {sync_type}'
        }), 200
        
    except Exception as e:
        logger.error(f"Error in manual sync: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/sync/status', methods=['GET'])
def sync_status():
    """Estado de la sincronización"""
    try:
        # Obtener estadísticas básicas
        recent_bookings = woo_client.get_recent_bookings(hours=1)
        
        return jsonify({
            'status': 'active',
            'recent_bookings_count': len(recent_bookings),
            'last_check': datetime.now().isoformat(),
            'environment': Config.ENVIRONMENT
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        return jsonify({'error': str(e)}), 500

def run_scheduler():
    """Ejecutar tareas programadas en un hilo separado"""
    logger.info("Iniciando scheduler")
    
    # Programar sincronización periódica
    schedule.every(Config.SYNC_INTERVAL).seconds.do(sync_service.scheduled_sync)
    
    # Programar limpieza de logs (diaria)
    schedule.every().day.at("02:00").do(sync_service.cleanup_logs)
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Revisar cada minuto

if __name__ == '__main__':
    logger.info(f"Iniciando aplicación en modo {Config.ENVIRONMENT}")
    
    # Probar conexiones
    if odoo_client.authenticate():
        logger.info("✅ Conexión a Odoo exitosa")
    else:
        logger.error("❌ Error conectando a Odoo")
    
    # Iniciar scheduler en hilo separado
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Iniciar Flask app
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
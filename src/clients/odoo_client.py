import xmlrpc.client
import logging
from typing import Dict, List, Optional, Any
from config import Config

class OdooClient:
    def __init__(self):
        self.url = Config.ODOO_URL
        self.db = Config.ODOO_DB
        self.username = Config.ODOO_USERNAME
        self.api_key = Config.ODOO_API_KEY
        self.uid = None
        self.logger = logging.getLogger(__name__)
        
        # Conexiones XML-RPC
        self.common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
        self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
        
    def authenticate(self) -> bool:
        """Autenticar con Odoo y obtener UID"""
        try:
            self.uid = self.common.authenticate(self.db, self.username, self.api_key, {})
            if self.uid:
                self.logger.info(f"Autenticado exitosamente en Odoo con UID: {self.uid}")
                return True
            else:
                self.logger.error("Falló la autenticación en Odoo")
                return False
        except Exception as e:
            self.logger.error(f"Error de autenticación en Odoo: {e}")
            return False
    
    def create_record(self, model: str, data: Dict) -> Optional[int]:
        """Crear un registro en Odoo"""
        try:
            if not self.uid:
                self.authenticate()
            
            record_id = self.models.execute_kw(
                self.db, self.uid, self.api_key,
                model, 'create', [data]
            )
            self.logger.info(f"Registro creado en {model} con ID: {record_id}")
            return record_id
        except Exception as e:
            self.logger.error(f"Error creando registro en {model}: {e}")
            return None
    
    def update_record(self, model: str, record_id: int, data: Dict) -> bool:
        """Actualizar un registro en Odoo"""
        try:
            if not self.uid:
                self.authenticate()
            
            result = self.models.execute_kw(
                self.db, self.uid, self.api_key,
                model, 'write', [[record_id], data]
            )
            self.logger.info(f"Registro {record_id} actualizado en {model}")
            return result
        except Exception as e:
            self.logger.error(f"Error actualizando registro {record_id} en {model}: {e}")
            return False
    
    def search_records(self, model: str, domain: List = None, fields: List = None, limit: int = None) -> List[Dict]:
        """Buscar registros en Odoo"""
        try:
            if not self.uid:
                self.authenticate()
            
            domain = domain or []
            
            # Buscar IDs
            record_ids = self.models.execute_kw(
                self.db, self.uid, self.api_key,
                model, 'search', [domain],
                {'limit': limit} if limit else {}
            )
            
            if not record_ids:
                return []
            
            # Leer registros
            records = self.models.execute_kw(
                self.db, self.uid, self.api_key,
                model, 'read', [record_ids],
                {'fields': fields} if fields else {}
            )
            
            return records
        except Exception as e:
            self.logger.error(f"Error buscando registros en {model}: {e}")
            return []
    
    def get_record_by_external_id(self, model: str, external_id: str) -> Optional[Dict]:
        """Buscar registro por ID externo (referencia de WooCommerce)"""
        records = self.search_records(
            model, 
            [['x_woo_id', '=', external_id]], 
            limit=1
        )
        return records[0] if records else None
    
    # Métodos específicos para el negocio
    
    def create_customer(self, customer_data: Dict) -> Optional[int]:
        """Crear cliente en Odoo"""
        odoo_data = {
            'name': customer_data.get('name'),
            'email': customer_data.get('email'),
            'phone': customer_data.get('phone'),
            'x_woo_id': customer_data.get('woo_id'),  # Campo personalizado para referencia
            'is_company': False,
            'customer_rank': 1
        }
        return self.create_record('res.partner', odoo_data)
    
    def create_product(self, product_data: Dict) -> Optional[int]:
        """Crear producto/servicio en Odoo"""
        odoo_data = {
            'name': product_data.get('name'),
            'default_code': product_data.get('sku'),
            'list_price': product_data.get('price', 0),
            'type': 'service',  # Para clases
            'sale_ok': True,
            'purchase_ok': False,
            'x_woo_id': product_data.get('woo_id'),
            'x_booking_date': product_data.get('booking_date'),
            'x_persons': product_data.get('persons', 1),
            'description': product_data.get('description', '')
        }
        return self.create_record('product.product', odoo_data)
    
    def create_sale_order(self, order_data: Dict) -> Optional[int]:
        """Crear orden de venta en Odoo"""
        partner_id = self.get_or_create_customer(order_data.get('customer'))
        
        if not partner_id:
            self.logger.error("No se pudo crear/encontrar cliente")
            return None
        
        # Crear orden
        order_odoo_data = {
            'partner_id': partner_id,
            'x_woo_order_id': order_data.get('woo_order_id'),
            'origin': f"WooCommerce #{order_data.get('woo_order_id')}",
            'state': 'draft'
        }
        
        order_id = self.create_record('sale.order', order_odoo_data)
        
        if order_id:
            # Agregar líneas de orden
            for line_data in order_data.get('lines', []):
                product_id = self.get_or_create_product(line_data.get('product'))
                
                if product_id:
                    line_odoo_data = {
                        'order_id': order_id,
                        'product_id': product_id,
                        'product_uom_qty': line_data.get('quantity', 1),
                        'price_unit': line_data.get('price', 0)
                    }
                    self.create_record('sale.order.line', line_odoo_data)
        
        return order_id
    
    def get_or_create_customer(self, customer_data: Dict) -> Optional[int]:
        """Buscar cliente existente o crear uno nuevo"""
        if customer_data.get('woo_id'):
            existing = self.get_record_by_external_id('res.partner', str(customer_data['woo_id']))
            if existing:
                return existing['id']
        
        # Buscar por email
        existing = self.search_records(
            'res.partner',
            [['email', '=', customer_data.get('email')]],
            limit=1
        )
        
        if existing:
            # Actualizar con WooCommerce ID si no lo tiene
            if customer_data.get('woo_id'):
                self.update_record('res.partner', existing[0]['id'], {
                    'x_woo_id': customer_data['woo_id']
                })
            return existing[0]['id']
        
        # Crear nuevo cliente
        return self.create_customer(customer_data)
    
    def get_or_create_product(self, product_data: Dict) -> Optional[int]:
        """Buscar producto existente o crear uno nuevo"""
        if product_data.get('woo_id'):
            existing = self.get_record_by_external_id('product.product', str(product_data['woo_id']))
            if existing:
                return existing['id']
        
        # Crear nuevo producto
        return self.create_product(product_data)
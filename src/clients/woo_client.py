import requests
from requests.auth import HTTPBasicAuth
import logging
from typing import Dict, List, Optional
from config import Config

class WooCommerceClient:
    def __init__(self):
        self.base_url = Config.WOO_URL.rstrip('/')
        self.api_url = f"{self.base_url}/wp-json/wc/v3"
        self.consumer_key = Config.WOO_CONSUMER_KEY
        self.consumer_secret = Config.WOO_CONSUMER_SECRET
        self.auth = HTTPBasicAuth(self.consumer_key, self.consumer_secret)
        self.logger = logging.getLogger(__name__)
        
    def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Optional[Dict]:
        """Realizar petición HTTP a WooCommerce API"""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                auth=self.auth,
                json=data if data else None,
                params=params if params else None,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                self.logger.error(f"Error en WooCommerce API: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error de conexión con WooCommerce: {e}")
            return None
    
    def get_orders(self, status: str = None, per_page: int = 100, page: int = 1, 
                   after: str = None, before: str = None) -> List[Dict]:
        """Obtener órdenes de WooCommerce"""
        params = {
            'per_page': per_page,
            'page': page
        }
        
        if status:
            params['status'] = status
        if after:
            params['after'] = after
        if before:
            params['before'] = before
            
        response = self._make_request('GET', 'orders', params=params)
        return response if isinstance(response, list) else []
    
    def get_order(self, order_id: int) -> Optional[Dict]:
        """Obtener una orden específica"""
        return self._make_request('GET', f'orders/{order_id}')
    
    def update_order(self, order_id: int, data: Dict) -> Optional[Dict]:
        """Actualizar una orden"""
        return self._make_request('PUT', f'orders/{order_id}', data=data)
    
    def get_products(self, per_page: int = 100, page: int = 1, type: str = None) -> List[Dict]:
        """Obtener productos"""
        params = {
            'per_page': per_page,
            'page': page
        }
        
        if type:
            params['type'] = type
            
        response = self._make_request('GET', 'products', params=params)
        return response if isinstance(response, list) else []
    
    def get_product(self, product_id: int) -> Optional[Dict]:
        """Obtener un producto específico"""
        return self._make_request('GET', f'products/{product_id}')
    
    def create_product(self, product_data: Dict) -> Optional[Dict]:
        """Crear producto en WooCommerce"""
        return self._make_request('POST', 'products', data=product_data)
    
    def update_product(self, product_id: int, data: Dict) -> Optional[Dict]:
        """Actualizar producto"""
        return self._make_request('PUT', f'products/{product_id}', data=data)
    
    def get_customers(self, per_page: int = 100, page: int = 1) -> List[Dict]:
        """Obtener clientes"""
        params = {
            'per_page': per_page,
            'page': page
        }
        
        response = self._make_request('GET', 'customers', params=params)
        return response if isinstance(response, list) else []
    
    def get_customer(self, customer_id: int) -> Optional[Dict]:
        """Obtener un cliente específico"""
        return self._make_request('GET', f'customers/{customer_id}')
    
    def create_customer(self, customer_data: Dict) -> Optional[Dict]:
        """Crear cliente en WooCommerce"""
        return self._make_request('POST', 'customers', data=customer_data)
    
    def update_customer(self, customer_id: int, data: Dict) -> Optional[Dict]:
        """Actualizar cliente"""
        return self._make_request('PUT', f'customers/{customer_id}', data=data)
    
    # Métodos específicos para booking
    
    def get_booking_orders(self, after: str = None) -> List[Dict]:
        """Obtener órdenes con productos booking"""
        orders = self.get_orders(status='completed', after=after, per_page=100)
        booking_orders = []
        
        for order in orders:
            has_booking = False
            for item in order.get('line_items', []):
                # Verificar si el item tiene datos de booking
                meta_data = item.get('meta_data', [])
                booking_meta = [meta for meta in meta_data if 'booking' in meta.get('key', '').lower()]
                
                if booking_meta:
                    has_booking = True
                    break
            
            if has_booking:
                booking_orders.append(order)
        
        return booking_orders
    
    def extract_booking_data(self, order: Dict) -> List[Dict]:
        """Extraer datos de booking de una orden"""
        bookings = []
        
        for item in order.get('line_items', []):
            booking_data = {
                'order_id': order['id'],
                'order_number': order['number'],
                'product_id': item['product_id'],
                'product_name': item['name'],
                'quantity': item['quantity'],
                'total': float(item['total']),
                'customer': {
                    'id': order['customer_id'],
                    'email': order['billing']['email'],
                    'name': f"{order['billing']['first_name']} {order['billing']['last_name']}",
                    'phone': order['billing']['phone']
                }
            }
            
            # Extraer meta data de booking
            meta_data = item.get('meta_data', [])
            for meta in meta_data:
                key = meta.get('key', '').lower()
                value = meta.get('value', '')
                
                if 'booking_date' in key or 'from' in key:
                    booking_data['booking_date'] = value
                elif 'persons' in key or 'person' in key:
                    booking_data['persons'] = int(value) if str(value).isdigit() else 1
                elif 'duration' in key:
                    booking_data['duration'] = value
                elif 'to' in key and 'booking_date' not in booking_data:
                    booking_data['booking_end'] = value
            
            # Si no encontramos fecha, usar fecha de la orden
            if 'booking_date' not in booking_data:
                booking_data['booking_date'] = order['date_created']
            
            # Asegurar que persons tenga un valor
            if 'persons' not in booking_data:
                booking_data['persons'] = 1
            
            bookings.append(booking_data)
        
        return bookings
    
    def get_recent_bookings(self, hours: int = 24) -> List[Dict]:
        """Obtener bookings recientes"""
        from datetime import datetime, timedelta
        
        # Calcular fecha límite
        after_date = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # Obtener órdenes recientes con bookings
        orders = self.get_booking_orders(after=after_date)
        
        all_bookings = []
        for order in orders:
            bookings = self.extract_booking_data(order)
            all_bookings.extend(bookings)
        
        return all_bookings
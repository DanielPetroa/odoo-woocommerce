# src/services/sync_service.py
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from src.clients.odoo_client import OdooClient
from src.clients.woo_client import WooCommerceClient

class SyncService:
    def __init__(self, odoo_client: OdooClient, woo_client: WooCommerceClient):
        self.odoo = odoo_client
        self.woo = woo_client
        self.logger = logging.getLogger(__name__)
        
    def process_woo_order(self, order_data: Dict) -> bool:
        """Procesar orden de WooCommerce y sincronizar con Odoo"""
        try:
            order_id = order_data.get('id')
            order_number = order_data.get('number')
            
            self.logger.info(f"Procesando orden WC#{order_number} (ID: {order_id})")
            
            # Verificar si la orden ya existe en Odoo
            existing_order = self.odoo.search_records(
                'sale.order',
                [['x_woo_order_id', '=', str(order_id)]],
                limit=1
            )
            
            if existing_order:
                self.logger.info(f"Orden {order_number} ya existe en Odoo, actualizando...")
                return self.update_existing_order(existing_order[0], order_data)
            
            # Extraer datos de booking de la orden
            bookings = self.woo.extract_booking_data(order_data)
            
            if not bookings:
                self.logger.warning(f"No se encontraron bookings en orden {order_number}")
                return False
            
            # Procesar cada booking como producto/servicio
            success_count = 0
            for booking in bookings:
                if self.sync_booking_to_odoo(booking):
                    success_count += 1
            
            # Crear orden de venta en Odoo
            if success_count > 0:
                self.create_sale_order_in_odoo(order_data, bookings)
            
            self.logger.info(f"Orden {order_number} procesada: {success_count}/{len(bookings)} bookings sincronizados")
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"Error procesando orden {order_data.get('number', 'unknown')}: {e}")
            return False
    
    def sync_booking_to_odoo(self, booking_data: Dict) -> bool:
        """Sincronizar datos de booking específico con Odoo"""
        try:
            # Formatear fecha para nombre del producto
            booking_date = booking_data.get('booking_date', '')
            if isinstance(booking_date, str) and 'T' in booking_date:
                date_obj = datetime.fromisoformat(booking_date.replace('Z', '+00:00'))
                formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
            else:
                formatted_date = str(booking_date)
            
            # Crear nombre único para el producto/servicio
            product_name = f"{booking_data['product_name']} - {formatted_date}"
            if booking_data.get('persons', 1) > 1:
                product_name += f" ({booking_data['persons']} personas)"
            
            # Datos del producto/servicio en Odoo
            product_data = {
                'name': product_name,
                'sku': f"BOOKING_{booking_data['order_id']}_{booking_data['product_id']}",
                'price': booking_data['total'],
                'woo_id': f"{booking_data['order_id']}_{booking_data['product_id']}",
                'booking_date': formatted_date,
                'persons': booking_data.get('persons', 1),
                'description': f"Clase reservada desde WooCommerce\nOrden: #{booking_data['order_number']}\nFecha: {formatted_date}\nPersonas: {booking_data.get('persons', 1)}"
            }
            
            # Crear o actualizar producto en Odoo
            product_id = self.odoo.get_or_create_product(product_data)
            
            if product_id:
                self.logger.info(f"Producto creado/actualizado en Odoo: {product_name}")
                return True
            else:
                self.logger.error(f"Error creando producto en Odoo: {product_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sincronizando booking: {e}")
            return False
    
    def process_woo_customer(self, customer_data: Dict) -> bool:
        """Procesar cliente de WooCommerce y sincronizar con Odoo"""
        try:
            customer_id = customer_data.get('id')
            customer_email = customer_data.get('email')
            
            self.logger.info(f"Procesando cliente: {customer_email}")
            
            # Preparar datos del cliente para Odoo
            odoo_customer_data = {
                'name': f"{customer_data.get('first_name', '')} {customer_data.get('last_name', '')}".strip(),
                'email': customer_email,
                'phone': customer_data.get('billing', {}).get('phone', ''),
                'woo_id': customer_id
            }
            
            # Crear o actualizar cliente en Odoo
            partner_id = self.odoo.get_or_create_customer(odoo_customer_data)
            
            if partner_id:
                self.logger.info(f"Cliente sincronizado con Odoo: {customer_email}")
                return True
            else:
                self.logger.error(f"Error sincronizando cliente: {customer_email}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error procesando cliente: {e}")
            return False
    
    def create_sale_order_in_odoo(self, woo_order: Dict, bookings: List[Dict]) -> Optional[int]:
        """Crear orden de venta en Odoo basada en datos de WooCommerce"""
        try:
            # Obtener o crear cliente
            customer_data = {
                'id': woo_order.get('customer_id'),
                'email': woo_order.get('billing', {}).get('email'),
                'name': f"{woo_order.get('billing', {}).get('first_name', '')} {woo_order.get('billing', {}).get('last_name', '')}".strip(),
                'phone': woo_order.get('billing', {}).get('phone'),
                'woo_id': woo_order.get('customer_id')
            }
            
            partner_id = self.odoo.get_or_create_customer(customer_data)
            
            if not partner_id:
                self.logger.error("No se pudo crear/encontrar cliente para la orden")
                return None
            
            # Crear orden de venta
            order_data = {
                'partner_id': partner_id,
                'x_woo_order_id': woo_order.get('id'),
                'origin': f"WooCommerce #{woo_order.get('number')}",
                'date_order': woo_order.get('date_created'),
                'state': 'draft',
                'note': f"Orden importada desde WooCommerce\nFecha original: {woo_order.get('date_created')}\nTotal WC: {woo_order.get('total')}"
            }
            
            order_id = self.odoo.create_record('sale.order', order_data)
            
            if not order_id:
                self.logger.error("Error creando orden de venta en Odoo")
                return None
            
            # Agregar líneas de la orden
            for booking in bookings:
                # Buscar el producto correspondiente
                product_external_id = f"{booking['order_id']}_{booking['product_id']}"
                product = self.odoo.get_record_by_external_id('product.product', product_external_id)
                
                if product:
                    line_data = {
                        'order_id': order_id,
                        'product_id': product['id'],
                        'product_uom_qty': booking.get('quantity', 1),
                        'price_unit': booking.get('total', 0) / booking.get('quantity', 1)
                    }
                    
                    line_id = self.odoo.create_record('sale.order.line', line_data)
                    if line_id:
                        self.logger.info(f"Línea de orden creada: {booking['product_name']}")
            
            self.logger.info(f"Orden de venta creada en Odoo: {order_id}")
            return order_id
            
        except Exception as e:
            self.logger.error(f"Error creando orden de venta en Odoo: {e}")
            return None
    
    def update_existing_order(self, existing_order: Dict, woo_order: Dict) -> bool:
        """Actualizar orden existente en Odoo"""
        try:
            order_id = existing_order['id']
            
            # Actualizar campos relevantes
            update_data = {
                'note': f"Orden actualizada desde WooCommerce\nÚltima actualización: {datetime.now().isoformat()}\nTotal WC: {woo_order.get('total')}"
            }
            
            # Actualizar estado si es necesario
            woo_status = woo_order.get('status')
            if woo_status == 'completed':
                update_data['state'] = 'sale'
            elif woo_status == 'cancelled':
                update_data['state'] = 'cancel'
            
            result = self.odoo.update_record('sale.order', order_id, update_data)
            
            if result:
                self.logger.info(f"Orden actualizada en Odoo: {order_id}")
                return True
            else:
                self.logger.error(f"Error actualizando orden en Odoo: {order_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error actualizando orden existente: {e}")
            return False
    
    def scheduled_sync(self) -> None:
        """Sincronización programada (ejecutada por scheduler)"""
        try:
            self.logger.info("Iniciando sincronización programada")
            
            # Sincronizar bookings de las últimas 2 horas
            recent_bookings = self.woo.get_recent_bookings(hours=2)
            
            sync_count = 0
            for booking in recent_bookings:
                if self.sync_booking_to_odoo(booking):
                    sync_count += 1
            
            self.logger.info(f"Sincronización programada completada: {sync_count} bookings procesados")
            
        except Exception as e:
            self.logger.error(f"Error en sincronización programada: {e}")
    
    def sync_odoo_to_woo(self) -> None:
        """Sincronización desde Odoo hacia WooCommerce (bidireccional)"""
        try:
            self.logger.info("Iniciando sincronización Odoo → WooCommerce")
            
            # Buscar productos en Odoo que no tengan equivalente en WooCommerce
            # o que hayan sido actualizados recientemente
            
            # Obtener productos de Odoo creados/modificados en las últimas 24 horas
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
            
            odoo_products = self.odoo.search_records(
                'product.product',
                [
                    ['write_date', '>=', yesterday],
                    ['sale_ok', '=', True],
                    ['type', '=', 'service']
                ],
                fields=['name', 'default_code', 'list_price', 'x_woo_id', 'description']
            )
            
            sync_count = 0
            for product in odoo_products:
                if self.sync_product_to_woo(product):
                    sync_count += 1
            
            self.logger.info(f"Sincronización Odoo → WooCommerce completada: {sync_count} productos procesados")
            
        except Exception as e:
            self.logger.error(f"Error en sincronización Odoo → WooCommerce: {e}")
    
    def sync_product_to_woo(self, odoo_product: Dict) -> bool:
        """Sincronizar producto de Odoo a WooCommerce"""
        try:
            # Verificar si el producto ya existe en WooCommerce
            woo_id = odoo_product.get('x_woo_id')
            
            if woo_id and woo_id != 'False':
                # Actualizar producto existente
                existing_product = self.woo.get_product(int(woo_id))
                if existing_product:
                    update_data = {
                        'name': odoo_product['name'],
                        'regular_price': str(odoo_product['list_price']),
                        'description': odoo_product.get('description', ''),
                        'sku': odoo_product.get('default_code', '')
                    }
                    
                    result = self.woo.update_product(int(woo_id), update_data)
                    if result:
                        self.logger.info(f"Producto actualizado en WooCommerce: {odoo_product['name']}")
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error sincronizando producto a WooCommerce: {e}")
            return False
    
    def cleanup_logs(self) -> None:
        """Limpiar logs antiguos"""
        try:
            self.logger.info("Ejecutando limpieza de logs")
            # Aquí puedes implementar lógica para limpiar logs antiguos
            # o hacer mantenimiento de la base de datos si usas una
            
        except Exception as e:
            self.logger.error(f"Error en limpieza de logs: {e}")
    
    def get_sync_statistics(self) -> Dict:
        """Obtener estadísticas de sincronización"""
        try:
            # Contar registros sincronizados en las últimas 24 horas
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
            
            recent_products = self.odoo.search_records(
                'product.product',
                [
                    ['create_date', '>=', yesterday],
                    ['x_woo_id', '!=', False]
                ]
            )
            
            recent_orders = self.odoo.search_records(
                'sale.order',
                [
                    ['create_date', '>=', yesterday],
                    ['x_woo_order_id', '!=', False]
                ]
            )
            
            return {
                'products_synced_24h': len(recent_products),
                'orders_synced_24h': len(recent_orders),
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas: {e}")
            return {
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
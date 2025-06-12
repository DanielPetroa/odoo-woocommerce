#!/usr/bin/env python3
"""
Test de Conexiones - WooCommerce-Odoo Booking Sync
Valida credenciales y conectividad para ambas APIs
"""

import os
import sys
import xmlrpc.client
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import json

# Colores para output en terminal
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(title):
    """Imprime header con formato"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{title.center(60)}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'='*60}{Colors.END}")

def print_success(message):
    """Imprime mensaje de éxito"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message):
    """Imprime mensaje de error"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_warning(message):
    """Imprime mensaje de advertencia"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def print_info(message):
    """Imprime mensaje informativo"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def load_env_config():
    """Carga configuración desde variables de entorno"""
    # Intentar cargar desde .env si existe
    env_file = '.env'
    if os.path.exists(env_file):
        print_info(f"Cargando configuración desde {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"').strip("'")
    
    config = {
        # Odoo
        'ODOO_URL': os.getenv('ODOO_URL'),
        'ODOO_DB': os.getenv('ODOO_DB'),
        'ODOO_USERNAME': os.getenv('ODOO_USERNAME'),
        'ODOO_API_KEY': os.getenv('ODOO_API_KEY'),
        
        # WooCommerce
        'WOO_URL': os.getenv('WOO_URL'),
        'WOO_CONSUMER_KEY': os.getenv('WOO_CONSUMER_KEY'),
        'WOO_CONSUMER_SECRET': os.getenv('WOO_CONSUMER_SECRET'),
        
        # Seguridad
        'WEBHOOK_SECRET': os.getenv('WEBHOOK_SECRET')
    }
    
    return config

def validate_env_variables(config):
    """Valida que todas las variables requeridas estén configuradas"""
    print_header("VALIDACIÓN DE VARIABLES DE ENTORNO")
    
    required_vars = {
        'Odoo': ['ODOO_URL', 'ODOO_DB', 'ODOO_USERNAME', 'ODOO_API_KEY'],
        'WooCommerce': ['WOO_URL', 'WOO_CONSUMER_KEY', 'WOO_CONSUMER_SECRET'],
        'Seguridad': ['WEBHOOK_SECRET']
    }
    
    all_valid = True
    
    for category, vars_list in required_vars.items():
        print(f"\n{Colors.BOLD}{category}:{Colors.END}")
        for var in vars_list:
            value = config.get(var)
            if value:
                masked_value = value[:8] + "..." if len(value) > 8 else value
                print_success(f"{var}: {masked_value}")
            else:
                print_error(f"{var}: No configurada")
                all_valid = False
    
    return all_valid

def test_odoo_connection(config):
    """Testa conexión con Odoo"""
    print_header("TEST DE CONEXIÓN ODOO")
    
    try:
        # Validar URL
        url = config['ODOO_URL']
        if not url:
            print_error("ODOO_URL no configurada")
            return False
            
        if not url.startswith(('http://', 'https://')):
            print_error("ODOO_URL debe comenzar con http:// o https://")
            return False
        
        print_info(f"Conectando a: {url}")
        
        # Test de conectividad básica
        try:
            response = requests.get(f"{url}/web/database/selector", timeout=10)
            print_success(f"Servidor Odoo alcanzable (Status: {response.status_code})")
        except requests.exceptions.RequestException as e:
            print_error(f"No se puede alcanzar el servidor Odoo: {e}")
            return False
        
        # Configurar XML-RPC
        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        
        # Test de versión
        try:
            version_info = common.version()
            print_success(f"Versión Odoo: {version_info.get('server_version', 'Desconocida')}")
        except Exception as e:
            print_error(f"Error obteniendo versión: {e}")
            return False
        
        # Test de autenticación
        try:
            uid = common.authenticate(
                config['ODOO_DB'], 
                config['ODOO_USERNAME'], 
                config['ODOO_API_KEY'], 
                {}
            )
            
            if uid:
                print_success(f"Autenticación exitosa - User ID: {uid}")
                
                # Test de permisos - intentar leer modelo res.users
                models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
                try:
                    user_data = models.execute_kw(
                        config['ODOO_DB'], uid, config['ODOO_API_KEY'],
                        'res.users', 'read', [uid], 
                        {'fields': ['name', 'login']}
                    )
                    print_success(f"Usuario: {user_data[0]['name']} ({user_data[0]['login']})")
                    
                    # Test de acceso a modelos críticos
                    critical_models = ['res.partner', 'product.product', 'sale.order']
                    for model in critical_models:
                        try:
                            models.execute_kw(
                                config['ODOO_DB'], uid, config['ODOO_API_KEY'],
                                model, 'search', [[]], {'limit': 1}
                            )
                            print_success(f"Acceso a modelo '{model}': OK")
                        except Exception as e:
                            print_error(f"Sin acceso a modelo '{model}': {e}")
                            
                except Exception as e:
                    print_error(f"Error verificando permisos: {e}")
                    return False
                    
                return True
            else:
                print_error("Autenticación fallida - Verificar credenciales")
                return False
                
        except Exception as e:
            print_error(f"Error en autenticación: {e}")
            return False
            
    except Exception as e:
        print_error(f"Error general conectando a Odoo: {e}")
        return False

def test_woocommerce_connection(config):
    """Testa conexión con WooCommerce"""
    print_header("TEST DE CONEXIÓN WOOCOMMERCE")
    
    try:
        # Validar configuración
        url = config['WOO_URL']
        key = config['WOO_CONSUMER_KEY']
        secret = config['WOO_CONSUMER_SECRET']
        
        if not all([url, key, secret]):
            print_error("Credenciales WooCommerce incompletas")
            return False
        
        if not url.startswith(('http://', 'https://')):
            print_error("WOO_URL debe comenzar con http:// o https://")
            return False
            
        print_info(f"Conectando a: {url}")
        
        # Preparar autenticación
        auth = HTTPBasicAuth(key, secret)
        api_base = f"{url.rstrip('/')}/wp-json/wc/v3"
        
        # Test de conectividad básica
        try:
            response = requests.get(f"{url}/wp-json/", timeout=10)
            if response.status_code == 200:
                print_success("WordPress API alcanzable")
                
                # Verificar si WooCommerce está activo
                wp_data = response.json()
                wc_namespace = any('wc/v3' in ns.get('_links', {}).get('self', [{}])[0].get('href', '') 
                                for ns in wp_data.get('namespaces', []) if isinstance(ns, dict))
                
                if 'wc/v3' in wp_data.get('namespaces', []):
                    print_success("WooCommerce API disponible")
                else:
                    print_warning("WooCommerce API no detectada en namespaces")
                    
            else:
                print_warning(f"WordPress responde con status: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print_error(f"No se puede alcanzar WordPress: {e}")
            return False
        
        # Test de autenticación WC
        try:
            response = requests.get(f"{api_base}/system_status", auth=auth, timeout=10)
            
            if response.status_code == 200:
                print_success("Autenticación WooCommerce exitosa")
                
                # Información del sistema
                system_data = response.json()
                wc_version = system_data.get('settings', {}).get('version', 'Desconocida')
                print_success(f"Versión WooCommerce: {wc_version}")
                
                # Test de endpoints críticos
                endpoints = {
                    'products': f"{api_base}/products",
                    'orders': f"{api_base}/orders", 
                    'customers': f"{api_base}/customers"
                }
                
                for name, endpoint in endpoints.items():
                    try:
                        resp = requests.get(f"{endpoint}?per_page=1", auth=auth, timeout=10)
                        if resp.status_code == 200:
                            data = resp.json()
                            count = len(data) if isinstance(data, list) else 'N/A'
                            print_success(f"Endpoint '{name}': OK ({count} registros en muestra)")
                        else:
                            print_error(f"Endpoint '{name}': Error {resp.status_code}")
                    except Exception as e:
                        print_error(f"Endpoint '{name}': {e}")
                
                # Test específico para YITH Booking
                print_info("Verificando productos con YITH Booking...")
                try:
                    response = requests.get(
                        f"{api_base}/products", 
                        auth=auth, 
                        params={'type': 'booking', 'per_page': 5},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        booking_products = response.json()
                        if booking_products:
                            print_success(f"Productos booking encontrados: {len(booking_products)}")
                            for product in booking_products[:3]:  # Mostrar hasta 3
                                print_info(f"  - {product['name']} (ID: {product['id']})")
                        else:
                            print_warning("No se encontraron productos tipo 'booking'")
                    else:
                        print_warning(f"No se pudieron obtener productos booking: {response.status_code}")
                        
                except Exception as e:
                    print_warning(f"Error verificando productos booking: {e}")
                
                return True
                
            elif response.status_code == 401:
                print_error("Credenciales WooCommerce inválidas (401)")
                return False
            elif response.status_code == 403:
                print_error("Sin permisos para acceder a WooCommerce API (403)")
                return False
            else:
                print_error(f"Error en WooCommerce API: {response.status_code}")
                print_error(f"Respuesta: {response.text[:200]}...")
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"Error conectando a WooCommerce API: {e}")
            return False
            
    except Exception as e:
        print_error(f"Error general conectando a WooCommerce: {e}")
        return False

def test_webhook_security(config):
    """Verifica configuración de seguridad de webhooks"""
    print_header("VERIFICACIÓN DE SEGURIDAD")
    
    webhook_secret = config.get('WEBHOOK_SECRET')
    if webhook_secret:
        if len(webhook_secret) >= 16:
            print_success(f"WEBHOOK_SECRET configurado (longitud: {len(webhook_secret)})")
        else:
            print_warning("WEBHOOK_SECRET muy corto, recomendado mínimo 16 caracteres")
    else:
        print_error("WEBHOOK_SECRET no configurado")
    
    return bool(webhook_secret)

def run_comprehensive_test():
    """Ejecuta todos los tests"""
    print(f"{Colors.BOLD}🔧 WooCommerce-Odoo Booking Sync - Test de Conexiones{Colors.END}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Cargar configuración
    config = load_env_config()
    
    # Ejecutar tests
    results = {
        'env_vars': validate_env_variables(config),
        'odoo': test_odoo_connection(config),
        'woocommerce': test_woocommerce_connection(config),
        'security': test_webhook_security(config)
    }
    
    # Resumen final
    print_header("RESUMEN DE RESULTADOS")
    
    for test_name, result in results.items():
        test_display = {
            'env_vars': 'Variables de Entorno',
            'odoo': 'Conexión Odoo',
            'woocommerce': 'Conexión WooCommerce', 
            'security': 'Configuración Seguridad'
        }
        
        if result:
            print_success(f"{test_display[test_name]}: PASS")
        else:
            print_error(f"{test_display[test_name]}: FAIL")
    
    # Estado general
    all_passed = all(results.values())
    print(f"\n{Colors.BOLD}Estado General: ", end="")
    if all_passed:
        print(f"{Colors.GREEN}✅ TODOS LOS TESTS PASARON{Colors.END}")
        print_info("El sistema está listo para sincronización")
    else:
        print(f"{Colors.RED}❌ ALGUNOS TESTS FALLARON{Colors.END}")
        print_warning("Revisar configuración antes de usar en producción")
    
    return all_passed

if __name__ == "__main__":
    try:
        success = run_comprehensive_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrumpido por usuario{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error inesperado: {e}")
        sys.exit(1)
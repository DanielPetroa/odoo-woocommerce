#!/usr/bin/env python3
"""
Prueba nombres comunes de bases de datos en Odoo
"""

import xmlrpc.client
import os

# Configuración
ODOO_URL = "http://15.235.35.248:8010"
ODOO_USERNAME = "juanescobaroble@gmail.com"
ODOO_API_KEY = "41142430bfd73acd548d422cf0a90982781c5bd3"

# Nombres comunes de bases de datos en Odoo
COMMON_DB_NAMES = [
    'test',
    'demo', 
    'production',
    'prod',
    'odoo',
    'main',
    'database',
    'db',
    'aquafit',
    'aquatraining',
    'booking',
    'aquatrainingboard',
    'atb',
    'test_db',
    'odoo_test',
    'odoo18',
    'test18',
    'AQUAFIT-TEST-2025-04-21'
]

def test_database_name(db_name):
    """Prueba si una base de datos existe y se puede autenticar"""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        
        # Intentar autenticación
        uid = common.authenticate(db_name, ODOO_USERNAME, ODOO_API_KEY, {})
        
        if uid:
            return True, f"✅ Autenticación exitosa - User ID: {uid}"
        else:
            return False, "❌ Credenciales incorrectas"
            
    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg:
            return False, "❌ Base de datos no existe"
        elif "authentication" in error_msg.lower():
            return False, "❌ Error de autenticación"
        else:
            return False, f"❌ Error: {error_msg[:100]}..."

def find_correct_database():
    """Busca la base de datos correcta probando nombres comunes"""
    print("🔍 Buscando la base de datos correcta...")
    print("=" * 60)
    
    found_databases = []
    
    for db_name in COMMON_DB_NAMES:
        print(f"Probando: {db_name:<20} ... ", end="", flush=True)
        
        success, message = test_database_name(db_name)
        print(message)
        
        if success:
            found_databases.append(db_name)
    
    print("\n" + "=" * 60)
    
    if found_databases:
        print(f"🎉 ¡Bases de datos encontradas!")
        for db in found_databases:
            print(f"   ✅ {db}")
            
        recommended = found_databases[0]
        print(f"\n💡 Recomendado usar: {recommended}")
        print(f"\n📝 Actualiza tu .env:")
        print(f"ODOO_DB={recommended}")
        
        return found_databases
    else:
        print("❌ No se encontró ninguna base de datos válida")
        print("\n💡 Posibles soluciones:")
        print("   1. Verificar que el usuario 'ju' existe en Odoo")
        print("   2. Verificar que la API Key '411' es correcta")
        print("   3. Contactar al administrador de Odoo")
        print("   4. Acceder vía web: http://15.235.35.248:8010")
        
        return []

if __name__ == "__main__":
    find_correct_database()
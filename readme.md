booking-sync/
├── app.py                  # Flask app principal
├── config.py              # Configuración y variables de entorno
├── requirements.txt       # Dependencias Python
├── .env.example          # Ejemplo de variables de entorno
├── .env                  # Variables de entorno (no subir a Git)
├── .gitignore           # Archivos a ignorar en Git
├── README.md            # Documentación
├── Dockerfile           # Para containerización (opcional)
├── deploy/              # Scripts de deploy
│   ├── deploy.sh        # Script de deploy automático
│   └── supervisor.conf  # Configuración de supervisor
├── src/                 # Código fuente
│   ├── __init__.py
│   ├── clients/         # Clientes API
│   │   ├── __init__.py
│   │   ├── odoo_client.py
│   │   └── woo_client.py
│   ├── models/          # Modelos de datos
│   │   ├── __init__.py
│   │   ├── booking.py
│   │   ├── customer.py
│   │   └── product.py
│   ├── services/        # Lógica de negocio
│   │   ├── __init__.py
│   │   ├── sync_service.py
│   │   └── webhook_service.py
│   └── utils/           # Utilidades
│       ├── __init__.py
│       ├── logger.py
│       └── validators.py
├── tests/               # Tests
│   ├── __init__.py
│   ├── test_odoo_client.py
│   └── test_sync_service.py
└── logs/               # Archivos de log
    └── app.log


# WooCommerce-Odoo Booking Sync - Estado Completo del Proyecto

## 🎯 **Objetivo**
Sistema de sincronización automática entre WooCommerce (YITH Booking) y Odoo 18.0 para facturación de clases deportivas con descuentos automáticos por volumen.

## 🏗️ **Arquitectura**
```
WordPress/WooCommerce → Webhooks → Python Flask App → Odoo API
```

## 📊 **Flujo Principal**
1. **Cliente reserva clase** en WooCommerce (ej: Fit Board, 5 personas)
2. **Descuento automático** si ≥4 personas/clases (5% descuento)
3. **Webhook automático** envía datos a Python app
4. **Python procesa** y crea en Odoo:
   - Producto/servicio: "Fit Board - 2025-06-03 17:00 (5 personas)"
   - Cliente (si no existe)
   - Orden de venta
5. **Facturación** desde Odoo

## 🛠️ **Stack Técnico**
- **Backend**: Python 3.8+ + Flask
- **APIs**: WooCommerce REST API + Odoo XML-RPC
- **WordPress**: YITH Booking and Appointment
- **Odoo**: v18.0 (Sales, Invoicing)
- **Deploy**: Supervisor + Nginx en VPS

## 📁 **Estructura del Proyecto ACTUAL**
```
booking-sync/
├── app.py                  # Flask app principal ✅
├── config.py              # Variables de entorno ✅
├── requirements.txt       # Dependencias Python ✅
├── readme.md              # Documentación ✅
├── .env                   # Credenciales (configurado) ✅
├── .env.example           # Template ✅
├── .gitignore             # ✅
├── logs/                  # Carpeta de logs ✅
└── src/
    ├── __init__.py        # ✅
    ├── clients/
    │   ├── __init__.py    # ✅
    │   ├── odoo_client.py # Cliente Odoo ✅
    │   └── woo_client.py  # Cliente WooCommerce ✅
    ├── services/
    │   ├── __init__.py    # ✅
    │   └── sync_service.py # Lógica de sincronización ✅
    └── utils/
        ├── __init__.py    # ✅
        └── logger.py      # Sistema de logging ✅
```

## 🔧 **Configuración ACTUAL**

### **Odoo (FUNCIONANDO)**
- URL: `https://test.aquatrainingboard.com/odoo`
- DB: `test`
- ✅ Conexión exitosa (UID: 9)
- ✅ API Key configurada

### **WordPress (FUNCIONANDO)**
- URL: `https://aquatrainingboard.com`
- ✅ WooCommerce instalado
- ✅ YITH Booking configurado
- ✅ Descuentos por volumen funcionando (4+ clases = 5%)

### **Python App (FUNCIONANDO LOCALMENTE)**
- ✅ Flask corriendo en `http://127.0.0.1:5002`
- ✅ Conexión a Odoo exitosa
- ✅ Health check OK: `{"status": "healthy", "odoo_connection": true}`
- ✅ Scheduler iniciado

## 🔗 **Componentes Implementados**

### **config.py**
- ✅ Carga variables de `.env`
- ✅ Validación de credenciales
- ✅ Configuración por entornos

### **OdooClient** (`src/clients/odoo_client.py`)
- ✅ Autenticación XML-RPC
- ✅ Métodos: `create_record()`, `update_record()`, `search_records()`
- ✅ Funciones específicas: `create_customer()`, `create_product()`

### **WooCommerceClient** (`src/clients/woo_client.py`)
- ✅ API REST con autenticación
- ✅ Métodos: `get_orders()`, `extract_booking_data()`

### **SyncService** (`src/services/sync_service.py`)
- ✅ `process_woo_order()`: Procesa webhooks
- ✅ `sync_booking_to_odoo()`: Convierte booking en producto Odoo
- ✅ `scheduled_sync()`: Sincronización automática

### **Flask App** (`app.py`)
- ✅ Endpoints: `/health`, `/webhook/order`, `/sync/manual`
- ✅ Verificación HMAC de webhooks
- ✅ Cron jobs cada 5 minutos

### **WordPress Integration** (functions.php)
- ✅ Descuentos automáticos por volumen
- ✅ Webhooks automáticos en `woocommerce_thankyou`
- ✅ Test webhook: `?test_sync=1`

## 🚨 **PROBLEMA ACTUAL**

**CONECTIVIDAD**: WordPress está en **servidor remoto** (https://aquatrainingboard.com) pero Python está en **desarrollo local** (127.0.0.1:5002).

**SOLUCIÓN NECESARIA**: Subir Python al mismo servidor donde está WordPress.

## 🎯 **ESTADO ACTUAL DEL TESTING**

### ✅ **LO QUE FUNCIONA:**
- Python Flask app corriendo localmente
- Conexión Python ↔ Odoo exitosa
- Health check OK
- Descuentos en WooCommerce (4+ personas = 5%)
- Código WordPress agregado a functions.php

### ⏳ **PENDIENTE:**
- Subir Python app al servidor de producción
- Configurar webhooks en servidor remoto
- Testing completo del flujo end-to-end

## 🔧 **CONFIGURACIÓN PARA PRODUCCIÓN**

### **.env Producción**
```env
ENVIRONMENT=production
DEBUG=False
HOST=0.0.0.0
PORT=5000

# Odoo
ODOO_URL=https://test.aquatrainingboard.com/odoo
ODOO_DB=test
ODOO_USERNAME=email@aquatrainingboard.com
ODOO_API_KEY=api-key-real

# WooCommerce
WOO_URL=https://aquatrainingboard.com
WOO_CONSUMER_KEY=ck_key-real
WOO_CONSUMER_SECRET=cs_secret-real

WEBHOOK_SECRET=secreto-super-seguro
```

### **WordPress functions.php**
```php
define('PYTHON_SYNC_URL', 'https://aquatrainingboard.com:5000');
define('WEBHOOK_SECRET', 'secreto-super-seguro');
```

## 🚀 **PRÓXIMOS PASOS INMEDIATOS**

1. **Subir Python al servidor** donde está WordPress
2. **Configurar .env** para producción
3. **Actualizar functions.php** con URL de producción
4. **Instalar dependencias** en servidor (Python, Flask, etc.)
5. **Configurar Supervisor/Nginx** para mantener app corriendo
6. **Testing completo** del flujo

## 📋 **COMANDOS ÚTILES TESTING**

### **Health Check**
```bash
curl https://aquatrainingboard.com:5000/health
```

### **Test Webhook desde WordPress**
```
https://aquatrainingboard.com/wp-admin?test_sync=1
```

### **Logs**
```bash
tail -f logs/app.log
```

## 🔍 **INFORMACIÓN DEL SERVIDOR NECESARIA**

Para continuar necesitamos saber:
1. **Tipo de hosting** (VPS, compartido, dedicado)
2. **Acceso SSH** disponible
3. **Soporte Python** en el servidor
4. **Panel de control** usado (cPanel, Plesk, etc.)

## 📞 **CREDENCIALES Y APIS**

### **Generadas/Configuradas:**
- ✅ Odoo API Key
- ✅ WooCommerce Consumer Key/Secret

### **URLs Confirmadas:**
- WordPress: `https://aquatrainingboard.com`
- Odoo: `https://test.aquatrainingboard.com/odoo`
- Python Local: `http://127.0.0.1:5002` (funcionando)
- Python Producción: `https://aquatrainingboard.com:5000` (pendiente)

## 🧪 **TESTING REALIZADO**

- ✅ Python app inicia correctamente
- ✅ Conexión Odoo exitosa (UID: 9)
- ✅ Health check responde JSON válido
- ✅ Código WordPress agregado
- ❌ Webhook test (por conectividad local/remoto)

---

**RESUMEN**: El sistema está 95% completo y funcionando localmente. Solo falta el deploy a producción para conectar WordPress remoto con Python remoto.
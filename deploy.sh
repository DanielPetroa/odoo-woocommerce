#!/bin/bash
# Deploy script automático para WooCommerce-Odoo Booking Sync
# Uso: ./deploy.sh [--no-backup] [--skip-tests]

set -e  # Salir en caso de error

# Configuración
APP_DIR="/home/bookingsync/booking-sync"
VENV_DIR="/home/bookingsync/venv"
BACKUP_DIR="/home/bookingsync/backups"
LOG_FILE="/home/bookingsync/deploy.log"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para logging
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a $LOG_FILE
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a $LOG_FILE
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a $LOG_FILE
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a $LOG_FILE
}

# Verificar que estamos ejecutando como usuario correcto
if [[ $USER != "bookingsync" ]]; then
    error "Este script debe ejecutarse como usuario 'bookingsync'"
fi

# Verificar que estamos en el directorio correcto
if [[ ! -f "$APP_DIR/app.py" ]]; then
    error "No se encuentra app.py en $APP_DIR"
fi

# Procesar argumentos
SKIP_BACKUP=false
SKIP_TESTS=false

for arg in "$@"; do
    case $arg in
        --no-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        *)
            echo "Uso: $0 [--no-backup] [--skip-tests]"
            exit 1
            ;;
    esac
done

log "🚀 Iniciando deploy de booking-sync..."

# Crear directorio de backups si no existe
mkdir -p $BACKUP_DIR

# Backup de configuración actual
if [[ $SKIP_BACKUP == false ]]; then
    log "📦 Creando backup de configuración..."
    if [[ -f "$APP_DIR/.env" ]]; then
        cp $APP_DIR/.env $BACKUP_DIR/.env.$(date +%Y%m%d_%H%M%S)
        log "✅ Backup creado en $BACKUP_DIR"
    else
        warning "No se encontró archivo .env para backup"
    fi
fi

# Verificar estado actual del servicio
log "🔍 Verificando estado actual..."
current_status=$(sudo supervisorctl status booking-sync | awk '{print $2}' || echo "STOPPED")
info "Estado actual del servicio: $current_status"

# Actualizar código desde Git
log "📥 Actualizando código desde repositorio..."
cd $APP_DIR

# Verificar si hay cambios locales no commiteados
if [[ -n $(git status --porcelain) ]]; then
    warning "Hay cambios locales no commiteados. Creando stash..."
    git stash push -m "Deploy stash $(date '+%Y-%m-%d %H:%M:%S')"
fi

# Pull de la rama principal
git fetch origin
git checkout main
git pull origin main

log "✅ Código actualizado"

# Activar virtual environment
log "🔌 Activando virtual environment..."
if [[ ! -d "$VENV_DIR" ]]; then
    error "Virtual environment no encontrado en $VENV_DIR"
fi

source $VENV_DIR/bin/activate

# Actualizar dependencias
log "📦 Actualizando dependencias Python..."
pip install --upgrade pip
pip install -r requirements.txt

log "✅ Dependencias actualizadas"

# Test de conexiones (si no se solicita omitir)
if [[ $SKIP_TESTS == false ]]; then
    log "🔍 Ejecutando test de conexiones..."
    
    if python3 test_connections.py; then
        log "✅ Test de conexiones exitoso"
    else
        error "❌ Test de conexiones falló. Deploy abortado."
    fi
else
    warning "⚠️ Tests omitidos por parámetro --skip-tests"
fi

# Verificar archivo .env
if [[ ! -f "$APP_DIR/.env" ]]; then
    error "Archivo .env no encontrado. Crear basado en .env.example"
fi

# Validar configuración crítica
log "🔧 Validando configuración crítica..."
source $APP_DIR/.env

required_vars=("ODOO_URL" "ODOO_DB" "ODOO_USERNAME" "ODOO_API_KEY" "WOO_URL" "WOO_CONSUMER_KEY" "WOO_CONSUMER_SECRET")

for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        error "Variable requerida $var no está configurada en .env"
    fi
done

log "✅ Configuración validada"

# Crear/verificar directorio de logs
mkdir -p $APP_DIR/logs
touch $APP_DIR/logs/app.log

# Parar el servicio actual para actualizarlo
log "⏹️ Deteniendo servicio actual..."
sudo supervisorctl stop booking-sync || warning "Servicio ya estaba detenido"

# Esperar un momento para que el proceso termine completamente
sleep 3

# Verificar que no hay procesos Python del proyecto ejecutándose
pids=$(pgrep -f "python.*app.py" || true)
if [[ -n "$pids" ]]; then
    warning "Terminando procesos Python residuales..."
    echo $pids | xargs kill -9 || true
    sleep 2
fi

# Reiniciar el servicio
log "🔄 Iniciando servicio actualizado..."
sudo supervisorctl start booking-sync

# Esperar a que el servicio se inicie
log "⏳ Esperando inicio del servicio..."
sleep 10

# Verificar estado del servicio
service_status=$(sudo supervisorctl status booking-sync)
log "📊 Estado del servicio: $service_status"

if echo "$service_status" | grep -q "RUNNING"; then
    log "✅ Servicio iniciado correctamente"
else
    error "❌ Servicio no pudo iniciarse. Revisar logs."
fi

# Test de health check
log "🏥 Ejecutando health check..."
max_attempts=6
attempt=1

while [[ $attempt -le $max_attempts ]]; do
    if curl -f -s http://localhost:5000/health > /dev/null; then
        log "✅ Health check exitoso"
        break
    else
        if [[ $attempt -eq $max_attempts ]]; then
            error "❌ Health check falló después de $max_attempts intentos"
        else
            warning "Health check intento $attempt/$max_attempts falló, reintentando..."
            sleep 5
            ((attempt++))
        fi
    fi
done

# Verificar logs recientes para errores
log "📝 Verificando logs recientes..."
recent_errors=$(tail -20 $APP_DIR/logs/app.log | grep -i error || true)
if [[ -n "$recent_errors" ]]; then
    warning "Se encontraron errores recientes en logs:"
    echo "$recent_errors"
else
    log "✅ No se encontraron errores en logs recientes"
fi

# Recargar Nginx (por si hay cambios en configuración)
log "🌐 Recargando Nginx..."
sudo nginx -t && sudo systemctl reload nginx || warning "Error recargando Nginx"

# Resumen final
log "🎉 Deploy completado exitosamente!"
log "📊 Resumen:"
log "   - Código actualizado desde Git"
log "   - Dependencias actualizadas"
log "   - Servicio reiniciado y funcionando"
log "   - Health check exitoso"

# Información útil
info "🔗 URLs importantes:"
info "   - Health check: http://localhost:5000/health"
info "   - Logs: tail -f $APP_DIR/logs/app.log"
info "   - Estado: sudo supervisorctl status booking-sync"

# Opcional: mostrar últimas líneas del log
log "📝 Últimas líneas del log de aplicación:"
tail -5 $APP_DIR/logs/app.log

log "✅ Deploy finalizado con éxito en $(date)"
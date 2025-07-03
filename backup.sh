#!/bin/bash
# Script de backup para WooCommerce-Odoo Booking Sync
# Crea backups de configuración, logs y código

set -e

# Configuración
APP_DIR="/home/bookingsync/booking-sync"
BACKUP_BASE_DIR="/home/bookingsync/backups"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_BASE_DIR/$TIMESTAMP"

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Verificar que estamos ejecutando como usuario correcto
if [[ $USER != "bookingsync" ]]; then
    error "Este script debe ejecutarse como usuario 'bookingsync'"
fi

log "📦 Iniciando backup del sistema booking-sync..."

# Crear directorio de backup
mkdir -p $BACKUP_DIR

# Backup de configuración
log "🔧 Backup de configuración..."
if [[ -f "$APP_DIR/.env" ]]; then
    cp $APP_DIR/.env $BACKUP_DIR/.env
    log "✅ .env copiado"
else
    warning "Archivo .env no encontrado"
fi

# Backup de logs
log "📝 Backup de logs..."
if [[ -d "$APP_DIR/logs" ]]; then
    cp -r $APP_DIR/logs $BACKUP_DIR/
    log "✅ Logs copiados"
else
    warning "Directorio de logs no encontrado"
fi

# Backup de configuración de Supervisor
log "⚙️ Backup de configuración Supervisor..."
if [[ -f "/etc/supervisor/conf.d/booking-sync.conf" ]]; then
    sudo cp /etc/supervisor/conf.d/booking-sync.conf $BACKUP_DIR/supervisor.conf
    sudo chown bookingsync:bookingsync $BACKUP_DIR/supervisor.conf
    log "✅ Configuración de Supervisor copiada"
else
    warning "Configuración de Supervisor no encontrada"
fi

# Backup de configuración de Nginx
log "🌐 Backup de configuración Nginx..."
if [[ -f "/etc/nginx/sites-available/booking-sync" ]]; then
    sudo cp /etc/nginx/sites-available/booking-sync $BACKUP_DIR/nginx.conf
    sudo chown bookingsync:bookingsync $BACKUP_DIR/nginx.conf
    log "✅ Configuración de Nginx copiada"
else
    warning "Configuración de Nginx no encontrada"
fi

# Backup de requirements.txt
log "📋 Backup de requirements..."
if [[ -f "$APP_DIR/requirements.txt" ]]; then
    cp $APP_DIR/requirements.txt $BACKUP_DIR/
    log "✅ requirements.txt copiado"
fi

# Información del sistema
log "📊 Recopilando información del sistema..."
{
    echo "# Backup creado: $(date)"
    echo "# Sistema: $(uname -a)"
    echo "# Usuario: $(whoami)"
    echo "# Directorio: $(pwd)"
    echo ""
    echo "## Estado de servicios"
    sudo supervisorctl status booking-sync || echo "Supervisor no disponible"
    echo ""
    echo "## Uso de disco"
    df -h $APP_DIR
    echo ""
    echo "## Procesos Python"
    pgrep -af python || echo "No hay procesos Python"
    echo ""
    echo "## Variables de entorno críticas (parciales)"
    if [[ -f "$APP_DIR/.env" ]]; then
        grep -E '^(ENVIRONMENT|ODOO_URL|WOO_URL)=' $APP_DIR/.env || echo "Variables no encontradas"
    fi
} > $BACKUP_DIR/system_info.txt

log "✅ Información del sistema recopilada"

# Crear archivo de metadatos del backup
{
    echo "timestamp=$TIMESTAMP"
    echo "date=$(date)"
    echo "app_dir=$APP_DIR"
    echo "backup_dir=$BACKUP_DIR"
    echo "user=$USER"
    echo "hostname=$(hostname)"
} > $BACKUP_DIR/backup_metadata.txt

# Comprimir backup
log "🗜️ Comprimiendo backup..."
cd $BACKUP_BASE_DIR
tar -czf "backup_$TIMESTAMP.tar.gz" $TIMESTAMP/

# Verificar compresión
if [[ -f "backup_$TIMESTAMP.tar.gz" ]]; then
    backup_size=$(du -h "backup_$TIMESTAMP.tar.gz" | cut -f1)
    log "✅ Backup comprimido: backup_$TIMESTAMP.tar.gz ($backup_size)"
    
    # Remover directorio sin comprimir
    rm -rf $TIMESTAMP/
else
    error "Error creando archivo comprimido"
fi

# Limpieza de backups antiguos
log "🧹 Limpiando backups antiguos (>$RETENTION_DAYS días)..."
old_backups=$(find $BACKUP_BASE_DIR -name "backup_*.tar.gz" -mtime +$RETENTION_DAYS 2>/dev/null || true)

if [[ -n "$old_backups" ]]; then
    echo "$old_backups" | while read -r backup_file; do
        rm -f "$backup_file"
        log "🗑️ Eliminado: $(basename $backup_file)"
    done
else
    log "ℹ️ No hay backups antiguos para eliminar"
fi

# Mostrar resumen de backups existentes
log "📋 Backups disponibles:"
ls -lh $BACKUP_BASE_DIR/backup_*.tar.gz 2>/dev/null | while read -r line; do
    echo "   $line"
done || log "ℹ️ No hay backups previos"

# Información final
log "🎉 Backup completado exitosamente!"
log "📂 Ubicación: $BACKUP_BASE_DIR/backup_$TIMESTAMP.tar.gz"
log "📏 Tamaño: $backup_size"

# Opcional: mostrar contenido del backup
log "📄 Contenido del backup:"
tar -tzf $BACKUP_BASE_DIR/backup_$TIMESTAMP.tar.gz | head -20

if [[ $(tar -tzf $BACKUP_BASE_DIR/backup_$TIMESTAMP.tar.gz | wc -l) -gt 20 ]]; then
    echo "   ... y $(( $(tar -tzf $BACKUP_BASE_DIR/backup_$TIMESTAMP.tar.gz | wc -l) - 20 )) archivos más"
fi

log "✅ Backup finalizado en $(date)"
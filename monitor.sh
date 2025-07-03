#!/bin/bash
# Script de monitoreo para WooCommerce-Odoo Booking Sync
# Verifica estado del sistema y genera alertas si es necesario

# Configuración
APP_DIR="/home/bookingsync/booking-sync"
LOG_FILE="/home/bookingsync/monitoring.log"
ALERT_LOG="/home/bookingsync/alerts.log"
HEALTH_URL="http://localhost:5000/health"
MAX_MEMORY_PERCENT=80
MAX_DISK_PERCENT=85
MAX_LOAD=2.0

# Configuración de alertas (configurar según necesidades)
ENABLE_EMAIL_ALERTS=false
ADMIN_EMAIL="admin@yourdomain.com"

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Función para logging
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a $LOG_FILE
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a $LOG_FILE
    alert "WARNING: $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a $LOG_FILE
    alert "ERROR: $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a $LOG_FILE
}

alert() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $ALERT_LOG
    
    # Enviar email si está configurado
    if [[ $ENABLE_EMAIL_ALERTS == true ]] && command -v mail &> /dev/null; then
        echo "$1" | mail -s "BookingSync Alert - $(hostname)" $ADMIN_EMAIL
    fi
}

# Función para verificar si un servicio está ejecutándose
check_service() {
    local service=$1
    if sudo supervisorctl status $service | grep -q "RUNNING"; then
        return 0
    else
        return 1
    fi
}

# Función para obtener uso de memoria en porcentaje
get_memory_usage() {
    free | awk 'NR==2{printf "%.0f", $3*100/$2}'
}

# Función para obtener uso de disco en porcentaje
get_disk_usage() {
    df $APP_DIR | awk 'NR==2{print $5}' | sed 's/%//'
}

# Función para obtener load average
get_load_average() {
    uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//'
}

# Verificar estado de la aplicación
check_app_status() {
    log "🔍 Verificando estado de la aplicación..."
    
    # Verificar servicio Supervisor
    if check_service "booking-sync"; then
        log "✅ Servicio booking-sync: RUNNING"
    else
        error "❌ Servicio booking-sync no está ejecutándose"
        return 1
    fi
    
    # Verificar health check
    if curl -f -s $HEALTH_URL > /dev/null; then
        log "✅ Health check: OK"
    else
        error "❌ Health check falló - aplicación no responde"
        return 1
    fi
    
    # Verificar Nginx
    if sudo systemctl is-active nginx > /dev/null; then
        log "✅ Nginx: Activo"
    else
        error "❌ Nginx no está activo"
        return 1
    fi
    
    return 0
}

# Verificar uso de recursos
check_resources() {
    log "📊 Verificando uso de recursos..."
    
    # Memoria
    memory_usage=$(get_memory_usage)
    if [[ $memory_usage -gt $MAX_MEMORY_PERCENT ]]; then
        warning "Uso de memoria alto: ${memory_usage}% (límite: ${MAX_MEMORY_PERCENT}%)"
    else
        log "✅ Uso de memoria: ${memory_usage}%"
    fi
    
    # Disco
    disk_usage=$(get_disk_usage)
    if [[ $disk_usage -gt $MAX_DISK_PERCENT ]]; then
        warning "Uso de disco alto: ${disk_usage}% (límite: ${MAX_DISK_PERCENT}%)"
    else
        log "✅ Uso de disco: ${disk_usage}%"
    fi
    
    # Load average
    load_avg=$(get_load_average)
    if (( $(echo "$load_avg > $MAX_LOAD" | bc -l) )); then
        warning "Load average alto: $load_avg (límite: $MAX_LOAD)"
    else
        log "✅ Load average: $load_avg"
    fi
}

# Verificar logs por errores recientes
check_logs() {
    log "📝 Verificando logs por errores..."
    
    # Buscar errores en log de aplicación (últimos 100 líneas)
    if [[ -f "$APP_DIR/logs/app.log" ]]; then
        recent_errors=$(tail -100 $APP_DIR/logs/app.log | grep -i error | tail -5)
        if [[ -n "$recent_errors" ]]; then
            warning "Errores recientes encontrados en aplicación:"
            echo "$recent_errors" | while read -r line; do
                warning "  $line"
            done
        else
            log "✅ No hay errores recientes en aplicación"
        fi
    fi
    
    # Buscar errores en Nginx (últimas 50 líneas)
    if [[ -f "/var/log/nginx/booking-sync.error.log" ]]; then
        nginx_errors=$(sudo tail -50 /var/log/nginx/booking-sync.error.log 2>/dev/null | grep -v "^\s*$" | tail -3)
        if [[ -n "$nginx_errors" ]]; then
            warning "Errores recientes en Nginx:"
            echo "$nginx_errors" | while read -r line; do
                warning "  $line"
            done
        else
            log "✅ No hay errores recientes en Nginx"
        fi
    fi
}

# Verificar conectividad externa
check_connectivity() {
    log "🌐 Verificando conectividad externa..."
    
    # Verificar conexión a Odoo
    if [[ -f "$APP_DIR/.env" ]]; then
        source $APP_DIR/.env
        if [[ -n "$ODOO_URL" ]]; then
            if curl -f -s --max-time 10 "$ODOO_URL" > /dev/null; then
                log "✅ Conectividad a Odoo: OK"
            else
                warning "❌ No se puede conectar a Odoo: $ODOO_URL"
            fi
        fi
        
        # Verificar conexión a WooCommerce
        if [[ -n "$WOO_URL" ]]; then
            if curl -f -s --max-time 10 "$WOO_URL/wp-json/" > /dev/null; then
                log "✅ Conectividad a WooCommerce: OK"
            else
                warning "❌ No se puede conectar a WooCommerce: $WOO_URL"
            fi
        fi
    fi
}

# Verificar procesos Python relacionados
check_processes() {
    log "🔧 Verificando procesos..."
    
    # Buscar procesos de la aplicación
    app_processes=$(pgrep -f "python.*app.py" || true)
    if [[ -n "$app_processes" ]]; then
        process_count=$(echo "$app_processes" | wc -l)
        log "✅ Procesos de aplicación encontrados: $process_count"
        
        # Verificar uso de memoria de los procesos
        echo "$app_processes" | while read -r pid; do
            if [[ -n "$pid" ]]; then
                memory_mb=$(ps -p $pid -o rss= 2>/dev/null | awk '{print int($1/1024)}' || echo "0")
                log "  PID $pid: ${memory_mb}MB RAM"
            fi
        done
    else
        error "❌ No se encontraron procesos de aplicación"
        return 1
    fi
}

# Generar estadísticas de sincronización
generate_sync_stats() {
    log "📈 Generando estadísticas de sincronización..."
    
    if [[ -f "$APP_DIR/logs/app.log" ]]; then
        # Contar sincronizaciones exitosas hoy
        today=$(date +%Y-%m-%d)
        sync_success=$(grep "$today" $APP_DIR/logs/app.log | grep -i "sync.*success\|sincronización.*exitosa" | wc -l)
        sync_errors=$(grep "$today" $APP_DIR/logs/app.log | grep -i "sync.*error\|error.*sync" | wc -l)
        
        log "📊 Estadísticas del día:"
        log "  Sincronizaciones exitosas: $sync_success"
        log "  Errores de sincronización: $sync_errors"
        
        if [[ $sync_errors -gt 5 ]]; then
            warning "Alto número de errores de sincronización hoy: $sync_errors"
        fi
    fi
}

# Función principal
main() {
    log "🚀 Iniciando monitoreo del sistema booking-sync..."
    
    # Contadores para determinar estado general
    total_checks=0
    failed_checks=0
    
    # Verificaciones principales
    checks=(
        "check_app_status"
        "check_resources" 
        "check_logs"
        "check_connectivity"
        "check_processes"
    )
    
    for check in "${checks[@]}"; do
        ((total_checks++))
        if ! $check; then
            ((failed_checks++))
        fi
    done
    
    # Generar estadísticas
    generate_sync_stats
    
    # Estado general
    log "📋 Resumen del monitoreo:"
    log "  Verificaciones totales: $total_checks"
    log "  Verificaciones fallidas: $failed_checks"
    
    if [[ $failed_checks -eq 0 ]]; then
        log "🎉 Sistema funcionando correctamente"
        return 0
    elif [[ $failed_checks -le 2 ]]; then
        warning "⚠️ Sistema con advertencias menores ($failed_checks/$total_checks)"
        return 1
    else
        error "🚨 Sistema con problemas graves ($failed_checks/$total_checks)"
        return 2
    fi
}

# Función para mostrar ayuda
show_help() {
    echo "Uso: $0 [opciones]"
    echo ""
    echo "Opciones:"
    echo "  --quiet    Ejecutar en modo silencioso (solo errores)"
    echo "  --full     Ejecutar monitoreo completo con detalles"
    echo "  --health   Solo verificar health check"
    echo "  --help     Mostrar esta ayuda"
    echo ""
}

# Procesar argumentos
QUIET_MODE=false
FULL_MODE=false
HEALTH_ONLY=false

for arg in "$@"; do
    case $arg in
        --quiet)
            QUIET_MODE=true
            shift
            ;;
        --full)
            FULL_MODE=true
            shift
            ;;
        --health)
            HEALTH_ONLY=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Argumento desconocido: $arg"
            show_help
            exit 1
            ;;
    esac
done

# Redirigir output si está en modo silencioso
if [[ $QUIET_MODE == true ]]; then
    exec 1>/dev/null
fi

# Ejecutar solo health check si se solicita
if [[ $HEALTH_ONLY == true ]]; then
    if curl -f -s $HEALTH_URL > /dev/null; then
        echo "OK"
        exit 0
    else
        echo "FAIL"
        exit 1
    fi
fi

# Ejecutar monitoreo principal
main
exit_code=$?

# Información adicional en modo full
if [[ $FULL_MODE == true ]]; then
    log "🔧 Información adicional del sistema:"
    log "  Uptime: $(uptime)"
    log "  Espacio libre: $(df -h $APP_DIR | awk 'NR==2{print $4}')"
    log "  Última sincronización: $(grep -i "sync" $APP_DIR/logs/app.log | tail -1 | cut -d' ' -f1-2 || echo "No disponible")"
fi

exit $exit_code
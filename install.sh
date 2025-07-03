#!/bin/bash
# Script de instalación inicial para WooCommerce-Odoo Booking Sync
# Configura todo el entorno en un VPS nuevo

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuración
APP_USER="bookingsync"
APP_DIR="/home/$APP_USER/booking-sync"
REPO_URL="https://github.com/tu-usuario/booking-sync.git"  # Cambiar por tu repo
DOMAIN=""  # Se configurará interactivamente

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

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Verificar que se ejecuta como root
if [[ $EUID -ne 0 ]]; then
   error "Este script debe ejecutarse como root (usar sudo)"
fi

# Función para detectar OS
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        error "No se puede detectar el sistema operativo"
    fi
    
    log "Sistema detectado: $OS $VER"
}

# Función para actualizar sistema
update_system() {
    log "📦 Actualizando sistema..."
    
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        apt update && apt upgrade -y
    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        yum update -y
    else
        warning "OS no reconocido, omitiendo actualización automática"
    fi
}

# Función para instalar dependencias
install_dependencies() {
    log "🔧 Instalando dependencias del sistema..."
    
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        apt install -y \
            python3 \
            python3-pip \
            python3-venv \
            nginx \
            supervisor \
            git \
            curl \
            wget \
            htop \
            ufw \
            certbot \
            python3-certbot-nginx \
            bc
            
    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        yum install -y \
            python3 \
            python3-pip \
            nginx \
            supervisor \
            git \
            curl \
            wget \
            htop \
            firewalld \
            bc
    else
        error "Sistema operativo no soportado: $OS"
    fi
    
    log "✅ Dependencias instaladas"
}

# Función para crear usuario de aplicación
create_app_user() {
    log "👤 Configurando usuario de aplicación..."
    
    if id "$APP_USER" &>/dev/null; then
        warning "Usuario $APP_USER ya existe, omitiendo creación"
    else
        useradd -m -s /bin/bash $APP_USER
        usermod -aG sudo $APP_USER
        log "✅ Usuario $APP_USER creado"
    fi
    
    # Crear estructura de directorios
    sudo -u $APP_USER mkdir -p /home/$APP_USER/{scripts,backups,logs}
}

# Función para configurar firewall
setup_firewall() {
    log "🔥 Configurando firewall..."
    
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        ufw --force reset
        ufw default deny incoming
        ufw default allow outgoing
        ufw allow 22/tcp
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw --force enable
        
    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        systemctl enable firewalld
        systemctl start firewalld
        firewall-cmd --permanent --add-service=ssh
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --reload
    fi
    
    log "✅ Firewall configurado"
}

# Función para clonar repositorio
clone_repository() {
    log "📥 Clonando repositorio..."
    
    # Preguntar por URL del repositorio si no está configurada
    if [[ "$REPO_URL" == *"tu-usuario"* ]]; then
        echo -n "Ingresa la URL del repositorio Git: "
        read REPO_URL
    fi
    
    if [[ -d "$APP_DIR" ]]; then
        warning "Directorio $APP_DIR ya existe, omitiendo clonado"
    else
        sudo -u $APP_USER git clone $REPO_URL $APP_DIR
        log "✅ Repositorio clonado"
    fi
}

# Función para configurar Python environment
setup_python_env() {
    log "🐍 Configurando entorno Python..."
    
    # Crear virtual environment
    sudo -u $APP_USER python3 -m venv /home/$APP_USER/venv
    
    # Instalar dependencias
    sudo -u $APP_USER bash -c "
        source /home/$APP_USER/venv/bin/activate
        pip install --upgrade pip
        cd $APP_DIR
        pip install -r requirements.txt
    "
    
    log "✅ Entorno Python configurado"
}

# Función para configurar archivo .env
setup_env_file() {
    log "⚙️ Configurando archivo .env..."
    
    if [[ -f "$APP_DIR/.env" ]]; then
        warning "Archivo .env ya existe, omitiendo configuración automática"
        return
    fi
    
    # Crear .env basado en ejemplo
    sudo -u $APP_USER cp $APP_DIR/.env.example $APP_DIR/.env
    
    info "📝 Archivo .env creado desde plantilla"
    info "⚠️  IMPORTANTE: Editar $APP_DIR/.env con las credenciales correctas"
    info "   - ODOO_DB, ODOO_USERNAME, ODOO_API_KEY"
    info "   - WOO_CONSUMER_KEY, WOO_CONSUMER_SECRET"
    info "   - WEBHOOK_SECRET"
}

# Función para configurar Supervisor
setup_supervisor() {
    log "⚙️ Configurando Supervisor..."
    
    cat > /etc/supervisor/conf.d/booking-sync.conf << EOF
[program:booking-sync]
command=/home/$APP_USER/venv/bin/python /home/$APP_USER/booking-sync/app.py
directory=/home/$APP_USER/booking-sync
user=$APP_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/$APP_USER/booking-sync/logs/supervisor.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=3
environment=PATH="/home/$APP_USER/venv/bin"
EOF
    
    # Recargar supervisor
    systemctl enable supervisor
    systemctl start supervisor
    supervisorctl reread
    supervisorctl update
    
    log "✅ Supervisor configurado"
}

# Función para configurar Nginx
setup_nginx() {
    log "🌐 Configurando Nginx..."
    
    # Preguntar por dominio
    if [[ -z "$DOMAIN" ]]; then
        echo -n "Ingresa el dominio para el sitio (ej: booking.tudominio.com): "
        read DOMAIN
    fi
    
    # Crear configuración de Nginx
    cat > /etc/nginx/sites-available/booking-sync << EOF
# Rate limiting zone para webhooks
limit_req_zone \$binary_remote_addr zone=webhook:10m rate=30r/m;

server {
    listen 80;
    server_name $DOMAIN;
    
    # Logs
    access_log /var/log/nginx/booking-sync.access.log;
    error_log /var/log/nginx/booking-sync.error.log;
    
    # Configuración principal
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:5000/health;
        access_log off;
    }
    
    # Webhook endpoint con limitación de rate
    location /webhook {
        proxy_pass http://127.0.0.1:5000/webhook;
        
        # Rate limiting
        limit_req zone=webhook burst=10 nodelay;
        
        # Solo permitir POST
        limit_except POST {
            deny all;
        }
    }
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
}
EOF
    
    # Activar sitio
    ln -sf /etc/nginx/sites-available/booking-sync /etc/nginx/sites-enabled/
    
    # Remover sitio por defecto
    rm -f /etc/nginx/sites-enabled/default
    
    # Test y reload
    nginx -t
    systemctl enable nginx
    systemctl restart nginx
    
    log "✅ Nginx configurado para dominio: $DOMAIN"
}

# Función para instalar scripts de mantenimiento
install_scripts() {
    log "📜 Instalando scripts de mantenimiento..."
    
    # Los scripts ya están en el repositorio, solo dar permisos
    sudo -u $APP_USER chmod +x $APP_DIR/deploy.sh
    sudo -u $APP_USER chmod +x $APP_DIR/backup.sh
    sudo -u $APP_USER chmod +x $APP_DIR/monitor.sh
    
    # Crear enlaces simbólicos en directorio de scripts
    sudo -u $APP_USER ln -sf $APP_DIR/deploy.sh /home/$APP_USER/scripts/
    sudo -u $APP_USER ln -sf $APP_DIR/backup.sh /home/$APP_USER/scripts/
    sudo -u $APP_USER ln -sf $APP_DIR/monitor.sh /home/$APP_USER/scripts/
    
    log "✅ Scripts de mantenimiento instalados"
}

# Función para configurar cron jobs
setup_cron_jobs() {
    log "⏰ Configurando tareas programadas..."
    
    # Crear crontab para usuario bookingsync
    sudo -u $APP_USER bash -c "
        # Backup diario a las 2 AM
        (crontab -l 2>/dev/null; echo '0 2 * * * /home/$APP_USER/scripts/backup.sh') | crontab -
        
        # Monitoreo cada 30 minutos
        (crontab -l 2>/dev/null; echo '*/30 * * * * /home/$APP_USER/scripts/monitor.sh --quiet') | crontab -
        
        # Limpieza de logs semanalmente
        (crontab -l 2>/dev/null; echo '0 3 * * 0 find /home/$APP_USER/booking-sync/logs -name \"*.log\" -mtime +30 -delete') | crontab -
    "
    
    log "✅ Tareas programadas configuradas"
}

# Función para configurar SSL
setup_ssl() {
    log "🔒 Configurando SSL..."
    
    echo -n "¿Deseas configurar SSL con Let's Encrypt? (y/n): "
    read setup_ssl_choice
    
    if [[ $setup_ssl_choice == "y" ]] || [[ $setup_ssl_choice == "Y" ]]; then
        # Verificar que el dominio apunte al servidor
        info "Verificando configuración DNS..."
        
        # Obtener certificado
        certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || {
            warning "Error configurando SSL. Verifica que el dominio $DOMAIN apunte a este servidor"
            return 1
        }
        
        # Configurar renovación automática
        (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
        
        log "✅ SSL configurado con Let's Encrypt"
    else
        info "SSL omitido. Puedes configurarlo más tarde con: certbot --nginx -d $DOMAIN"
    fi
}

# Función para realizar test final
final_test() {
    log "🧪 Realizando test final del sistema..."
    
    # Verificar que el servicio esté ejecutándose
    sleep 5
    if supervisorctl status booking-sync | grep -q "RUNNING"; then
        log "✅ Servicio booking-sync ejecutándose"
    else
        error "❌ Servicio no está ejecutándose. Revisar logs."
    fi
    
    # Test de health check
    if curl -f -s http://localhost:5000/health > /dev/null; then
        log "✅ Health check exitoso"
    else
        warning "⚠️ Health check falló. Verificar configuración .env"
    fi
    
    # Test de conectividad externa
    if [[ -n "$DOMAIN" ]]; then
        if curl -f -s http://$DOMAIN/health > /dev/null; then
            log "✅ Acceso externo funcionando"
        else
            warning "⚠️ Acceso externo no disponible. Verificar DNS/firewall"
        fi
    fi
}

# Función principal
main() {
    log "🚀 Iniciando instalación de WooCommerce-Odoo Booking Sync"
    log "======================================================"
    
    # Verificaciones y configuración inicial
    detect_os
    update_system
    install_dependencies
    create_app_user
    setup_firewall
    
    # Instalación de la aplicación
    clone_repository
    setup_python_env
    setup_env_file
    
    # Configuración de servicios
    setup_supervisor
    setup_nginx
    
    # Scripts y automatización
    install_scripts
    setup_cron_jobs
    
    # SSL (opcional)
    setup_ssl
    
    # Test final
    final_test
    
    # Información final
    log "🎉 Instalación completada exitosamente!"
    log "======================================"
    info "📋 Próximos pasos:"
    info "   1. Editar archivo de configuración: $APP_DIR/.env"
    info "   2. Ejecutar test de conexiones: sudo -u $APP_USER $APP_DIR/test_connections.py"
    info "   3. Reiniciar servicio: supervisorctl restart booking-sync"
    info "   4. Verificar funcionamiento: curl http://$DOMAIN/health"
    info ""
    info "🔧 Comandos útiles:"
    info "   - Ver logs: sudo -u $APP_USER tail -f $APP_DIR/logs/app.log"
    info "   - Estado del servicio: supervisorctl status booking-sync"
    info "   - Deploy: sudo -u $APP_USER $APP_DIR/deploy.sh"
    info "   - Backup: sudo -u $APP_USER $APP_DIR/backup.sh"
    info "   - Monitoreo: sudo -u $APP_USER $APP_DIR/monitor.sh"
    info ""
    info "🌐 URLs importantes:"
    if [[ -n "$DOMAIN" ]]; then
        info "   - Sitio principal: http://$DOMAIN"
        info "   - Health check: http://$DOMAIN/health"
        info "   - Webhook endpoint: http://$DOMAIN/webhook/order"
    else
        info "   - Health check: http://localhost:5000/health"
    fi
}

# Mostrar ayuda
show_help() {
    echo "Script de instalación para WooCommerce-Odoo Booking Sync"
    echo ""
    echo "Uso: sudo $0 [opciones]"
    echo ""
    echo "Opciones:"
    echo "  --domain DOMAIN    Configurar dominio específico"
    echo "  --repo URL         URL del repositorio Git"
    echo "  --help             Mostrar esta ayuda"
    echo ""
    echo "Ejemplo:"
    echo "  sudo $0 --domain booking.midominio.com --repo https://github.com/miusuario/booking-sync.git"
}

# Procesar argumentos
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --repo)
            REPO_URL="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            error "Argumento desconocido: $1"
            ;;
    esac
done

# Ejecutar instalación
main
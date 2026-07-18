#!/bin/bash
# Instalador para Sistema de Búsqueda de Palabras Clave
# 1 bot cada 30 minutos desde país VPN diferente

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Búsqueda de Palabras Clave - Installer   ║${NC}"
echo -e "${BLUE}║  1 Bot Cada 30 Minutos + Mullvad VPN      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"

# Detectar distro
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    else
        echo "unknown"
    fi
}

DISTRO=$(detect_distro)
echo -e "${BLUE}Distribución: $DISTRO${NC}"

# ============================================================================
# PASO 1: Python 3
# ============================================================================
echo -e "\n${YELLOW}[1/4]${NC} Verificando Python 3..."
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓${NC} Python 3: $PY_VERSION"
else
    echo -e "${RED}✗${NC} Python 3 no instalado"
    
    case "$DISTRO" in
        fedora|centos|rhel|almalinux|rockylinux)
            sudo dnf install -y python3 python3-pip >/dev/null 2>&1
            ;;
        ubuntu|debian)
            sudo apt update >/dev/null 2>&1
            sudo apt install -y python3 python3-pip >/dev/null 2>&1
            ;;
        arch|manjaro)
            sudo pacman -S --noconfirm python python-pip >/dev/null 2>&1
            ;;
        *)
            echo -e "${RED}No se pudo instalar Python 3${NC}"
            exit 1
            ;;
    esac
fi

# ============================================================================
# PASO 2: Virtual Environment
# ============================================================================
echo -e "\n${YELLOW}[2/4]${NC} Configurando Python..."
VENV_DIR="search_env"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓${NC} Virtual environment creado"
else
    echo -e "${GREEN}✓${NC} Virtual environment existente"
fi

source "$VENV_DIR/bin/activate"

# ============================================================================
# PASO 3: Dependencias Python
# ============================================================================
echo -e "\n${YELLOW}[3/4]${NC} Instalando dependencias..."
python3 -m pip install --upgrade pip >/dev/null 2>&1 || true
python3 -m pip install requests beautifulsoup4 lxml >/dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Dependencias instaladas"
else
    echo -e "${RED}✗${NC} Error instalando dependencias"
    exit 1
fi

# ============================================================================
# PASO 4: Mullvad VPN
# ============================================================================
echo -e "\n${YELLOW}[4/4]${NC} Verificando Mullvad VPN..."

if command -v mullvad &> /dev/null; then
    echo -e "${GREEN}✓${NC} Mullvad VPN ya instalado"
else
    echo -e "${YELLOW}Instalando Mullvad VPN...${NC}"
    
    case "$DISTRO" in
        fedora|centos|rhel|almalinux|rockylinux)
            sudo dnf install -y mullvad-vpn >/dev/null 2>&1
            ;;
        ubuntu|debian)
            curl -s https://repository.mullvad.net/deb/mullvad-keyring.asc | sudo apt-key add - 2>/dev/null || true
            echo "deb https://repository.mullvad.net/deb/stable $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/mullvad.list >/dev/null
            sudo apt update >/dev/null 2>&1
            sudo apt install -y mullvad-vpn >/dev/null 2>&1
            ;;
        arch|manjaro)
            sudo pacman -S --noconfirm mullvad-vpn >/dev/null 2>&1
            ;;
        *)
            echo -e "${YELLOW}⚠️  No se pudo instalar Mullvad${NC}"
            ;;
    esac
    
    if command -v mullvad &> /dev/null; then
        echo -e "${GREEN}✓${NC} Mullvad VPN instalado"
    else
        echo -e "${YELLOW}⚠️  Mullvad no se instaló, continuando sin VPN${NC}"
    fi
fi

# ============================================================================
# Permisos
# ============================================================================
echo -e "\n${YELLOW}Configurando scripts...${NC}"
chmod +x orchestrator_30min.py 2>/dev/null || true
chmod +x bot_keyword_search.py 2>/dev/null || true
chmod +x mullvad_manager.py 2>/dev/null || true

# Crear wrapper
cat > search_bots << 'EOFWRAPPER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/search_env"

if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

python3 "$SCRIPT_DIR/orchestrator_30min.py" "$@"
EOFWRAPPER

chmod +x search_bots

echo -e "${GREEN}✓${NC} Scripts configurados"

# ============================================================================
# Resumen
# ============================================================================
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Instalación Completada ✓             ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"

echo ""
echo -e "${BLUE}📋 PRÓXIMOS PASOS:${NC}"
echo ""
echo "1️⃣  Crear archivos de credenciales:"
echo "   for i in {01..10}; do"
echo "     cp config.json.example config_bot\$i.json"
echo "     nano config_bot\$i.json"
echo "   done"
echo ""
echo "2️⃣  Verificar configuración:"
echo "   ./search_bots --list-bots"
echo ""
echo "3️⃣  Probar un bot:"
echo "   ./search_bots --bot bot_01"
echo ""
echo "4️⃣  Ver estado:"
echo "   ./search_bots --status"
echo ""
echo "5️⃣  Ejecutar TODOS los bots ahora:"
echo "   ./search_bots --run-all"
echo ""
echo "6️⃣  Iniciar scheduler (1 bot cada 30 min):"
echo "   ./search_bots --schedule"
echo ""
echo -e "${YELLOW}⚙️  COMANDOS ÚTILES:${NC}"
echo ""
echo "   # Ver todos los bots"
echo "   ./search_bots --list-bots"
echo ""
echo "   # Ver logs en tiempo real"
echo "   tail -f orchestrator_30min.log"
echo ""
echo "   # Ver resultados de búsqueda"
echo "   ls -la resultados/"
echo ""
echo "   # Ver estado de VPN"
echo "   python3 mullvad_manager.py status"
echo ""
echo "   # Ver países disponibles"
echo "   python3 mullvad_manager.py countries"
echo ""
echo -e "${YELLOW}💡 CÓMO FUNCIONA:${NC}"
echo ""
echo "   Minuto 0:   bot_01 busca 'confidencial' desde Suecia"
echo "   Minuto 30:  bot_02 busca 'urgente' desde USA"
echo "   Minuto 60:  bot_03 busca 'cambio' desde México"
echo "   ... y así cada 30 minutos"
echo ""
echo -e "${YELLOW}📁 ARCHIVOS PRINCIPALES:${NC}"
echo ""
echo "   - orchestrator_30min.py    → Orquestador (ejecuta 1 bot cada 30 min)"
echo "   - bot_keyword_search.py    → Bot que busca palabras en párrafos"
echo "   - bots_simple.json         → Config de 10 bots + palabras clave"
echo "   - mullvad_manager.py       → Gestor de VPN"
echo "   - config_botXX.json        → Credenciales (crear estos)"
echo ""
echo -e "${YELLOW}📊 CONFIGURACIÓN:${NC}"
echo ""
echo "   Editar bots_simple.json para:"
echo "   - Cambiar palabras clave a buscar"
echo "   - Cambiar URLs a buscar"
echo "   - Cambiar países VPN"
echo "   - Agregar/quitar bots"
echo ""

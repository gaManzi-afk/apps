# 🔍 Sistema de Bots - Búsqueda de Palabras en Enlaces

**Sistema completo y limpio para buscar palabras clave en URLs de intranet**

- ✅ SIN credenciales (acceso directo)
- ✅ Busca PALABRA en ENLACES (URLs)
- ✅ 1 bot cada 30 minutos
- ✅ Cada bot desde PAÍS VPN diferente
- ✅ 10 bots pre-configurados
- ✅ Compatible: Kali Linux, Ubuntu, Fedora

---

## 📦 ARCHIVOS A DESCARGAR (6 archivos principales)

```
1. bot_link_search.py          - Bot que busca palabra en URLs
2. orchestrator_links.py       - Orquestador (1 bot cada 30 min)
3. bots_links.json             - Configuración de 10 bots
4. mullvad_manager.py          - Gestor de VPN Mullvad
5. install_search.sh           - Instalador automático
6. README.md                   - Documentación completa
```

---

## 🚀 INSTALACIÓN (3 Pasos)

### Paso 1: Descargar y Preparar

```bash
# Crear carpeta
mkdir -p ~/bots_intranet
cd ~/bots_intranet

# Descargar los 6 archivos principales
# Guardarlos en ~/bots_intranet/
```

### Paso 2: Instalar Mullvad (Kali Linux)

```bash
# Opción A: Usar el instalador
bash install_search.sh

# Opción B: Manual (recomendado para Kali)
sudo curl -fsSLo /usr/share/keyrings/mullvad-keyring.asc \
  https://repository.mullvad.net/deb/mullvad-keyring.asc

echo "deb [signed-by=/usr/share/keyrings/mullvad-keyring.asc arch=$(dpkg --print-architecture)] \
  https://repository.mullvad.net/deb/stable stable main" | \
  sudo tee /etc/apt/sources.list.d/mullvad.list

sudo apt update
sudo apt install mullvad-vpn

# Verificar
mullvad --version
```

### Paso 3: Ejecutar

```bash
cd ~/bots_intranet

# Crear virtual environment
python3 -m venv search_env
source search_env/bin/activate

# Instalar dependencias
pip install requests beautifulsoup4

# Ver bots
python3 orchestrator_links.py --list-bots

# EJECUTAR (1 bot cada 30 minutos)
python3 orchestrator_links.py --schedule
```

---

## 📊 Qué Hace

```
Minuto 0:    bot_01 se conecta a VPN Suecia
             Extrae enlaces de /documentos, /noticias, /reportes
             Busca: "confidencial" en los URLs
             Resultado: lista de URLs con "confidencial"

Minuto 30:   bot_02 se conecta a VPN USA
             Extrae enlaces de /noticias, /anuncios, /admin
             Busca: "urgente" en los URLs

Minuto 60:   bot_03 se conecta a VPN México
             Busca: "cambio"
             ... y así cada 30 minutos
```

---

## ⚙️ COMANDOS PRINCIPALES

```bash
# Activar environment (siempre primero)
source search_env/bin/activate

# Listar bots configurados
python3 orchestrator_links.py --list-bots

# Ver estado (VPN, configuración)
python3 orchestrator_links.py --status

# Probar un bot
python3 orchestrator_links.py --bot bot_01

# Ejecutar todos los bots ahora (testing)
python3 orchestrator_links.py --run-all

# EJECUTAR SCHEDULER (1 bot cada 30 min)
python3 orchestrator_links.py --schedule

# Ver VPN status
mullvad status

# Ver logs
tail -f orchestrator_links.log

# Ver resultados
ls -la resultados/
cat resultados/*/enlaces_*.txt
```

---

## 📝 CONFIGURACIÓN

### Editar bots_links.json

```bash
nano bots_links.json
```

Cambiar tu intranet:

```json
{
  "base_url": "https://tu_intranet.com",    // ← Tu intranet
  
  "bots": [
    {
      "id": "bot_01",
      "pais_vpn": "se",                     // ← País VPN
      "palabra_clave": "confidencial",      // ← Tu palabra
      "urls": [                             // ← Tus URLs
        "/documentos",
        "/noticias",
        "/reportes"
      ]
    }
  ]
}
```

---

## 🌍 PAÍSES VPN DISPONIBLES

```
se = Suecia          nl = Países Bajos    tw = Taiwán
us = USA             es = España          hk = Hong Kong
mx = México          it = Italia          nz = Nueva Zelanda
co = Colombia        br = Brasil          ch = Suiza
ca = Canadá          in = India
gb = Reino Unido     sg = Singapur
de = Alemania
fr = Francia
jp = Japón
au = Australia
```

---

## ✨ QUICK START

```bash
# 1. Descargar archivos a ~/bots_intranet/

# 2. Instalar Mullvad
sudo curl -fsSLo /usr/share/keyrings/mullvad-keyring.asc \
  https://repository.mullvad.net/deb/mullvad-keyring.asc

echo "deb [signed-by=/usr/share/keyrings/mullvad-keyring.asc arch=$(dpkg --print-architecture)] \
  https://repository.mullvad.net/deb/stable stable main" | \
  sudo tee /etc/apt/sources.list.d/mullvad.list

sudo apt update && sudo apt install mullvad-vpn

# 3. Verificar
mullvad --version

# 4. Ejecutar
cd ~/bots_intranet
python3 -m venv search_env
source search_env/bin/activate
pip install requests beautifulsoup4

python3 orchestrator_links.py --schedule
```

---

**¡Sistema listo para usar! 🚀**

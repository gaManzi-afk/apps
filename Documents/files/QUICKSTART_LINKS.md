# 🔗 Búsqueda en Enlaces - Guía Simplificada

**Sistema Ultra-Simple:**
- ✅ SIN credenciales (la intranet se accede directamente)
- ✅ Busca PALABRA en URLs/ENLACES
- ✅ 1 bot cada 30 minutos
- ✅ Cada bot desde país VPN diferente

---

## 🚀 Inicio Rápido (2 Pasos)

### Paso 1: Instalar
```bash
chmod +x install_search.sh
bash install_search.sh
```

### Paso 2: Ejecutar
```bash
# Ver bots
./search_bots --list-bots

# Probar un bot
./search_bots --bot bot_01

# EJECUTAR (1 bot cada 30 min)
./search_bots --schedule
```

---

## 📊 Qué Hace

```
Minuto 0:   bot_01 se conecta a VPN Suecia
            Descarga enlaces de: /documentos, /noticias, /reportes
            Busca: "confidencial" en los URLs
            Resultado: lista de URLs que contienen "confidencial"

Minuto 30:  bot_02 se conecta a VPN USA
            Descarga enlaces de: /noticias, /anuncios, /admin
            Busca: "urgente" en los URLs
            Resultado: lista de URLs que contienen "urgente"

Minuto 60:  bot_03 se conecta a VPN México
            ... y así cada 30 minutos
```

---

## 🔧 Configuración

### Ver Configuración Actual
```bash
./search_bots --list-bots
```

### Cambiar Palabra a Buscar
```bash
nano bots_links.json

# Buscar en bot_01:
"palabra_clave": "confidencial"   # ← Cambiar aquí

# Ejemplos:
"palabra_clave": "urgente"
"palabra_clave": "privado"
"palabra_clave": "importante"
```

### Cambiar País VPN
```bash
nano bots_links.json

# En bot_01:
"pais_vpn": "se"   # ← Cambiar aquí

# Opciones: us, mx, co, ca, gb, de, fr, jp, au, nl, es, br, in, sg, etc
```

### Cambiar URLs a Buscar
```bash
nano bots_links.json

# En bot_01:
"urls": [
  "/documentos",    # ← Cambiar aquí
  "/noticias",
  "/reportes"
]
```

---

## 📁 Resultados

```bash
# Ver resultados
ls -la resultados/

# Ver contenido
cat resultados/YYYYMMDD_HHMMSS/enlaces_confidencial.txt
```

Contenido típico:
```
BÚSQUEDA EN ENLACES
Palabra clave: confidencial
Página: /documentos
Total enlaces: 45
Enlaces encontrados: 7

============================================================

ENLACES CON 'confidencial':

[1] https://intranet.empresa.com/documentos/confidencial-2024.pdf
[2] https://intranet.empresa.com/documentos/datos/confidencial-v2.doc
[3] https://intranet.empresa.com/reportes/confidencial-report.xlsx
[4] https://intranet.empresa.com/noticias/confidencial-announcement.html
[5] https://intranet.empresa.com/documentos/confidential-info.pdf
[6] https://intranet.empresa.com/admin/confidencial-settings.php
[7] https://intranet.empresa.com/archive/confidencial-2023.zip
```

---

## 🔧 Comandos

```bash
# Listar bots
./search_bots --list-bots

# Ver estado
./search_bots --status

# Probar un bot
./search_bots --bot bot_01

# Ejecutar todos (testing)
./search_bots --run-all

# Iniciar scheduler (1 bot cada 30 min)
./search_bots --schedule

# Ver logs
tail -f orchestrator_links.log
```

---

## 💻 Producción

### Screen (Fácil)
```bash
screen -S search_bots
./search_bots --schedule
# Ctrl+A, D para salir
screen -r search_bots   # Reconectar
```

### Systemd (Recomendado)
```bash
sudo nano /etc/systemd/system/search-bots.service
```

Agregar:
```ini
[Unit]
Description=Link Search Bots
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/intranet_bot
Environment="PATH=/home/ubuntu/intranet_bot/search_env/bin"
ExecStart=/home/ubuntu/intranet_bot/orchestrator_links.py --schedule
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Luego:
```bash
sudo systemctl daemon-reload
sudo systemctl enable search-bots
sudo systemctl start search-bots
sudo systemctl status search-bots
```

---

## 🎯 Ejemplo: Personalizar para tu Intranet

### Tu Intranet: https://miintranet.com

1. Editar `bots_links.json`:
```bash
nano bots_links.json
```

2. Cambiar:
```json
"base_url": "https://miintranet.com"    # ← Tu intranet
```

3. Cambiar palabras y URLs para cada bot:
```json
{
  "id": "bot_01",
  "palabra_clave": "importante",        # ← Tu palabra
  "urls": [
    "/seccion1",                        # ← Tus secciones
    "/seccion2",
    "/seccion3"
  ]
}
```

4. Ejecutar:
```bash
./search_bots --schedule
```

---

## ✨ Flujo Completo

```bash
# 1. INSTALAR
bash install_search.sh

# 2. EDITAR CONFIGURACIÓN
nano bots_links.json
# Cambiar:
#   - base_url (tu intranet)
#   - palabras_clave para cada bot
#   - urls a buscar
#   - pais_vpn (si lo deseas)

# 3. VER CONFIGURACIÓN
./search_bots --list-bots

# 4. PROBAR
./search_bots --run-all
tail -f orchestrator_links.log

# 5. EJECUTAR PARA SIEMPRE
./search_bots --schedule

# ✓ CADA 30 MINUTOS:
# bot_01 desde Suecia busca "tu_palabra1" en /url1, /url2, /url3
# bot_02 desde USA busca "tu_palabra2" en /url4, /url5, /url6
# ... etc cada 30 min
```

---

## 📋 Diferencias vs Versión Anterior

| Característica | Anterior | Nueva |
|---|---|---|
| **Credenciales** | ✅ Requería | ❌ NO requiere |
| **Acceso Intranet** | Login manual | Acceso directo |
| **Qué busca** | Párrafos completos | SOLO URLs/enlaces |
| **Búsqueda** | Palabra en contenido | Palabra en URLs |
| **Complejidad** | Media | Muy simple |

---

## 🎯 Casos de Uso

### Monitorear documentos confidenciales
```json
"palabra_clave": "confidencial"
"urls": ["/documentos", "/reportes", "/archivos"]
```

### Seguir proyectos urgentes
```json
"palabra_clave": "urgente"
"urls": ["/noticias", "/anuncios", "/alertas"]
```

### Buscar políticas de cambio
```json
"palabra_clave": "cambio"
"urls": ["/politicas", "/documentos", "/procedimientos"]
```

---

## 🐛 Troubleshooting

### Bot no se ejecuta
```bash
tail -f orchestrator_links.log
./search_bots --bot bot_01
```

### No encuentra enlaces
1. Verificar que la URL es correcta
2. Verificar que hay enlaces en esa página
3. Ver ejemplo: `cat resultados/*/enlaces_*.txt`

### VPN no conecta
```bash
python3 mullvad_manager.py status
python3 mullvad_manager.py countries
```

---

## 📚 Referencia

```bash
# Instalar
bash install_search.sh

# Editar config
nano bots_links.json

# Listar
./search_bots --list-bots

# Probar
./search_bots --run-all

# Ejecutar
./search_bots --schedule

# Ver logs
tail -f orchestrator_links.log

# Ver resultados
ls -la resultados/
cat resultados/*/enlaces_*.txt
```

---

¡Listo! Sistema simple, sin credenciales, busca en enlaces cada 30 minutos desde países VPN diferentes.

# ❓ ¿Mullvad Necesita Instalación?

## Respuesta Corta

**SÍ, Mullvad necesita estar instalado en el sistema Linux.**

Pero:
- ✅ El instalador lo hace automáticamente
- ✅ Es GRATIS
- ✅ NO requiere credenciales
- ✅ Se usa automáticamente (sin configuración manual)

---

## 📋 Flujo de Instalación

```
bash install_search.sh
    ↓
Instala Python 3 (si falta)
    ↓
Instala Virtual Environment
    ↓
Instala Mullvad VPN (automáticamente)
    ↓
Scripts configurados y listos
    ↓
./search_bots --schedule
```

---

## 🔧 ¿Qué Hace el Instalador?

```bash
bash install_search.sh
```

Instala automáticamente:

### En Ubuntu:
```bash
curl -s https://repository.mullvad.net/deb/mullvad-keyring.asc | sudo apt-key add -
echo "deb https://repository.mullvad.net/deb/stable $(lsb_release -cs) main" | \
  sudo tee /etc/apt/sources.list.d/mullvad.list
sudo apt update
sudo apt install -y mullvad-vpn
```

### En Fedora:
```bash
sudo dnf install -y mullvad-vpn
```

### En Arch:
```bash
sudo pacman -S --noconfirm mullvad-vpn
```

---

## ✅ Después de Instalar

**Ya está listo, NO necesitas hacer nada más.**

El bot automatiza TODO:

```python
# El orquestador hace esto automáticamente:

# Minuto 0:
mullvad relay set location se    # Conectar a Suecia
mullvad connect                   # Activar VPN

# Minuto 30:
mullvad relay set location us    # Cambiar a USA
mullvad connect                   # Activar VPN

# Minuto 60:
mullvad relay set location mx    # Cambiar a México
mullvad connect
```

**TÚ NO haces nada**, el bot lo hace automáticamente.

---

## 🎯 Verificación Rápida

Después de instalar, verificar que Mullvad funciona:

```bash
# Ver estado
mullvad status

# Ver países disponibles
mullvad relay list

# Conectar a Suecia (prueba)
mullvad relay set location se
mullvad connect

# Ver IP (debe ser de Suecia)
curl ifconfig.me

# Desconectar
mullvad disconnect
```

---

## 📊 Comparación: Con VPN vs Sin VPN

### SIN VPN (si no instalas Mullvad)

```
Tu sistema → Intranet
IP aparente: Tu IP real (ej: 203.x.x.x Colombia)

Resultado:
- Todas las búsquedas desde MISMA IP
- La intranet ve siempre desde Colombia
- No es lo que quieres
```

### CON VPN (instala Mullvad)

```
Tu sistema → Mullvad → Intranet

Minuto 0:
  IP aparente: Suecia (185.x.x.x)

Minuto 30:
  IP aparente: USA (64.x.x.x)

Minuto 60:
  IP aparente: México (201.x.x.x)

Resultado:
- Cada bot desde IP diferente
- Parece que hay 10 usuarios en países diferentes
- Exactamente lo que quieres
```

---

## ⚡ Alternativa: Sin VPN

Si NO quieres VPN, simplemente:

```bash
# 1. No ejecutar install_search.sh
# 2. Instalar solo dependencias Python:
python3 -m venv search_env
source search_env/bin/activate
pip install requests beautifulsoup4

# 3. Editar orchestrator_links.py:
# Cambiar: self.usar_vpn = True
# A:       self.usar_vpn = False

# 4. Ejecutar
python3 orchestrator_links.py --schedule
```

**Pero entonces:**
- ✗ Todas las búsquedas desde tu IP real
- ✗ Pierdes el beneficio de países diferentes
- ✗ La intranet verá 10 bots desde misma IP

---

## 🔐 ¿Mullvad Requiere Credenciales?

**NO. Mullvad es completamente gratis y sin login.**

```bash
# No necesitas:
mullvad login usuario@ejemplo.com
mullvad password mi_contraseña

# Solo funciona:
mullvad connect                    # Conectar (sin credenciales)
mullvad disconnect                 # Desconectar
mullvad relay set location se     # Cambiar país
mullvad status                     # Ver estado
```

---

## 📋 Checklist: ¿Tiene Mullvad Instalado?

### En Ubuntu:
```bash
# Verificar
mullvad --version

# Si no está instalado, verás:
# mullvad: command not found

# Entonces:
bash install_search.sh    # Lo instala automáticamente
```

### En Fedora:
```bash
mullvad --version
# Si no existe, el instalador lo instala
```

---

## 🎯 Resumen Final

| Pregunta | Respuesta |
|----------|-----------|
| ¿Mullvad necesita instalación? | ✅ Sí |
| ¿Lo instala el script? | ✅ Sí, automáticamente |
| ¿Necesita credenciales? | ❌ No, es gratis |
| ¿Es obligatorio? | ✅ Sí, para IP diferente |
| ¿Costo? | ✅ Gratis |
| ¿Configuración manual? | ❌ No, el bot lo hace todo |

---

## 🚀 Instalación Completa (1 Comando)

```bash
bash install_search.sh
```

Esto hace TODO:
1. Instala Python 3
2. Instala Virtual Environment
3. **Instala Mullvad VPN automáticamente**
4. Instala dependencias Python
5. Configura scripts
6. ¡Listo para usar!

---

## 🔄 Después de Instalar

```bash
# Solo ejecutas:
./search_bots --schedule

# El bot automáticamente:
# - Conecta a Mullvad
# - Cambia de país cada 30 min
# - Busca palabras en URLs
# - Guarda resultados
```

---

## ❌ Si NO Quieres VPN

Si prefieres NO usar VPN (todas las búsquedas desde tu IP real):

1. No ejecutes install_search.sh
2. Instala solo Python:
   ```bash
   pip install requests beautifulsoup4
   ```
3. Edita orchestrator_links.py:
   ```python
   # Cambiar línea 32:
   self.usar_vpn = False  # ← Así NO usa VPN
   ```
4. Ejecuta:
   ```bash
   python3 orchestrator_links.py --schedule
   ```

**Pero pierdes el beneficio de IPs diferentes.**

---

## ✅ Respuesta a Tu Pregunta

**No, no se conecta "solo" a la VPN.**

**Lo que pasa:**
1. Mullvad NECESITA estar instalado (el script lo hace)
2. El bot lo usa automáticamente
3. No requiere configuración manual
4. Todo es automático

---

¿Vas a instalar con VPN o prefieres sin VPN?

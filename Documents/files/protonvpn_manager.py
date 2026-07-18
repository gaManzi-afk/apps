#!/usr/bin/env python3
"""
ProtonVPN Manager
Controla ProtonVPN para cambiar de país automáticamente

Uso:
    vpn = ProtonVPNManager()
    vpn.connect_to_country('se')    # Conectar a Suecia
    vpn.get_current_ip()            # Obtener IP
    vpn.disconnect()                # Desconectar
"""

import logging
import subprocess
import time
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProtonVPNManager:
    """Manager para ProtonVPN"""
    
    def __init__(self):
        """Inicializar ProtonVPN Manager"""
        self.connected = False
        self.current_country = None
        self.current_ip = None
        
        # Mapeo de códigos de país
        self.country_names = {
            'se': 'Sweden',
            'us': 'United States',
            'mx': 'Mexico',
            'co': 'Colombia',
            'ca': 'Canada',
            'gb': 'United Kingdom',
            'de': 'Germany',
            'fr': 'France',
            'jp': 'Japan',
            'au': 'Australia',
            'nl': 'Netherlands',
            'es': 'Spain',
            'it': 'Italy',
            'br': 'Brazil',
            'in': 'India',
            'sg': 'Singapore',
            'tw': 'Taiwan',
            'hk': 'Hong Kong',
            'nz': 'New Zealand',
            'ch': 'Switzerland',
            'ro': 'Romania',
        }
        
        logger.info("ProtonVPN Manager inicializado")
    
    def _run_command(self, cmd) -> str:
        """Ejecuta comando y retorna output"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.stdout + result.stderr
        except Exception as e:
            logger.error(f"Error ejecutando comando: {e}")
            return ""
    
    def get_status(self) -> dict:
        """Obtiene estado de ProtonVPN"""
        try:
            output = self._run_command("protonvpn status")
            
            connected = "Connected to" in output
            
            # Extraer IP
            ip_match = re.search(r'IP: (\d+\.\d+\.\d+\.\d+)', output)
            ip = ip_match.group(1) if ip_match else "Desconocida"
            
            return {
                'connected': connected,
                'ip': ip,
                'output': output
            }
        except Exception as e:
            logger.error(f"Error obteniendo status: {e}")
            return {'connected': False, 'ip': 'Error', 'output': ''}
    
    def connect_to_country(self, country_code: str) -> bool:
        """
        Conecta a un país específico
        
        Args:
            country_code: Código de país (se, us, mx, etc)
        
        Returns:
            True si se conectó, False si falló
        """
        try:
            country_name = self.country_names.get(country_code.lower(), country_code)
            
            logger.info(f"Conectando a {country_name}...")
            
            # Desconectar primero si está conectado
            output = self._run_command("protonvpn status")
            if "Connected to" in output:
                logger.info("Desconectando de VPN anterior...")
                self._run_command("protonvpn disconnect")
                time.sleep(2)
            
            # Conectar al país
            cmd = f"protonvpn connect --country {country_code.upper()}"
            output = self._run_command(cmd)
            
            if "Connected to" in output or "Connecting to" in output:
                time.sleep(3)  # Esperar a que conecte
                
                # Verificar conexión
                status = self.get_status()
                if status['connected']:
                    self.current_country = country_code
                    self.current_ip = status['ip']
                    self.connected = True
                    logger.info(f"✓ Conectado a {country_name} - IP: {self.current_ip}")
                    return True
                else:
                    logger.warning(f"No se confirmó conexión a {country_name}")
                    return False
            else:
                logger.error(f"Error conectando a {country_name}")
                return False
        
        except Exception as e:
            logger.error(f"Error conectando a VPN: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Desconecta de VPN"""
        try:
            logger.info("Desconectando de VPN...")
            output = self._run_command("protonvpn disconnect")
            
            time.sleep(2)
            
            self.connected = False
            self.current_country = None
            logger.info("✓ Desconectado de VPN")
            return True
        
        except Exception as e:
            logger.error(f"Error desconectando: {e}")
            return False
    
    def get_current_ip(self) -> str:
        """Obtiene IP actual"""
        try:
            status = self.get_status()
            return status['ip']
        except:
            return "Desconocida"
    
    def list_countries(self) -> list:
        """Lista países disponibles"""
        return list(self.country_names.keys())


if __name__ == '__main__':
    import sys
    
    vpn = ProtonVPNManager()
    
    if len(sys.argv) < 2:
        print("Uso: python3 protonvpn_manager.py <comando> [args]")
        print("\nComandos:")
        print("  status                    - Ver estado")
        print("  connect <país>            - Conectar a país (se, us, mx, etc)")
        print("  disconnect                - Desconectar")
        print("  countries                 - Listar países")
        print("  ip                        - Ver IP actual")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == 'status':
        status = vpn.get_status()
        print(f"Conectado: {status['connected']}")
        print(f"IP: {status['ip']}")
    
    elif cmd == 'connect' and len(sys.argv) > 2:
        country = sys.argv[2]
        vpn.connect_to_country(country)
    
    elif cmd == 'disconnect':
        vpn.disconnect()
    
    elif cmd == 'countries':
        print("Países disponibles:")
        for code, name in sorted(vpn.country_names.items()):
            print(f"  {code} = {name}")
    
    elif cmd == 'ip':
        print(f"IP: {vpn.get_current_ip()}")
    
    else:
        print(f"Comando desconocido: {cmd}")
        sys.exit(1)

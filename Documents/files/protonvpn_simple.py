#!/usr/bin/env python3
"""
ProtonVPN Simple Manager
Solo usa: protonvpn connect
"""

import logging
import subprocess
import time
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProtonVPNSimple:
    """Manager simple para ProtonVPN"""
    
    def __init__(self):
        logger.info("ProtonVPN Simple Manager inicializado")
    
    def _run_command(self, cmd) -> str:
        """Ejecuta comando"""
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
            logger.error(f"Error: {e}")
            return ""
    
    def connect(self) -> bool:
        """Conecta a ProtonVPN (servidor más rápido automáticamente)"""
        try:
            logger.info("Conectando a ProtonVPN...")
            output = self._run_command("protonvpn connect")
            
            if "Connected to" in output or "Connecting to" in output:
                time.sleep(3)
                
                # Obtener ubicación
                status = self._run_command("protonvpn status")
                logger.info(f"Status: {status}")
                
                # Extraer servidor y país
                server_match = re.search(r'Connected to (.+)', status)
                ip_match = re.search(r'IP: (\d+\.\d+\.\d+\.\d+)', status)
                
                server = server_match.group(1) if server_match else "Desconocido"
                ip = ip_match.group(1) if ip_match else "Desconocida"
                
                logger.info(f"✓ Conectado a: {server}")
                logger.info(f"✓ IP: {ip}")
                return True
            else:
                logger.error("No se pudo conectar")
                return False
        
        except Exception as e:
            logger.error(f"Error conectando: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Desconecta de ProtonVPN"""
        try:
            logger.info("Desconectando...")
            self._run_command("protonvpn disconnect")
            time.sleep(2)
            logger.info("✓ Desconectado")
            return True
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
    
    def get_status(self) -> dict:
        """Obtiene estado"""
        try:
            output = self._run_command("protonvpn status")
            connected = "Connected to" in output
            
            server_match = re.search(r'Connected to (.+)', output)
            ip_match = re.search(r'IP: (\d+\.\d+\.\d+\.\d+)', output)
            
            server = server_match.group(1) if server_match else "Desconectado"
            ip = ip_match.group(1) if ip_match else "Desconocida"
            
            return {
                'connected': connected,
                'server': server,
                'ip': ip
            }
        except:
            return {'connected': False, 'server': 'Error', 'ip': 'Error'}


if __name__ == '__main__':
    vpn = ProtonVPNSimple()
    
    # Conectar
    vpn.connect()
    time.sleep(2)
    
    # Ver estado
    status = vpn.get_status()
    print(f"\nConectado: {status['connected']}")
    print(f"Servidor: {status['server']}")
    print(f"IP: {status['ip']}")

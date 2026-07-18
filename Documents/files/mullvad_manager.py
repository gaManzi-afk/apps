#!/usr/bin/env python3
"""
Mullvad Manager - Gestor de VPN para cambiar entre países
Permite ejecutar bots con diferentes IPs automáticamente

Requiere:
    - Mullvad VPN instalado (sudo apt install mullvad-vpn en Ubuntu)
    - Ejecutable 'mullvad' en PATH
"""

import subprocess
import time
import logging
import json
from pathlib import Path
from typing import List, Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mullvad_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MullvadManager:
    """Gestor de conexiones Mullvad VPN"""
    
    def __init__(self, cache_countries=True):
        """
        Args:
            cache_countries: Cachear lista de países para evitar llamadas repetidas
        """
        self.cache_file = Path('mullvad_countries_cache.json')
        self.cache_countries = cache_countries
        self._countries_cache = None
        
        # Verificar que mullvad está instalado
        if not self._check_mullvad_installed():
            raise RuntimeError(
                "Mullvad VPN no está instalado.\n"
                "Ubuntu/Debian: sudo apt install mullvad-vpn\n"
                "Fedora: sudo dnf install mullvad-vpn\n"
                "Arch: sudo pacman -S mullvad-vpn"
            )
        
        logger.info("Mullvad Manager inicializado")
    
    def _check_mullvad_installed(self) -> bool:
        """Verifica si mullvad está instalado"""
        try:
            subprocess.run(
                ['mullvad', '--version'],
                capture_output=True,
                timeout=5
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def _run_mullvad_cmd(self, cmd: List[str], timeout=30) -> str:
        """Ejecuta comando mullvad y retorna output"""
        try:
            result = subprocess.run(
                ['mullvad'] + cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout ejecutando: mullvad {' '.join(cmd)}")
            return ""
        except Exception as e:
            logger.error(f"Error ejecutando mullvad: {e}")
            return ""
    
    def get_status(self) -> Dict:
        """Obtiene estado actual de Mullvad"""
        try:
            output = self._run_mullvad_cmd(['status'])
            
            return {
                'status': output,
                'connected': 'Connected' in output or 'Conectado' in output,
                'country': self._extract_country_from_status(output),
                'ip': self._extract_ip_from_status(output)
            }
        except Exception as e:
            logger.error(f"Error obteniendo estado: {e}")
            return {'status': 'ERROR', 'connected': False}
    
    def _extract_country_from_status(self, status_output: str) -> Optional[str]:
        """Extrae país del output de estado"""
        try:
            for line in status_output.split('\n'):
                if 'Country' in line or 'País' in line:
                    return line.split(':')[-1].strip()
        except:
            pass
        return None
    
    def _extract_ip_from_status(self, status_output: str) -> Optional[str]:
        """Extrae IP del output de estado"""
        try:
            for line in status_output.split('\n'):
                if 'IP' in line:
                    parts = line.split(':')
                    if len(parts) > 1:
                        return parts[-1].strip()
        except:
            pass
        return None
    
    def connect(self) -> bool:
        """Conecta a Mullvad (ubicación automática)"""
        logger.info("Conectando a Mullvad...")
        self._run_mullvad_cmd(['connect'])
        
        # Esperar conexión
        for i in range(30):
            status = self.get_status()
            if status['connected']:
                logger.info(f"✓ Conectado a {status.get('country', 'VPN')}")
                logger.info(f"  IP: {status.get('ip', 'desconocida')}")
                return True
            time.sleep(1)
        
        logger.error("No se pudo conectar a Mullvad")
        return False
    
    def disconnect(self) -> bool:
        """Desconecta de Mullvad"""
        logger.info("Desconectando de Mullvad...")
        self._run_mullvad_cmd(['disconnect'])
        time.sleep(2)
        
        status = self.get_status()
        if not status['connected']:
            logger.info("✓ Desconectado")
            return True
        else:
            logger.warning("No se pudo desconectar")
            return False
    
    def get_available_countries(self, force_refresh=False) -> List[str]:
        """Obtiene lista de países disponibles en Mullvad"""
        
        # Usar caché si está disponible
        if self.cache_countries and not force_refresh and self._countries_cache:
            return self._countries_cache
        
        if self.cache_file.exists() and not force_refresh:
            try:
                with open(self.cache_file, 'r') as f:
                    self._countries_cache = json.load(f)
                    logger.info(f"Países cargados desde caché: {len(self._countries_cache)} países")
                    return self._countries_cache
            except:
                pass
        
        # Obtener desde Mullvad
        logger.info("Obteniendo lista de países desde Mullvad...")
        try:
            output = self._run_mullvad_cmd(['relay', 'list'], timeout=10)
            
            countries = []
            for line in output.split('\n'):
                # Mullvad output típico: "  se - Sweden"
                if line.strip() and len(line.split()) >= 2:
                    parts = line.split()
                    if len(parts[0]) == 2:  # Código país (2 letras)
                        country_code = parts[0]
                        country_name = ' '.join(parts[1:])
                        countries.append(country_code)
            
            countries = list(set(countries))  # Remover duplicados
            
            if countries:
                # Guardar en caché
                with open(self.cache_file, 'w') as f:
                    json.dump(countries, f)
                
                self._countries_cache = countries
                logger.info(f"✓ {len(countries)} países disponibles")
                return countries
            else:
                logger.warning("No se pudieron parsear países del output de Mullvad")
                return []
        
        except Exception as e:
            logger.error(f"Error obteniendo países: {e}")
            return []
    
    def connect_to_country(self, country_code: str) -> bool:
        """
        Conecta a un país específico
        
        Args:
            country_code: Código de país (ej: 'se', 'us', 'mx', 'co')
        
        Returns:
            True si conectó exitosamente
        """
        country_code = country_code.lower()
        logger.info(f"Conectando a {country_code.upper()}...")
        
        # Establecer país
        self._run_mullvad_cmd(['relay', 'set', 'location', country_code])
        time.sleep(2)
        
        # Conectar
        self._run_mullvad_cmd(['connect'])
        
        # Esperar conexión
        for i in range(30):
            status = self.get_status()
            if status['connected']:
                logger.info(f"✓ Conectado a {country_code.upper()}")
                logger.info(f"  IP: {status.get('ip', 'desconocida')}")
                return True
            time.sleep(1)
        
        logger.error(f"No se pudo conectar a {country_code.upper()}")
        return False
    
    def rotate_country(self, countries: List[str] = None) -> Optional[str]:
        """
        Conecta a un país aleatorio de la lista
        
        Args:
            countries: Lista de códigos de país. Si None, usa todos disponibles.
        
        Returns:
            Código del país conectado, o None si falló
        """
        import random
        
        if countries is None:
            countries = self.get_available_countries()
        
        if not countries:
            logger.error("No hay países disponibles")
            return None
        
        country = random.choice(countries)
        if self.connect_to_country(country):
            return country
        return None
    
    def get_current_country(self) -> Optional[str]:
        """Obtiene país actual conectado"""
        status = self.get_status()
        return status.get('country')
    
    def get_current_ip(self) -> Optional[str]:
        """Obtiene IP actual"""
        status = self.get_status()
        return status.get('ip')
    
    def is_connected(self) -> bool:
        """Verifica si está conectado a VPN"""
        status = self.get_status()
        return status.get('connected', False)


# Funciones helper
def connect_to_vpn(country_code: str = None) -> bool:
    """Helper: conecta a VPN (país específico o automático)"""
    try:
        manager = MullvadManager()
        
        if country_code:
            return manager.connect_to_country(country_code)
        else:
            return manager.connect()
    except Exception as e:
        logger.error(f"Error conectando: {e}")
        return False


def disconnect_from_vpn() -> bool:
    """Helper: desconecta de VPN"""
    try:
        manager = MullvadManager()
        return manager.disconnect()
    except Exception as e:
        logger.error(f"Error desconectando: {e}")
        return False


def get_vpn_status() -> Dict:
    """Helper: obtiene estado actual de VPN"""
    try:
        manager = MullvadManager()
        return manager.get_status()
    except Exception as e:
        logger.error(f"Error obteniendo estado: {e}")
        return {'status': 'ERROR', 'connected': False}


if __name__ == '__main__':
    # Ejemplo de uso
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python3 mullvad_manager.py <comando> [args]")
        print("\nComandos:")
        print("  status                    - Mostrar estado actual")
        print("  connect [país]            - Conectar a país (ej: 'se', 'us')")
        print("  disconnect                - Desconectar")
        print("  countries                 - Listar países disponibles")
        print("  rotate [país1,país2,...]  - Conectar a país aleatorio")
        sys.exit(1)
    
    cmd = sys.argv[1].lower()
    
    try:
        manager = MullvadManager()
        
        if cmd == 'status':
            status = manager.get_status()
            print(json.dumps(status, indent=2))
        
        elif cmd == 'connect':
            country = sys.argv[2] if len(sys.argv) > 2 else None
            if country:
                manager.connect_to_country(country)
            else:
                manager.connect()
        
        elif cmd == 'disconnect':
            manager.disconnect()
        
        elif cmd == 'countries':
            countries = manager.get_available_countries()
            print(f"Países disponibles ({len(countries)}):")
            for country in sorted(countries):
                print(f"  {country.upper()}")
        
        elif cmd == 'rotate':
            allowed = None
            if len(sys.argv) > 2:
                allowed = sys.argv[2].split(',')
            country = manager.rotate_country(allowed)
            if country:
                print(f"Conectado a: {country.upper()}")
        
        else:
            print(f"Comando desconocido: {cmd}")
            sys.exit(1)
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

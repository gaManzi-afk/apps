#!/usr/bin/env python3
"""
Orquestador Simple v2 - Sin Credenciales, Busca en Enlaces
1 Bot Cada 30 Minutos, Busca Palabra en URLs

Uso:
    python3 orchestrator_links.py                 # Ejecuta continuamente
    python3 orchestrator_links.py --run-all       # Ejecuta todos ahora
    python3 orchestrator_links.py --list-bots     # Lista bots
    python3 orchestrator_links.py --bot bot_01    # Ejecuta bot específico
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
from argparse import ArgumentParser
import sys

from bot_link_search import LinkBot

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('orchestrator_links.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LinksOrchestrator:
    """Orquestador: 1 bot cada 30 minutos, busca en enlaces"""
    
    def __init__(self, config_file='bots_links.json'):
        self.config_file = Path(config_file)
        self.config = self._load_config()
        
        self.base_url = self.config.get('base_url')
        self.bots = self.config.get('bots', [])
        self.intervalo = self.config.get('intervalo_minutos', 30)
        
        # Gestor VPN
        try:
            from mullvad_manager import MullvadManager
            self.vpn = MullvadManager()
            self.usar_vpn = True
            logger.info("✓ Mullvad VPN Manager inicializado")
        except Exception as e:
            logger.warning(f"VPN no disponible: {e}")
            self.vpn = None
            self.usar_vpn = False
        
        logger.info(f"Orquestador inicializado: {len(self.bots)} bots, intervalo {self.intervalo} min")
    
    def _load_config(self) -> Dict:
        if not self.config_file.exists():
            logger.error(f"Archivo no encontrado: {self.config_file}")
            return {}
        
        with open(self.config_file, 'r') as f:
            return json.load(f)
    
    def _connect_vpn(self, bot_id: str, country: str) -> bool:
        """Conecta a VPN"""
        if not self.vpn:
            return True
        
        logger.info(f"[{bot_id}] Conectando a VPN: {country.upper()}")
        
        try:
            if self.vpn.connect_to_country(country):
                time.sleep(2)
                ip = self.vpn.get_current_ip()
                logger.info(f"[{bot_id}] ✓ IP actual: {ip}")
                return True
            else:
                logger.error(f"[{bot_id}] Error conectando a VPN")
                return False
        except Exception as e:
            logger.error(f"[{bot_id}] Error VPN: {e}")
            return False
    
    def execute_bot(self, bot_id: str) -> bool:
        """
        Ejecuta un bot específico
        
        Returns:
            True si fue exitoso
        """
        # Buscar configuración del bot
        bot_config = None
        for bot in self.bots:
            if bot['id'] == bot_id:
                bot_config = bot
                break
        
        if not bot_config:
            logger.error(f"Bot no encontrado: {bot_id}")
            return False
        
        if not bot_config.get('habilitado', True):
            logger.info(f"[{bot_id}] Bot deshabilitado, saltando")
            return False
        
        bot_nombre = bot_config.get('nombre', bot_id)
        logger.info(f"\n{'='*60}")
        logger.info(f"Ejecutando: {bot_nombre} ({bot_id})")
        logger.info(f"{'='*60}")
        
        inicio = datetime.now()
        
        try:
            # Paso 1: Conectar a VPN
            if self.usar_vpn:
                pais = bot_config.get('pais_vpn')
                if not self._connect_vpn(bot_id, pais):
                    logger.error(f"[{bot_id}] Falló conexión VPN")
                    return False
            
            # Paso 2: Inicializar bot de búsqueda
            bot = LinkBot(self.base_url)
            
            # Paso 3: Ejecutar búsquedas
            palabra_clave = bot_config.get('palabra_clave')
            urls = bot_config.get('urls', [])
            usar_crawl = bot_config.get('crawl', False)
            
            if not palabra_clave:
                logger.warning(f"[{bot_id}] Palabra clave no definida")
                return False
            
            logger.info(f"[{bot_id}] Palabra clave: '{palabra_clave}'")
            logger.info(f"[{bot_id}] URLs a buscar: {len(urls)}")
            
            # Búsqueda simple en URLs
            if urls and not usar_crawl:
                resultado = bot.search_multiple_urls(urls, palabra_clave)
                
                if resultado['exito']:
                    logger.info(f"[{bot_id}] ✓ Enlaces encontrados: {resultado['total_enlaces']}")
                else:
                    logger.warning(f"[{bot_id}] Búsqueda sin resultados")
            
            # Búsqueda con crawl
            elif usar_crawl:
                crawl_url = bot_config.get('crawl_url', urls[0] if urls else '/')
                depth = bot_config.get('crawl_depth', 1)
                max_pages = bot_config.get('crawl_max_pages', 10)
                
                logger.info(f"[{bot_id}] Crawl + búsqueda: profundidad {depth}, máx {max_pages} páginas")
                
                resultado = bot.crawl_and_search_links(
                    crawl_url,
                    palabra_clave,
                    depth=depth,
                    max_pages=max_pages
                )
                
                if resultado['exito']:
                    logger.info(f"[{bot_id}] ✓ Páginas procesadas: {resultado['paginas_procesadas']}")
                    logger.info(f"[{bot_id}] ✓ Enlaces encontrados: {resultado['total_enlaces']}")
            
            # Resumen
            duracion = (datetime.now() - inicio).total_seconds()
            logger.info(f"[{bot_id}] ✓ Completado en {duracion:.1f}s")
            
            return True
        
        except Exception as e:
            logger.error(f"[{bot_id}] Error ejecutando bot: {e}")
            return False
        
        finally:
            logger.info(f"{'='*60}\n")
    
    def execute_all_bots(self) -> Dict[str, bool]:
        """Ejecuta todos los bots de una vez (para testing)"""
        logger.info("\n" + "="*70)
        logger.info("EJECUTANDO TODOS LOS BOTS (Testing)")
        logger.info("="*70)
        
        resultados = {}
        for bot in self.bots:
            bot_id = bot['id']
            if bot.get('habilitado', True):
                resultados[bot_id] = self.execute_bot(bot_id)
                time.sleep(2)
        
        return resultados
    
    def start_scheduler(self):
        """Inicia ejecución: 1 bot cada 30 minutos"""
        
        logger.info("\n" + "="*70)
        logger.info("SCHEDULER INICIADO: 1 Bot Cada 30 Minutos")
        logger.info("="*70)
        
        bots_habilitados = [b for b in self.bots if b.get('habilitado', True)]
        
        if not bots_habilitados:
            logger.error("No hay bots habilitados")
            return
        
        logger.info(f"Bots a ejecutar: {len(bots_habilitados)}")
        for bot in bots_habilitados:
            logger.info(f"  - {bot['id']}: {bot['nombre']}")
        
        idx_actual = 0
        
        try:
            while True:
                bot_actual = bots_habilitados[idx_actual % len(bots_habilitados)]
                bot_id = bot_actual['id']
                
                ahora = datetime.now()
                proximo = ahora + timedelta(minutes=self.intervalo)
                
                logger.info(f"\n{'='*70}")
                logger.info(f"Próximo bot en {self.intervalo} minutos ({proximo.strftime('%H:%M')})")
                logger.info(f"{'='*70}\n")
                
                time.sleep(self.intervalo * 60)
                
                self.execute_bot(bot_id)
                
                idx_actual += 1
        
        except KeyboardInterrupt:
            logger.info("\nScheduler detenido por usuario")
    
    def list_bots(self):
        """Lista todos los bots configurados"""
        print("\n" + "="*70)
        print("BOTS CONFIGURADOS")
        print("="*70)
        
        for bot in self.bots:
            estado = "✓" if bot.get('habilitado', True) else "✗"
            print(f"\n[{estado}] {bot['id']} - {bot['nombre']}")
            print(f"    País VPN: {bot.get('pais_vpn', 'N/A').upper()}")
            print(f"    Palabra clave: {bot.get('palabra_clave', 'N/A')}")
            print(f"    URLs: {len(bot.get('urls', []))}")
            
            if bot.get('crawl'):
                print(f"    Crawl: Sí (prof. {bot.get('crawl_depth', 1)}, máx {bot.get('crawl_max_pages', 10)})")
            else:
                print(f"    Crawl: No")
        
        print("\n" + "="*70)
        print(f"Total: {len(self.bots)} bots\n")
    
    def show_status(self):
        """Muestra estado actual"""
        print("\n" + "="*70)
        print("ESTADO DEL ORQUESTADOR")
        print("="*70)
        
        print(f"\nConfiguración:")
        print(f"  Base URL: {self.base_url}")
        print(f"  Intervalo: {self.intervalo} minutos entre bots")
        print(f"  Usar VPN: {'Sí' if self.usar_vpn else 'No'}")
        
        if self.usar_vpn and self.vpn:
            status = self.vpn.get_status()
            print(f"  VPN Conectada: {'Sí' if status.get('connected') else 'No'}")
            print(f"  IP actual: {status.get('ip', 'Desconocida')}")
        
        print(f"\nBots habilitados: {len([b for b in self.bots if b.get('habilitado', True)])}")
        print("\n" + "="*70 + "\n")


def main():
    parser = ArgumentParser(description='Orquestador - 1 Bot Cada 30 Min, Busca en Enlaces')
    parser.add_argument('--config', default='bots_links.json',
                       help='Archivo de configuración')
    parser.add_argument('--bot', help='Ejecutar bot específico')
    parser.add_argument('--run-all', action='store_true',
                       help='Ejecutar todos los bots ahora')
    parser.add_argument('--list-bots', action='store_true',
                       help='Listar todos los bots')
    parser.add_argument('--status', action='store_true',
                       help='Mostrar estado')
    parser.add_argument('--schedule', action='store_true',
                       help='Iniciar scheduler (1 bot cada 30 min)')
    
    args = parser.parse_args()
    
    try:
        orchestrator = LinksOrchestrator(args.config)
        
        if args.list_bots:
            orchestrator.list_bots()
        
        elif args.status:
            orchestrator.show_status()
        
        elif args.bot:
            orchestrator.execute_bot(args.bot)
        
        elif args.run_all:
            resultados = orchestrator.execute_all_bots()
            print("\n" + "="*70)
            print("RESULTADOS")
            print("="*70)
            for bot_id, resultado in resultados.items():
                estado = "✓ OK" if resultado else "✗ FALLÓ"
                print(f"  {bot_id}: {estado}")
            print()
        
        elif args.schedule:
            orchestrator.start_scheduler()
        
        else:
            orchestrator.start_scheduler()
    
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

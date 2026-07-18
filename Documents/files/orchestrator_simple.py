#!/usr/bin/env python3
"""
Orquestador Simple - ProtonVPN
1 Bot Cada 30 Minutos
ProtonVPN conecta automáticamente al servidor más rápido

Uso:
    python3 orchestrator_simple.py --schedule
    python3 orchestrator_simple.py --bot bot_01
    python3 orchestrator_simple.py --list-bots
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict
from argparse import ArgumentParser
import sys

from bot_link_search import LinkBot
from protonvpn_simple import ProtonVPNSimple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('orchestrator_simple.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SimpleOrchestrator:
    """Orquestador simple: 1 bot cada 30 min, ProtonVPN automático"""
    
    def __init__(self, config_file='bots_links.json'):
        self.config_file = Path(config_file)
        self.config = self._load_config()
        
        self.base_url = self.config.get('base_url')
        self.bots = self.config.get('bots', [])
        self.intervalo = self.config.get('intervalo_minutos', 30)
        
        # ProtonVPN Simple
        self.vpn = ProtonVPNSimple()
        logger.info("✓ ProtonVPN Simple Manager inicializado")
        logger.info(f"Orquestador: {len(self.bots)} bots, intervalo {self.intervalo} min")
    
    def _load_config(self) -> Dict:
        if not self.config_file.exists():
            logger.error(f"No existe: {self.config_file}")
            return {}
        with open(self.config_file, 'r') as f:
            return json.load(f)
    
    def execute_bot(self, bot_id: str) -> bool:
        """Ejecuta un bot"""
        
        bot_config = None
        for bot in self.bots:
            if bot['id'] == bot_id:
                bot_config = bot
                break
        
        if not bot_config:
            logger.error(f"Bot no encontrado: {bot_id}")
            return False
        
        if not bot_config.get('habilitado', True):
            logger.info(f"[{bot_id}] Bot deshabilitado")
            return False
        
        bot_nombre = bot_config.get('nombre', bot_id)
        logger.info(f"\n{'='*60}")
        logger.info(f"Ejecutando: {bot_nombre} ({bot_id})")
        logger.info(f"{'='*60}")
        
        inicio = datetime.now()
        
        try:
            # Conectar a ProtonVPN
            logger.info(f"[{bot_id}] Conectando a ProtonVPN...")
            if not self.vpn.connect():
                logger.error(f"[{bot_id}] Error conectando VPN")
                return False
            
            # Ver ubicación
            status = self.vpn.get_status()
            logger.info(f"[{bot_id}] Servidor: {status['server']}")
            logger.info(f"[{bot_id}] IP: {status['ip']}")
            
            time.sleep(2)
            
            # Búsqueda
            bot = LinkBot(self.base_url)
            palabra_clave = bot_config.get('palabra_clave')
            urls = bot_config.get('urls', [])
            
            if not palabra_clave:
                logger.warning(f"[{bot_id}] Sin palabra clave")
                return False
            
            logger.info(f"[{bot_id}] Buscando: '{palabra_clave}'")
            
            if urls:
                resultado = bot.search_multiple_urls(urls, palabra_clave)
                
                if resultado['exito']:
                    logger.info(f"[{bot_id}] ✓ Enlaces: {resultado['total_enlaces']}")
                else:
                    logger.warning(f"[{bot_id}] Sin resultados")
            
            duracion = (datetime.now() - inicio).total_seconds()
            logger.info(f"[{bot_id}] ✓ Completado en {duracion:.1f}s")
            
            return True
        
        except Exception as e:
            logger.error(f"[{bot_id}] Error: {e}")
            return False
        
        finally:
            logger.info(f"{'='*60}\n")
    
    def execute_all_bots(self) -> Dict[str, bool]:
        """Ejecuta todos los bots"""
        logger.info("\n" + "="*70)
        logger.info("EJECUTANDO TODOS LOS BOTS")
        logger.info("="*70)
        
        resultados = {}
        for bot in self.bots:
            bot_id = bot['id']
            if bot.get('habilitado', True):
                resultados[bot_id] = self.execute_bot(bot_id)
                time.sleep(2)
        
        return resultados
    
    def start_scheduler(self):
        """Inicia scheduler: 1 bot cada 30 minutos"""
        
        logger.info("\n" + "="*70)
        logger.info("SCHEDULER: 1 Bot Cada 30 Minutos (ProtonVPN)")
        logger.info("="*70)
        
        bots_habilitados = [b for b in self.bots if b.get('habilitado', True)]
        
        if not bots_habilitados:
            logger.error("Sin bots habilitados")
            return
        
        logger.info(f"Bots: {len(bots_habilitados)}")
        for bot in bots_habilitados:
            logger.info(f"  - {bot['id']}: {bot['nombre']}")
        
        idx = 0
        
        try:
            while True:
                bot_actual = bots_habilitados[idx % len(bots_habilitados)]
                
                proximo = datetime.now() + timedelta(minutes=self.intervalo)
                logger.info(f"\nProximo bot en {self.intervalo} min ({proximo.strftime('%H:%M')})")
                
                time.sleep(self.intervalo * 60)
                self.execute_bot(bot_actual['id'])
                
                idx += 1
        
        except KeyboardInterrupt:
            logger.info("\nDetenido por usuario")
            self.vpn.disconnect()
    
    def list_bots(self):
        """Lista bots"""
        print("\n" + "="*70)
        print("BOTS")
        print("="*70)
        
        for bot in self.bots:
            estado = "✓" if bot.get('habilitado', True) else "✗"
            print(f"[{estado}] {bot['id']} - {bot['nombre']}")
            print(f"    Palabra: {bot.get('palabra_clave', 'N/A')}")
            print(f"    URLs: {len(bot.get('urls', []))}")
        
        print("\n" + "="*70 + "\n")
    
    def show_status(self):
        """Muestra estado"""
        print("\n" + "="*70)
        print("ESTADO")
        print("="*70)
        
        print(f"Base URL: {self.base_url}")
        print(f"Intervalo: {self.intervalo} minutos")
        print(f"VPN: ProtonVPN (automático)")
        
        status = self.vpn.get_status()
        print(f"VPN Conectada: {'Sí' if status['connected'] else 'No'}")
        print(f"Servidor: {status['server']}")
        print(f"IP: {status['ip']}")
        
        print(f"Bots: {len([b for b in self.bots if b.get('habilitado', True)])}")
        print("\n" + "="*70 + "\n")


def main():
    parser = ArgumentParser(description='Orquestador Simple - ProtonVPN')
    parser.add_argument('--config', default='bots_links.json')
    parser.add_argument('--bot', help='Ejecutar bot específico')
    parser.add_argument('--run-all', action='store_true')
    parser.add_argument('--list-bots', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--schedule', action='store_true')
    
    args = parser.parse_args()
    
    try:
        orch = SimpleOrchestrator(args.config)
        
        if args.list_bots:
            orch.list_bots()
        elif args.status:
            orch.show_status()
        elif args.bot:
            orch.execute_bot(args.bot)
        elif args.run_all:
            resultados = orch.execute_all_bots()
            print("\n" + "="*70)
            for bot_id, resultado in resultados.items():
                print(f"  {bot_id}: {'✓' if resultado else '✗'}")
            print()
        elif args.schedule:
            orch.start_scheduler()
        else:
            orch.start_scheduler()
    
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

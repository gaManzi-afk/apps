#!/usr/bin/env python3
"""
Bot Búsqueda en Enlaces - Versión Simplificada
Busca una palabra en los ENLACES (URLs) de la intranet
Sin credenciales (acceso directo)

Uso:
    bot = LinkBot('https://intranet.empresa.com')
    bot.search_in_links('/documentos', 'confidencial')
"""

import logging
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Instala: pip install requests beautifulsoup4")
    exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('link_search.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LinkBot:
    """Bot para buscar palabras en enlaces (URLs)"""
    
    def __init__(self, base_url):
        """
        Args:
            base_url: URL base de la intranet (sin credenciales)
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Bot/1.0)'
        })
        
        # Directorio de salida
        self.output_dir = Path('resultados') / datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"LinkBot inicializado: {self.base_url}")
        logger.info(f"Directorio de salida: {self.output_dir}")
    
    def fetch_page(self, url_path) -> Optional[BeautifulSoup]:
        """Descarga una página (sin credenciales)"""
        url = urljoin(self.base_url, url_path)
        try:
            logger.info(f"Descargando: {url}")
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            return BeautifulSoup(resp.content, 'html.parser')
        except Exception as e:
            logger.error(f"Error descargando {url}: {e}")
            return None
    
    def extract_links(self, soup) -> List[str]:
        """
        Extrae todos los enlaces (URLs) del HTML
        
        Returns:
            Lista de URLs absolutas
        """
        links = []
        
        for a_tag in soup.find_all('a', href=True):
            url = a_tag.get('href', '')
            # Convertir a URL absoluta
            absolute_url = urljoin(self.base_url, url)
            
            # Validar que sea del mismo dominio
            if urlparse(absolute_url).netloc == urlparse(self.base_url).netloc:
                if absolute_url not in links:  # Evitar duplicados
                    links.append(absolute_url)
        
        return links
    
    def search_in_links(self, url_path: str, keyword: str, 
                       case_sensitive: bool = False) -> Dict:
        """
        Busca palabra clave en los ENLACES (URLs) de una página
        
        Args:
            url_path: Ruta de la página
            keyword: Palabra a buscar en los enlaces
            case_sensitive: Distinguir mayúsculas
        
        Returns:
            Dict con resultados
        """
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Buscando '{keyword}' en ENLACES de: {url_path}")
        logger.info(f"{'='*60}")
        
        # Descargar página
        soup = self.fetch_page(url_path)
        if not soup:
            return {'exito': False, 'mensaje': 'No se pudo descargar la página'}
        
        # Extraer enlaces
        todos_los_enlaces = self.extract_links(soup)
        logger.info(f"Total de enlaces encontrados: {len(todos_los_enlaces)}")
        
        # Buscar palabra en enlaces
        enlaces_encontrados = []
        patron = re.compile(
            re.escape(keyword),
            0 if case_sensitive else re.IGNORECASE
        )
        
        for enlace in todos_los_enlaces:
            if patron.search(enlace):
                enlaces_encontrados.append(enlace)
                logger.info(f"  ✓ {enlace}")
        
        logger.info(f"Enlaces con '{keyword}': {len(enlaces_encontrados)}")
        
        # Guardar resultados
        resultado_file = self.output_dir / f"enlaces_{keyword}.txt"
        with open(resultado_file, 'w', encoding='utf-8') as f:
            f.write(f"BÚSQUEDA EN ENLACES\n")
            f.write(f"Palabra clave: {keyword}\n")
            f.write(f"Página: {url_path}\n")
            f.write(f"Total enlaces: {len(todos_los_enlaces)}\n")
            f.write(f"Enlaces encontrados: {len(enlaces_encontrados)}\n")
            f.write(f"Fecha: {datetime.now()}\n")
            f.write(f"\n{'='*60}\n\n")
            
            f.write(f"ENLACES CON '{keyword}':\n\n")
            for i, enlace in enumerate(enlaces_encontrados, 1):
                f.write(f"[{i}] {enlace}\n")
            
            if len(todos_los_enlaces) > len(enlaces_encontrados):
                f.write(f"\n{'='*60}\n")
                f.write(f"TODOS LOS ENLACES (para referencia):\n\n")
                for i, enlace in enumerate(todos_los_enlaces, 1):
                    marca = " ← ENCONTRADO" if enlace in enlaces_encontrados else ""
                    f.write(f"[{i}] {enlace}{marca}\n")
        
        logger.info(f"✓ Resultados guardados: {resultado_file}")
        
        return {
            'exito': True,
            'palabra': keyword,
            'url': url_path,
            'total_enlaces': len(todos_los_enlaces),
            'enlaces_encontrados': len(enlaces_encontrados),
            'enlaces': enlaces_encontrados,
            'archivo': str(resultado_file)
        }
    
    def search_multiple_urls(self, urls: List[str], keyword: str) -> Dict:
        """
        Busca palabra clave en enlaces de múltiples URLs
        
        Args:
            urls: Lista de rutas
            keyword: Palabra clave
        
        Returns:
            Resultados consolidados
        """
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Búsqueda multi-URL: '{keyword}' en {len(urls)} páginas")
        logger.info(f"{'='*70}")
        
        resultados_totales = []
        urls_procesadas = 0
        urls_fallidas = 0
        
        for url in urls:
            resultado = self.search_in_links(url, keyword)
            
            if resultado['exito']:
                urls_procesadas += 1
                resultados_totales.extend(resultado['enlaces'])
            else:
                urls_fallidas += 1
            
            logger.info(f"Progreso: {urls_procesadas}/{len(urls)}")
        
        # Guardar resumen consolidado
        resumen_file = self.output_dir / f"resumen_{keyword}.txt"
        with open(resumen_file, 'w', encoding='utf-8') as f:
            f.write(f"BÚSQUEDA CONSOLIDADA EN ENLACES\n")
            f.write(f"Palabra clave: {keyword}\n")
            f.write(f"URLs procesadas: {urls_procesadas}\n")
            f.write(f"URLs fallidas: {urls_fallidas}\n")
            f.write(f"Total enlaces encontrados: {len(resultados_totales)}\n")
            f.write(f"Fecha: {datetime.now()}\n")
            f.write(f"\n{'='*60}\n\n")
            
            f.write(f"TODOS LOS ENLACES CON '{keyword}':\n\n")
            for i, enlace in enumerate(resultados_totales, 1):
                f.write(f"[{i}] {enlace}\n")
        
        logger.info(f"\n✓ Resumen consolidado: {resumen_file}")
        
        return {
            'exito': True,
            'palabra': keyword,
            'urls_procesadas': urls_procesadas,
            'urls_fallidas': urls_fallidas,
            'total_enlaces': len(resultados_totales),
            'enlaces': resultados_totales,
            'archivo': str(resumen_file)
        }
    
    def crawl_and_search_links(self, start_url: str, keyword: str, 
                              depth: int = 1, max_pages: int = 10) -> Dict:
        """
        Crawlea página y busca palabra en enlaces recursivamente
        
        Args:
            start_url: URL inicial
            keyword: Palabra clave
            depth: Profundidad del crawl
            max_pages: Máximo de páginas
        
        Returns:
            Resultados del crawl
        """
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Crawl + Búsqueda en Enlaces: '{keyword}'")
        logger.info(f"Inicio: {start_url}")
        logger.info(f"Profundidad: {depth}, Máximo: {max_pages} páginas")
        logger.info(f"{'='*70}")
        
        visited = set()
        to_visit = [(start_url, 0)]
        resultados_totales = []
        paginas_procesadas = 0
        
        while to_visit and paginas_procesadas < max_pages:
            current_url, current_depth = to_visit.pop(0)
            
            if current_url in visited or current_depth > depth:
                continue
            
            visited.add(current_url)
            
            # Buscar palabra en enlaces de esta página
            resultado = self.search_in_links(current_url, keyword)
            
            if resultado['exito']:
                paginas_procesadas += 1
                resultados_totales.extend(resultado['enlaces'])
                
                # Extraer enlaces para siguiente nivel
                soup = self.fetch_page(current_url)
                if soup and current_depth < depth:
                    for link in self.extract_links(soup):
                        if link not in visited:
                            to_visit.append((link, current_depth + 1))
            
            logger.info(f"Progreso: {paginas_procesadas}/{max_pages} páginas")
        
        # Guardar resumen crawl
        resumen_file = self.output_dir / f"crawl_{keyword}.txt"
        with open(resumen_file, 'w', encoding='utf-8') as f:
            f.write(f"CRAWL + BÚSQUEDA EN ENLACES\n")
            f.write(f"Palabra clave: {keyword}\n")
            f.write(f"URL inicial: {start_url}\n")
            f.write(f"Páginas procesadas: {paginas_procesadas}\n")
            f.write(f"Total enlaces encontrados: {len(resultados_totales)}\n")
            f.write(f"Fecha: {datetime.now()}\n")
            f.write(f"\n{'='*60}\n\n")
            
            f.write(f"ENLACES CON '{keyword}':\n\n")
            for i, enlace in enumerate(resultados_totales, 1):
                f.write(f"[{i}] {enlace}\n")
        
        logger.info(f"✓ Crawl completado: {resumen_file}")
        
        return {
            'exito': True,
            'palabra': keyword,
            'paginas_procesadas': paginas_procesadas,
            'total_enlaces': len(resultados_totales),
            'enlaces': resultados_totales,
            'archivo': str(resumen_file)
        }


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Uso: python3 bot_link_search.py <base_url> <url_path> <keyword>")
        print("\nEjemplos:")
        print("  python3 bot_link_search.py https://intranet.local /documentos confidencial")
        print("  python3 bot_link_search.py https://intranet.local /noticias urgente")
        sys.exit(1)
    
    base_url = sys.argv[1]
    url_path = sys.argv[2]
    keyword = sys.argv[3]
    
    bot = LinkBot(base_url)
    resultado = bot.search_in_links(url_path, keyword)
    
    print(f"\n✓ Búsqueda completada")
    print(f"  Enlaces encontrados: {resultado['enlaces_encontrados']}/{resultado['total_enlaces']}")
    print(f"  Resultados: {resultado['archivo']}")

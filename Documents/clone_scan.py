#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clone_scan.py — Detector de clones / phishing de un sitio web.

Toma un sitio como referencia y busca copias combinando:
  1. Hash de favicon (formato estilo Shodan) para pivoteo.
  2. dnstwist: typosquatting, homoglifos, cambios de TLD + similitud de DOM.
  3. Certificate Transparency (crt.sh): dominios que contienen tu marca.
  4. urlscan.io: huella de contenido (hash de recursos + IDs de analítica),
     que detecta clones en CUALQUIER dominio, no solo en nombres parecidos.
  5. Comparación de contenido (texto, estructura de etiquetas, recursos).

Pensado para brand monitoring / anti-phishing sobre dominios propios.

Dependencias:
    pip install requests mmh3 dnstwist dnspython beautifulsoup4

Uso:
    python3 clone_scan.py
    (pide el link de forma interactiva)

    python3 clone_scan.py https://tusitio.com      # o pasándolo como argumento

    Requiere: pip install requests mmh3 dnstwist dnspython beautifulsoup4 reportlab
"""

import sys
import re
import json
import time
import os
import codecs
import base64
import hashlib
import difflib
import datetime
import threading
import itertools
from urllib.parse import urlparse, urljoin

try:
    import requests
except ImportError:
    sys.exit("Falta 'requests'. Instala con: pip install requests")

try:
    import mmh3
except ImportError:
    sys.exit("Falta 'mmh3'. Instala con: pip install mmh3")

# bs4 es opcional: mejora el parseo de DOM, pero hay fallback.
try:
    from bs4 import BeautifulSoup
    HAVE_BS4 = True
except ImportError:
    HAVE_BS4 = False

# dnstwist como módulo; si no está, se avisa y se omite esa fase.
try:
    import dnstwist
    HAVE_DNSTWIST = True
except ImportError:
    HAVE_DNSTWIST = False


# ----------------------------- Configuración ------------------------------ #

# User-Agent de navegador real: evita bloqueos de Cloudflare/WAF al bajar
# favicon y HTML (antes muchos sitios devolvían 403 al UA del script).
UA = ("Mozilla/5.0 (X11; Linux x86_64; rv:128.0) "
      "Gecko/20100101 Firefox/128.0")
# UA alternativo para reintentar si el principal devuelve una página vacía
# o de bloqueo (algunos WAF se comportan al revés con uno u otro).
UA_ALT = "Mozilla/5.0 (compatible; CloneScan/1.0; brand-monitoring)"
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    # Sin 'br' a propósito: requests descomprime gzip/deflate sin librerías
    # extra, pero Brotli necesitaría el paquete 'brotli' o el HTML llega
    # ilegible (título y recursos vacíos).
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
TIMEOUT = 12
# Hilos y tiempo límite de dnstwist, ajustables por entorno. DoH es I/O (red),
# así que subir los hilos acelera casi en proporción; úsalo si DoH se agota:
#   export DNSTWIST_THREADS=100   export DNSTWIST_TIMEOUT=600
DNSTWIST_THREADS = int(os.environ.get("DNSTWIST_THREADS", "40"))
DNSTWIST_TIMEOUT = int(os.environ.get("DNSTWIST_TIMEOUT", "300"))
# Resolvers: la causa habitual de que dnstwist se agote es un resolver local
# lento o secuestrado. En redes que secuestran el puerto 53, usa DoH (DNS sobre
# HTTPS), que no se puede interceptar:
#   export DNSTWIST_NAMESERVERS="https://cloudflare-dns.com/dns-query"
# Vacío ("") usa el resolver del sistema.
DNSTWIST_NAMESERVERS = os.environ.get("DNSTWIST_NAMESERVERS", "1.1.1.1,8.8.8.8")
DNSTWIST_MAX_CANDIDATOS = 200  # tope de permutaciones a verificar; por encima,
                               # se asume resolver con wildcard/secuestro de DNS

# urlscan.io (huella de contenido, agnóstico al dominio).
URLSCAN_ENABLED = True
# La clave se lee de la variable de entorno URLSCAN_API_KEY (no se escribe en el
# archivo, para no exponer secretos). Consíguela gratis en urlscan.io ->
# Settings -> API Keys y expórtala:  export URLSCAN_API_KEY="tu_clave"
URLSCAN_API_KEY = os.environ.get("URLSCAN_API_KEY", "")
URLSCAN_MAX_RECURSOS = 8     # nº de recursos propios a hashear y buscar
# Con clave el límite es mayor, así que podemos consultar más rápido.
URLSCAN_PAUSA = 1.2 if URLSCAN_API_KEY else 2.5   # segundos entre consultas
URLSCAN_MAX_HITS = 20        # si un hash aparece en MÁS scans que esto, es un
                             # archivo genérico (jQuery, WP core...) y se
                             # descarta: una huella real sale en pocos sitios
URLSCAN_MAX_CANDIDATOS = 60  # tope de dominios de la fase 3 a verificar

# Archivos de frameworks/librerías comunes: su hash es idéntico en millones de
# sitios, así que NO sirven como huella. Se saltan antes de consultar urlscan.
RECURSOS_GENERICOS = re.compile(
    r"(jquery|jquery-migrate|bootstrap|popper|underscore|backbone|react|"
    r"vue|swiper|slick|owl\.?carousel|masonry|imagesloaded|hoverintent|"
    r"wp-emoji|wp-embed|wp-polyfill|comment-reply|regenerator|core\.min|"
    r"fontawesome|font-awesome|all\.min|modernizr|lodash|moment|"
    r"elementor|frontend\.min|animate\.min|normalize|reset\.css)", re.I)

# Dominios que son proxies/espejos/cachés o traductores, no clones reales.
DOMINIOS_IGNORAR = ("translate.goog", "webcache.googleusercontent.com",
                    "web.archive.org", "cachedview.nl")

# Umbrales de similitud (0-1) para considerar que el contenido se parece.
SIM_HTML_FUERTE = 0.75   # HTML casi idéntico
SIM_HTML_MEDIA = 0.50    # parecido notable

# Pesos para el puntaje de sospecha (0-100).
PESO_FAVICON = 40
PESO_HTML = 35
PESO_TITULO = 15
PESO_RECURSOS = 10


# ------------------------------- Utilidades -------------------------------- #

def normaliza_url(entrada: str) -> str:
    """Asegura esquema http(s) y devuelve una URL usable."""
    entrada = entrada.strip()
    if not entrada:
        raise ValueError("URL vacía")
    if not re.match(r"^https?://", entrada, re.I):
        entrada = "https://" + entrada
    return entrada


def dominio_de(url: str) -> str:
    return urlparse(url).netloc.split("@")[-1].split(":")[0].lower()


def registrable(dominio: str) -> str:
    """Aproximación simple del dominio registrable (marca + TLD)."""
    partes = dominio.split(".")
    if len(partes) >= 2:
        return ".".join(partes[-2:])
    return dominio


def palabra_marca(dominio: str) -> str:
    """Primer label del dominio registrable (p.ej. 'tusitio')."""
    return registrable(dominio).split(".")[0]


def get(url: str, headers: dict | None = None):
    """GET tolerante a fallos; devuelve requests.Response o None."""
    try:
        return requests.get(
            url, headers=headers or HEADERS, timeout=TIMEOUT,
            allow_redirects=True, verify=True,
        )
    except requests.RequestException:
        return None


def ejecuta_con_progreso(fn, etiqueta: str, timeout: int):
    """
    Corre fn() en un hilo mostrando un contador en vivo (spinner + segundos).
    Si supera 'timeout', deja de esperar y devuelve None (el hilo queda en
    segundo plano y muere al salir). Evita que la fase parezca colgada.
    """
    caja = {}

    def worker():
        try:
            caja["valor"] = fn()
        except Exception as e:                      # noqa: BLE001
            caja["error"] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    spin = itertools.cycle("|/-\\")
    inicio = time.time()
    while t.is_alive():
        seg = int(time.time() - inicio)
        print(f"\r    {etiqueta} {next(spin)}  {seg:>3}s "
              f"(límite {timeout}s)", end="", flush=True)
        t.join(timeout=0.4)
        if time.time() - inicio > timeout:
            print(f"\r    {etiqueta} — se alcanzó el límite de {timeout}s, "
                  f"se omite esta fase.{' ' * 10}")
            return None
    print("\r" + " " * 70 + "\r", end="")           # limpia la línea
    return caja.get("valor")


# ------------------------------ Favicon hash ------------------------------- #

def url_favicon(url: str, html: str | None) -> str:
    """Busca <link rel=icon> en el HTML; si no, usa /favicon.ico."""
    base = f"{urlparse(url).scheme}://{dominio_de(url)}"
    if html:
        m = re.search(
            r'<link[^>]+rel=["\'][^"\']*icon[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
            html, re.I,
        )
        if m:
            href = m.group(1)
            if href.startswith("//"):
                return urlparse(url).scheme + ":" + href
            if href.startswith("http"):
                return href
            if href.startswith("/"):
                return base + href
            return base + "/" + href
    return base + "/favicon.ico"


def hash_favicon(url: str, html: str | None):
    """Devuelve (hash_shodan, url_favicon) o (None, url_favicon).

    Prueba primero el favicon declarado en el HTML y, si falla, cae a
    /favicon.ico (muchos sitios bloquean uno pero sirven el otro).
    """
    base = f"{urlparse(url).scheme}://{dominio_de(url)}"
    declarado = url_favicon(url, html)
    candidatas = [declarado]
    ico = base + "/favicon.ico"
    if ico not in candidatas:
        candidatas.append(ico)
    for fav in candidatas:
        r = get(fav)
        if r and r.status_code == 200 and r.content:
            # Formato Shodan: base64 del contenido (con saltos de línea) + mmh3.
            b64 = codecs.encode(r.content, "base64")
            return mmh3.hash(b64), fav
    return None, declarado


# --------------------------- Análisis de contenido ------------------------- #

def extrae_features(html: str) -> dict:
    """Saca título, texto visible, estructura de etiquetas y recursos."""
    if HAVE_BS4:
        soup = BeautifulSoup(html, "html.parser")
        titulo = (soup.title.string or "").strip() if soup.title else ""
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        texto = re.sub(r"\s+", " ", soup.get_text(" ")).strip().lower()
        etiquetas = " ".join(t.name for t in soup.find_all(True))
        recursos = set()
        for tag, attr in (("script", "src"), ("link", "href"), ("img", "src")):
            for el in BeautifulSoup(html, "html.parser").find_all(tag):
                v = el.get(attr)
                if v:
                    recursos.add(v.split("?")[0].rsplit("/", 1)[-1])
    else:
        mt = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        titulo = (mt.group(1).strip() if mt else "")
        texto = re.sub(r"<[^>]+>", " ", html)
        texto = re.sub(r"\s+", " ", texto).strip().lower()
        etiquetas = " ".join(re.findall(r"<\s*([a-zA-Z0-9]+)", html)).lower()
        recursos = set(
            m.rsplit("/", 1)[-1].split("?")[0]
            for m in re.findall(r'(?:src|href)=["\']([^"\']+)["\']', html, re.I)
        )
    return {"titulo": titulo, "texto": texto,
            "etiquetas": etiquetas, "recursos": recursos}


def ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def compara(base: dict, otro: dict) -> dict:
    """Puntúa el parecido entre el sitio base y un candidato."""
    sim_texto = ratio(base["texto"][:20000], otro["texto"][:20000])
    sim_estruct = ratio(base["etiquetas"][:20000], otro["etiquetas"][:20000])
    sim_html = round((sim_texto * 0.6 + sim_estruct * 0.4), 3)

    titulo_igual = bool(base["titulo"]) and base["titulo"].lower() == otro["titulo"].lower()

    comunes = base["recursos"] & otro["recursos"]
    sim_rec = len(comunes) / len(base["recursos"]) if base["recursos"] else 0.0

    return {
        "sim_texto": round(sim_texto, 3),
        "sim_estructura": round(sim_estruct, 3),
        "sim_html": sim_html,
        "titulo_igual": titulo_igual,
        "recursos_compartidos": sorted(comunes),
        "sim_recursos": round(sim_rec, 3),
    }


# -------------------------------- crt.sh ----------------------------------- #

def consulta_crtsh(dominio: str) -> list[str]:
    """Dominios distintos vistos en CT que contienen la marca."""
    marca = palabra_marca(dominio)
    url = f"https://crt.sh/?q=%25{marca}%25&output=json"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25)
        if r.status_code != 200:
            return []
        data = r.json()
    except (requests.RequestException, ValueError):
        return []
    vistos = set()
    propio = registrable(dominio)
    for fila in data:
        for nombre in str(fila.get("name_value", "")).splitlines():
            nombre = nombre.strip().lstrip("*.").lower()
            if not nombre or nombre.endswith(propio):
                continue
            if marca in nombre:
                vistos.add(nombre)
    return sorted(vistos)


# ----------------------------- cambio de TLD ------------------------------- #
# dnstwist por defecto NO cubre bien el cambio de extensión (.com -> .pro, .net,
# .co, .shop...), que es de las técnicas de clonado más usadas. Aquí generamos y
# resolvemos esos TLD de alto abuso y nos quedamos solo con los que existen.
TLD_ALTO_ABUSO = [
    "net", "org", "co", "pro", "info", "biz", "site", "online", "shop", "store",
    "xyz", "top", "club", "live", "app", "io", "me", "us", "website", "space",
    "icu", "vip", "cc", "sbs", "com.co", "company", "digital", "link", "click",
]


def _resuelve_ips(dominio: str, nameservers: str) -> set:
    """IPs A de un dominio vía el resolver indicado (o el del sistema)."""
    try:
        import dns.resolver
    except Exception:
        return set()
    try:
        res = dns.resolver.Resolver(configure=True)
        if nameservers and not nameservers.startswith("https"):
            srv = [x.strip() for x in nameservers.split(",") if x.strip()]
            if srv:
                res.nameservers = srv
        return set(str(r) for r in res.resolve(dominio, "A", lifetime=4))
    except Exception:
        return set()


def candidatos_tld_swap(dominio: str) -> list:
    """Variantes de TLD de alto abuso que SÍ resuelven (p.ej. marca.pro)."""
    palabra = palabra_marca(dominio)
    tld_orig = ".".join(registrable(dominio).split(".")[1:])
    hijack = ips_de_secuestro(DNSTWIST_NAMESERVERS)
    vivos = []
    for tld in TLD_ALTO_ABUSO:
        if tld == tld_orig:
            continue
        cand = f"{palabra}.{tld}"
        ips = _resuelve_ips(cand, DNSTWIST_NAMESERVERS)
        # Existe si resuelve a una IP que no sea la del secuestro.
        if ips and not (hijack and ips.issubset(hijack)):
            vivos.append(cand)
    return list(dict.fromkeys(vivos))


# -------------------------------- dnstwist --------------------------------- #

def ips_de_secuestro(nameservers: str) -> set:
    """
    Descubre la(s) IP con que la red 'secuestra' dominios inexistentes.
    Resuelve varios dominios que no existen: si responden, esas IP son del
    secuestro y luego sirven para descartar las permutaciones falsas.
    Solo aplica a DNS plano (DoH no se intercepta).
    """
    if nameservers and nameservers.startswith("https"):
        return set()
    try:
        import dns.resolver
    except Exception:
        return set()
    res = dns.resolver.Resolver(configure=True)
    if nameservers:
        srv = [x.strip() for x in nameservers.split(",") if x.strip()]
        if srv:
            res.nameservers = srv
    ips = set()
    for canary in ("nx-7f3a9q2k-check.com", "zzqxkv18273-nope.net",
                   "no-existe-4a9x1.org"):
        try:
            for rr in res.resolve(canary, "A", lifetime=4):
                ips.add(str(rr))
        except Exception:
            pass
    return ips


def candidatos_dnstwist(dominio: str):
    """Permutaciones realmente registradas según dnstwist.

    Devuelve (dominios_capados, total_pre_tope, descartados_por_secuestro).
    Si la red secuestra el DNS, descubre su IP y descarta las permutaciones que
    resuelven a ella (son falsas), quedándose solo con las que apuntan a otra IP
    (registradas de verdad). Así se usa DNS plano rápido sin tragarse el ruido.
    """
    if not HAVE_DNSTWIST:
        return [], 0, 0
    base = registrable(dominio)
    hijack = ips_de_secuestro(DNSTWIST_NAMESERVERS)   # IPs del secuestro, si hay
    kwargs = dict(domain=base, registered=True, format="null",
                  threads=DNSTWIST_THREADS)
    if DNSTWIST_NAMESERVERS:
        kwargs["nameservers"] = DNSTWIST_NAMESERVERS
    try:
        resultados = dnstwist.run(**kwargs)
    except TypeError:
        try:
            resultados = dnstwist.run(domain=base, registered=True,
                                      format="null", threads=DNSTWIST_THREADS)
        except Exception:
            return [], 0, 0
    except Exception:
        return [], 0, 0
    dominios, descartados = [], 0
    for item in resultados or []:
        d = item.get("domain")
        ips = set(map(str, item.get("dns_a") or []))
        if not d or d == base or not (ips or item.get("dns_aaaa")):
            continue
        # Si TODAS sus IP son de secuestro, es un falso positivo: descartar.
        if hijack and ips and ips.issubset(hijack):
            descartados += 1
            continue
        dominios.append(d)
    dominios = list(dict.fromkeys(dominios))      # sin duplicados, en orden
    total = len(dominios)
    return dominios[:DNSTWIST_MAX_CANDIDATOS], total, descartados


# ------------------------- urlscan.io (contenido) -------------------------- #
# A diferencia de dnstwist y crt.sh (que parten del NOMBRE del dominio), esto
# parte del CONTENIDO del sitio: busca quién sirve tus mismos recursos o tus
# mismos IDs de analítica. Así aparecen clones alojados en dominios que no se
# parecen en nada al tuyo.

def identificadores_analitica(html: str) -> set:
    """Extrae IDs de Google Analytics / GTM / AdSense / Facebook Pixel."""
    ids = set()
    patrones = [
        r"UA-\d{4,10}-\d{1,4}",        # Google Analytics clásico
        r"G-[A-Z0-9]{8,12}",           # GA4
        r"GTM-[A-Z0-9]{5,8}",          # Google Tag Manager
        r"ca-pub-\d{13,20}",           # AdSense
    ]
    for p in patrones:
        ids.update(re.findall(p, html))
    # Facebook Pixel: fbq('init', '123456789').
    ids.update(re.findall(r"fbq\(['\"]init['\"],\s*['\"](\d{10,20})['\"]", html))
    return ids


def recursos_mismo_origen(url: str, html: str, limite: int) -> list:
    """URLs de JS/CSS propios del sitio (mejores huellas que los de CDN)."""
    reg = registrable(dominio_de(url))
    urls, vistos = [], set()
    for m in re.findall(r'(?:src|href)=["\']([^"\']+)["\']', html, re.I):
        limpio = m.split("?")[0]
        if not limpio.lower().endswith((".js", ".css")):
            continue
        full = urljoin(url, m)
        if not dominio_de(full).endswith(reg):
            continue                               # salta CDNs externos
        if full in vistos:
            continue
        vistos.add(full)
        urls.append(full)
        if len(urls) >= limite:
            break
    return urls


def recursos_huella(url: str, html: str, limite: int) -> list:
    """
    Recursos DISTINTIVOS para buscar en urlscan: JS/CSS propios + imágenes
    subidas (logo, banners), EXCLUYENDO librerías de framework cuyo hash es
    común a millones de sitios. Esto es lo que evita los falsos positivos.
    """
    reg = registrable(dominio_de(url))
    urls, vistos = [], set()
    for m in re.findall(r'(?:src|href)=["\']([^"\']+)["\']', html, re.I):
        limpio = m.split("?")[0]
        low = limpio.lower()
        es_js_css = low.endswith((".js", ".css"))
        es_img_subida = ("/wp-content/uploads/" in low and
                         low.endswith((".png", ".jpg", ".jpeg", ".svg", ".webp")))
        if not (es_js_css or es_img_subida):
            continue
        if RECURSOS_GENERICOS.search(limpio):
            continue                               # salta jQuery, WP core, etc.
        full = urljoin(url, m)
        if not dominio_de(full).endswith(reg):
            continue                               # salta CDNs externos
        if full in vistos:
            continue
        vistos.add(full)
        urls.append(full)
        if len(urls) >= limite:
            break
    return urls


def sha256_recurso(url: str):
    r = get(url)
    if r and r.status_code == 200 and r.content:
        return hashlib.sha256(r.content).hexdigest()
    return None


def _sha256_favicon(url: str, html: str):
    """SHA-256 del favicon (como lo indexa urlscan). Muy distintivo por marca."""
    base = f"{urlparse(url).scheme}://{dominio_de(url)}"
    for fav in (url_favicon(url, html), base + "/favicon.ico"):
        h = sha256_recurso(fav)
        if h:
            return h
    return None


def imagenes_distintivas(url: str, html: str, limite: int = 6) -> list:
    """
    Imágenes propias y únicas del sitio (logo, portada, og:image), buscadas
    en src, data-src, srcset, og:image y url() de CSS inline. Son huellas
    excelentes porque un clon casi siempre copia el logo y la imagen social.
    """
    reg = registrable(dominio_de(url))
    crudas = []
    # og:image / twitter:image (imagen social, suele ser el logo o la portada).
    crudas += re.findall(
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']'
        r'[^>]+content=["\']([^"\']+)', html, re.I)
    # Atributos de imagen habituales (incluye lazy-load).
    for m in re.findall(
            r'(?:src|data-src|data-lazy-src|srcset|content)=["\']([^"\']+)',
            html, re.I):
        crudas.append(m.split(",")[0].strip().split(" ")[0])   # srcset: 1ª URL
    # Fondos en CSS inline: url(...).
    crudas += [m[1] for m in re.findall(r'url\((["\']?)([^)"\']+)\1\)', html, re.I)]

    salida, vistos = [], set()
    for u in crudas:
        limpio = u.split("?")[0]
        low = limpio.lower()
        if "/wp-content/uploads/" not in low:
            continue
        if not low.endswith((".png", ".jpg", ".jpeg", ".svg", ".webp")):
            continue
        full = urljoin(url, u).split("?")[0]
        if not dominio_de(full).endswith(reg):
            continue
        if RECURSOS_GENERICOS.search(full) or full in vistos:
            continue
        vistos.add(full)
        salida.append(full)
        if len(salida) >= limite:
            break
    return salida


def ids_desde_js(url: str, html: str, max_js: int = 3) -> set:
    """
    Extrae IDs de analítica también desde los JS propios (no solo del HTML):
    en WordPress el ID de GA4/GTM suele inyectarse desde un archivo .js.
    """
    ids, n = set(), 0
    for ru in recursos_huella(url, html, 15):
        if not ru.split("?")[0].lower().endswith(".js"):
            continue
        r = get(ru)
        if r and r.text:
            ids |= identificadores_analitica(r.text)
        n += 1
        if n >= max_js:
            break
    return ids


def _urlscan_buscar(query: str):
    """Consulta a urlscan.io. Devuelve (resultados, total_de_coincidencias).

    El 'total' es clave: un hash con miles de coincidencias es un archivo de
    librería genérico, no una huella del sitio.
    """
    headers = {"User-Agent": UA}
    if URLSCAN_API_KEY:
        headers["API-Key"] = URLSCAN_API_KEY
    try:
        r = requests.get(
            "https://urlscan.io/api/v1/search/",
            params={"q": query, "size": 100},
            headers=headers, timeout=25,
        )
        if r.status_code == 429:
            print("\n    [i] urlscan.io: límite de consultas alcanzado, "
                  "pausando el resto.")
            return "RATE_LIMIT", None
        if r.status_code != 200:
            return [], None
        data = r.json()
        return data.get("results", []), data.get("total", 0)
    except (requests.RequestException, ValueError):
        return [], None


def candidatos_urlscan(url: str, html: str) -> dict:
    """
    Busca en urlscan.io dominios ajenos que sirven la misma huella DISTINTIVA.
    Descarta hashes genéricos (muchas coincidencias) y proxies/espejos.
    Devuelve ({dominio: motivo}, nº_huellas_limpias): el dict ordenado de más a
    menos distintivo y capado, y cuántas huellas únicas salieron sin coincidencia.
    """
    if not URLSCAN_ENABLED:
        return {}, 0

    reg = registrable(dominio_de(url))
    encontrados = {}   # dominio -> (motivo, total_del_query)

    # Construir consultas desde todas las huellas distintivas disponibles.
    queries = []
    fav_sha = _sha256_favicon(url, html)
    if fav_sha:
        queries.append((f"hash:{fav_sha}", "favicon"))
    for img in imagenes_distintivas(url, html):
        h = sha256_recurso(img)
        if h:
            queries.append((f"hash:{h}", f"imagen ({img.rsplit('/', 1)[-1]})"))
    for ru in recursos_huella(url, html, URLSCAN_MAX_RECURSOS):
        h = sha256_recurso(ru)
        if h:
            queries.append((f"hash:{h}",
                            f"recurso ({ru.rsplit('/', 1)[-1].split('?')[0]})"))
    for ident in (identificadores_analitica(html) | ids_desde_js(url, html)):
        queries.append((f'"{ident}"', f"ID de analítica ({ident})"))

    # Quitar consultas duplicadas (p.ej. favicon declarado == /favicon.ico).
    vistas, unicas = set(), []
    for q, m in queries:
        if q not in vistas:
            vistas.add(q)
            unicas.append((q, m))

    if not unicas:
        print("    (sin huellas distintivas que buscar en urlscan)")
        return {}, 0

    limpias = 0
    for q, motivo in unicas:
        res, total = _urlscan_buscar(q)
        if res == "RATE_LIMIT":
            break
        if total is None:
            time.sleep(URLSCAN_PAUSA)
            continue
        # Un hash con demasiadas coincidencias es un archivo genérico: descartar.
        if total > URLSCAN_MAX_HITS:
            print(f"    - {motivo}: {total} scans -> genérico, descartado")
            time.sleep(URLSCAN_PAUSA)
            continue
        nuevos = 0
        for item in res or []:
            d = (item.get("page", {}).get("domain") or "").lower().strip()
            if not d or d.endswith(reg):
                continue
            if any(x in d for x in DOMINIOS_IGNORAR):
                continue
            if d not in encontrados:
                encontrados[d] = (motivo, total)
                nuevos += 1
        if nuevos:
            print(f"    + {motivo}: {total} scans -> {nuevos} dominios ajenos")
        else:
            print(f"    ✓ {motivo}: {total} scans -> solo en tu dominio (limpio)")
            limpias += 1
        time.sleep(URLSCAN_PAUSA)

    if not encontrados and limpias:
        print(f"    => {limpias} huella(s) distintiva(s) verificada(s), "
              f"ninguna aparece en otro dominio.")

    # Ordenar por distintividad (menos coincidencias = más único) y capar.
    ordenados = sorted(encontrados.items(), key=lambda kv: kv[1][1])
    cap = {d: mot for d, (mot, _tot) in ordenados[:URLSCAN_MAX_CANDIDATOS]}
    return cap, limpias


# ------------------------------- Evaluación -------------------------------- #

def evalua_candidato(dom: str, base_feats: dict, fav_base, origen: str) -> dict:
    """Analiza un dominio candidato y calcula su puntaje de sospecha."""
    url = "https://" + dom
    r = get(url)
    if not r:
        r = get("http://" + dom)
    if not r or not r.text:
        return {"dominio": dom, "origen": origen, "alcanzable": False,
                "puntaje": 0, "nota": "no responde / sin HTML"}

    feats = extrae_features(r.text)
    cmp = compara(base_feats, feats)
    fav_c, _ = hash_favicon(r.url, r.text)
    fav_igual = (fav_base is not None and fav_c is not None and fav_base == fav_c)

    puntaje = 0
    señales = []
    if fav_igual:
        puntaje += PESO_FAVICON
        señales.append("favicon idéntico")
    if cmp["sim_html"] >= SIM_HTML_FUERTE:
        puntaje += PESO_HTML
        señales.append(f"HTML muy similar ({cmp['sim_html']})")
    elif cmp["sim_html"] >= SIM_HTML_MEDIA:
        puntaje += int(PESO_HTML * 0.6)
        señales.append(f"HTML parecido ({cmp['sim_html']})")
    if cmp["titulo_igual"]:
        puntaje += PESO_TITULO
        señales.append("mismo título")
    if cmp["sim_recursos"] >= 0.5:
        puntaje += PESO_RECURSOS
        señales.append(f"recursos compartidos ({len(cmp['recursos_compartidos'])})")

    if puntaje >= 70:
        veredicto = "ALTA sospecha de clon"
    elif puntaje >= 40:
        veredicto = "sospecha media — revisar"
    else:
        veredicto = "baja / probable falso positivo"

    return {
        "dominio": dom,
        "url_final": r.url,
        "origen": origen,
        "alcanzable": True,
        "favicon_igual": fav_igual,
        "titulo": feats["titulo"][:120],
        "similitud": cmp,
        "puntaje": puntaje,
        "señales": señales,
        "veredicto": veredicto,
    }


# --------------------------------- Main ------------------------------------ #

def main():
    print("=" * 64)
    print("  CloneScan — detector de clones / phishing de sitios web")
    print("=" * 64)

    if len(sys.argv) > 1:
        entrada = sys.argv[1]
    else:
        entrada = input("\nLink de la página a revisar: ").strip()

    try:
        url = normaliza_url(entrada)
    except ValueError as e:
        sys.exit(f"[!] {e}")

    dom = dominio_de(url)
    print(f"\n[*] Referencia: {url}")
    print(f"[*] Dominio base: {dom}  (registrable: {registrable(dom)})")

    r = get(url)
    if not r or not r.text:
        sys.exit("[!] No se pudo descargar el sitio de referencia. Revisa el link.")

    base_feats = extrae_features(r.text)

    # Reintento: si el HTML llegó vacío (bloqueo WAF, compresión no soportada
    # o página-reto), prueba con el UA alternativo antes de darse por vencido.
    if not base_feats["titulo"] and not recursos_mismo_origen(r.url, r.text, 1):
        print("[i] HTML de referencia vacío; reintentando con UA alternativo...")
        r_alt = get(url, headers={"User-Agent": UA_ALT,
                                  "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"})
        if r_alt and r_alt.text and re.search(r"<title", r_alt.text, re.I):
            r = r_alt
            base_feats = extrae_features(r.text)
            print("[i] Recuperado con UA alternativo.")

    fav_base, fav_url = hash_favicon(r.url, r.text)
    print(f"[*] Título: {base_feats['titulo'][:80]!r}")
    print(f"[*] Favicon: {fav_url}  hash={fav_base}")
    if fav_base is not None:
        print(f"    -> Pivoteo manual en Shodan:  http.favicon.hash:{fav_base}")
    if not HAVE_BS4:
        print("[i] bs4 no instalado: parseo de DOM en modo básico.")

    # Reunir candidatos.
    candidatos = {}  # dominio -> origen

    print("\n[*] Fase 1/3 — dnstwist (typosquatting)...")
    dnstwist_status = "ok"
    if HAVE_DNSTWIST:
        _ns = DNSTWIST_NAMESERVERS or "resolver del sistema"
        print(f"    ({DNSTWIST_THREADS} hilos vía {_ns}; límite {DNSTWIST_TIMEOUT}s)")
        res_dt = ejecuta_con_progreso(
            lambda: candidatos_dnstwist(dom),
            "resolviendo variantes del dominio",
            DNSTWIST_TIMEOUT,
        )
        lista, total_dt, desc_sec = res_dt if res_dt else ([], 0, 0)
        if desc_sec:
            print(f"    [i] Secuestro de DNS detectado: {desc_sec} permutaciones "
                  f"falsas (apuntaban a la IP del secuestro) descartadas.")
        if total_dt > DNSTWIST_MAX_CANDIDATOS:
            # La red intercepta el DNS con IPs variables: no se puede distinguir
            # registrado de inexistente. No se sondea basura; fase INCONCLUSA.
            dnstwist_status = "inconcluso_dns"
            print(f"    [!] {total_dt} permutaciones resuelven a alguna IP: tu red "
                  f"intercepta el DNS y no permite distinguir un dominio "
                  f"registrado de uno inexistente.")
            print(f"        -> La fase de typosquatting queda INCONCLUSA (no se "
                  f"evalúa). Córrela desde una red sin intercepción de DNS, p.ej. "
                  f"un hotspot del celular.")
        else:
            for d in lista:
                candidatos.setdefault(d, "dnstwist")
            n = sum(1 for o in candidatos.values() if o == 'dnstwist')
            print(f"    {n} dominios registrados.")
    else:
        dnstwist_status = "omitido"
        print("    dnstwist no instalado (pip install dnstwist) — fase omitida.")

    # Cobertura de cambio de TLD (dnstwist no la cubre): marca.pro, .net, .co...
    tld_cands = candidatos_tld_swap(dom)
    for d in tld_cands:
        candidatos.setdefault(d, "tld-swap")
    print(f"    + cambio de TLD: {len(tld_cands)} variante(s) activa(s) "
          f"({', '.join(tld_cands[:6]) if tld_cands else 'ninguna'}).")

    print("[*] Fase 2/3 — Certificate Transparency (crt.sh)...")
    for d in consulta_crtsh(dom):
        candidatos.setdefault(d, "crt.sh")
    print(f"    {sum(1 for o in candidatos.values() if o=='crt.sh')} dominios con la marca en CT.")

    _kinfo = "con API key" if URLSCAN_API_KEY else "sin API key (límite básico)"
    print(f"[*] Fase 3/3 — urlscan.io (huella de contenido, cualquier dominio) [{_kinfo}]...")
    nuevos_us, huellas_validadas = candidatos_urlscan(r.url, r.text)
    for d, motivo in nuevos_us.items():
        if d not in candidatos:
            candidatos[d] = f"urlscan:{motivo}"
    print(f"    {sum(1 for o in candidatos.values() if str(o).startswith('urlscan'))} "
          f"dominios ajenos con tu huella de contenido.")

    # Analizar candidatos (si los hay).
    reporte = []
    if candidatos:
        print(f"\n[*] Analizando {len(candidatos)} candidatos (favicon + DOM)...\n")
        for i, (d, origen) in enumerate(sorted(candidatos.items()), 1):
            print(f"  [{i}/{len(candidatos)}] {d} ...", end=" ", flush=True)
            res = evalua_candidato(d, base_feats, fav_base, origen)
            reporte.append(res)
            print(f"puntaje={res['puntaje']}  {res['veredicto']}"
                  if res["alcanzable"] else "sin respuesta")
        reporte.sort(key=lambda x: x["puntaje"], reverse=True)
    else:
        print("\n[=] No se encontraron candidatos por ninguna vía.")

    # Resumen en consola.
    print("\n" + "=" * 64)
    print("  RESUMEN  (ordenado por sospecha)")
    print("=" * 64)
    sospechosos = [r for r in reporte if r["puntaje"] >= 40]
    if not sospechosos:
        print("  Sin coincidencias relevantes: no se detectaron clones.")
    if dnstwist_status == "inconcluso_dns":
        print("  [!] Nota: la fase de typosquatting quedó INCONCLUSA por "
              "intercepción de DNS; ese vector no está cubierto en esta corrida.")
    for res in sospechosos:
        print(f"\n  ● {res['dominio']}   [{res['puntaje']}/100]  {res['veredicto']}")
        print(f"      origen: {res['origen']}   url: {res.get('url_final','-')}")
        print(f"      señales: {', '.join(res['señales']) or '—'}")

    # Veredicto global para el certificado.
    veredicto_global = "limpio" if not sospechosos else "revision"

    # Guardar reporte SIEMPRE (incluido el caso limpio, que es el habitual).
    marca_t = palabra_marca(dom)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    salida = f"clone_scan_{marca_t}_{ts}.json"
    with open(salida, "w", encoding="utf-8") as f:
        json.dump({
            "referencia": url,
            "dominio_base": dom,
            "titulo": base_feats.get("titulo", ""),
            "favicon_hash": fav_base,
            "fecha": ts,
            "huellas_validadas": huellas_validadas,
            "total_candidatos": len(candidatos),
            "sospechosos": len(sospechosos),
            "veredicto_global": veredicto_global,
            "typosquatting_status": dnstwist_status,
            "resultados": reporte,
        }, f, ensure_ascii=False, indent=2)
    # Puntero al último reporte, para que el certificado lo encuentre fácil.
    with open("ultimo_reporte.txt", "w", encoding="utf-8") as f:
        f.write(salida + "\n")
    print(f"\n[+] Reporte guardado en: {salida}  (veredicto: {veredicto_global})")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrumpido.")

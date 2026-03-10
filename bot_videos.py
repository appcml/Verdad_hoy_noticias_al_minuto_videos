#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Videos para Facebook - Verdad Hoy
Versión OPTIMIZADA - Fuentes estables: Reddit, Rumble, Bitchute, TikTok, Vimeo
Descarga: yt-dlp con múltiples estrategias de fallback
"""

import requests
import re
import hashlib
import json
import os
import random
import time
import subprocess
from datetime import datetime, timedelta
from urllib.parse import urlparse
import yt_dlp

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_videos.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot.json')

TIEMPO_ENTRE_PUBLICACIONES = 58

# =============================================================================
# CATEGORÍAS OPTIMIZADAS
# =============================================================================

CATEGORIAS = {
    'conflictos': {
        'palabras': ['guerra', 'conflicto', 'ataque', 'bombardeo', 'invasión', 'misil', 
                     'batalla', 'ucrania', 'rusia', 'gaza', 'palestina', 'israel', 
                     'hamás', 'siria', 'militar', 'soldados', 'dron', 'combate', 'explosión'],
        'hashtags': '#Guerra #Conflicto #Militar #Urgente'
    },
    'narcotrafico': {
        'palabras': ['narcotráfico', 'cártel', 'droga', 'cocaína', 'fentanilo', 
                     'narco', 'sicario', 'decomiso', 'sinaloa', 'jalisco', 'cjng', 
                     'balacera', 'ejecución', 'clan', 'golfo'],
        'hashtags': '#Narcotráfico #Seguridad #CrimenOrganizado #Mexico'
    },
    'politica': {
        'palabras': ['gobierno', 'presidente', 'elecciones', 'política', 'protesta', 
                     'golpe', 'corrupción', 'onu', 'diplomacia', 'sanciones', 'congreso'],
        'hashtags': '#Política #Internacional #Gobierno #Noticias'
    },
    'desastres': {
        'palabras': ['terremoto', 'tsunami', 'huracán', 'inundación', 'incendio', 
                     'desastre', 'tragedia', 'accidente', 'víctimas', 'evacuación', 'derrumbe'],
        'hashtags': '#Desastre #Emergencia #Tragedia #ÚltimaHora'
    }
}

TODAS_PALABRAS = []
for cat in CATEGORIAS.values():
    TODAS_PALABRAS.extend(cat['palabras'])

# =============================================================================
# FUENTES ESTABLES (Priorizadas por confiabilidad)
# =============================================================================

# 1. REDDIT - Muy estable, mucho contenido de conflictos
REDDIT_SUBREDDITS = [
    'CombatFootage', 'war', 'UkraineWarVideoReport', 'syriancivilwar',
    'NarcoFootage', 'ActualPublicFreakouts', 'CatastrophicFailure', 
    'worldnews', 'news', 'PublicFreakout', 'IdiotsNearlyDying'
]

# 2. RUMBLE - Alternativa a YouTube, muy permisiva
RUMBLE_CHANNELS = [
    'RT', 'AlJazeeraEnglish', 'Reuters', 'France24', 'TRTWorld', 
    'CGTN', 'TelesurEnglish', 'PressTV'
]

# 3. BITCHUTE - Sin censura, contenido alternativo
BITCHUTE_CHANNELS = [
    'timcast', 'styxhexenhammer666', 'thejimmydoreshow', 'corbettreport'
]

# 4. TIKTOK - Tags públicos funcionan bien
TIKTOK_TAGS = ['war', 'military', 'news', 'breakingnews', 'conflict', 'police']

# 5. VIMEO - Canales de documentales/noticias
VIMEO_CHANNELS = ['aljazeera', 'reuters', 'afp', 'france24', 'euronews']

# =============================================================================
# UTILIDADES
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'video': '🎬', 'buscar': '🔍'}
    print(f"{iconos.get(tipo, 'ℹ️')} {mensaje}", flush=True)

def cargar_json(ruta, default=None):
    if default is None:
        default = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return default

def guardar_json(ruta, datos):
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"Error guardando: {e}", 'error')
        return False

def generar_hash(texto):
    return hashlib.md5(texto.lower().strip().encode()).hexdigest()

def detectar_categoria(titulo, descripcion=''):
    texto = f"{titulo} {descripcion}".lower()
    puntuaciones = {}
    for nombre, datos in CATEGORIAS.items():
        score = sum(1 for palabra in datos['palabras'] if palabra in texto)
        puntuaciones[nombre] = score
    mejor = max(puntuaciones, key=puntuaciones.get)
    return mejor if puntuaciones[mejor] > 0 else 'conflictos'

def obtener_hashtags(categoria):
    return CATEGORIAS.get(categoria, {}).get('hashtags', '#Noticias #Actualidad')

# =============================================================================
# HISTORIAL Y ESTADO
# =============================================================================

def cargar_historial():
    default = {'urls': [], 'titulos': [], 'hashes': [], 'videos': []}
    historial = cargar_json(HISTORIAL_PATH, default)
    log(f"Historial: {len(historial.get('videos', []))} videos guardados")
    return historial

def guardar_historial(historial, url, titulo, fuente):
    url_hash = generar_hash(url)
    historial.setdefault('urls', []).append(url)
    historial.setdefault('titulos', []).append(titulo[:100])
    historial.setdefault('hashes', []).append(url_hash)
    historial.setdefault('videos', []).append({
        'url': url, 'titulo': titulo[:100], 
        'fecha': datetime.now().isoformat(), 'fuente': fuente
    })
    # Mantener últimos 150
    for key in ['urls', 'titulos', 'hashes']:
        historial[key] = historial[key][-150:]
    historial['videos'] = historial['videos'][-150:]
    guardar_json(HISTORIAL_PATH, historial)
    log(f"Guardado en historial [{fuente}]", 'exito')

def ya_publicado(historial, url, titulo):
    if generar_hash(url) in historial.get('hashes', []):
        return True
    if url in historial.get('urls', []):
        return True
    # Comparación de título simplificada
    titulo_simple = re.sub(r'[^\w]', '', titulo.lower())[:25]
    for t in historial.get('titulos', []):
        if re.sub(r'[^\w]', '', t.lower())[:25] == titulo_simple:
            return True
    return False

def verificar_tiempo():
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None, 'total': 0})
    if not estado.get('ultima_publicacion'):
        return True, estado
    try:
        ultima = datetime.fromisoformat(estado['ultima_publicacion'])
        transcurrido = (datetime.now() - ultima).total_seconds() / 60
        if transcurrido < TIEMPO_ENTRE_PUBLICACIONES:
            faltan = TIEMPO_ENTRE_PUBLICACIONES - transcurrido
            log(f"⏳ Esperando {faltan:.0f} minutos...", 'advertencia')
            return False, estado
    except:
        pass
    return True, estado

# =============================================================================
# BÚSQUEDA EN FUENTES (Ordenadas por prioridad)
# =============================================================================

def buscar_reddit():
    """FUENTE #1: Reddit - Muy estable, mucho contenido"""
    videos = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    
    subreddits = random.sample(REDDIT_SUBREDDITS, min(5, len(REDDIT_SUBREDDITS)))
    
    for subreddit in subreddits:
        try:
            time.sleep(1.5)  # Respetar rate limit
            url = f"https://www.reddit.com/r/ {subreddit}/hot.json?limit=15"
            resp = requests.get(url, headers=headers, timeout=20)
            
            if resp.status_code == 429:
                log(f"Reddit rate limit en r/{subreddit}", 'advertencia')
                time.sleep(5)
                continue
            
            if resp.status_code != 200:
                continue
                
            data = resp.json()
            if 'data' not in data or 'children' not in data['data']:
                continue
            
            for post in data['data']['children']:
                try:
                    post_data = post['data']
                    
                    # Solo posts con video
                    is_video = post_data.get('is_video', False)
                    url_overridden = post_data.get('url_overridden_by_dest', '')
                    has_video_url = 'v.redd.it' in url_overridden
                    
                    if not is_video and not has_video_url:
                        continue
                    
                    titulo = post_data.get('title', '')
                    if len(titulo) < 10:  # Títulos muy cortos suelen ser spam
                        continue
                    
                    # Verificar relevancia
                    es_relevante = any(p in titulo.lower() for p in TODAS_PALABRAS)
                    if not es_relevante:
                        continue
                    
                    permalink = post_data.get('permalink', '')
                    if not permalink:
                        continue
                    
                    videos.append({
                        'titulo': titulo[:200],
                        'url': f"https://www.reddit.com {permalink}",
                        'video_url_directa': url_overridden if has_video_url else None,
                        'fuente': f'Reddit/r/{subreddit}',
                        'tipo': 'reddit',
                        'categoria': detectar_categoria(titulo),
                        'score': post_data.get('score', 0),
                        'prioridad': 10  # Alta prioridad
                    })
                except:
                    continue
                    
        except Exception as e:
            log(f"Reddit r/{subreddit} error: {str(e)[:60]}", 'advertencia')
    
    # Ordenar por score (popularidad)
    videos.sort(key=lambda x: x.get('score', 0), reverse=True)
    log(f"Reddit: {len(videos)} videos encontrados", 'exito')
    return videos

def buscar_rumble():
    """FUENTE #2: Rumble - Plataforma alternativa estable"""
    videos = []
    
    try:
        canales = random.sample(RUMBLE_CHANNELS, min(3, len(RUMBLE_CHANNELS)))
        
        for canal in canales:
            try:
                time.sleep(1)
                # Rumble tiene una estructura HTML predecible
                url = f"https://rumble.com/c/ {canal}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                resp = requests.get(url, headers=headers, timeout=15)
                
                if resp.status_code != 200:
                    continue
                
                html = resp.text
                
                # Buscar videos en el HTML (patrones comunes de Rumble)
                # Pattern 1: URLs de video directas
                pattern1 = r'https://rumble\.com/v[a-zA-Z0-9]+-[^\"]+'
                matches = list(set(re.findall(pattern1, html)))
                
                # Pattern 2: Data attributes
                pattern2 = r'data-video-url="(/v[a-zA-Z0-9]+-[^"]+)"'
                matches2 = re.findall(pattern2, html)
                matches2 = [f"https://rumble.com{m}" for m in matches2]
                
                all_matches = list(set(matches + matches2))
                
                for match in all_matches[:8]:
                    try:
                        # Extraer título de la URL
                        slug = match.split('/')[-1]
                        titulo = slug.replace('-', ' ').replace('v', '', 1).title()
                        # Limpiar ID al inicio
                        titulo = re.sub(r'^[a-z0-9]+ ', '', titulo, flags=re.IGNORECASE)
                        
                        if any(p in titulo.lower() for p in TODAS_PALABRAS):
                            videos.append({
                                'titulo': titulo[:150],
                                'url': match,
                                'fuente': f'Rumble/{canal}',
                                'tipo': 'rumble',
                                'categoria': detectar_categoria(titulo),
                                'prioridad': 8
                            })
                    except:
                        continue
                        
            except Exception as e:
                log(f"Rumble {canal} error: {str(e)[:50]}", 'advertencia')
                
    except Exception as e:
        log(f"Rumble general error: {str(e)[:50]}", 'advertencia')
    
    log(f"Rumble: {len(videos)} videos encontrados", 'exito')
    return videos

def buscar_bitchute():
    """FUENTE #3: Bitchute - Contenido alternativo sin censura"""
    videos = []
    
    try:
        canales = random.sample(BITCHUTE_CHANNELS, min(2, len(BITCHUTE_CHANNELS)))
        
        for canal in canales:
            try:
                time.sleep(1)
                url = f"https://www.bitchute.com/channel/ {canal}/"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                resp = requests.get(url, headers=headers, timeout=15)
                
                if resp.status_code != 200:
                    continue
                
                # Extraer IDs de video
                pattern = r'/video/([a-zA-Z0-9]+)/'
                matches = list(set(re.findall(pattern, resp.text)))
                
                for video_id in matches[:6]:
                    video_url = f"https://www.bitchute.com/video/ {video_id}/"
                    
                    videos.append({
                        'titulo': f'Video {video_id[:8]}...',  # Simplificado
                        'url': video_url,
                        'fuente': f'Bitchute/{canal}',
                        'tipo': 'bitchute',
                        'categoria': 'conflictos',  # Por defecto
                        'prioridad': 6
                    })
                    
            except Exception as e:
                log(f"Bitchute {canal} error: {str(e)[:50]}", 'advertencia')
                
    except Exception as e:
        log(f"Bitchute error: {str(e)[:50]}", 'advertencia')
    
    log(f"Bitchute: {len(videos)} videos encontrados", 'exito')
    return videos

def buscar_tiktok():
    """FUENTE #4: TikTok - Tags públicos"""
    videos = []
    
    try:
        tags = random.sample(TIKTOK_TAGS, min(3, len(TIKTOK_TAGS)))
        
        for tag in tags:
            try:
                time.sleep(2)  # TikTok es más estricto con rate limits
                url = f"https://www.tiktok.com/tag/ {tag}?lang=en"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Cache-Control': 'max-age=0',
                }
                
                resp = requests.get(url, headers=headers, timeout=20)
                
                if resp.status_code != 200:
                    continue
                
                # Buscar URLs de video en el HTML/JSON incrustado
                pattern = r'https://www\.tiktok\.com/@[\w\.]+/video/\d+'
                matches = list(set(re.findall(pattern, resp.text)))
                
                for match in matches[:5]:
                    videos.append({
                        'titulo': f'TikTok #{tag}',
                        'url': match,
                        'fuente': 'TikTok',
                        'tipo': 'tiktok',
                        'categoria': detectar_categoria(tag),
                        'prioridad': 7
                    })
                    
            except Exception as e:
                log(f"TikTok #{tag} error: {str(e)[:50]}", 'advertencia')
                
    except Exception as e:
        log(f"TikTok error: {str(e)[:50]}", 'advertencia')
    
    log(f"TikTok: {len(videos)} videos encontrados", 'exito')
    return videos

def buscar_vimeo():
    """FUENTE #5: Vimeo - Canales de noticias"""
    videos = []
    
    try:
        canales = random.sample(VIMEO_CHANNELS, min(3, len(VIMEO_CHANNELS)))
        
        for canal in canales:
            try:
                time.sleep(1)
                # Vimeo tiene RSS/feed disponible
                url = f"https://vimeo.com/ {canal}/videos/rss"
                resp = requests.get(url, timeout=15)
                
                if resp.status_code != 200:
                    # Intentar con la página normal
                    url = f"https://vimeo.com/ {canal}"
                    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                    
                    if resp.status_code == 200:
                        # Extraer de HTML
                        pattern = r'https://vimeo\.com/(\d+)'
                        matches = list(set(re.findall(pattern, resp.text)))
                        
                        for video_id in matches[:5]:
                            videos.append({
                                'titulo': f'Vimeo {video_id}',
                                'url': f"https://vimeo.com/ {video_id}",
                                'fuente': f'Vimeo/{canal}',
                                'tipo': 'vimeo',
                                'categoria': 'politica',
                                'prioridad': 5
                            })
                    continue
                
                # Parsear RSS
                import xml.etree.ElementTree as ET
                root = ET.fromstring(resp.content)
                
                # Namespace de media
                ns = {'media': 'http://search.yahoo.com/mrss/'}
                
                for item in root.findall('.//item')[:5]:
                    titulo = item.find('title').text if item.find('title') is not None else ''
                    link = item.find('link').text if item.find('link') is not None else ''
                    
                    # Buscar contenido media
                    media_content = item.find('media:content', ns)
                    if media_content is not None:
                        video_url = media_content.get('url', '')
                    else:
                        video_url = link
                    
                    if titulo and any(p in titulo.lower() for p in TODAS_PALABRAS):
                        videos.append({
                            'titulo': titulo[:150],
                            'url': video_url or link,
                            'fuente': f'Vimeo/{canal}',
                            'tipo': 'vimeo',
                            'categoria': detectar_categoria(titulo),
                            'prioridad': 6
                        })
                        
            except Exception as e:
                log(f"Vimeo {canal} error: {str(e)[:50]}", 'advertencia')
                
    except Exception as e:
        log(f"Vimeo error: {str(e)[:50]}", 'advertencia')
    
    log(f"Vimeo: {len(videos)} videos encontrados", 'exito')
    return videos

def buscar_newsapi():
    """FUENTE #6: NewsAPI - Como fallback"""
    videos = []
    if not NEWS_API_KEY:
        return videos
    
    try:
        # Buscar noticias recientes con video potencial
        queries = ['war footage', 'military conflict', 'breaking news video']
        query = random.choice(queries)
        
        resp = requests.get(
            "https://newsapi.org/v2/everything ",
            params={
                'q': query,
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 15,
                'apiKey': NEWS_API_KEY
            },
            timeout=15
        )
        
        data = resp.json()
        if data.get('status') == 'ok':
            for art in data.get('articles', []):
                titulo = art.get('title', '')
                url = art.get('url', '')
                
                if '[Removed]' in titulo or not url:
                    continue
                
                # Solo si es relevante
                if any(p in titulo.lower() for p in TODAS_PALABRAS):
                    # yt-dlp intentará extraer video de la página de noticias
                    videos.append({
                        'titulo': titulo[:200],
                        'url': url,
                        'fuente': art.get('source', {}).get('name', 'NewsAPI'),
                        'tipo': 'news_site',
                        'categoria': detectar_categoria(titulo),
                        'prioridad': 4
                    })
    except Exception as e:
        log(f"NewsAPI error: {str(e)[:50]}", 'advertencia')
    
    log(f"NewsAPI: {len(videos)} noticias", 'exito')
    return videos

def buscar_todos():
    """Busca en todas las fuentes por orden de prioridad"""
    log("Iniciando búsqueda en fuentes...", 'buscar')
    todos_videos = []
    
    # Prioridad 1: Reddit (más contenido, más estable)
    reddit_videos = buscar_reddit()
    todos_videos.extend(reddit_videos)
    if len(reddit_videos) >= 3:
        log("Suficientes videos de Reddit, omitiendo otras fuentes...", 'info')
        return deduplicar_y_ordenar(todos_videos)
    
    # Prioridad 2: Rumble
    if len(todos_videos) < 5:
        todos_videos.extend(buscar_rumble())
    
    # Prioridad 3: TikTok
    if len(todos_videos) < 5:
        todos_videos.extend(buscar_tiktok())
    
    # Prioridad 4: Bitchute
    if len(todos_videos) < 4:
        todos_videos.extend(buscar_bitchute())
    
    # Prioridad 5: Vimeo
    if len(todos_videos) < 3:
        todos_videos.extend(buscar_vimeo())
    
    # Prioridad 6: NewsAPI (fallback)
    if len(todos_videos) < 3:
        todos_videos.extend(buscar_newsapi())
    
    return deduplicar_y_ordenar(todos_videos)

def deduplicar_y_ordenar(videos):
    """Elimina duplicados y ordena por prioridad"""
    if not videos:
        return []
    
    # Eliminar duplicados por URL
    urls_vistas = set()
    unicos = []
    for v in videos:
        url = v.get('url', '')
        if url and url not in urls_vistas:
            urls_vistas.add(url)
            unicos.append(v)
    
    # Ordenar por prioridad (descendente)
    unicos.sort(key=lambda x: x.get('prioridad', 0), reverse=True)
    
    log(f"Total videos únicos: {len(unicos)}", 'exito')
    return unicos

# =============================================================================
# DESCARGA DE VIDEO - SISTEMA ROBUSTO CON MÚLTIPLES ESTRATEGIAS
# =============================================================================

def descargar_video(url, tipo):
    """
    Sistema de descarga con múltiples estrategias de fallback
    """
    log(f"Descargando [{tipo}]: {url[:70]}...", 'video')
    
    # Estrategia 1: yt-dlp con configuración estándar
    video_path = _descargar_ytdlp_estandar(url, tipo)
    if video_path:
        return video_path
    
    # Estrategia 2: yt-dlp con formato más permisivo
    log("Reintentando con formato alternativo...", 'advertencia')
    video_path = _descargar_ytdlp_permisivo(url, tipo)
    if video_path:
        return video_path
    
    # Estrategia 3: yt-dlp con extractor específico
    if tipo == 'reddit':
        video_path = _descargar_reddit_directo(url)
        if video_path:
            return video_path
    
    log("No se pudo descargar el video", 'error')
    return None

def _descargar_ytdlp_estandar(url, tipo):
    """Configuración estándar de yt-dlp"""
    try:
        ydl_opts = {
            'format': 'best[height<=720][filesize<80M]/best[height<=480][filesize<80M]/best[filesize<80M]',
            'outtmpl': '/tmp/video_%(id)s_%(height)sp.%(ext)s',
            'max_filesize': 80000000,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            },
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if not info:
                return None
            
            video_path = ydl.prepare_filename(info)
            
            # Verificar si existe (puede cambiar extensión)
            if not os.path.exists(video_path):
                base = os.path.splitext(video_path)[0]
                for ext in ['.mp4', '.mkv', '.webm', '.mov']:
                    if os.path.exists(base + ext):
                        video_path = base + ext
                        break
            
            if os.path.exists(video_path) and os.path.getsize(video_path) > 300000:
                size_mb = os.path.getsize(video_path) / 1024 / 1024
                log(f"✅ Descargado: {size_mb:.1f} MB [{info.get('height', '?')}p]", 'exito')
                return video_path
            
            return None
            
    except Exception as e:
        error_msg = str(e).lower()
        if "format" in error_msg:
            log("Formato no disponible en estándar", 'advertencia')
        elif "unavailable" in error_msg:
            log("Video no disponible", 'advertencia')
        else:
            log(f"Error estándar: {str(e)[:80]}", 'advertencia')
        return None

def _descargar_ytdlp_permisivo(url, tipo):
    """Configuración más permisiva - cualquier formato"""
    try:
        ydl_opts = {
            'format': 'worst[filesize<100M]/best[filesize<100M]/worst/best',
            'outtmpl': '/tmp/video_fallback_%(id)s.%(ext)s',
            'max_filesize': 100000000,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)
            
            if not os.path.exists(video_path):
                base = os.path.splitext(video_path)[0]
                for ext in ['.mp4', '.mkv', '.webm', '.mov']:
                    if os.path.exists(base + ext):
                        video_path = base + ext
                        break
            
            if os.path.exists(video_path) and os.path.getsize(video_path) > 300000:
                log(f"✅ Descargado (formato alternativo): {os.path.getsize(video_path)/1024/1024:.1f} MB", 'exito')
                return video_path
            
            return None
            
    except Exception as e:
        log(f"Error permisivo: {str(e)[:80]}", 'advertencia')
        return None

def _descargar_reddit_directo(url):
    """Método específico para Reddit usando la API de Reddit"""
    try:
        # Extraer ID del post de Reddit
        match = re.search(r'/comments/([a-z0-9]+)/', url)
        if not match:
            return None
        
        post_id = match.group(1)
        
        # Obtener JSON del post
        json_url = f"https://www.reddit.com/comments/ {post_id}.json"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        resp = requests.get(json_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        if not data or len(data) < 2:
            return None
        
        # Extraer URL de video
        post_data = data[0]['data']['children'][0]['data']
        
        if post_data.get('is_video') and 'media' in post_data:
            media = post_data['media']
            if 'reddit_video' in media:
                video_url = media['reddit_video'].get('fallback_url')
                if video_url:
                    # Descargar directamente
                    video_path = f"/tmp/reddit_{post_id}.mp4"
                    vresp = requests.get(video_url, headers=headers, timeout=60, stream=True)
                    
                    if vresp.status_code == 200:
                        with open(video_path, 'wb') as f:
                            for chunk in vresp.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        if os.path.exists(video_path) and os.path.getsize(video_path) > 300000:
                            log(f"✅ Descargado vía API Reddit: {os.path.getsize(video_path)/1024/1024:.1f} MB", 'exito')
                            return video_path
        
        return None
        
    except Exception as e:
        log(f"Error Reddit API: {str(e)[:80]}", 'advertencia')
        return None

# =============================================================================
# VERIFICACIÓN Y PUBLICACIÓN
# =============================================================================

def verificar_video(video_path):
    """Verifica que el video sea válido para Facebook"""
    try:
        if not os.path.exists(video_path):
            return False, "No existe archivo"
        
        size = os.path.getsize(video_path)
        size_mb = size / 1024 / 1024
        
        if size < 300000:  # 300KB mínimo
            return False, f"Muy pequeño ({size_mb:.1f} MB)"
        
        if size > 1073741824:  # 1GB máximo para Facebook
            return False, f"Muy grande ({size_mb:.1f} MB)"
        
        # Verificar con ffprobe si está disponible
        try:
            cmd = [
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,duration,codec_name',
                '-of', 'json', video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            info = json.loads(result.stdout)
            
            if 'streams' in info and info['streams']:
                stream = info['streams'][0]
                width = stream.get('width', 0)
                height = stream.get('height', 0)
                duration = float(stream.get('duration', 0))
                codec = stream.get('codec_name', '')
                
                log(f"Video info: {width}x{height} | {duration:.1f}s | {codec}", 'info')
                
                # Reglas de validación
                if duration > 600:  # 10 minutos máximo
                    return False, f"Muy largo ({duration/60:.1f} min)"
                
                if width < 480 or height < 360:  # Calidad mínima
                    return False, f"Baja calidad ({width}x{height})"
                
                # Si es MKV o WEBM, convertir a MP4 para Facebook
                if codec in ['vp9', 'av1'] or video_path.endswith(('.mkv', '.webm')):
                    return _convertir_a_mp4(video_path)
                
                return True, video_path
                
        except Exception as e:
            # Si ffprobe no está disponible, asumir OK si tiene tamaño adecuado
            log(f"ffprobe no disponible, verificación básica", 'advertencia')
            if size_mb > 1:  # Si es más de 1MB, probablemente está bien
                return True, video_path
            return False, "No se pudo verificar"
            
    except Exception as e:
        log(f"Error verificación: {e}", 'error')
        return False, str(e)

def _convertir_a_mp4(video_path):
    """Convierte video a MP4 compatible con Facebook"""
    try:
        output_path = video_path.rsplit('.', 1)[0] + '_fb.mp4'
        
        cmd = [
            'ffmpeg', '-y', '-i', video_path,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            '-pix_fmt', 'yuv420p',
            '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',  # Dimensiones pares
            output_path
        ]
        
        log("Convirtiendo a MP4 compatible...", 'video')
        result = subprocess.run(cmd, capture_output=True, timeout=180)
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 300000:
            # Eliminar original
            try:
                os.remove(video_path)
            except:
                pass
            return True, output_path
        
        return False, "Falló conversión"
        
    except Exception as e:
        log(f"Error conversión: {e}", 'error')
        return False, str(e)

def publicar_facebook(titulo, descripcion, video_path, categoria):
    """Publica video en Facebook con manejo de errores"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales Facebook", 'error')
        return False
    
    if not os.path.exists(video_path):
        log("ERROR: Archivo de video no existe", 'error')
        return False
    
    hashtags = obtener_hashtags(categoria)
    
    # Construir mensaje optimizado para engagement
    mensaje = f"""🎬 {titulo}

{descripcion[:180]}{'...' if len(descripcion) > 180 else ''}

{hashtags} #Video #Noticias #ÚltimaHora #VerdadHoy

📢 Noticias sin censura. Síguenos para más contenido."""

    # Truncar si es necesario (límite de Facebook es 2200 chars, pero mejor ser breve)
    if len(mensaje) > 2000:
        mensaje = mensaje[:1990] + "..."
    
    size_mb = os.path.getsize(video_path) / 1024 / 1024
    log(f"Subiendo a Facebook: {size_mb:.1f} MB...", 'video')
    
    try:
        url = f"https://graph.facebook.com/v18.0/ {FB_PAGE_ID}/videos"
        
        with open(video_path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {
                'description': mensaje,
                'access_token': FB_ACCESS_TOKEN,
                'published': 'true'
            }
            
            resp = requests.post(url, files=files, data=data, timeout=600)
        
        result = resp.json()
        
        if resp.status_code == 200 and 'id' in result:
            video_id = result['id']
            log(f"✅ PUBLICADO EXITOSAMENTE: {video_id}", 'exito')
            
            # Mostrar URL del post
            post_url = f"https://facebook.com/ {FB_PAGE_ID}/videos/{video_id}"
            log(f"URL: {post_url}", 'exito')
            return True
            
        else:
            error = result.get('error', {})
            error_msg = error.get('message', str(result))
            error_code = error.get('code', 'unknown')
            log(f"❌ Error Facebook [{error_code}]: {error_msg}", 'error')
            
            # Manejar errores específicos
            if error_code == 190:  # Token inválido
                log("El token de acceso ha expirado o es inválido", 'error')
            elif error_code == 4:  # Límite de API
                log("Límite de API alcanzado, esperar...", 'error')
            elif 'size' in error_msg.lower():
                log("Video demasiado grande para Facebook", 'error')
            
            return False
            
    except requests.exceptions.Timeout:
        log("❌ Timeout al subir a Facebook (10 min)", 'error')
        return False
    except Exception as e:
        log(f"❌ Error publicando: {e}", 'error')
        return False

# =============================================================================
# LIMPIEZA Y MAIN
# =============================================================================

def limpiar_temporales():
    """Limpia archivos temporales de ejecuciones anteriores"""
    try:
        import glob
        patterns = ['/tmp/video_*', '/tmp/reddit_*', '/tmp/fb_*', '/tmp/*.part']
        eliminados = 0
        
        for pattern in patterns:
            for f in glob.glob(pattern):
                try:
                    os.remove(f)
                    eliminados += 1
                except:
                    pass
        
        if eliminados > 0:
            log(f"Limpiados {eliminados} archivos temporales", 'info')
    except:
        pass

def main():
    """Función principal del bot"""
    print("\n" + "="*70)
    print("🎬 BOT DE VIDEOS - VERDAD HOY")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  Intervalo: {TIEMPO_ENTRE_PUBLICACIONES} minutos")
    print("="*70)
    
    # Verificar tiempo entre publicaciones
    puede_proceder, estado = verificar_tiempo()
    if not puede_proceder:
        return True  # No es error, solo no toca publicar aún
    
    # Verificar credenciales
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR CRÍTICO: Faltan credenciales de Facebook", 'error')
        log("Configura FB_PAGE_ID y FB_ACCESS_TOKEN en secrets", 'error')
        return False
    
    # Limpiar temporales
    limpiar_temporales()
    
    # Cargar historial
    historial = cargar_historial()
    
    # Buscar videos
    videos = buscar_todos()
    
    if not videos:
        log("ERROR: No se encontraron videos en ninguna fuente", 'error')
        return False
    
    # Filtrar ya publicados
    videos_nuevos = [v for v in videos if not ya_publicado(historial, v['url'], v['titulo'])]
    log(f"Videos nuevos: {len(videos_nuevos)} de {len(videos)}", 'info')
    
    if not videos_nuevos:
        log("No hay videos nuevos para publicar", 'advertencia')
        return False
    
    # Intentar publicar (hasta 5 intentos)
    exito_total = False
    
    for intento, video in enumerate(videos_nuevos[:5], 1):
        log(f"\n{'='*70}", 'info')
        log(f"INTENTO {intento}/5", 'info')
        log(f"Título: {video['titulo'][:60]}...", 'info')
        log(f"Fuente: {video['fuente']} | Tipo: {video['tipo']}", 'info')
        log(f"Categoría: {video.get('categoria', 'conflictos')}", 'info')
        log(f"Prioridad: {video.get('prioridad', 0)}", 'info')
        
        # Descargar
        video_path = descargar_video(video['url'], video['tipo'])
        
        if not video_path:
            log("❌ Falló descarga, siguiente...", 'advertencia')
            continue
        
        # Verificar
        ok, resultado = verificar_video(video_path)
        
        if not ok:
            log(f"❌ Video rechazado: {resultado}", 'advertencia')
            try:
                os.remove(video_path)
            except:
                pass
            continue
        
        if isinstance(resultado, str) and resultado != video_path:
            video_path = resultado  # Path convertido
        
        # Publicar
        exito = publicar_facebook(
            video['titulo'],
            video.get('descripcion', ''),
            video_path,
            video.get('categoria', 'conflictos')
        )
        
        # Limpiar archivo
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
                log("Archivo temporal eliminado", 'info')
        except Exception as e:
            log(f"No se pudo eliminar temporal: {e}", 'advertencia')
        
        if exito:
            # Guardar en historial
            guardar_historial(historial, video['url'], video['titulo'], video['fuente'])
            
            # Actualizar estado
            estado['ultima_publicacion'] = datetime.now().isoformat()
            estado['total'] = estado.get('total', 0) + 1
            guardar_json(ESTADO_PATH, estado)
            
            # Resumen final
            print("\n" + "="*70)
            log("🎉 ÉXITO TOTAL", 'exito')
            print(f"✅ Video publicado #{estado['total']}")
            print(f"🎬 {video['titulo'][:70]}")
            print(f"🏢 Fuente: {video['fuente']}")
            print(f"📂 Categoría: {video.get('categoria', 'conflictos')}")
            print(f"⏰ Próxima: {(datetime.now() + timedelta(minutes=TIEMPO_ENTRE_PUBLICACIONES)).strftime('%H:%M')}")
            print("="*70)
            
            exito_total = True
            break
        else:
            log("❌ Falló publicación, intentando siguiente...", 'advertencia')
    
    if not exito_total:
        log("❌ Todos los intentos fallaron", 'error')
        return False
    
    return True

if __name__ == "__main__":
    try:
        resultado = main()
        exit(0 if resultado else 1)
    except KeyboardInterrupt:
        log("\n🛑 Interrumpido por usuario", 'advertencia')
        exit(1)
    except Exception as e:
        log(f"\n💥 ERROR CRÍTICO NO MANEJADO: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

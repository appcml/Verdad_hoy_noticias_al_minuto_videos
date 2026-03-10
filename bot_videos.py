#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Videos para Facebook - Verdad Hoy
Publica videos de noticias cada 1 hora
Fuentes: Dailymotion, Vimeo, Reddit (corregido), RSS de video
"""

import requests
import feedparser
import re
import hashlib
import json
import os
import random
import subprocess
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
import yt_dlp

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_videos.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot.json')

TIEMPO_ENTRE_PUBLICACIONES = 58  # minutos

# =============================================================================
# CATEGORÍAS
# =============================================================================

CATEGORIAS = {
    'conflictos_guerra': {
        'palabras': [
            'guerra', 'conflicto', 'ataque', 'bombardeo', 'invasión', 'ofensiva', 'misil',
            'batalla', 'combate', 'enfrentamiento', 'tensión internacional', 'sanciones',
            'embargo', 'crisis diplomática', 'guerra civil', 'rebelión', 'insurgencia',
            'terrorismo', 'ataque terrorista', 'extremista', 'yihadista', 'talibán',
            'isis', 'al qaeda', 'guerrilla', 'paramilitar', 'milicia', 'ejército',
            'soldados', 'tropas', 'despliegue militar', 'base militar', 'arsenal',
            'armas', 'destrucción', 'masacre', 'genocidio', 'crímenes de guerra',
            'ucrania', 'rusia', 'gaza', 'palestina', 'israel', 'hamás', 'líbano', 'hezbolá',
            'siria', 'irak', 'afganistán', 'yemen', 'myanmar', 'sudán', 'etiopía', 'somalia',
            'mali', 'níger', 'burkina faso', 'haití', 'dron', 'drones', 'ucav', 'misil balístico',
            'artillería', 'tanque', 'blindado', 'helicóptero', 'caza', 'bombardero',
        ],
        'hashtags': ['#Guerra', '#Conflicto', '#Militar']
    },
    
    'narcotrafico': {
        'palabras': [
            'narcotráfico', 'droga', 'cártel', 'cartel', 'tráfico de drogas', 'cocaína',
            'marihuana', 'fentanilo', 'metanfetamina', 'laboratorio clandestino',
            'narco', 'narcotraficante', 'capo', 'jefe de cartel', 'sicario', 'ejecución',
            'balacera', 'enfrentamiento armado', 'decomiso', 'incautación', 'tonelada',
            'ruta del narcotráfico', 'lavado de dinero', 'narcobloqueo', 'narcotúnel',
            'sinaloa', 'jalisco', 'cjng', 'golfo', 'zetas', 'michoacana', 'tijuana',
            'colombia', 'méxico', 'perú', 'bolivia', 'honduras', 'guatemala', 'el salvador',
        ],
        'hashtags': ['#Narcotráfico', '#Seguridad', '#CrimenOrganizado']
    },
    
    'politica_internacional': {
        'palabras': [
            'gobierno', 'presidente', 'elecciones', 'política', 'político', 'congreso',
            'parlamento', 'senado', 'ministro', 'canciller', 'embajador', 'diplomacia',
            'cumbre', 'g20', 'g7', 'onu', 'otan', 'unión europea', 'brexit',
            'impeachment', 'corrupción', 'protesta', 'manifestación', 'huelga',
            'golpe de estado', 'crisis política', 'dimisión', 'renuncia', 'fraude electoral',
            'oposición', 'partido político', 'campaña electoral', 'debate', 'discurso',
        ],
        'hashtags': ['#Política', '#Internacional', '#Gobierno']
    },
    
    'crisis_economica': {
        'palabras': [
            'crisis económica', 'recesión', 'inflación', 'devaluación', 'quiebra',
            'bancarrota', 'crisis financiera', 'colapso económico', 'deuda',
            'fmi', 'bm', 'reserva federal', 'bce', 'crisis bancaria', 'corralito',
            'deuda soberana', 'crisis de deuda', 'rescate económico', 'austeridad',
            'desempleo', 'paro', 'crisis laboral', 'huelga general', 'protesta social',
        ],
        'hashtags': ['#Economía', '#Crisis', '#Finanzas']
    },
    
    'desastres_tragedias': {
        'palabras': [
            'terremoto', 'tsunami', 'huracán', 'tornado', 'inundación', 'incendio',
            'sequía', 'hambruna', 'epidemia', 'pandemia', 'accidente', 'tragedia',
            'desastre natural', 'catástrofe', 'emergencia', 'evacuación', 'rescate',
            'derrumbe', 'explosión', 'accidente aéreo', 'accidente marítimo',
            'víctimas', 'muertos', 'heridos', 'desaparecidos', 'damnificados',
        ],
        'hashtags': ['#Desastre', '#Emergencia', '#Tragedia']
    },
    
    'violencia_crimen': {
        'palabras': [
            'violencia', 'homicidio', 'asesinato', 'masacre', 'ejecución', 'secuestro',
            'extorsión', 'tráfico de personas', 'tráfico de armas', 'contrabando',
            'crimen organizado', 'pandilla', 'mara', 'prisión', 'fuga', 'motín',
            'robo', 'atraco', 'asalto', 'agresión', 'detenido', 'arrestado',
            'operativo policial', 'redada', 'allanamiento', 'persecución',
        ],
        'hashtags': ['#Violencia', '#Crimen', '#Seguridad']
    }
}

TODAS_PALABRAS = []
for cat in CATEGORIAS.values():
    TODAS_PALABRAS.extend(cat['palabras'])

# =============================================================================
# FUENTES ESTABLES (Sin YouTube, Facebook, Instagram - requieren auth)
# =============================================================================

# Canales de Dailymotion de noticias (más permisivo que YouTube)
DAILYMOTION_CHANNELS = [
    'euronews', 'france24', 'rt', 'trtworld', 'cgtn', 'aljazeera', 'afp', 'reuters'
]

# Búsquedas por términos en Dailymotion
DAILYMOTION_SEARCH_TERMS = [
    'war', 'conflict', 'attack', 'military', 'news', 'breaking', 'crisis',
    'gaza', 'ukraine', 'israel', 'palestine', 'syria', 'narcotraffic', 'police'
]

# Subreddits de video de conflictos (con manejo de errores mejorado)
REDDIT_SUBREDDITS = [
    'CombatFootage', 'war', 'syriancivilwar', 'UkraineWarVideoReport', 
    'NarcoFootage', 'ActualPublicFreakouts', 'CatastrophicFailure',
    'worldnews', 'news'
]

# Canales de Vimeo de noticias/documentales
VIMEO_CHANNELS = [
    'aljazeera', 'reuters', 'afp', 'france24', 'euronews'
]

# RSS Feeds de video que funcionan
RSS_FEEDS_VIDEO = [
    'https://feeds.bbci.co.uk/news/video_and_audio/world/rss.xml',
    'https://www.reutersagency.com/feed/?best-topics=world&format=mrss',
]

# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def log(mensaje, tipo='info'):
    """Imprime mensajes con formato"""
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍', 'video': '🎬'}
    icono = iconos.get(tipo, 'ℹ️')
    print(f"{icono} {mensaje}")

def cargar_json(ruta, default=None):
    """Carga un archivo JSON"""
    if default is None:
        default = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error cargando {ruta}: {e}", 'error')
    return default

def guardar_json(ruta, datos):
    """Guarda datos en archivo JSON"""
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"Error guardando {ruta}: {e}", 'error')
        return False

def generar_hash(texto):
    """Genera hash MD5"""
    return hashlib.md5(texto.lower().strip().encode()).hexdigest()

def detectar_categoria(titulo, descripcion):
    """Detecta la categoría de una noticia"""
    texto = f"{titulo} {descripcion}".lower()
    
    puntuaciones = {}
    for nombre_categoria, datos in CATEGORIAS.items():
        score = sum(1 for palabra in datos['palabras'] if palabra in texto)
        puntuaciones[nombre_categoria] = score
    
    if max(puntuaciones.values()) > 0:
        return max(puntuaciones, key=puntuaciones.get)
    
    return 'conflictos_guerra'

def obtener_hashtags_categoria(categoria):
    """Obtiene hashtags de una categoría"""
    return ' '.join(CATEGORIAS.get(categoria, {}).get('hashtags', ['#Noticias', '#Actualidad']))

# =============================================================================
# GESTIÓN DE HISTORIAL Y ESTADO
# =============================================================================

def cargar_historial():
    """Carga el historial de videos"""
    default = {
        'urls': [], 
        'titulos': [], 
        'hashes': [], 
        'ultima_publicacion': None, 
        'videos': []
    }
    historial = cargar_json(HISTORIAL_PATH, default)
    log(f"Historial cargado: {len(historial.get('videos', []))} videos")
    return historial

def guardar_historial(historial, url, titulo, video_path, fuente_tipo='dailymotion'):
    """Guarda un video en el historial"""
    url_hash = generar_hash(url)
    
    historial.setdefault('urls', []).append(url)
    historial.setdefault('titulos', []).append(titulo[:100])
    historial.setdefault('hashes', []).append(url_hash)
    historial.setdefault('videos', []).append({
        'url': url,
        'titulo': titulo[:100],
        'fecha': datetime.now().isoformat(),
        'archivo': os.path.basename(video_path) if video_path else None,
        'fuente': fuente_tipo
    })
    historial['ultima_publicacion'] = datetime.now().isoformat()
    
    for key in ['urls', 'titulos', 'hashes']:
        historial[key] = historial[key][-200:]
    historial['videos'] = historial['videos'][-200:]
    
    guardar_json(HISTORIAL_PATH, historial)
    log(f"Video guardado en historial [{fuente_tipo}]", 'exito')

def noticia_ya_publicada(historial, url, titulo):
    """Verifica si ya fue publicada"""
    url_hash = generar_hash(url)
    
    if url_hash in historial.get('hashes', []):
        return True
    if url in historial.get('urls', []):
        return True
    
    titulo_simple = re.sub(r'[^\w]', '', titulo.lower())[:30]
    for t in historial.get('titulos', []):
        t_simple = re.sub(r'[^\w]', '', t.lower())[:30]
        if titulo_simple == t_simple:
            return True
    
    return False

def cargar_estado():
    """Carga el estado del bot"""
    default = {
        'ultima_publicacion': None,
        'total_publicadas': 0,
        'ultima_fuente': None,
        'ultima_categoria': None
    }
    return cargar_json(ESTADO_PATH, default)

def guardar_estado(estado):
    """Guarda el estado del bot"""
    guardar_json(ESTADO_PATH, estado)

def verificar_tiempo_ultima_publicacion(estado):
    """Verifica si ya pasó el tiempo mínimo"""
    if not estado.get('ultima_publicacion'):
        return True, 0, 0
    
    try:
        ultima = datetime.fromisoformat(estado['ultima_publicacion'])
        ahora = datetime.now()
        transcurrido = (ahora - ultima).total_seconds() / 60
        
        if transcurrido < TIEMPO_ENTRE_PUBLICACIONES:
            faltan = TIEMPO_ENTRE_PUBLICACIONES - transcurrido
            return False, transcurrido, faltan
        
        return True, transcurrido, 0
        
    except Exception as e:
        return True, 0, 0

# =============================================================================
# BÚSQUEDA DE VIDEOS EN FUENTES ALTERNATIVAS
# =============================================================================

def buscar_videos_dailymotion():
    """
    Busca videos en Dailymotion de canales de noticias
    CORREGIDO: Manejo de errores y formato de IDs
    """
    videos = []
    
    try:
        # Intentar búsqueda por canales
        canales = random.sample(DAILYMOTION_CHANNELS, min(4, len(DAILYMOTION_CHANNELS)))
        
        for canal in canales:
            try:
                # Buscar videos del canal con términos de búsqueda
                termino = random.choice(DAILYMOTION_SEARCH_TERMS)
                
                # API pública de Dailymotion - CORREGIDA
                url_api = f"https://api.dailymotion.com/videos?owners={canal}&search={termino}&limit=10&sort=recent&fields=id,title,description,url,created_time,duration"
                
                resp = requests.get(url_api, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                
                if 'list' in data:
                    for video in data['list']:
                        try:
                            titulo = video.get('title', '')
                            descripcion = video.get('description', '') or ''
                            duracion = video.get('duration', 0)
                            video_id = video.get('id', '')
                            
                            if not video_id or not titulo:
                                continue
                            
                            # Filtrar por relevancia
                            texto_completo = f"{titulo} {descripcion}".lower()
                            es_relevante = any(p in texto_completo for p in TODAS_PALABRAS)
                            
                            # Priorizar videos cortos (30s - 5min) y relevantes
                            if es_relevante and 30 <= duracion <= 300:
                                categoria = detectar_categoria(titulo, descripcion)
                                
                                # URL correcta de Dailymotion
                                video_url = f"https://www.dailymotion.com/video/{video_id}"
                                
                                videos.append({
                                    'titulo': titulo,
                                    'descripcion': descripcion[:300],
                                    'url': video_url,
                                    'fuente': f'Dailymotion/{canal}',
                                    'fecha': video.get('created_time', ''),
                                    'duracion': duracion,
                                    'puntaje': 10 if categoria in ['conflictos_guerra', 'narcotrafico'] else 7,
                                    'tipo_url': 'dailymotion',
                                    'categoria': categoria,
                                    'id_video': video_id
                                })
                        except Exception as e:
                            continue
                            
            except Exception as e:
                log(f"Error Dailymotion canal {canal}: {str(e)[:50]}", 'advertencia')
                continue
        
        # También buscar por términos generales (sin canal específico)
        try:
            terminos_busqueda = ['war', 'conflict', 'news', 'breaking']
            for termino in random.sample(terminos_busqueda, 2):
                url_api = f"https://api.dailymotion.com/videos?search={termino}&limit=10&sort=recent&fields=id,title,description,url,created_time,duration"
                
                resp = requests.get(url_api, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                
                if 'list' in data:
                    for video in data['list']:
                        try:
                            titulo = video.get('title', '')
                            descripcion = video.get('description', '') or ''
                            duracion = video.get('duration', 0)
                            video_id = video.get('id', '')
                            
                            if not video_id or not titulo:
                                continue
                            
                            texto_completo = f"{titulo} {descripcion}".lower()
                            es_relevante = any(p in texto_completo for p in TODAS_PALABRAS)
                            
                            if es_relevante and 30 <= duracion <= 300:
                                categoria = detectar_categoria(titulo, descripcion)
                                video_url = f"https://www.dailymotion.com/video/{video_id}"
                                
                                videos.append({
                                    'titulo': titulo,
                                    'descripcion': descripcion[:300],
                                    'url': video_url,
                                    'fuente': 'Dailymotion/search',
                                    'fecha': video.get('created_time', ''),
                                    'duracion': duracion,
                                    'puntaje': 8,
                                    'tipo_url': 'dailymotion',
                                    'categoria': categoria,
                                    'id_video': video_id
                                })
                        except:
                            continue
        except Exception as e:
            log(f"Error búsqueda general Dailymotion: {str(e)[:50]}", 'advertencia')
                
    except Exception as e:
        log(f"Error general Dailymotion: {str(e)[:50]}", 'advertencia')
    
    log(f"Dailymotion: {len(videos)} videos encontrados", 'video')
    return videos

def buscar_videos_reddit():
    """
    Busca videos en subreddits de conflictos
    CORREGIDO: Headers mejorados y manejo de rate limiting
    """
    videos = []
    
    try:
        # Headers más completos para evitar bloqueos
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        subreddits = random.sample(REDDIT_SUBREDDITS, min(4, len(REDDIT_SUBREDDITS)))
        
        for subreddit in subreddits:
            try:
                # Añadir delay para evitar rate limiting
                time.sleep(1)
                
                url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=10"
                resp = requests.get(url, headers=headers, timeout=20)
                
                if resp.status_code == 429:
                    log(f"Rate limit en Reddit {subreddit}, esperando...", 'advertencia')
                    time.sleep(5)
                    continue
                
                resp.raise_for_status()
                data = resp.json()
                
                if 'data' in data and 'children' in data['data']:
                    for post in data['data']['children']:
                        try:
                            post_data = post['data']
                            
                            # Solo posts con video
                            if not post_data.get('is_video') and 'v.redd.it' not in post_data.get('url', ''):
                                continue
                            
                            titulo = post_data.get('title', '')
                            
                            # Verificar relevancia
                            es_relevante = any(p in titulo.lower() for p in TODAS_PALABRAS)
                            
                            if es_relevante:
                                # Obtener URL del video
                                video_url = post_data.get('url', '')
                                permalink = post_data.get('permalink', '')
                                
                                # Si es video de Reddit directo
                                if 'v.redd.it' in video_url or post_data.get('is_video'):
                                    categoria = detectar_categoria(titulo, '')
                                    
                                    videos.append({
                                        'titulo': titulo,
                                        'descripcion': post_data.get('selftext', '')[:300],
                                        'url': f"https://www.reddit.com{permalink}",
                                        'video_url_directa': video_url if 'v.redd.it' in video_url else None,
                                        'fuente': f'Reddit/r/{subreddit}',
                                        'fecha': datetime.fromtimestamp(post_data.get('created_utc', 0)).isoformat(),
                                        'puntaje': 9,
                                        'tipo_url': 'reddit',
                                        'categoria': categoria,
                                        'reddit_id': post_data.get('id')
                                    })
                        except Exception as e:
                            continue
                            
            except Exception as e:
                log(f"Error Reddit {subreddit}: {str(e)[:50]}", 'advertencia')
                continue
                
    except Exception as e:
        log(f"Error general Reddit: {str(e)[:50]}", 'advertencia')
    
    log(f"Reddit: {len(videos)} videos encontrados", 'video')
    return videos

def buscar_videos_vimeo():
    """
    Busca videos en canales de Vimeo de noticias
    Vimeo es más permisivo que YouTube
    """
    videos = []
    
    try:
        # Vimeo tiene un endpoint de búsqueda básica
        terminos = ['war', 'conflict', 'news', 'documentary', 'military']
        
        for termino in random.sample(terminos, 3):
            try:
                # API básica de Vimeo (pública para búsquedas simples)
                url = f"https://vimeo.com/search?q={termino}&type=videos"
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                resp = requests.get(url, headers=headers, timeout=15)
                
                if resp.status_code == 200:
                    # Extraer URLs de videos de la página HTML
                    pattern = r'https://vimeo\.com/(\d+)'
                    matches = re.findall(pattern, resp.text)
                    
                    for video_id in set(matches[:5]):  # Evitar duplicados
                        try:
                            # Obtener info del video oEmbed
                            oembed_url = f"https://vimeo.com/api/oembed.json?url=https://vimeo.com/{video_id}"
                            info_resp = requests.get(oembed_url, timeout=10)
                            
                            if info_resp.status_code == 200:
                                info = info_resp.json()
                                titulo = info.get('title', '')
                                descripcion = info.get('description', '') or ''
                                
                                es_relevante = any(p in f"{titulo} {descripcion}".lower() for p in TODAS_PALABRAS)
                                
                                if es_relevante:
                                    categoria = detectar_categoria(titulo, descripcion)
                                    
                                    videos.append({
                                        'titulo': titulo,
                                        'descripcion': descripcion[:300],
                                        'url': f"https://vimeo.com/{video_id}",
                                        'fuente': 'Vimeo',
                                        'fecha': datetime.now().isoformat(),
                                        'puntaje': 7,
                                        'tipo_url': 'vimeo',
                                        'categoria': categoria
                                    })
                        except:
                            continue
                            
            except Exception as e:
                continue
                
    except Exception as e:
        log(f"Error Vimeo: {str(e)[:50]}", 'advertencia')
    
    log(f"Vimeo: {len(videos)} videos encontrados", 'video')
    return videos

def buscar_videos_newsapi():
    """
    Busca noticias con video usando NewsAPI
    CORREGIDO: Mejor filtrado de URLs de video
    """
    videos = []
    if not NEWS_API_KEY:
        log("NewsAPI no configurado", 'advertencia')
        return videos
    
    try:
        # Términos de búsqueda específicos para video
        queries = [
            'war video footage',
            'military conflict video',
            'breaking news video',
            'drone footage war',
            'combat footage'
        ]
        
        for query in random.sample(queries, 2):
            try:
                resp = requests.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        'q': query,
                        'language': 'en',
                        'sortBy': 'publishedAt',
                        'pageSize': 20,
                        'apiKey': NEWS_API_KEY
                    },
                    timeout=15
                )
                data = resp.json()
                
                if data.get('status') == 'ok':
                    for art in data.get('articles', []):
                        titulo = art.get('title', '')
                        url = art.get('url', '')
                        contenido = art.get('content', '') or art.get('description', '')
                        
                        if not titulo or '[Removed]' in titulo:
                            continue
                        
                        # Buscar URLs de video en el contenido
                        video_urls = []
                        
                        # Dailymotion
                        if 'dailymotion.com' in url or 'dai.ly' in url:
                            video_urls.append(('dailymotion', url))
                        
                        # Vimeo
                        if 'vimeo.com' in url:
                            video_urls.append(('vimeo', url))
                        
                        # Extraer URLs de video del contenido
                        dm_matches = re.findall(r'https?://(?:www\.)?dailymotion\.com/video/[a-zA-Z0-9]+', contenido)
                        vimeo_matches = re.findall(r'https?://(?:www\.)?vimeo\.com/\d+', contenido)
                        
                        for match in dm_matches:
                            video_urls.append(('dailymotion', match))
                        for match in vimeo_matches:
                            video_urls.append(('vimeo', match))
                        
                        # Si encontramos URLs de video
                        for tipo_video, video_url in video_urls:
                            categoria = detectar_categoria(titulo, art.get('description', ''))
                            
                            videos.append({
                                'titulo': titulo,
                                'descripcion': art.get('description', ''),
                                'url': video_url,
                                'fuente': art.get('source', {}).get('name', 'NewsAPI'),
                                'fecha': art.get('publishedAt', ''),
                                'puntaje': 8 if categoria in ['conflictos_guerra', 'narcotrafico'] else 5,
                                'tipo_url': tipo_video,
                                'categoria': categoria
                            })
                            
            except Exception as e:
                log(f"Error NewsAPI query {query}: {str(e)[:50]}", 'advertencia')
                
    except Exception as e:
        log(f"Error general NewsAPI: {str(e)[:50]}", 'advertencia')
    
    log(f"NewsAPI: {len(videos)} videos encontrados", 'info')
    return videos

def buscar_videos_rss():
    """
    RSS feeds de video - CORREGIDO
    """
    videos = []
    
    for feed_url in RSS_FEEDS_VIDEO[:2]:
        try:
            feed = feedparser.parse(feed_url)
            fuente = feed.feed.get('title', 'RSS')
            
            for entry in feed.entries[:5]:
                try:
                    titulo = entry.get('title', '')
                    if not titulo:
                        continue
                    
                    # Buscar media content
                    video_url = None
                    
                    if hasattr(entry, 'media_content'):
                        for media in entry.media_content:
                            url = media.get('url', '')
                            if any(ext in url.lower() for ext in ['.mp4', '.m3u8', 'video']):
                                video_url = url
                                break
                    
                    # Buscar en enlaces
                    if not video_url and hasattr(entry, 'links'):
                        for link in entry.links:
                            if 'video' in link.get('type', ''):
                                video_url = link.href
                                break
                    
                    if video_url:
                        categoria = detectar_categoria(titulo, entry.get('summary', ''))
                        
                        videos.append({
                            'titulo': titulo,
                            'descripcion': entry.get('summary', ''),
                            'url': video_url,
                            'fuente': fuente,
                            'fecha': entry.get('published', ''),
                            'puntaje': 6,
                            'tipo_url': 'rss_directo',
                            'categoria': categoria
                        })
                except:
                    continue
                    
        except Exception as e:
            log(f"Error RSS {feed_url}: {str(e)[:50]}", 'advertencia')
    
    log(f"RSS: {len(videos)} videos encontrados", 'info')
    return videos

def buscar_todos_videos():
    """Busca videos en todas las fuentes disponibles"""
    log("Iniciando búsqueda de videos...", 'video')
    
    todos_videos = []
    
    # Fuente 1: Dailymotion (más estable)
    todos_videos.extend(buscar_videos_dailymotion())
    
    # Fuente 2: Reddit (con delay para rate limiting)
    if len(todos_videos) < 5:
        todos_videos.extend(buscar_videos_reddit())
    
    # Fuente 3: Vimeo
    if len(todos_videos) < 5:
        todos_videos.extend(buscar_videos_vimeo())
    
    # Fuente 4: NewsAPI
    if len(todos_videos) < 5:
        todos_videos.extend(buscar_videos_newsapi())
    
    # Fuente 5: RSS
    if len(todos_videos) < 3:
        todos_videos.extend(buscar_videos_rss())
    
    # Eliminar duplicados por URL
    urls_vistas = set()
    videos_unicos = []
    for v in todos_videos:
        url = v['url']
        if url and url not in urls_vistas:
            urls_vistas.add(url)
            videos_unicos.append(v)
    
    log(f"Total videos únicos: {len(videos_unicos)}", 'exito')
    return videos_unicos

# =============================================================================
# DESCARGA DE VIDEOS
# =============================================================================

def descargar_video(url, tipo_fuente='dailymotion', info_extra=None):
    """
    Descarga video según la fuente
    CORREGIDO: Mejor manejo de errores y formatos
    """
    if not url:
        return None, None
    
    log(f"Descargando desde {tipo_fuente}: {url[:60]}...", 'video')
    
    try:
        # Configuración base mejorada
        ydl_opts = {
            'format': 'best[height<=720][filesize<80M]/best[height<=480][filesize<80M]/best[filesize<80M]',
            'outtmpl': '/tmp/video_%(id)s_%(height)s.%(ext)s',
            'max_filesize': 80000000,  # 80MB
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
            'socket_timeout': 30,
            'retries': 3,
        }
        
        # Configuración específica por fuente
        if tipo_fuente == 'reddit':
            ydl_opts['format'] = 'best[filesize<80M]/best'
        elif tipo_fuente == 'vimeo':
            ydl_opts['format'] = 'best[height<=720]/best'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return None, None
            
            # Verificar duración (máximo 5 minutos)
            duracion = info.get('duration', 0)
            if duracion > 300:
                log(f"Video muy largo ({duracion}s), ignorando", 'advertencia')
                return None, info
            
            # Descargar
            ydl.download([url])
            
            # Encontrar archivo descargado
            video_path = ydl.prepare_filename(info)
            
            if not os.path.exists(video_path):
                base = os.path.splitext(video_path)[0]
                for ext in ['.mp4', '.mkv', '.webm', '.mov']:
                    if os.path.exists(base + ext):
                        video_path = base + ext
                        break
            
            if os.path.exists(video_path):
                size_mb = os.path.getsize(video_path) / 1024 / 1024
                if size_mb > 0.5:  # Mínimo 500KB
                    log(f"Descargado: {size_mb:.1f} MB", 'exito')
                    return video_path, info
                else:
                    os.remove(video_path)
                    return None, info
            
            return None, info
            
    except Exception as e:
        error_msg = str(e)
        if "unavailable" in error_msg.lower():
            log(f"Video no disponible", 'advertencia')
        elif "private" in error_msg.lower():
            log(f"Video privado", 'advertencia')
        else:
            log(f"Error descarga: {error_msg[:80]}", 'error')
        return None, None

def verificar_video(video_path):
    """Verifica que el video sea válido"""
    try:
        if not os.path.exists(video_path):
            return False, "No existe"
        
        size = os.path.getsize(video_path)
        if size < 500000:  # Menos de 500KB
            return False, "Muy pequeño"
        
        # Verificar con ffprobe si está disponible
        try:
            cmd = [
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,duration',
                '-of', 'json', video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            info = json.loads(result.stdout)
            
            if 'streams' in info and info['streams']:
                stream = info['streams'][0]
                height = stream.get('height', 0)
                duration = float(stream.get('duration', 0))
                
                log(f"Video: {height}p | {duration:.1f}s", 'debug')
                
                if height < 360:  # Calidad mínima aceptable
                    return False, f"Baja calidad ({height}p)"
                
                if duration > 300:
                    return recortar_video(video_path, 180)
                
                return True, video_path
        except:
            # Si ffprobe falla, asumir que está bien si tiene tamaño adecuado
            pass
        
        return True, video_path
        
    except Exception as e:
        log(f"Error verificación: {e}", 'advertencia')
        return True, video_path

def recortar_video(video_path, duracion=180):
    """Recorta video a duración específica"""
    try:
        output = video_path.replace('.mp4', '_cut.mp4')
        if output == video_path:
            output = video_path + '_cut.mp4'
        
        cmd = [
            'ffmpeg', '-y', '-i', video_path,
            '-t', str(duracion),
            '-c:v', 'libx264', '-preset', 'fast',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            output
        ]
        
        subprocess.run(cmd, capture_output=True, timeout=120)
        
        if os.path.exists(output):
            os.remove(video_path)
            return True, output
        
        return False, "No se pudo recortar"
        
    except Exception as e:
        return False, str(e)

# =============================================================================
# PUBLICACIÓN EN FACEBOOK
# =============================================================================

def publicar_video(titulo, descripcion, video_path, categoria):
    """Publica video en Facebook"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Faltan credenciales Facebook", 'error')
        return False
    
    if not os.path.exists(video_path):
        log("Archivo no existe", 'error')
        return False
    
    hashtags = obtener_hashtags_categoria(categoria)
    
    mensaje = f"""🎬 {titulo}

{descripcion[:200]}{"..." if len(descripcion) > 200 else ""}

{hashtags} #Video #Noticias

— Verdad Hoy: Noticias al minuto"""
    
    if len(mensaje) > 2000:
        mensaje = mensaje[:1990] + "..."
    
    size_mb = os.path.getsize(video_path) / 1024 / 1024
    log(f"Subiendo a Facebook ({size_mb:.1f} MB)...", 'video')
    
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
        
        with open(video_path, 'rb') as f:
            resp = requests.post(
                url,
                files={'file': f},
                data={
                    'description': mensaje,
                    'access_token': FB_ACCESS_TOKEN
                },
                timeout=600
            )
        
        result = resp.json()
        
        if resp.status_code == 200 and 'id' in result:
            log(f"✅ Publicado: {result['id']}", 'exito')
            return True
        else:
            error = result.get('error', {}).get('message', str(result))
            log(f"Error Facebook: {error}", 'error')
            return False
            
    except Exception as e:
        log(f"Error: {e}", 'error')
        return False

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def main():
    """Función principal"""
    print("\n" + "="*70)
    print("🎬 BOT DE VIDEOS - VERDAD HOY")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  Frecuencia: cada ~{TIEMPO_ENTRE_PUBLICACIONES+2} minutos")
    print("="*70)
    
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales Facebook", 'error')
        return False
    
    log("Credenciales OK")
    
    estado = cargar_estado()
    puede_publicar, transcurrido, faltan = verificar_tiempo_ultima_publicacion(estado)
    
    if not puede_publicar:
        log(f"⏳ Esperando {faltan:.0f} minutos", 'advertencia')
        return True
    
    log("✅ Iniciando búsqueda", 'exito')
    
    historial = cargar_historial()
    
    # Buscar videos
    videos = buscar_todos_videos()
    
    if not videos:
        log("No se encontraron videos", 'error')
        return False
    
    # Filtrar ya publicados
    videos_nuevos = [v for v in videos if not noticia_ya_publicada(historial, v['url'], v['titulo'])]
    log(f"Nuevos: {len(videos_nuevos)} de {len(videos)}")
    
    candidatos = videos_nuevos if videos_nuevos else videos
    
    # Evitar misma fuente consecutiva
    ultima_fuente = estado.get('ultima_fuente', '')
    diferentes = [v for v in candidatos if v['fuente'] != ultima_fuente]
    if diferentes:
        candidatos = diferentes
    
    # Ordenar por puntaje
    candidatos.sort(key=lambda x: x.get('puntaje', 0), reverse=True)
    
    # Intentar descargar y publicar (máximo 5 intentos)
    for intento, video_info in enumerate(candidatos[:5]):
        log(f"\nIntento {intento+1}: {video_info['titulo'][:50]}...")
        log(f"Fuente: {video_info['fuente']} | Tipo: {video_info['tipo_url']}")
        
        # Descargar según tipo
        tipo = video_info.get('tipo_url', 'dailymotion')
        video_path, info = descargar_video(
            video_info['url'], 
            tipo,
            video_info
        )
        
        if not video_path:
            log("No se pudo descargar, siguiente...", 'advertencia')
            continue
        
        # Verificar video
        ok, resultado = verificar_video(video_path)
        
        if not ok:
            log(f"Rechazado: {resultado}", 'advertencia')
            try:
                os.remove(video_path)
            except:
                pass
            continue
        
        if isinstance(resultado, str) and resultado != video_path:
            video_path = resultado
        
        # Publicar
        exito = publicar_video(
            video_info['titulo'],
            video_info.get('descripcion', ''),
            video_path,
            video_info.get('categoria', 'conflictos_guerra')
        )
        
        # Limpiar archivo temporal
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
                # Limpiar también archivos relacionados
                base = os.path.splitext(video_path)[0]
                for ext in ['.mp4', '.mkv', '.webm', '.mov', '.part']:
                    for suffix in ['', '_cut']:
                        f = base + suffix + ext
                        if os.path.exists(f):
                            os.remove(f)
        except Exception as e:
            pass
        
        if exito:
            # Guardar en historial
            guardar_historial(
                historial, 
                video_info['url'], 
                video_info['titulo'], 
                video_path,
                video_info.get('tipo_url', 'dailymotion')
            )
            
            # Actualizar estado
            estado['ultima_publicacion'] = datetime.now().isoformat()
            estado['ultima_fuente'] = video_info['fuente']
            estado['ultima_categoria'] = video_info.get('categoria', 'conflictos_guerra')
            estado['total_publicadas'] = estado.get('total_publicadas', 0) + 1
            guardar_estado(estado)
            
            print("\n" + "="*70)
            log("VIDEO PUBLICADO EXITOSAMENTE", 'exito')
            print(f"🎬 {video_info['titulo'][:60]}...")
            print(f"🏢 {video_info['fuente']}")
            print(f"📂 Categoría: {video_info.get('categoria', 'conflictos_guerra')}")
            print(f"📊 Total publicadas: {estado['total_publicadas']}")
            print(f"⏰ Próxima publicación: {(datetime.now() + timedelta(minutes=TIEMPO_ENTRE_PUBLICACIONES)).strftime('%H:%M')}")
            print("="*70)
            return True
        
        log("Falló publicación, intentando siguiente...", 'advertencia')
    
    log("Todos los intentos fallaron", 'error')
    return False

if __name__ == "__main__":
    try:
        resultado = main()
        exit(0 if resultado else 1)
    except KeyboardInterrupt:
        log("Interrumpido por usuario", 'advertencia')
        exit(1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

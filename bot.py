#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias en VIDEO para Facebook
- Busca noticias internacionales en formato video (YouTube, Twitter/X, noticieros)
- Publica videos nativos en Facebook
- Prioriza: Conflictos bélicos, política global, economía mundial
"""

import requests
import feedparser
import re
import hashlib
import json
import os
import random
import html as html_module
from datetime import datetime, timedelta
from bs4 import BeautifulSoup, Comment
from difflib import SequenceMatcher
import urllib.parse

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
GNEWS_API_KEY = os.getenv('GNEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')  # 🆕 NUEVO: Para búsqueda de videos

HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_publicaciones.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot.json')

TIEMPO_ENTRE_PUBLICACIONES = 60  # 60 minutos
VENTANA_DUPLICADOS_HORAS = 72
UMBRAL_SIMILITUD_TITULO = 0.85

# =============================================================================
# PALABRAS CLAVE INTERNACIONALES - OPTIMIZADAS PARA VIDEO
# =============================================================================

PALABRAS_ALTA_PRIORIDAD = [
    # Términos de video/noticieros
    "breaking news", "ultima hora", "en vivo", "live", "noticiero", "news report",
    "footage", "video footage", "war footage", "conflict video",
    
    # Conflictos actuales
    "guerra ucrania video", "gaza video", "israel palestina video",
    "rusia ucrania noticias", "zelensky", "putin", "netanyahu", "hamas",
    "bombardeo video", "ataque drone video", "military footage",
    
    # Crisis geopolíticas
    "taiwan tension", "china taiwan video", "south china sea",
    "iran israel", "red sea crisis", "houthis attack",
    
    # Tecnología militar
    "drones militares", "hypersonic missile", "nuclear test",
    "cyber attack", "space force", "satellite footage",
    
    # Crisis humanitarias
    "refugee crisis video", "humanitarian crisis", "war crimes tribunal",
    
    # Economía/Recursos
    "rare earth war", "lithium conflict", "chip war", "sanctions impact",
    
    # Protests/Dictaduras
    "protestas venezuela", "myanmar coup", "iran protestas",
]

PALABRAS_MEDIA_PRIORIDAD = [
    'economía mundial', 'mercados globales', 'inflación', 'FMI',
    'China', 'EEUU', 'Estados Unidos', 'Reino Unido', 'OTAN', 'ONU'
]

TERMINOS_EXCLUIR = [
    'liga local', 'campeonato municipal', 'feria del pueblo',
    'concurso de belleza local', 'deporte local', 'receta', 'tutorial',
    'gameplay', 'unboxing', 'review', 'comedia', 'meme'
]

# =============================================================================
# FUNCIONES DE UTILIDAD (mantener las mismas)
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍'}
    icono = iconos.get(tipo, 'ℹ️')
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {icono} {mensaje}")

def cargar_json(ruta, default=None):
    if default is None:
        default = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                contenido = f.read().strip()
                if not contenido:
                    return default.copy()
                return json.loads(contenido)
        except Exception as e:
            log(f"Error cargando JSON: {e}", 'error')
    return default.copy()

def guardar_json(ruta, datos):
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"Error guardando JSON: {e}", 'error')
        return False

def generar_hash(texto):
    if not texto:
        return ""
    texto_normalizado = re.sub(r'[^\w\s]', '', texto.lower().strip())
    texto_normalizado = re.sub(r'\s+', ' ', texto_normalizado)
    return hashlib.md5(texto_normalizado.encode()).hexdigest()

def normalizar_url(url):
    if not url:
        return ""
    url = re.sub(r'\?.*$', '', url)
    url = re.sub(r'#.*$', '', url)
    url = re.sub(r'https?://(www\.)?', '', url)
    return url.lower().rstrip('/')

def calcular_similitud_titulos(titulo1, titulo2):
    if not titulo1 or not titulo2:
        return 0.0
    
    def normalizar(t):
        t = t.lower()
        t = re.sub(r'[^\w\s]', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t
    
    t1 = normalizar(titulo1)
    t2 = normalizar(titulo2)
    
    if not t1 or not t2:
        return 0.0
    
    return SequenceMatcher(None, t1, t2).ratio()

def limpiar_texto(texto):
    if not texto:
        return ""
    texto = html_module.unescape(texto)
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', texto)
    texto = re.sub(r'https?://\S*', '', texto)
    texto = texto.strip()
    if texto and texto[-1] not in '.!?':
        texto += '.'
    return texto.strip()

def es_noticia_excluible(titulo, descripcion=""):
    texto = f"{titulo} {descripcion}".lower()
    for termino in TERMINOS_EXCLUIR:
        if termino.lower() in texto:
            return True
    return False

def calcular_puntaje_internacional(titulo, descripcion):
    texto = f"{titulo} {descripcion}".lower()
    puntaje = 0
    
    for palabra in PALABRAS_ALTA_PRIORIDAD:
        if palabra.lower() in texto:
            puntaje += 10
    
    for palabra in PALABRAS_MEDIA_PRIORIDAD:
        if palabra.lower() in texto:
            puntaje += 3
    
    if 50 <= len(titulo) <= 120:
        puntaje += 2
    
    # Bonus por ser video
    if any(x in texto for x in ['video', 'footage', 'en vivo', 'live']):
        puntaje += 5
    
    return puntaje

# =============================================================================
# 🆕 NUEVO: BÚSQUEDA DE VIDEOS EN YOUTUBE
# =============================================================================

def buscar_videos_youtube():
    """Busca videos de noticias internacionales en YouTube"""
    if not YOUTUBE_API_KEY:
        log("YouTube API Key no configurada", 'advertencia')
        return []
    
    videos = []
    queries = [
        "noticias internacionales ultima hora",
        "guerra ucrania noticias hoy",
        "israel palestina conflicto noticias",
        "breaking news international",
        "world news today",
        "geopolitica actualidad",
        "crisis mundial noticias"
    ]
    
    for query in queries:
        try:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'videoDuration': 'short',  # Menos de 4 minutos (ideal para FB)
                'order': 'date',  # Más recientes primero
                'maxResults': 10,
                'key': YOUTUBE_API_KEY,
                'relevanceLanguage': 'es',
                'publishedAfter': (datetime.now() - timedelta(hours=48)).isoformat("T") + "Z"
            }
            
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            
            if 'items' in data:
                for item in data['items']:
                    video_id = item['id']['videoId']
                    snippet = item['snippet']
                    
                    titulo = snippet.get('title', '')
                    descripcion = snippet.get('description', '')
                    canal = snippet.get('channelTitle', '')
                    publicado = snippet.get('publishedAt', '')
                    
                    # Filtrar canales de noticias confiables
                    canales_confiables = [
                        'BBC', 'CNN', 'Al Jazeera', 'DW', 'France 24', 
                        'Euronews', 'RT', 'TeleSUR', 'Actualidad RT'
                    ]
                    
                    es_canal_confiable = any(c.lower() in canal.lower() for c in canales_confiables)
                    
                    if es_canal_confiable or calcular_puntaje_internacional(titulo, descripcion) > 10:
                        videos.append({
                            'titulo': limpiar_texto(titulo),
                            'descripcion': limpiar_texto(descripcion),
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                            'video_id': video_id,
                            'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                            'fuente': f"YouTube:{canal}",
                            'fecha': publicado,
                            'puntaje': calcular_puntaje_internacional(titulo, descripcion) + (5 if es_canal_confiable else 0),
                            'tipo': 'youtube'
                        })
                        
        except Exception as e:
            log(f"Error YouTube API: {e}", 'error')
            continue
    
    log(f"YouTube: {len(videos)} videos encontrados", 'info')
    return videos

def obtener_video_info_youtube(video_id):
    """Obtiene información detallada del video incluyendo duración"""
    if not YOUTUBE_API_KEY:
        return None
    
    try:
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            'part': 'contentDetails,statistics',
            'id': video_id,
            'key': YOUTUBE_API_KEY
        }
        
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        if data.get('items'):
            item = data['items'][0]
            # Convertir duración ISO 8601 a segundos
            duracion_iso = item['contentDetails']['duration']
            # PT4M20S -> 260 segundos
            import isodate
            duracion_seg = isodate.parse_duration(duracion_iso).total_seconds()
            
            return {
                'duracion_segundos': duracion_seg,
                'vistas': item['statistics'].get('viewCount', 0)
            }
    except:
        pass
    
    return None

# =============================================================================
# 🆕 NUEVO: BÚSQUEDA DE VIDEOS EN OTRAS FUENTES
# =============================================================================

def buscar_videos_twitter_x():
    """Busca videos de noticias en Twitter/X (requiere API de pago, placeholder)"""
    # Nota: La API de X (Twitter) requiere nivel Basic ($100/mes) para búsqueda
    # Este es un placeholder para futura implementación
    log("Twitter/X video search requiere API de pago - omitiendo", 'debug')
    return []

def buscar_videos_news_apis():
    """Busca noticias que incluyan videos en las APIs de noticias"""
    videos = []
    
    # NewsAPI - buscar videos
    if NEWS_API_KEY:
        try:
            url = 'https://newsapi.org/v2/everything'
            params = {
                'apiKey': NEWS_API_KEY,
                'q': 'video AND (war OR conflict OR Ukraine OR Israel OR Gaza)',
                'language': 'es',
                'sortBy': 'publishedAt',
                'pageSize': 15
            }
            
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            
            if data.get('status') == 'ok':
                for art in data.get('articles', []):
                    titulo = art.get('title', '')
                    url_art = art.get('url', '')
                    
                    # Detectar si la URL es de video
                    dominios_video = ['youtube.com', 'youtu.be', 'twitter.com', 'x.com', 
                                     'facebook.com/watch', 'instagram.com/reel', 'tiktok.com',
                                     'rumble.com', 'bilibili.com']
                    
                    es_video = any(d in url_art.lower() for d in dominios_video)
                    
                    if es_video and not es_noticia_excluible(titulo):
                        videos.append({
                            'titulo': limpiar_texto(titulo),
                            'descripcion': limpiar_texto(art.get('description', '')),
                            'url': url_art,
                            'imagen': art.get('urlToImage'),
                            'fuente': f"NewsAPI-Video:{art.get('source', {}).get('name', 'Unknown')}",
                            'fecha': art.get('publishedAt'),
                            'puntaje': calcular_puntaje_internacional(titulo, art.get('description', '')),
                            'tipo': 'externo'
                        })
        except Exception as e:
            log(f"Error NewsAPI video: {e}", 'error')
    
    log(f"NewsAPI Videos: {len(videos)} encontrados", 'info')
    return videos

def buscar_videos_rss_noticieros():
    """Busca videos en feeds RSS de noticieros internacionales"""
    feeds_video = [
        'https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA',  # BBC Mundo
        'https://www.youtube.com/feeds/videos.xml?channel_id=UCzUV528KlngtCTr2gBCiNbQ',  # CNN Español
        'https://www.youtube.com/feeds/videos.xml?channel_id=UCknLrEdhRCp1aegoMqRaCZg',  # DW Español
        'https://www.youtube.com/feeds/videos.xml?channel_id=UCdTD5Y9dyXOFbHq6FeLdmfA',  # FRANCE 24 Español
    ]
    
    videos = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for feed_url in feeds_video:
        try:
            feed = feedparser.parse(feed_url, request_headers=headers)
            canal = feed.feed.get('title', 'Unknown')
            
            for entry in feed.entries[:5]:  # Últimos 5 videos del canal
                titulo = entry.get('title', '')
                link = entry.get('link', '')
                
                # Extraer video ID de YouTube
                video_id = None
                if 'youtube.com/watch?v=' in link:
                    video_id = link.split('v=')[1].split('&')[0]
                
                if video_id and not es_noticia_excluible(titulo):
                    videos.append({
                        'titulo': limpiar_texto(titulo),
                        'descripcion': '',
                        'url': link,
                        'video_id': video_id,
                        'fuente': f"RSS:{canal}",
                        'fecha': entry.get('published'),
                        'puntaje': calcular_puntaje_internacional(titulo, ''),
                        'tipo': 'youtube_rss'
                    })
        except Exception as e:
            continue
    
    log(f"RSS Noticieros: {len(videos)} videos", 'info')
    return videos

# =============================================================================
# 🆕 NUEVO: DESCARGA Y PROCESAMIENTO DE VIDEO
# =============================================================================

def descargar_video_youtube(video_url, video_id):
    """
    Descarga video de YouTube usando yt-dlp
    Retorna path del archivo descargado o None
    """
    try:
        import subprocess
        import tempfile
        
        # Crear directorio temporal
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"{video_id}.mp4")
        
        # Configurar yt-dlp para descarga optimizada para Facebook
        # Formatos: 720p máximo, mp4, con audio
        cmd = [
            'yt-dlp',
            '-f', 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
            '--merge-output-format', 'mp4',
            '--output', output_path,
            '--no-playlist',
            '--quiet',
            '--no-warnings',
            video_url
        ]
        
        log(f"   ⬇️ Descargando video: {video_id}", 'info')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0 and os.path.exists(output_path):
            # Verificar tamaño (Facebook permite hasta 10GB, pero mantenemos <100MB para velocidad)
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            log(f"   ✅ Video descargado: {size_mb:.1f} MB", 'exito')
            return output_path
        else:
            log(f"   ❌ Error descarga: {result.stderr}", 'error')
            return None
            
    except subprocess.TimeoutExpired:
        log("   ⏱️ Timeout descargando video", 'error')
        return None
    except Exception as e:
        log(f"   ❌ Error: {e}", 'error')
        return None

def obtener_thumbnail_video(url_thumbnail, video_id):
    """Descarga thumbnail como fallback si el video falla"""
    if not url_thumbnail:
        return None
    
    try:
        resp = requests.get(url_thumbnail, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if resp.status_code == 200:
            temp_path = f'/tmp/thumb_{video_id}.jpg'
            with open(temp_path, 'wb') as f:
                f.write(resp.content)
            return temp_path
    except:
        pass
    
    return None

# =============================================================================
# 🆕 NUEVO: PUBLICACIÓN DE VIDEO EN FACEBOOK
# =============================================================================

def publicar_video_facebook(titulo, descripcion, video_path, hashtags, video_info=None):
    """
    Publica video nativo en Facebook usando Graph API
    """
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Faltan credenciales Facebook", 'error')
        return False
    
    # Construir mensaje
    mensaje = f"📰 {titulo}\n\n{descripcion}\n\n{hashtags}\n\n— 🌐 Verdad Hoy | Agencia de Noticias Internacionales"
    
    # Truncar si es necesario
    if len(mensaje) > 2000:
        mensaje = mensaje[:1900] + "...\n\n" + hashtags
    
    try:
        # Endpoint para videos
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
        
        # Preparar archivo
        file_size = os.path.getsize(video_path)
        
        # Para videos grandes, usar resumable upload
        if file_size > 50 * 1024 * 1024:  # > 50MB
            log("   📤 Usando upload resumable para video grande...", 'info')
            return publicar_video_resumable(url, video_path, mensaje)
        
        # Upload simple para videos < 50MB
        with open(video_path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {
                'description': mensaje,
                'access_token': FB_ACCESS_TOKEN,
                'published': 'true'
            }
            
            # Añadir título si está disponible
            if video_info:
                data['title'] = titulo[:100]
            
            log("   📤 Subiendo video a Facebook...", 'info')
            resp = requests.post(url, files=files, data=data, timeout=300)
            result = resp.json()
        
        if resp.status_code == 200 and 'id' in result:
            log(f"✅ Video publicado ID: {result['id']}", 'exito')
            return True
        else:
            error_msg = result.get('error', {}).get('message', 'Unknown error')
            log(f"❌ Error FB: {error_msg}", 'error')
            
            # Si falla por tamaño, intentar como enlace
            if 'file size' in error_msg.lower() or 'larger' in error_msg.lower():
                log("   ⚠️ Intentando publicar como enlace de video...", 'advertencia')
                return False  # Retornamos False para que el caller intente thumbnail
            
            return False
            
    except Exception as e:
        log(f"Error publicando video: {e}", 'error')
        return False

def publicar_video_resumable(url, video_path, mensaje):
    """
    Upload resumable para videos grandes (no implementado completamente)
    En producción, implementar start-upload, transfer, finish-upload
    """
    log("Upload resumable requiere implementación adicional", 'advertencia')
    return False

def publicar_enlace_video_facebook(titulo, descripcion, url_video, hashtags, thumbnail_path=None):
    """
    Fallback: Publica como enlace de video con preview
    """
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        return False
    
    mensaje = f"📰 {titulo}\n\n{descripcion}\n\n🔗 Ver video: {url_video}\n\n{hashtags}\n\n— 🌐 Verdad Hoy"
    
    try:
        # Si tenemos thumbnail, publicar como foto con enlace
        if thumbnail_path and os.path.exists(thumbnail_path):
            url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
            with open(thumbnail_path, 'rb') as f:
                files = {'file': ('thumbnail.jpg', f, 'image/jpeg')}
                data = {
                    'message': mensaje,
                    'access_token': FB_ACCESS_TOKEN
                }
                resp = requests.post(url, files=files, data=data, timeout=60)
        else:
            # Solo enlace
            url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed"
            data = {
                'message': mensaje,
                'link': url_video,
                'access_token': FB_ACCESS_TOKEN
            }
            resp = requests.post(url, data=data, timeout=60)
        
        result = resp.json()
        
        if resp.status_code == 200 and 'id' in result:
            log(f"✅ Enlace de video publicado ID: {result['id']}", 'exito')
            return True
        else:
            log(f"❌ Error: {result.get('error', {}).get('message', 'Unknown')}", 'error')
            return False
            
    except Exception as e:
        log(f"Error: {e}", 'error')
        return False

# =============================================================================
# GESTIÓN DE HISTORIAL (mantener igual)
# =============================================================================

def cargar_historial():
    default = {
        'urls': [], 
        'hashes': [],
        'timestamps': [],
        'titulos': [],
        'video_ids': [],  # 🆕 NUEVO: Tracking específico de videos
        'estadisticas': {'total_publicadas': 0, 'videos': 0, 'links': 0}
    }
    datos = cargar_json(HISTORIAL_PATH, default)
    
    for key in ['urls', 'hashes', 'timestamps', 'titulos', 'video_ids']:
        if key not in datos or not isinstance(datos[key], list):
            datos[key] = []
    
    return datos

def limpiar_historial_antiguo(historial):
    if not historial or not isinstance(historial, dict):
        return cargar_historial()
    
    ahora = datetime.now()
    indices_validos = []
    
    timestamps = historial.get('timestamps', [])
    
    for i, ts_str in enumerate(timestamps):
        try:
            if isinstance(ts_str, str):
                ts = datetime.fromisoformat(ts_str)
                if (ahora - ts) < timedelta(hours=VENTANA_DUPLICADOS_HORAS):
                    indices_validos.append(i)
        except:
            continue
    
    nuevo_historial = {
        'urls': [],
        'hashes': [],
        'timestamps': [],
        'titulos': [],
        'video_ids': [],
        'estadisticas': historial.get('estadisticas', {'total_publicadas': 0, 'videos': 0, 'links': 0})
    }
    
    for key in ['urls', 'hashes', 'timestamps', 'titulos', 'video_ids']:
        arr = historial.get(key, [])
        for i in indices_validos:
            if i < len(arr):
                nuevo_historial[key].append(arr[i])
    
    # Hashes permanentes
    todos_hashes = historial.get('hashes', [])
    if len(todos_hashes) > 200:
        nuevo_historial['hashes_permanentes'] = todos_hashes[-200:]
    elif 'hashes_permanentes' in historial:
        nuevo_historial['hashes_permanentes'] = historial['hashes_permanentes']
    else:
        nuevo_historial['hashes_permanentes'] = []
    
    return nuevo_historial

def noticia_ya_publicada(historial, url, titulo, video_id=None):
    """🆕 MEJORADO: También verifica video_id"""
    if not historial or not isinstance(historial, dict):
        return False
    
    # Verificar video_id específico
    if video_id:
        video_ids_guardados = historial.get('video_ids', [])
        if video_id in video_ids_guardados:
            log(f"   ⚠️ DUPLICADO: Video ID {video_id} ya publicado", 'debug')
            return True
    
    # Verificaciones estándar (URL, hash, similitud)
    url_normalizada = normalizar_url(url)
    
    urls_guardadas = historial.get('urls', [])
    for url_hist in urls_guardadas:
        if normalizar_url(url_hist) == url_normalizada:
            return True
    
    hash_titulo = generar_hash(titulo)
    todos_hashes = historial.get('hashes', []) + historial.get('hashes_permanentes', [])
    if hash_titulo in todos_hashes:
        return True
    
    titulos_guardados = historial.get('titulos', [])
    for titulo_hist in titulos_guardados:
        if calcular_similitud_titulos(titulo, titulo_hist) >= UMBRAL_SIMILITUD_TITULO:
            return True
    
    return False

def guardar_historial(historial, url, titulo, video_id=None, tipo_publicacion='video'):
    """🆕 MEJORADO: Guarda video_id y tipo de publicación"""
    url_limpia = re.sub(r'\?.*$', '', url)
    hash_titulo = generar_hash(titulo)
    ahora = datetime.now().isoformat()
    
    historial['urls'].append(url_limpia)
    historial['hashes'].append(hash_titulo)
    historial['timestamps'].append(ahora)
    historial['titulos'].append(titulo)
    
    if video_id:
        historial['video_ids'].append(video_id)
    
    stats = historial.get('estadisticas', {'total_publicadas': 0, 'videos': 0, 'links': 0})
    stats['total_publicadas'] = stats.get('total_publicadas', 0) + 1
    if tipo_publicacion == 'video':
        stats['videos'] = stats.get('videos', 0) + 1
    else:
        stats['links'] = stats.get('links', 0) + 1
    historial['estadisticas'] = stats
    
    if 'hashes_permanentes' not in historial:
        historial['hashes_permanentes'] = []
    historial['hashes_permanentes'].append(hash_titulo)
    if len(historial['hashes_permanentes']) > 200:
        historial['hashes_permanentes'] = historial['hashes_permanentes'][-200:]
    
    historial = limpiar_historial_antiguo(historial)
    
    max_size = 500
    for key in ['urls', 'hashes', 'timestamps', 'titulos', 'video_ids']:
        if len(historial[key]) > max_size:
            historial[key] = historial[key][-max_size:]
    
    guardar_json(HISTORIAL_PATH, historial)

def cargar_estado():
    return cargar_json(ESTADO_PATH, {'ultima_publicacion': None})

def guardar_estado(estado):
    guardar_json(ESTADO_PATH, estado)

def verificar_tiempo():
    estado = cargar_estado()
    ultima = estado.get('ultima_publicacion')
    
    if not ultima:
        return True
    
    try:
        ultima_dt = datetime.fromisoformat(ultima)
        minutos = (datetime.now() - ultima_dt).total_seconds() / 60
        if minutos < TIEMPO_ENTRE_PUBLICACIONES:
            log(f"⏱️ Esperando... Última hace {minutos:.0f} min", 'info')
            return False
        return True
    except:
        return True

# =============================================================================
# FUNCIÓN PRINCIPAL - VIDEO
# =============================================================================

def main():
    print("\n" + "="*60)
    print("🎥 BOT DE NOTICIAS EN VIDEO PARA FACEBOOK")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales de Facebook", 'error')
        return False
    
    if not verificar_tiempo():
        return False
    
    # Verificar dependencias
    try:
        import subprocess
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True)
        log(f"yt-dlp versión: {result.stdout.strip()}", 'debug')
    except:
        log("⚠️ ADVERTENCIA: yt-dlp no instalado. Instalar con: pip install yt-dlp", 'advertencia')
        log("   Se usará modo de enlaces de video solamente", 'advertencia')
    
    historial = cargar_historial()
    log(f"📊 Historial: {len(historial.get('urls', []))} videos recientes (72h)")
    
    # Recolectar videos de todas las fuentes
    todos_videos = []
    
    # YouTube API (principal)
    if YOUTUBE_API_KEY:
        todos_videos.extend(buscar_videos_youtube())
    
    # Videos en APIs de noticias
    todos_videos.extend(buscar_videos_news_apis())
    
    # RSS de noticieros
    todos_videos.extend(buscar_videos_rss_noticieros())
    
    log(f"🎥 Total videos recolectados: {len(todos_videos)}")
    
    if not todos_videos:
        log("ERROR: No se encontraron videos", 'error')
        return False
    
    # Ordenar por puntaje
    todos_videos.sort(key=lambda x: (x.get('puntaje', 0), x.get('fecha', '')), reverse=True)
    
    # Seleccionar video no publicado
    video_seleccionado = None
    intentos = 0
    
    for video in todos_videos:
        url = video.get('url', '')
        titulo = video.get('titulo', '')
        video_id = video.get('video_id', '')
        intentos += 1
        
        if not url or not titulo:
            continue
        
        log(f"   [{intentos}] Probando: {titulo[:50]}...", 'debug')
        
        if noticia_ya_publicada(historial, url, titulo, video_id):
            log(f"      ❌ Rechazado: Ya publicado", 'debug')
            continue
        
        if video.get('puntaje', 0) < 5:
            log(f"      ❌ Rechazado: Puntaje bajo ({video.get('puntaje', 0)})", 'debug')
            continue
        
        video_seleccionado = video
        log(f"      ✅ Aceptado: Video válido encontrado", 'debug')
        break
    
    if not video_seleccionado:
        log(f"ERROR: No hay videos nuevos (revisados {intentos})", 'error')
        return False
    
    log(f"\n🎬 VIDEO SELECCIONADO:")
    log(f"   Título: {video_seleccionado['titulo'][:60]}...")
    log(f"   Fuente: {video_seleccionado['fuente']}")
    log(f"   URL: {video_seleccionado['url'][:60]}...")
    
    # Generar hashtags
    hashtags = generar_hashtags_video(video_seleccionado['titulo'], video_seleccionado.get('descripcion', ''))
    
    # Intentar descargar y publicar video nativo
    video_path = None
    thumbnail_path = None
    exito = False
    
    if video_seleccionado.get('tipo') == 'youtube' and video_seleccionado.get('video_id'):
        video_id = video_seleccionado['video_id']
        
        # Descargar thumbnail primero (fallback)
        if video_seleccionado.get('thumbnail'):
            thumbnail_path = obtener_thumbnail_video(video_seleccionado['thumbnail'], video_id)
        
        # Intentar descargar video
        video_path = descargar_video_youtube(video_seleccionado['url'], video_id)
        
        if video_path and os.path.exists(video_path):
            # Publicar video nativo
            exito = publicar_video_facebook(
                video_seleccionado['titulo'],
                video_seleccionado.get('descripcion', ''),
                video_path,
                hashtags,
                {'video_id': video_id}
            )
            
            # Limpiar archivo temporal
            try:
                os.remove(video_path)
                if os.path.exists(os.path.dirname(video_path)):
                    os.rmdir(os.path.dirname(video_path))
            except:
                pass
    
    # Si falló la publicación nativa, usar enlace con thumbnail
    if not exito:
        log("   📎 Publicando como enlace de video...", 'info')
        exito = publicar_enlace_video_facebook(
            video_seleccionado['titulo'],
            video_seleccionado.get('descripcion', ''),
            video_seleccionado['url'],
            hashtags,
            thumbnail_path
        )
        
        tipo_pub = 'link'
    else:
        tipo_pub = 'video'
    
    # Limpiar thumbnail si existe
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            os.remove(thumbnail_path)
        except:
            pass
    
    # Guardar estado
    if exito:
        guardar_historial(
            historial, 
            video_seleccionado['url'], 
            video_seleccionado['titulo'],
            video_seleccionado.get('video_id'),
            tipo_pub
        )
        
        estado = cargar_estado()
        estado['ultima_publicacion'] = datetime.now().isoformat()
        guardar_estado(estado)
        
        stats = cargar_historial().get('estadisticas', {})
        log(f"✅ ÉXITO - Videos nativos: {stats.get('videos', 0)}, Enlaces: {stats.get('links', 0)}", 'exito')
        return True
    
    return False

def generar_hashtags_video(titulo, descripcion):
    """Genera hashtags específicos para videos de noticias"""
    texto = f"{titulo} {descripcion}".lower()
    hashtags = ['#NoticiasEnVideo', '#ÚltimaHora', '#VideoNoticias']
    
    temas = {
        'guerra|conflicto|ataque|bombardeo': '#ConflictoArmado',
        'ucrania|rusia|zelensky|putin': '#UcraniaRusia',
        'gaza|israel|palestina|hamas|netanyahu': '#IsraelGaza',
        'trump|biden': '#PolíticaGlobal',
        'economía|mercados': '#EconomíaMundial',
        'iran|yemen|arabia': '#OrienteMedio',
        'china|taiwan': '#ChinaTaiwán',
        'drone|dron|footage': '#WarFootage',
        'protest|protesta': '#Protestas',
    }
    
    for patron, tag in temas.items():
        if re.search(patron, texto):
            hashtags.append(tag)
    
    hashtags.append('#Mundo')
    return ' '.join(hashtags)

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

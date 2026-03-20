#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias en VIDEO para Facebook - V2.4 FINAL
Todo en un solo archivo - Lista para GitHub Actions
"""

import os
import sys
import re
import hashlib
import json
import tempfile
import subprocess
import base64
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

# =============================================================================
# MANEJO DE DEPENDENCIAS OPCIONALES
# =============================================================================

DEPENDENCIAS_FALTANTES = []

try:
    import requests
    REQUESTS_DISPONIBLE = True
except ImportError:
    REQUESTS_DISPONIBLE = False
    DEPENDENCIAS_FALTANTES.append('requests')

try:
    import feedparser
    FEEDPARSER_DISPONIBLE = True
except ImportError:
    FEEDPARSER_DISPONIBLE = False
    DEPENDENCIAS_FALTANTES.append('feedparser')

try:
    from difflib import SequenceMatcher
    DIFFLIB_DISPONIBLE = True
except ImportError:
    DIFFLIB_DISPONIBLE = False
    class SequenceMatcher:
        def __init__(self, *args): pass
        def ratio(self): return 0.0

try:
    import html as html_module
    HTML_DISPONIBLE = True
except ImportError:
    HTML_DISPONIBLE = False
    class html_module:
        @staticmethod
        def unescape(s): return s

if DEPENDENCIAS_FALTANTES:
    print(f"⚠️ Dependencias faltantes: {', '.join(DEPENDENCIAS_FALTANTES)}")
    if 'requests' in DEPENDENCIAS_FALTANTES:
        print("❌ ERROR CRÍTICO: requests es obligatorio")
        sys.exit(1)

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_publicaciones.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot.json')

TIEMPO_ENTRE_PUBLICACIONES = 60
VENTANA_DUPLICADOS_HORAS = 72
UMBRAL_SIMILITUD_TITULO = 0.85

# =============================================================================
# PALABRAS CLAVE
# =============================================================================

PALABRAS_INDIVIDUALES = {
    'war': 10, 'guerra': 10, 'conflict': 10, 'conflicto': 10,
    'attack': 10, 'ataque': 10, 'missile': 10, 'misil': 10,
    'bomb': 10, 'bomba': 10, 'strike': 10, 'bombardeo': 10,
    'drone': 10, 'dron': 10, 'invasion': 10, 'invasión': 10,
    'offensive': 10, 'ofensiva': 10, 'combat': 10, 'combate': 10,
    'ceasefire': 8, 'cese': 8, 'fire': 5, 'fuego': 5,
    'ukraine': 10, 'ucrania': 10, 'russia': 10, 'rusia': 10,
    'gaza': 10, 'israel': 10, 'palestine': 10, 'palestina': 10,
    'iran': 10, 'irán': 10, 'korea': 10, 'corea': 10, 'north': 5, 'norte': 5,
    'taiwan': 10, 'china': 8, 'syria': 10, 'siria': 10, 'yemen': 10,
    'lebanon': 10, 'líbano': 10, 'myanmar': 10, 'venezuela': 8,
    'trump': 10, 'biden': 10, 'putin': 10, 'zelensky': 10, 'zelenskyy': 10,
    'netanyahu': 10, 'hamas': 10, 'hezbollah': 10, 'houthis': 10, 'houthi': 10,
    'kim': 8, 'jong': 8, 'starmer': 8, 'macron': 8, 'milei': 8,
    'nato': 8, 'otan': 8, 'un': 8, 'onu': 8, 'eu': 8, 'ue': 8,
    'brics': 8, 'g7': 5, 'g20': 5, 'opec': 5,
    'crisis': 8, 'sanctions': 8, 'sanciones': 8, 'embargo': 8,
    'humanitarian': 8, 'humanitaria': 8, 'refugee': 8, 'refugiado': 8,
    'famine': 8, 'hambruna': 8, 'genocide': 10, 'genocidio': 10,
    'nuclear': 10, 'ballistic': 10, 'balístico': 10, 'hypersonic': 10,
    'hipersónico': 10, 'cyber': 8, 'ciber': 8, 'satellite': 8, 'satélite': 8,
    'ai': 5, 'ia': 5, 'artificial': 5, 'intelligence': 5,
    'oil': 5, 'petróleo': 5, 'gas': 5, 'economy': 5, 'economía': 5,
    'inflation': 5, 'inflación': 5, 'market': 5, 'mercado': 5,
    'rare': 8, 'tierras': 8, 'lithium': 8, 'litio': 8, 'cobalt': 8, 'cobalto': 8,
    'footage': 5, 'video': 3, 'live': 3, 'en vivo': 3, 'breaking': 5,
    'urgent': 5, 'urgente': 5, 'alert': 5, 'alerta': 5,
}

FRASES_PRIORITARIAS = [
    'breaking news', 'ultima hora', 'en vivo', 'live now', 'news report',
    'war footage', 'conflict zone', 'military operation', 'air strike',
    'ballistic missile', 'misil balístico', 'nuclear test', 'prueba nuclear',
    'drone attack', 'ataque drone', 'ceasefire broken', 'cese al fuego',
    'humanitarian crisis', 'crisis humanitaria', 'mass casualty', 'bajas masivas',
]

TERMINOS_EXCLUIR = [
    'gameplay', 'unboxing', 'review', 'tutorial', 'receta', 
    'comedia', 'meme', 'challenge', 'prank', 'broma',
    'trailer', 'how to', 'cómo', 'gaming', 'tiktok dance'
]

# =============================================================================
# FUNCIONES BÁSICAS
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
    
    if DIFFLIB_DISPONIBLE:
        return SequenceMatcher(None, t1, t2).ratio()
    return 0.0

def limpiar_texto(texto):
    if not texto:
        return ""
    if HTML_DISPONIBLE:
        texto = html_module.unescape(texto)
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', texto)
    texto = texto.strip()
    if texto and texto[-1] not in '.!?':
        texto += '.'
    return texto.strip()

def es_noticia_excluible(titulo, descripcion=""):
    texto = f"{titulo} {descripcion}".lower()
    for termino in TERMINOS_EXCLUIR:
        if termino in texto:
            return True
    return False

def calcular_puntaje_mejorado(titulo, descripcion=""):
    texto_completo = f"{titulo} {descripcion}".lower()
    puntaje = 0
    detalles = []
    
    # Palabras individuales
    palabras_encontradas = []
    for palabra, valor in PALABRAS_INDIVIDUALES.items():
        if palabra in texto_completo:
            puntaje += valor
            palabras_encontradas.append(f"{palabra}(+{valor})")
    
    # Frases completas
    for frase in FRASES_PRIORITARIAS:
        if frase in texto_completo:
            puntaje += 15
            detalles.append(f"FRASE:{frase}(+15)")
    
    # Fuentes confiables
    fuentes_confiables = ['bbc', 'cnn', 'reuters', 'ap ', 'al jazeera', 'dw ', 
                         'france 24', 'euronews', 'rt ', 'fox news', 'msnbc', 
                         'sky news', 'bloomberg', 'abc news', 'cbs news', 'nbc news']
    for fuente in fuentes_confiables:
        if fuente in texto_completo:
            puntaje += 5
            detalles.append(f"FUENTE:{fuente}(+5)")
            break
    
    # Longitud apropiada
    if 40 <= len(titulo) <= 100:
        puntaje += 2
        detalles.append("LONGITUD(+2)")
    
    # Penalización
    no_noticia = ['trailer', 'review', 'how to', 'cómo', 'tutorial', 'gaming']
    for termino in no_noticia:
        if termino in texto_completo:
            puntaje -= 10
            detalles.append(f"NO_NOTICIA:{termino}(-10)")
    
    if palabras_encontradas:
        detalles.append(f"PALABRAS:{','.join(palabras_encontradas[:3])}")
    
    return max(0, puntaje), detalles

# =============================================================================
# BÚSQUEDA DE VIDEOS
# =============================================================================

def buscar_videos_youtube():
    if not YOUTUBE_API_KEY:
        return []
    
    videos = []
    queries = [
        "breaking news today", "world news now", "international news",
        "war news", "conflict news", "political crisis", "military news"
    ]
    
    for query in queries:
        try:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'videoDuration': 'any',
                'order': 'date',
                'maxResults': 15,
                'key': YOUTUBE_API_KEY,
                'publishedAfter': (datetime.now() - timedelta(hours=24)).isoformat("T") + "Z"
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
                    
                    puntaje, detalles = calcular_puntaje_mejorado(titulo, descripcion)
                    
                    canales_noticias = ['bbc', 'cnn', 'reuters', 'al jazeera', 'dw ', 
                                       'france 24', 'euronews', 'sky news', 'msnbc',
                                       'fox news', 'washington post', 'ny times',
                                       'guardian', 'bloomberg', 'abc news', 'cbs news',
                                       'nbc news', 'pbs', 'npr', 'vice news', 'nowthis',
                                       'aj+', 'democracy now', 'the intercept']
                    
                    es_noticiero = any(c in canal.lower() for c in canales_noticias)
                    
                    if puntaje >= 3 or es_noticiero:
                        videos.append({
                            'titulo': limpiar_texto(titulo),
                            'descripcion': limpiar_texto(descripcion),
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                            'video_id': video_id,
                            'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                            'fuente': f"YouTube:{canal}",
                            'fecha': snippet.get('publishedAt'),
                            'puntaje': puntaje + (5 if es_noticiero else 0),
                            'detalles': detalles,
                            'tipo': 'youtube'
                        })
        except Exception as e:
            log(f"Error YouTube: {e}", 'error')
    
    log(f"YouTube: {len(videos)} videos", 'info')
    return videos

def buscar_videos_news_apis():
    videos = []
    
    if NEWS_API_KEY:
        try:
            url = 'https://newsapi.org/v2/everything'
            queries = [
                'war OR conflict OR attack OR missile OR drone',
                'ukraine OR russia OR gaza OR israel OR iran',
                'trump OR biden OR putin OR zelensky',
                'breaking news video footage'
            ]
            
            for q in queries:
                params = {
                    'apiKey': NEWS_API_KEY,
                    'q': q,
                    'language': 'en',
                    'sortBy': 'publishedAt',
                    'pageSize': 10
                }
                
                resp = requests.get(url, params=params, timeout=15)
                data = resp.json()
                
                if data.get('status') == 'ok':
                    for art in data.get('articles', []):
                        titulo = art.get('title', '')
                        url_art = art.get('url', '')
                        
                        es_video = any(d in url_art.lower() for d in 
                                     ['youtube', 'youtu.be', 'twitter', 'rumble'])
                        
                        if es_video:
                            puntaje, detalles = calcular_puntaje_mejorado(titulo, art.get('description', ''))
                            if puntaje >= 5:
                                videos.append({
                                    'titulo': limpiar_texto(titulo),
                                    'descripcion': limpiar_texto(art.get('description', '')),
                                    'url': url_art,
                                    'fuente': f"NewsAPI:{art.get('source', {}).get('name', 'Unknown')}",
                                    'fecha': art.get('publishedAt'),
                                    'puntaje': puntaje,
                                    'detalles': detalles,
                                    'tipo': 'externo'
                                })
        except Exception as e:
            log(f"Error NewsAPI: {e}", 'error')
    
    log(f"NewsAPI: {len(videos)} videos", 'info')
    return videos

def buscar_videos_rss_noticieros():
    if not FEEDPARSER_DISPONIBLE:
        return []
    
    feeds_video = [
        'https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA',
        'https://www.youtube.com/feeds/videos.xml?channel_id=UCupvZG-5ko_eiXAupbDfxWw',
        'https://www.youtube.com/feeds/videos.xml?channel_id=UCNye-wNBqNL5ZzHSJj3l8Bg',
        'https://www.youtube.com/feeds/videos.xml?channel_id=UCknLrEdhRCp1aegoMqRaCZg',
        'https://www.youtube.com/feeds/videos.xml?channel_id=UCQfwfsi5VrQ8yKZUdWkAR_g',
        'https://www.youtube.com/feeds/videos.xml?channel_id=UCoMdktPbSTixAyNGwb-UYkQ',
        'https://www.youtube.com/feeds/videos.xml?channel_id=UCBi2mrWuNuyYy4gbM6fU18Q',
        'https://www.youtube.com/feeds/videos.xml?channel_id=UC8p1vwvWtl6TAx0Rh_6NJwQ',
    ]
    
    videos = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for feed_url in feeds_video:
        try:
            feed = feedparser.parse(feed_url, request_headers=headers)
            canal = feed.feed.get('title', 'Unknown')
            
            for entry in feed.entries[:3]:
                titulo = entry.get('title', '')
                link = entry.get('link', '')
                
                video_id = None
                if 'youtube.com/watch?v=' in link:
                    video_id = link.split('v=')[1].split('&')[0]
                elif 'youtu.be/' in link:
                    video_id = link.split('youtu.be/')[1].split('?')[0]
                
                if not video_id:
                    continue
                
                puntaje, detalles = calcular_puntaje_mejorado(titulo, "")
                
                if puntaje >= 5 and not es_noticia_excluible(titulo):
                    videos.append({
                        'titulo': limpiar_texto(titulo),
                        'descripcion': limpiar_texto(entry.get('summary', '')),
                        'url': link,
                        'video_id': video_id,
                        'fuente': f"RSS:{canal}",
                        'fecha': entry.get('published'),
                        'puntaje': puntaje,
                        'detalles': detalles,
                        'tipo': 'youtube_rss'
                    })
        except Exception as e:
            continue
    
    log(f"RSS: {len(videos)} videos", 'info')
    return videos

# =============================================================================
# DESCARGA DE VIDEOS - MÚLTIPLES ESTRATEGIAS
# =============================================================================

def verificar_yt_dlp():
    try:
        result = subprocess.run(['yt-dlp', '--version'], 
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def verificar_youtube_dl():
    try:
        result = subprocess.run(['youtube-dl', '--version'], 
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def verificar_pytube():
    try:
        from pytube import YouTube
        return True
    except ImportError:
        return False

def descargar_video_yt_dlp(video_url, video_id):
    """Estrategia 1: yt-dlp"""
    try:
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"{video_id}.mp4")
        
        cmd = [
            'yt-dlp',
            '--format', 'best[height<=720][ext=mp4]/best[height<=720]',
            '--merge-output-format', 'mp4',
            '--output', output_path,
            '--no-playlist',
            '--quiet',
            '--no-warnings',
            '--no-check-certificates',
            '--geo-bypass',
            video_url
        ]
        
        log(f"   ⬇️ Descargando con yt-dlp...", 'info')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0 and os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            log(f"   ✅ yt-dlp: {size_mb:.1f} MB", 'exito')
            return output_path, 'yt_dlp'
        
        # Intentar formato alternativo
        cmd_alt = [
            'yt-dlp',
            '-f', 'mp4/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
            '--output', output_path,
            '--no-playlist', '--quiet',
            video_url
        ]
        
        result = subprocess.run(cmd_alt, capture_output=True, text=True, timeout=180)
        if result.returncode == 0 and os.path.exists(output_path):
            return output_path, 'yt_dlp_alt'
        
        # Limpiar si falló
        try:
            os.rmdir(temp_dir)
        except:
            pass
        return None, None
        
    except Exception as e:
        log(f"   ❌ yt-dlp error: {str(e)[:100]}", 'debug')
        return None, None

def descargar_video_youtube_dl(video_url, video_id):
    """Estrategia 2: youtube-dl"""
    try:
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"{video_id}.mp4")
        
        cmd = [
            'youtube-dl',
            '-f', 'best[height<=720]',
            '--merge-output-format', 'mp4',
            '-o', output_path,
            '--no-playlist',
            '--quiet',
            '--no-check-certificate',
            video_url
        ]
        
        log(f"   ⬇️ Intentando con youtube-dl...", 'info')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0 and os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            log(f"   ✅ youtube-dl: {size_mb:.1f} MB", 'exito')
            return output_path, 'youtube_dl'
        
        try:
            os.rmdir(temp_dir)
        except:
            pass
        return None, None
        
    except Exception as e:
        log(f"   ❌ youtube-dl error: {str(e)[:100]}", 'debug')
        return None, None

def descargar_video_pytube(video_url, video_id):
    """Estrategia 3: pytube"""
    try:
        from pytube import YouTube
        
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"{video_id}.mp4")
        
        log(f"   ⬇️ Intentando con pytube...", 'info')
        yt = YouTube(video_url)
        
        # Stream progresivo (video+audio)
        stream = yt.streams.filter(
            progressive=True, 
            file_extension='mp4',
            res='720p'
        ).first()
        
        if not stream:
            stream = yt.streams.filter(
                progressive=True,
                file_extension='mp4'
            ).order_by('resolution').desc().first()
        
        if stream:
            downloaded = stream.download(output_path=temp_dir, filename=video_id)
            
            # Verificar que se descargó correctamente
            if os.path.exists(downloaded) and os.path.getsize(downloaded) > 1024:
                # Renombrar si es necesario
                if downloaded != output_path:
                    os.rename(downloaded, output_path)
                
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                log(f"   ✅ pytube: {size_mb:.1f} MB", 'exito')
                return output_path, 'pytube'
        
        try:
            os.rmdir(temp_dir)
        except:
            pass
        return None, None
        
    except Exception as e:
        log(f"   ❌ pytube error: {str(e)[:100]}", 'debug')
        return None, None

def descargar_video_multiestrategia(video_url, video_id):
    """
    Intenta descargar con múltiples estrategias en orden
    """
    # Verificar qué herramientas están disponibles
    tiene_yt_dlp = verificar_yt_dlp()
    tiene_youtube_dl = verificar_youtube_dl()
    tiene_pytube = verificar_pytube()
    
    log(f"   📥 Herramientas disponibles: yt-dlp={'✅' if tiene_yt_dlp else '❌'}, "
        f"youtube-dl={'✅' if tiene_youtube_dl else '❌'}, "
        f"pytube={'✅' if tiene_pytube else '❌'}", 'debug')
    
    # Estrategia 1: yt-dlp (mejor opción)
    if tiene_yt_dlp:
        resultado, metodo = descargar_video_yt_dlp(video_url, video_id)
        if resultado:
            return resultado, metodo
    
    # Estrategia 2: youtube-dl
    if tiene_youtube_dl:
        resultado, metodo = descargar_video_youtube_dl(video_url, video_id)
        if resultado:
            return resultado, metodo
    
    # Estrategia 3: pytube
    if tiene_pytube:
        resultado, metodo = descargar_video_pytube(video_url, video_id)
        if resultado:
            return resultado, metodo
    
    log("   ❌ Todas las estrategias de descarga fallaron", 'error')
    return None, None

# =============================================================================
# DESCARGA DE THUMBNAILS
# =============================================================================

def descargar_thumbnail(video_id, url_primaria=None):
    """Descarga thumbnail de múltiples fuentes"""
    fuentes = [
        f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg',
        f'https://img.youtube.com/vi/{video_id}/sddefault.jpg',
        f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg',
        f'https://img.youtube.com/vi/{video_id}/mqdefault.jpg',
        f'https://img.youtube.com/vi/{video_id}/default.jpg',
    ]
    
    if url_primaria:
        fuentes.insert(0, url_primaria)
    
    for url in fuentes:
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            
            if resp.status_code == 200 and len(resp.content) > 2000:
                temp_path = f'/tmp/thumb_{video_id}.jpg'
                with open(temp_path, 'wb') as f:
                    f.write(resp.content)
                return temp_path
        except:
            continue
    
    return None

# =============================================================================
# PUBLICACIÓN FACEBOOK
# =============================================================================

def publicar_video_facebook(titulo, descripcion, video_path, hashtags):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Faltan credenciales FB", 'error')
        return False
    
    mensaje = f"📰 {titulo}\n\n{descripcion}\n\n{hashtags}\n\n— 🌐 Verdad Hoy"
    if len(mensaje) > 2000:
        mensaje = mensaje[:1900] + "...\n\n" + hashtags
    
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
        
        with open(video_path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {
                'description': mensaje,
                'access_token': FB_ACCESS_TOKEN,
                'published': 'true'
            }
            
            log("   📤 Subiendo video a Facebook...", 'info')
            resp = requests.post(url, files=files, data=data, timeout=300)
            result = resp.json()
        
        if resp.status_code == 200 and 'id' in result:
            log(f"✅ Video publicado: {result['id']}", 'exito')
            return True
        else:
            error_msg = result.get('error', {}).get('message', 'Unknown')
            log(f"❌ Error FB: {error_msg[:100]}", 'error')
            return False
    except Exception as e:
        log(f"Error: {e}", 'error')
        return False

def publicar_enlace_facebook(titulo, descripcion, url_video, hashtags, thumbnail_path=None):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        return False
    
    mensaje = f"📰 {titulo}\n\n{descripcion}\n\n🔗 Ver video: {url_video}\n\n{hashtags}\n\n— 🌐 Verdad Hoy"
    
    try:
        if thumbnail_path and os.path.exists(thumbnail_path):
            url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
            with open(thumbnail_path, 'rb') as f:
                files = {'file': ('thumbnail.jpg', f, 'image/jpeg')}
                data = {'message': mensaje, 'access_token': FB_ACCESS_TOKEN}
                resp = requests.post(url, files=files, data=data, timeout=60)
        else:
            url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed"
            data = {
                'message': mensaje,
                'link': url_video,
                'access_token': FB_ACCESS_TOKEN
            }
            resp = requests.post(url, data=data, timeout=60)
        
        result = resp.json()
        
        if resp.status_code == 200 and 'id' in result:
            log(f"✅ Enlace publicado: {result['id']}", 'exito')
            return True
        return False
    except:
        return False

# =============================================================================
# HISTORIAL Y ESTADO
# =============================================================================

def cargar_historial():
    default = {
        'urls': [], 'hashes': [], 'timestamps': [], 'titulos': [],
        'video_ids': [], 'estadisticas': {'total': 0, 'videos': 0, 'links': 0}
    }
    return cargar_json(HISTORIAL_PATH, default)

def limpiar_historial_antiguo(historial):
    if not historial:
        return cargar_historial()
    
    ahora = datetime.now()
    indices = []
    
    for i, ts in enumerate(historial.get('timestamps', [])):
        try:
            if (ahora - datetime.fromisoformat(ts)) < timedelta(hours=VENTANA_DUPLICADOS_HORAS):
                indices.append(i)
        except:
            pass
    
    nuevo = {
        'urls': [], 'hashes': [], 'timestamps': [], 
        'titulos': [], 'video_ids': [],
        'estadisticas': historial.get('estadisticas', {'total': 0, 'videos': 0, 'links': 0})
    }
    
    for key in ['urls', 'hashes', 'timestamps', 'titulos', 'video_ids']:
        arr = historial.get(key, [])
        nuevo[key] = [arr[i] for i in indices if i < len(arr)]
    
    hashes = historial.get('hashes', [])
    nuevo['hashes_permanentes'] = hashes[-200:] if len(hashes) > 200 else hashes
    
    return nuevo

def noticia_ya_publicada(historial, url, titulo, video_id=None):
    if not historial:
        return False
    
    if video_id and video_id in historial.get('video_ids', []):
        return True
    
    url_norm = normalizar_url(url)
    for u in historial.get('urls', []):
        if normalizar_url(u) == url_norm:
            return True
    
    h = generar_hash(titulo)
    if h in historial.get('hashes', []) + historial.get('hashes_permanentes', []):
        return True
    
    for t in historial.get('titulos', []):
        if calcular_similitud_titulos(titulo, t) >= UMBRAL_SIMILITUD_TITULO:
            return True
    
    return False

def guardar_historial(historial, url, titulo, video_id=None, tipo='video'):
    url_limpia = re.sub(r'\?.*$', '', url)
    h = generar_hash(titulo)
    ahora = datetime.now().isoformat()
    
    historial['urls'].append(url_limpia)
    historial['hashes'].append(h)
    historial['timestamps'].append(ahora)
    historial['titulos'].append(titulo)
    if video_id:
        historial['video_ids'].append(video_id)
    
    stats = historial.get('estadisticas', {'total': 0, 'videos': 0, 'links': 0})
    stats['total'] += 1
    stats[tipo] = stats.get(tipo, 0) + 1
    historial['estadisticas'] = stats
    
    if 'hashes_permanentes' not in historial:
        historial['hashes_permanentes'] = []
    historial['hashes_permanentes'].append(h)
    if len(historial['hashes_permanentes']) > 200:
        historial['hashes_permanentes'] = historial['hashes_permanentes'][-200:]
    
    historial = limpiar_historial_antiguo(historial)
    
    for key in ['urls', 'hashes', 'timestamps', 'titulos', 'video_ids']:
        if len(historial[key]) > 500:
            historial[key] = historial[key][-500:]
    
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
        minutos = (datetime.now() - datetime.fromisoformat(ultima)).total_seconds() / 60
        if minutos < TIEMPO_ENTRE_PUBLICACIONES:
            log(f"⏱️ Esperando... Última hace {minutos:.0f} min", 'info')
            return False
        return True
    except:
        return True

# =============================================================================
# MAIN
# =============================================================================

def generar_hashtags(titulo, descripcion):
    texto = f"{titulo} {descripcion}".lower()
    hashtags = ['#NoticiasEnVideo', '#ÚltimaHora']
    
    temas = {
        'war|guerra|conflict|conflicto': '#ConflictoArmado',
        'ukraine|ucrania|russia|rusia': '#UcraniaRusia',
        'gaza|israel|palestine|palestina|hamas': '#IsraelGaza',
        'iran|yemen|syria|siria|lebanon|líbano': '#OrienteMedio',
        'korea|corea|north|norte|kim|jong': '#CoreaDelNorte',
        'trump|biden|putin|zelensky': '#PolíticaGlobal',
        'china|taiwan': '#ChinaTaiwán',
        'missile|misil|ballistic|balístico|nuclear': '#Armas',
        'drone|dron|footage': '#WarFootage',
        'crisis|sanctions|sanciones': '#Crisis',
    }
    
    for patron, tag in temas.items():
        if re.search(patron, texto):
            hashtags.append(tag)
            break
    
    hashtags.append('#Mundo')
    return ' '.join(hashtags)

def main():
    print("\n" + "="*60)
    print("🎥 BOT DE NOTICIAS VIDEO - V2.4 FINAL")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    if DEPENDENCIAS_FALTANTES:
        print(f"⚠️ Faltan: {', '.join(DEPENDENCIAS_FALTANTES)}")
    
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales Facebook", 'error')
        return False
    
    if not verificar_tiempo():
        return False
    
    # Verificar herramientas de descarga
    tiene_yt_dlp = verificar_yt_dlp()
    tiene_youtube_dl = verificar_youtube_dl()
    tiene_pytube = verificar_pytube()
    
    log(f"📥 Descarga: yt-dlp={'✅' if tiene_yt_dlp else '❌'}, "
        f"youtube-dl={'✅' if tiene_youtube_dl else '❌'}, "
        f"pytube={'✅' if tiene_pytube else '❌'}", 'info')
    
    historial = cargar_historial()
    log(f"📊 Historial: {len(historial.get('urls', []))} items (72h)")
    
    # Recolectar videos
    todos_videos = []
    
    if YOUTUBE_API_KEY:
        todos_videos.extend(buscar_videos_youtube())
    
    todos_videos.extend(buscar_videos_news_apis())
    todos_videos.extend(buscar_videos_rss_noticieros())
    
    log(f"🎥 Total: {len(todos_videos)} videos")
    
    if not todos_videos:
        log("ERROR: No se encontraron videos", 'error')
        return False
    
    # Ordenar por puntaje
    todos_videos.sort(key=lambda x: x.get('puntaje', 0), reverse=True)
    
    # Debug: mostrar top 5
    log("📋 Top videos:", 'debug')
    for i, v in enumerate(todos_videos[:5]):
        log(f"   {i+1}. [P{v.get('puntaje', 0)}] {v['titulo'][:50]}...", 'debug')
    
    # Seleccionar video
    video_sel = None
    intentos = 0
    
    for video in todos_videos:
        url = video.get('url', '')
        titulo = video.get('titulo', '')
        video_id = video.get('video_id', '')
        intentos += 1
        
        if not url or not titulo:
            continue
        
        puntaje = video.get('puntaje', 0)
        log(f"   [{intentos}] (P{puntaje}) {titulo[:50]}...", 'debug')
        
        if noticia_ya_publicada(historial, url, titulo, video_id):
            log(f"      ❌ Duplicado", 'debug')
            continue
        
        if puntaje < 5:
            log(f"      ❌ Puntaje bajo ({puntaje})", 'debug')
            continue
        
        video_sel = video
        log(f"      ✅ Aceptado (P{puntaje})", 'debug')
        break
    
    # Fallback si no hay videos nuevos con buen puntaje
    if not video_sel:
        log("⚠️ No hay videos nuevos con criterios estrictos", 'advertencia')
        for video in todos_videos:
            if video.get('puntaje', 0) >= 3:
                if not noticia_ya_publicada(historial, video['url'], video['titulo'], video.get('video_id')):
                    video_sel = video
                    log(f"🔄 Fallback: P{video['puntaje']}", 'advertencia')
                    break
        
        if not video_sel and todos_videos:
            video_sel = todos_videos[0]
            log(f"🔄 Fallback último recurso: P{video_sel['puntaje']}", 'advertencia')
    
    if not video_sel:
        log(f"ERROR: Sin videos disponibles ({intentos} revisados)", 'error')
        return False
    
    log(f"\n🎬 Seleccionado (P{video_sel['puntaje']}): {video_sel['titulo'][:60]}...")
    log(f"   Fuente: {video_sel['fuente']}")
    
    # Publicar
    hashtags = generar_hashtags(video_sel['titulo'], video_sel.get('descripcion', ''))
    
    video_path = None
    thumbnail_path = None
    exito = False
    tipo_pub = 'link'
    metodo_descarga = None
    
    # Intentar descargar video
    if video_sel.get('video_id'):
        video_id = video_sel['video_id']
        
        # Descargar thumbnail primero (siempre útil)
        thumbnail_path = descargar_thumbnail(video_id, video_sel.get('thumbnail'))
        
        # Intentar descargar video con múltiples estrategias
        video_path, metodo_descarga = descargar_video_multiestrategia(
            video_sel['url'], 
            video_id
        )
        
        if video_path:
            log(f"   ✅ Descargado via {metodo_descarga}", 'exito')
            exito = publicar_video_facebook(
                video_sel['titulo'],
                video_sel.get('descripcion', ''),
                video_path,
                hashtags
            )
            
            # Limpiar video
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
                    os.rmdir(os.path.dirname(video_path))
            except:
                pass
            
            if exito:
                tipo_pub = 'video'
    
    # Fallback a enlace
    if not exito:
        log("   📎 Publicando como enlace...", 'info')
        exito = publicar_enlace_facebook(
            video_sel['titulo'],
            video_sel.get('descripcion', ''),
            video_sel['url'],
            hashtags,
            thumbnail_path
        )
    
    # Limpiar thumbnail
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            os.remove(thumbnail_path)
        except:
            pass
    
    # Guardar
    if exito:
        guardar_historial(historial, video_sel['url'], video_sel['titulo'], 
                         video_sel.get('video_id'), tipo_pub)
        
        estado = cargar_estado()
        estado['ultima_publicacion'] = datetime.now().isoformat()
        guardar_estado(estado)
        
        stats = cargar_historial().get('estadisticas', {})
        log(f"✅ ÉXITO - Videos: {stats.get('videos', 0)}, Links: {stats.get('links', 0)}", 'exito')
        return True
    
    return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

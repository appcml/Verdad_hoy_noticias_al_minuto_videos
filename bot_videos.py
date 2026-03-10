#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Videos para Facebook - Verdad Hoy
Versión OPTIMIZADA para GitHub Actions - Con timeouts estrictos
Fuentes: NewsAPI + YouTube (con fallback a RSS)
"""

import os
import re
import json
import hashlib
import random
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path
import requests
import feedparser  # Para RSS de noticias

# Manejo de timeout global
class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Operación excedió el tiempo límite")

# Configurar timeout para todo el script (8 minutos max)
signal.signal(signal.SIGALRM, timeout_handler)

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

DATA_DIR = Path('data')
VIDEOS_DIR = DATA_DIR / 'videos'
HISTORIAL_PATH = DATA_DIR / 'historial.json'
ESTADO_PATH = DATA_DIR / 'estado.json'

DATA_DIR.mkdir(exist_ok=True)
VIDEOS_DIR.mkdir(exist_ok=True)

TIEMPO_ENTRE_PUBLICACIONES = 58

# =============================================================================
# UTILIDADES RÁPIDAS
# =============================================================================

def log(msg, tipo='info'):
    iconos = {'info': 'ℹ️', 'ok': '✅', 'error': '❌', 'warn': '⚠️', 'video': '🎬'}
    print(f"{iconos.get(tipo, 'ℹ️')} {msg}", flush=True)

def cargar_json(ruta, default=None):
    default = default or {}
    if ruta.exists():
        try:
            return json.loads(ruta.read_text())
        except:
            pass
    return default

def guardar_json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2))

def generar_hash(texto):
    return hashlib.md5(str(texto).lower().encode()).hexdigest()[:12]

def verificar_tiempo():
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None})
    if not estado.get('ultima_publicacion'):
        return True, estado
    try:
        ultima = datetime.fromisoformat(estado['ultima_publicacion'])
        return (datetime.now() - ultima).total_seconds() / 60 >= TIEMPO_ENTRE_PUBLICACIONES, estado
    except:
        return True, estado

# =============================================================================
# BÚSQUEDA RÁPIDA - NewsAPI (más confiable que scraping)
# =============================================================================

def buscar_noticias_newsapi(timeout=15):
    """Busca noticias reales vía NewsAPI - Funciona en GitHub Actions"""
    if not NEWS_API_KEY:
        log("NEWS_API_KEY no configurado", 'error')
        return []
    
    queries = ['war', 'conflict', 'military', 'ukraine', 'gaza', 'breaking']
    query = random.choice(queries)
    
    url = "https://newsapi.org/v2/everything"
    params = {
        'q': query,
        'language': 'en',
        'sortBy': 'publishedAt',
        'pageSize': 10,
        'from': (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d'),
        'apiKey': NEWS_API_KEY
    }
    
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        data = resp.json()
        
        if data.get('status') != 'ok':
            log(f"NewsAPI error: {data.get('message', 'Unknown')}", 'error')
            return []
        
        noticias = []
        for art in data.get('articles', [])[:5]:  # Máximo 5
            if art.get('title') and len(art['title']) > 10:
                noticias.append({
                    'titulo': art['title'],
                    'descripcion': art.get('description', ''),
                    'url': art['url'],
                    'fuente': art['source']['name'],
                    'tipo': 'noticia'
                })
        
        log(f"NewsAPI: {len(noticias)} noticias", 'ok')
        return noticias
        
    except requests.Timeout:
        log("Timeout NewsAPI", 'warn')
        return []
    except Exception as e:
        log(f"Error NewsAPI: {str(e)[:50]}", 'error')
        return []

# =============================================================================
# BÚSQUEDA RSS (Fallback si NewsAPI falla)
# =============================================================================

def buscar_noticias_rss(timeout=10):
    """Backup usando feeds RSS - No requiere API key"""
    feeds = [
        'http://feeds.bbci.co.uk/news/world/rss.xml',
        'http://rss.cnn.com/rss/edition_world.rss',
        'https://www.reutersagency.com/feed/?taxonomy=markets&post_type=reuters-best',
    ]
    
    noticias = []
    feed_url = random.choice(feeds)
    
    try:
        signal.alarm(timeout)  # Timeout estricto
        feed = feedparser.parse(feed_url)
        signal.alarm(0)
        
        for entry in feed.entries[:5]:
            if hasattr(entry, 'title') and len(entry.title) > 10:
                noticias.append({
                    'titulo': entry.title,
                    'descripcion': entry.get('summary', '')[:200],
                    'url': entry.link,
                    'fuente': feed.feed.title if hasattr(feed.feed, 'title') else 'RSS',
                    'tipo': 'noticia'
                })
        
        log(f"RSS: {len(noticias)} noticias", 'ok')
        return noticias
        
    except TimeoutException:
        log("Timeout RSS", 'warn')
        return []
    except Exception as e:
        log(f"Error RSS: {str(e)[:50]}", 'warn')
        return []

# =============================================================================
# BÚSQUEDA YOUTUBE (con timeout muy estricto)
# =============================================================================

def buscar_video_youtube(query, timeout=20):
    """
    Busca video en YouTube con timeout estricto
    Usa yt-dlp solo si está disponible, si no, retorna None rápido
    """
    try:
        import yt_dlp
    except ImportError:
        log("yt-dlp no instalado", 'warn')
        return None
    
    # Timeout para operaciones de red
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'socket_timeout': 10,  # 10 segundos max por operación
        'retries': 1,
    }
    
    search_url = f"ytsearch3:{query} video"  # Solo 3 resultados
    
    try:
        signal.alarm(timeout)  # Timeout global
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(search_url, download=False)
        signal.alarm(0)
        
        if not result or 'entries' not in result:
            return None
        
        for entry in result['entries']:
            if not entry:
                continue
            duracion = entry.get('duration', 0)
            # Videos entre 30s y 3 minutos
            if 30 < duracion < 180:
                return {
                    'titulo': entry.get('title', ''),
                    'url': entry.get('url', ''),
                    'id': entry.get('id', ''),
                    'duracion': duracion
                }
        return None
        
    except TimeoutException:
        log("Timeout YouTube search", 'warn')
        return None
    except Exception as e:
        log(f"YouTube error: {str(e)[:50]}", 'warn')
        return None

# =============================================================================
# DESCARGA RÁPIDA DE VIDEO
# =============================================================================

def descargar_video_yt(url, video_id, timeout=60):
    """Descarga video con timeout estricto"""
    try:
        import yt_dlp
    except ImportError:
        return None
    
    output_path = VIDEOS_DIR / f"vid_{video_id}.%(ext)s"
    
    ydl_opts = {
        'format': 'worst[filesize<30M]/best[filesize<30M]',  # Archivos pequeños
        'outtmpl': str(output_path),
        'max_filesize': 30000000,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 15,
        'retries': 2,
    }
    
    try:
        signal.alarm(timeout)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)
        signal.alarm(0)
        
        # Verificar archivo
        path = Path(video_path)
        if not path.exists():
            # Probar otras extensiones
            for ext in ['.mp4', '.webm', '.mkv']:
                alt = path.with_suffix(ext)
                if alt.exists():
                    path = alt
                    break
        
        if path.exists() and path.stat().st_size > 1000000:  # Mínimo 1MB
            size_mb = path.stat().st_size / (1024*1024)
            log(f"Video: {size_mb:.1f}MB", 'ok')
            return str(path)
        return None
        
    except TimeoutException:
        log("Timeout descarga", 'warn')
        return None
    except Exception as e:
        log(f"Error descarga: {str(e)[:50]}", 'warn')
        return None

# =============================================================================
# PUBLICACIÓN FACEBOOK
# =============================================================================

def publicar_fb(titulo, descripcion, video_path):
    """Publica en Facebook"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Sin credenciales FB", 'error')
        return False
    
    mensaje = f"🎬 {titulo}\n\n{descripcion[:150]}{'...' if len(descripcion) > 150 else ''}\n\n#Noticias #Actualidad #Video"
    
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
        with open(video_path, 'rb') as f:
            resp = requests.post(
                url,
                files={'file': ('video.mp4', f, 'video/mp4')},
                data={'description': mensaje[:1990], 'access_token': FB_ACCESS_TOKEN},
                timeout=120
            )
        
        result = resp.json()
        if 'id' in result:
            log(f"Publicado: {result['id']}", 'ok')
            return result['id']
        else:
            log(f"FB error: {result.get('error', {}).get('message', 'Unknown')[:50]}", 'error')
            return False
            
    except Exception as e:
        log(f"Error FB: {str(e)[:50]}", 'error')
        return False

# =============================================================================
# HISTORIAL
# =============================================================================

def cargar_historial():
    return cargar_json(HISTORIAL_PATH, {'hashes': [], 'videos': []})

def ya_publicado(historial, titulo):
    h = generar_hash(titulo)
    return h in historial.get('hashes', [])

def guardar_historial(historial, titulo, url, post_id):
    h = generar_hash(titulo)
    historial['hashes'].append(h)
    historial['videos'].append({
        'titulo': titulo[:100],
        'url': url,
        'post_id': post_id,
        'fecha': datetime.now().isoformat()
    })
    historial['hashes'] = historial['hashes'][-100:]
    historial['videos'] = historial['videos'][-50:]
    guardar_json(HISTORIAL_PATH, historial)

# =============================================================================
# MAIN - EJECUCIÓN RÁPIDA
# =============================================================================

def main():
    # Timeout global de 7 minutos para todo el script
    signal.alarm(420)  # 7 minutos
    
    print("\n" + "="*60)
    print("🎬 BOT VIDEOS - VERSIÓN RÁPIDA")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    start_time = time.time()
    
    # 1. Verificar tiempo entre publicaciones
    puede, estado = verificar_tiempo()
    if not puede:
        log("Esperando intervalo de 58 minutos...", 'warn')
        return True
    
    # 2. Cargar historial
    historial = cargar_historial()
    log(f"Historial: {len(historial.get('videos', []))} videos")
    
    # 3. Buscar noticias (NewsAPI primero, RSS si falla)
    noticias = buscar_noticias_newsapi(timeout=15)
    if not noticias:
        log("Intentando RSS...", 'info')
        noticias = buscar_noticias_rss(timeout=10)
    
    if not noticias:
        log("No se encontraron noticias", 'error')
        return False
    
    log(f"Procesando {len(noticias)} noticias...")
    
    # 4. Para cada noticia, buscar video y publicar
    for noticia in noticias[:3]:  # Máximo 3 intentos
        if ya_publicado(historial, noticia['titulo']):
            continue
        
        log(f"\n📰 {noticia['titulo'][:50]}...")
        
        # Buscar video relacionado
        video = buscar_video_youtube(noticia['titulo'], timeout=20)
        if not video:
            continue
        
        log(f"🎬 {video['titulo'][:50]}...")
        
        # Descargar
        video_path = descargar_video_yt(video['url'], video['id'], timeout=60)
        if not video_path:
            continue
        
        # Publicar
        post_id = publicar_fb(noticia['titulo'], noticia['descripcion'], video_path)
        
        # Limpiar
        try:
            Path(video_path).unlink()
        except:
            pass
        
        if post_id:
            guardar_historial(historial, noticia['titulo'], video['url'], post_id)
            estado['ultima_publicacion'] = datetime.now().isoformat()
            guardar_json(ESTADO_PATH, estado)
            
            elapsed = time.time() - start_time
            print("\n" + "="*60)
            log("✅ ÉXITO - Video publicado")
            print(f"⏱️  Tiempo total: {elapsed:.0f} segundos")
            print(f"📰 {noticia['titulo'][:60]}")
            print("="*60)
            return True
    
    log("No se pudo publicar ningún video", 'error')
    return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except TimeoutException:
        log("⏱️ Script excedió tiempo máximo (7 min)", 'error')
        exit(1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

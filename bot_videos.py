#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Reels de Noticias - Verdad Hoy v2.0
Estrategia: RSS → YouTube → Descarga → Reel 9:16
"""

import os
import json
import re
import hashlib
import random
import time
import subprocess
import requests
import feedparser
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

# =============================================================================
# CONFIGURACIÓN DE APIS
# =============================================================================

# 1. YOUTUBE API (obligatorio para búsqueda de videos)
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

# 2. VIDEO DOWNLOAD API (opcional pero recomendado)
# Opciones: rapidapi.com (más estable) o similar
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')  # Para Video Download API

# 3. FACEBOOK (para publicar)
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')

# 4. APITUBE (alternativa premium - opcional)
APITUBE_KEY = os.getenv('APITUBE_KEY')

# =============================================================================
# CONFIGURACIÓN DEL BOT
# =============================================================================

DATA_DIR = Path('data')
VIDEOS_DIR = DATA_DIR / 'videos'
REELS_DIR = DATA_DIR / 'reels'
HISTORIAL_PATH = DATA_DIR / 'historial_reels.json'
ESTADO_PATH = DATA_DIR / 'estado_bot.json'

for d in [DATA_DIR, VIDEOS_DIR, REELS_DIR]:
    d.mkdir(exist_ok=True)

TIEMPO_ENTRE_PUBLICACIONES = 58  # minutos

# Categorías y palabras clave para filtrar noticias
CATEGORIAS = {
    'guerra': {
        'keywords': ['war', 'conflict', 'ukraine', 'gaza', 'israel', 'military', 'attack', 'invasion'],
        'search_yt': ['war footage', 'ukraine war', 'gaza conflict', 'military combat']
    },
    'politica': {
        'keywords': ['election', 'biden', 'trump', 'putin', 'government', 'politics', 'sanctions'],
        'search_yt': ['political news', 'election coverage', 'government announcement']
    },
    'economia': {
        'keywords': ['economy', 'inflation', 'recession', 'market', 'stock', 'trade', 'crisis'],
        'search_yt': ['economy news', 'market crash', 'financial crisis', 'stock market today']
    },
    'mundo': {
        'keywords': ['china', 'russia', 'usa', 'nato', 'eu', 'diplomacy', 'summit', 'treaty'],
        'search_yt': ['world news today', 'international relations', 'global news']
    }
}

# Fuentes RSS confiables
FEEDS_RSS = [
    'http://feeds.bbci.co.uk/news/world/rss.xml',
    'http://rss.cnn.com/rss/edition_world.rss',
    'https://www.reutersagency.com/feed/?taxonomy=markets&post_type=reuters-best',
    'https://feeds.a.dj.com/rss/RSSWorldNews.xml',  # WSJ
    'https://feeds.npr.org/1004/rss.xml',  # NPR World
    'https://www.aljazeera.com/xml/rss/all.xml',
    'https://feeds.skynews.com/feeds/rss/world.xml',
]

# =============================================================================
# UTILIDADES
# =============================================================================

def log(msg, tipo='info'):
    iconos = {
        'info': 'ℹ️', 'ok': '✅', 'error': '❌', 
        'warn': '⚠️', 'video': '🎬', 'reel': '📱', 
        'news': '📰', 'yt': '▶️', 'rss': '📡'
    }
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {iconos.get(tipo, 'ℹ️')} {msg}", flush=True)

def cargar_json(ruta, default=None):
    default = default or {}
    if ruta.exists():
        try:
            return json.loads(ruta.read_text(encoding='utf-8'))
        except:
            pass
    return default

def guardar_json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')

def generar_hash(texto):
    return hashlib.md5(str(texto).encode()).hexdigest()[:12]

def detectar_categoria(texto):
    """Detecta la categoría de la noticia basada en palabras clave"""
    texto = texto.lower()
    scores = {}
    for cat, data in CATEGORIAS.items():
        score = sum(1 for k in data['keywords'] if k in texto)
        scores[cat] = score
    mejor = max(scores, key=scores.get)
    return mejor if scores[mejor] > 0 else 'mundo'

# =============================================================================
# 1️⃣ OBTENER NOTICIAS (RSS)
# =============================================================================

def obtener_noticias_rss(max_noticias=10):
    """Obtiene noticias de feeds RSS"""
    log("Obteniendo noticias de RSS...", 'rss')
    noticias = []
    
    # Seleccionar 3 feeds aleatorios para variedad
    feeds = random.sample(FEEDS_RSS, min(3, len(FEEDS_RSS)))
    
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:  # 5 noticias por feed
                if not hasattr(entry, 'title'):
                    continue
                
                noticia = {
                    'titulo': entry.title,
                    'descripcion': entry.get('summary', '')[:300],
                    'link': entry.link,
                    'fuente': feed.feed.title if hasattr(feed.feed, 'title') else 'RSS',
                    'fecha': entry.get('published', ''),
                    'categoria': detectar_categoria(entry.title + ' ' + entry.get('summary', ''))
                }
                noticias.append(noticia)
                
        except Exception as e:
            log(f"Error RSS {feed_url}: {str(e)[:50]}", 'warn')
            continue
    
    # Ordenar por relevancia (categoría con más keywords)
    noticias.sort(key=lambda x: sum(1 for k in CATEGORIAS[x['categoria']]['keywords'] 
                                   if k in (x['titulo'] + x['descripcion']).lower()), 
                 reverse=True)
    
    log(f"RSS: {len(noticias)} noticias obtenidas", 'ok')
    return noticias[:max_noticias]

# =============================================================================
# 2️⃣ BUSCAR VIDEO EN YOUTUBE (YouTube Data API v3)
# =============================================================================

def buscar_video_youtube_api(titulo_noticia, categoria, max_resultados=5):
    """
    Busca video relacionado usando YouTube Data API v3
    Requiere: YOUTUBE_API_KEY
    """
    if not YOUTUBE_API_KEY:
        log("YOUTUBE_API_KEY no configurado", 'error')
        return None
    
    # Construir query de búsqueda
    palabras_clave = [w for w in titulo_noticia.split() if len(w) > 3][:6]
    query = ' '.join(palabras_clave)
    
    # Agregar términos de búsqueda específicos de la categoría
    terminos_extra = random.choice(CATEGORIAS[categoria]['search_yt'])
    query += f" {terminos_extra}"
    
    log(f"Buscando en YouTube: {query[:50]}...", 'yt')
    
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': query,
        'type': 'video',
        'videoDuration': 'short',  # < 4 minutos
        'maxResults': max_resultados,
        'order': 'relevance',
        'key': YOUTUBE_API_KEY
    }
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        
        if 'error' in data:
            log(f"YouTube API error: {data['error'].get('message', 'Unknown')}", 'error')
            return None
        
        items = data.get('items', [])
        if not items:
            log("No se encontraron videos", 'warn')
            return None
        
        # Seleccionar video más relevante
        for item in items:
            video_id = item['id']['videoId']
            titulo = item['snippet']['title']
            
            # Verificar duración exacta con videos.list
            detalles = obtener_detalles_video(video_id)
            if detalles:
                duracion = detalles['duracion']
                # Ideal: 30 segundos a 3 minutos para reels
                if 30 <= duracion <= 180:
                    return {
                        'video_id': video_id,
                        'titulo': titulo,
                        'url': f"https://youtube.com/watch?v={video_id}",
                        'duracion': duracion,
                        'thumbnail': item['snippet']['thumbnails']['high']['url']
                    }
        
        return None
        
    except Exception as e:
        log(f"Error YouTube API: {str(e)[:60]}", 'error')
        return None

def obtener_detalles_video(video_id):
    """Obtiene duración del video usando videos.list"""
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        'part': 'contentDetails,statistics',
        'id': video_id,
        'key': YOUTUBE_API_KEY
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        items = data.get('items', [])
        if not items:
            return None
        
        # Parsear duración ISO 8601 (PT1M30S)
        duracion_iso = items[0]['contentDetails']['duration']
        duracion_seg = parsear_duracion_iso(duracion_iso)
        
        return {
            'duracion': duracion_seg,
            'vistas': items[0]['statistics'].get('viewCount', 0)
        }
    except:
        return None

def parsear_duracion_iso(duracion):
    """Convierte PT1M30S a segundos"""
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duracion)
    if not match:
        return 0
    horas, minutos, segundos = match.groups()
    total = 0
    if horas:
        total += int(horas) * 3600
    if minutos:
        total += int(minutos) * 60
    if segundos:
        total += int(segundos)
    return total

# =============================================================================
# 3️⃣ DESCARGAR VIDEO (Múltiples métodos)
# =============================================================================

def descargar_video(video_info, metodo='auto'):
    """
    Descarga video de YouTube
    metodo: 'auto', 'yt-dlp', 'rapidapi'
    """
    video_id = video_info['video_id']
    url = video_info['url']
    
    # Intentar yt-dlp primero (gratis)
    if metodo in ['auto', 'yt-dlp']:
        resultado = descargar_ytdlp(url, video_id)
        if resultado:
            return resultado
    
    # Fallback a RapidAPI si está configurado
    if metodo in ['auto', 'rapidapi'] and RAPIDAPI_KEY:
        resultado = descargar_rapidapi(url, video_id)
        if resultado:
            return resultado
    
    return None

def descargar_ytdlp(url, video_id):
    """Descarga usando yt-dlp (gratis, pero puede fallar en GitHub Actions)"""
    output_path = VIDEOS_DIR / f"vid_{video_id}.%(ext)s"
    
    cmd = [
        'yt-dlp',
        '--no-playlist',
        '--format', 'best[height<=720][filesize<50M]/best[filesize<50M]/worst',
        '--max-filesize', '50M',
        '--output', str(output_path),
        '--no-warnings',
        '--quiet',
        '--socket-timeout', '20',
        '--retries', '2',
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            return None
        
        # Encontrar archivo
        archivos = list(VIDEOS_DIR.glob(f"vid_{video_id}.*"))
        if archivos:
            path = archivos[0]
            if path.stat().st_size > 500000:  # Mínimo 500KB
                return str(path)
    except:
        pass
    return None

def descargar_rapidapi(url, video_id):
    """
    Descarga usando RapidAPI (más estable, requiere suscripción)
    API recomendada: "YouTube Video Downloader" o similar
    """
    if not RAPIDAPI_KEY:
        return None
    
    log("Intentando descarga vía RapidAPI...", 'info')
    
    # Ejemplo con API de descarga genérica
    # Debes suscribirte a una API de descarga en rapidapi.com
    api_url = "https://youtube-video-download-info.p.rapidapi.com/dl"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "youtube-video-download-info.p.rapidapi.com"
    }
    params = {"id": video_id}
    
    try:
        resp = requests.get(api_url, headers=headers, params=params, timeout=30)
        data = resp.json()
        
        if 'link' in data or 'url' in data:
            download_url = data.get('link') or data.get('url')
            # Descargar archivo
            video_path = VIDEOS_DIR / f"vid_{video_id}.mp4"
            r = requests.get(download_url, timeout=60)
            if r.status_code == 200:
                video_path.write_bytes(r.content)
                if video_path.stat().st_size > 500000:
                    return str(video_path)
    except Exception as e:
        log(f"Error RapidAPI: {str(e)[:50]}", 'warn')
    
    return None

# =============================================================================
# 4️⃣ CONVERTIR A REEL (9:16)
# =============================================================================

def convertir_a_reel(video_path, noticia_id):
    """
    Convierte video a formato vertical 9:16 usando ffmpeg
    Requiere: ffmpeg instalado
    """
    if not subprocess.run(['which', 'ffmpeg'], capture_output=True).returncode == 0:
        log("ffmpeg no instalado, usando video original", 'warn')
        return video_path
    
    input_path = Path(video_path)
    output_path = REELS_DIR / f"reel_{noticia_id}.mp4"
    
    # Comando ffmpeg: escalar a 1080x1920, crop centrado, sin audio si es necesario
    cmd = [
        'ffmpeg',
        '-i', str(input_path),
        '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '28',  # Calidad media-alta, tamaño reducido
        '-c:a', 'aac',
        '-b:a', '128k',
        '-movflags', '+faststart',
        '-y',  # Sobrescribir
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and output_path.exists():
            size_mb = output_path.stat().st_size / (1024*1024)
            log(f"Reel generado: {size_mb:.1f} MB", 'ok')
            return str(output_path)
    except Exception as e:
        log(f"Error ffmpeg: {str(e)[:50]}", 'error')
    
    # Si falla, retornar original
    return video_path

# =============================================================================
# 5️⃣ PUBLICAR EN FACEBOOK (Reel)
# =============================================================================

def publicar_reel(video_path, texto):
    """
    Publica como Reel en Facebook
    Nota: La API de Meta para Reels es diferente a videos normales
    """
    if not FB_ACCESS_TOKEN or not FB_PAGE_ID:
        log("Sin credenciales FB", 'error')
        return None
    
    # Para reels, usamos el endpoint de videos pero con configuración específica
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': ('reel.mp4', f, 'video/mp4')}
            data = {
                'description': texto[:2200],  # Límite reels
                'access_token': FB_ACCESS_TOKEN,
                # Parámetros específicos para formato reel/short
                'file_url': '',  # Si fuera URL remota
            }
            
            log("Subiendo reel a Facebook...", 'reel')
            resp = requests.post(url, files=files, data=data, timeout=300)
            result = resp.json()
        
        if 'id' in result:
            video_id = result['id']
            log(f"✅ Reel publicado ID: {video_id}", 'ok')
            return video_id
        else:
            error = result.get('error', {}).get('message', 'Unknown')
            log(f"Error FB: {error[:80]}", 'error')
            return None
            
    except Exception as e:
        log(f"Error publicando: {str(e)[:60]}", 'error')
        return None

def generar_texto_reel(noticia, video_titulo):
    """Genera texto optimizado para reels"""
    titulo = noticia['titulo']
    categoria = noticia['categoria']
    
    # Emojis por categoría
    emojis = {
        'guerra': '⚔️🔥',
        'politica': '🏛️📢',
        'economia': '💰📉',
        'mundo': '🌍🌐'
    }
    emoji = emojis.get(categoria, '📰')
    
    # Texto corto y impactante para reels
    texto = f"""{emoji} {titulo[:80]}{'...' if len(titulo) > 80 else ''}

🎥 {video_titulo[:60]}{'...' if len(video_titulo) > 60 else ''}

💬 ¿Qué opinas? Comenta abajo 👇

#{categoria.capitalize()} #Noticias #Actualidad #Reels #Viral"""
    
    return texto

# =============================================================================
# CONTROL Y HISTORIAL
# =============================================================================

def cargar_historial():
    return cargar_json(HISTORIAL_PATH, {
        'publicados': [],  # hashes de noticias ya usadas
        'videos': [],
        'ultima_publicacion': None
    })

def ya_publicado(historial, titulo_noticia):
    h = generar_hash(titulo_noticia)
    return h in historial.get('publicados', [])

def guardar_registro(historial, noticia, video_info, post_id):
    h = generar_hash(noticia['titulo'])
    historial['publicados'].append(h)
    historial['videos'].append({
        'noticia': noticia['titulo'][:100],
        'video_yt': video_info['titulo'],
        'video_id': video_info['video_id'],
        'post_id': post_id,
        'fecha': datetime.now().isoformat(),
        'categoria': noticia['categoria']
    })
    # Mantener últimos 100
    historial['publicados'] = historial['publicados'][-100:]
    historial['videos'] = historial['videos'][-50:]
    guardar_json(HISTORIAL_PATH, historial)

def verificar_tiempo():
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None})
    if not estado.get('ultima_publicacion'):
        return True, estado
    try:
        ultima = datetime.fromisoformat(estado['ultima_publicacion'])
        return (datetime.now() - ultima).total_seconds() / 60 >= TIEMPO_ENTRE_PUBLICACIONES, estado
    except:
        return True, estado

def limpiar_archivos():
    """Limpia videos viejos"""
    try:
        for carpeta in [VIDEOS_DIR, REELS_DIR]:
            for f in carpeta.glob('*'):
                if f.is_file() and f.stat().st_mtime < (time.time() - 86400):  # 24h
                    f.unlink()
    except:
        pass

# =============================================================================
# FLUJO PRINCIPAL
# =============================================================================

def main():
    inicio = time.time()
    
    print("\n" + "="*70)
    print("📱 BOT DE REELS - VERDAD HOY v2.0")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # 1. Verificar tiempo
    puede, estado = verificar_tiempo()
    if not puede:
        log("Esperando intervalo de 58 minutos...", 'warn')
        return True
    
    # 2. Verificar configuración mínima
    if not YOUTUBE_API_KEY:
        log("❌ YOUTUBE_API_KEY es obligatorio", 'error')
        return False
    
    # 3. Cargar historial
    historial = cargar_historial()
    log(f"Historial: {len(historial.get('videos', []))} reels publicados")
    
    # 4. Obtener noticias
    noticias = obtener_noticias_rss(max_noticias=8)
    if not noticias:
        log("No se obtuvieron noticias", 'error')
        return False
    
    # 5. Procesar noticias
    for noticia in noticias:
        if ya_publicado(historial, noticia['titulo']):
            continue
        
        log(f"\n📰 {noticia['titulo'][:60]}...")
        log(f"   Categoría: {noticia['categoria']}")
        
        # 6. Buscar video en YouTube
        video = buscar_video_youtube_api(
            noticia['titulo'], 
            noticia['categoria']
        )
        
        if not video:
            log("No se encontró video adecuado", 'warn')
            continue
        
        log(f"🎬 Video: {video['titulo'][:50]}...")
        
        # 7. Descargar video
        video_path = descargar_video(video, metodo='auto')
        if not video_path:
            log("No se pudo descargar el video", 'error')
            continue
        
        # 8. Convertir a reel (9:16)
        reel_path = convertir_a_reel(video_path, generar_hash(noticia['titulo']))
        
        # 9. Generar texto y publicar
        texto = generar_texto_reel(noticia, video['titulo'])
        post_id = publicar_reel(reel_path, texto)
        
        # 10. Limpiar y guardar
        try:
            Path(video_path).unlink(missing_ok=True)
            if reel_path != video_path:
                Path(reel_path).unlink(missing_ok=True)
        except:
            pass
        
        if post_id:
            guardar_registro(historial, noticia, video, post_id)
            estado['ultima_publicacion'] = datetime.now().isoformat()
            guardar_json(ESTADO_PATH, estado)
            limpiar_archivos()
            
            tiempo = time.time() - inicio
            print("\n" + "="*70)
            log("✅ REEL PUBLICADO EXITOSAMENTE")
            print(f"⏱️ Tiempo total: {tiempo:.0f}s")
            print(f"📱 Post ID: {post_id}")
            print(f"📰 {noticia['titulo'][:60]}")
            print("="*70)
            return True
        
        log("Falló publicación, intentando siguiente...", 'warn')
    
    log("No se pudo publicar ningún reel", 'error')
    return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

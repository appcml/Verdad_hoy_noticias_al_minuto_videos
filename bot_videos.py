#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Videos para Facebook - Verdad Hoy
Publica videos de noticias cada 1 hora
Fuentes: Reddit, RSS, Vimeo (fuentes estables)
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
# CATEGORÍAS SIMPLIFICADAS
# =============================================================================

CATEGORIAS = {
    'conflictos': {
        'palabras': ['guerra', 'conflicto', 'ataque', 'bombardeo', 'invasión', 'misil', 
                     'batalla', 'ucrania', 'rusia', 'gaza', 'palestina', 'israel', 
                     'hamás', 'siria', 'militar', 'soldados', 'dron'],
        'hashtags': '#Guerra #Conflicto #Militar'
    },
    'narcotrafico': {
        'palabras': ['narcotráfico', 'cártel', 'droga', 'cocaína', 'fentanilo', 
                     'narco', 'sicario', 'decomiso', 'sinaloa', 'jalisco', 'cjng'],
        'hashtags': '#Narcotráfico #Seguridad #CrimenOrganizado'
    },
    'politica': {
        'palabras': ['gobierno', 'presidente', 'elecciones', 'política', 'protesta', 
                     'golpe de estado', 'corrupción', 'onu', 'diplomacia'],
        'hashtags': '#Política #Internacional #Gobierno'
    },
    'desastres': {
        'palabras': ['terremoto', 'tsunami', 'huracán', 'inundación', 'incendio', 
                     'desastre', 'tragedia', 'accidente', 'víctimas'],
        'hashtags': '#Desastre #Emergencia #Tragedia'
    }
}

TODAS_PALABRAS = []
for cat in CATEGORIAS.values():
    TODAS_PALABRAS.extend(cat['palabras'])

# =============================================================================
# FUENTES ESTABLES
# =============================================================================

REDDIT_SUBREDDITS = [
    'CombatFootage', 'war', 'UkraineWarVideoReport', 
    'NarcoFootage', 'ActualPublicFreakouts', 'CatastrophicFailure'
]

RSS_FEEDS = [
    'https://feeds.bbci.co.uk/news/video_and_audio/world/rss.xml',
    'https://www.reutersagency.com/feed/?best-topics=world&format=mrss',
]

# =============================================================================
# FUNCIONES UTILIDAD
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'video': '🎬'}
    print(f"{iconos.get(tipo, 'ℹ️')} {mensaje}")

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
        log(f"Error guardando {ruta}: {e}", 'error')
        return False

def generar_hash(texto):
    return hashlib.md5(texto.lower().strip().encode()).hexdigest()

def detectar_categoria(titulo, descripcion=''):
    texto = f"{titulo} {descripcion}".lower()
    puntuaciones = {}
    for nombre, datos in CATEGORIAS.items():
        score = sum(1 for palabra in datos['palabras'] if palabra in texto)
        puntuaciones[nombre] = score
    return max(puntuaciones, key=puntuaciones.get) if max(puntuaciones.values()) > 0 else 'conflictos'

def obtener_hashtags(categoria):
    return CATEGORIAS.get(categoria, {}).get('hashtags', '#Noticias #Actualidad')

# =============================================================================
# HISTORIAL Y ESTADO
# =============================================================================

def cargar_historial():
    default = {'urls': [], 'titulos': [], 'hashes': [], 'videos': []}
    historial = cargar_json(HISTORIAL_PATH, default)
    log(f"Historial: {len(historial.get('videos', []))} videos")
    return historial

def guardar_historial(historial, url, titulo, fuente):
    url_hash = generar_hash(url)
    historial.setdefault('urls', []).append(url)
    historial.setdefault('titulos', []).append(titulo[:100])
    historial.setdefault('hashes', []).append(url_hash)
    historial.setdefault('videos', []).append({
        'url': url, 'titulo': titulo[:100], 'fecha': datetime.now().isoformat(), 'fuente': fuente
    })
    # Mantener solo últimos 100
    for key in ['urls', 'titulos', 'hashes']:
        historial[key] = historial[key][-100:]
    historial['videos'] = historial['videos'][-100:]
    guardar_json(HISTORIAL_PATH, historial)

def ya_publicado(historial, url, titulo):
    if generar_hash(url) in historial.get('hashes', []):
        return True
    if url in historial.get('urls', []):
        return True
    titulo_simple = re.sub(r'[^\w]', '', titulo.lower())[:30]
    for t in historial.get('titulos', []):
        if re.sub(r'[^\w]', '', t.lower())[:30] == titulo_simple:
            return True
    return False

def verificar_tiempo():
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None})
    if not estado.get('ultima_publicacion'):
        return True, estado
    try:
        ultima = datetime.fromisoformat(estado['ultima_publicacion'])
        transcurrido = (datetime.now() - ultima).total_seconds() / 60
        if transcurrido < TIEMPO_ENTRE_PUBLICACIONES:
            log(f"Esperando {TIEMPO_ENTRE_PUBLICACIONES - transcurrido:.0f} minutos", 'advertencia')
            return False, estado
    except:
        pass
    return True, estado

# =============================================================================
# BÚSQUEDA DE VIDEOS
# =============================================================================

def buscar_reddit():
    videos = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for subreddit in random.sample(REDDIT_SUBREDDITS, min(3, len(REDDIT_SUBREDDITS))):
        try:
            time.sleep(2)  # Evitar rate limit
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=10"
            resp = requests.get(url, headers=headers, timeout=15)
            
            if resp.status_code != 200:
                continue
                
            data = resp.json()
            if 'data' not in data or 'children' not in data['data']:
                continue
                
            for post in data['data']['children']:
                post_data = post['data']
                
                # Solo videos
                if not post_data.get('is_video') and 'v.redd.it' not in post_data.get('url', ''):
                    continue
                
                titulo = post_data.get('title', '')
                if not any(p in titulo.lower() for p in TODAS_PALABRAS):
                    continue
                
                permalink = post_data.get('permalink', '')
                videos.append({
                    'titulo': titulo,
                    'url': f"https://www.reddit.com{permalink}",
                    'fuente': f'Reddit/r/{subreddit}',
                    'tipo': 'reddit',
                    'categoria': detectar_categoria(titulo)
                })
        except Exception as e:
            log(f"Error Reddit {subreddit}: {str(e)[:50]}", 'advertencia')
    
    log(f"Reddit: {len(videos)} videos", 'video')
    return videos

def buscar_rss():
    videos = []
    
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            fuente = feed.feed.get('title', 'RSS')
            
            for entry in feed.entries[:5]:
                titulo = entry.get('title', '')
                if not titulo:
                    continue
                
                # Buscar media content
                video_url = None
                if hasattr(entry, 'media_content'):
                    for media in entry.media_content:
                        url = media.get('url', '')
                        if any(ext in url.lower() for ext in ['.mp4', '.m3u8']):
                            video_url = url
                            break
                
                if video_url and any(p in titulo.lower() for p in TODAS_PALABRAS):
                    videos.append({
                        'titulo': titulo,
                        'url': video_url,
                        'fuente': fuente,
                        'tipo': 'rss',
                        'categoria': detectar_categoria(titulo)
                    })
        except Exception as e:
            log(f"Error RSS: {str(e)[:50]}", 'advertencia')
    
    log(f"RSS: {len(videos)} videos", 'video')
    return videos

def buscar_newsapi():
    videos = []
    if not NEWS_API_KEY:
        return videos
    
    try:
        # Buscar noticias recientes
        resp = requests.get(
            "https://newsapi.org/v2/top-headlines",
            params={'category': 'general', 'language': 'en', 'pageSize': 20, 'apiKey': NEWS_API_KEY},
            timeout=15
        )
        data = resp.json()
        
        if data.get('status') == 'ok':
            for art in data.get('articles', []):
                titulo = art.get('title', '')
                if '[Removed]' in titulo:
                    continue
                
                # Solo si es relevante
                if any(p in titulo.lower() for p in TODAS_PALABRAS):
                    # Intentar obtener URL de video (si existe)
                    url = art.get('url', '')
                    # Aquí podrías hacer scraping de la página para encontrar video
                    # Por ahora solo lo usamos como fallback
                    videos.append({
                        'titulo': titulo,
                        'url': url,
                        'fuente': art.get('source', {}).get('name', 'NewsAPI'),
                        'tipo': 'newsapi',
                        'categoria': detectar_categoria(titulo)
                    })
    except Exception as e:
        log(f"Error NewsAPI: {str(e)[:50]}", 'advertencia')
    
    log(f"NewsAPI: {len(videos)} noticias", 'video')
    return videos

def buscar_todos():
    log("Buscando videos...", 'video')
    videos = []
    videos.extend(buscar_reddit())
    if len(videos) < 3:
        videos.extend(buscar_rss())
    if len(videos) < 3:
        videos.extend(buscar_newsapi())
    
    # Eliminar duplicados
    urls_vistas = set()
    unicos = []
    for v in videos:
        if v['url'] not in urls_vistas:
            urls_vistas.add(v['url'])
            unicos.append(v)
    
    log(f"Total únicos: {len(unicos)}", 'exito')
    return unicos

# =============================================================================
# DESCARGA Y PUBLICACIÓN
# =============================================================================

def descargar_video(url, tipo):
    log(f"Descargando {tipo}: {url[:60]}...", 'video')
    
    try:
        # Configuración simplificada - formato más flexible
        ydl_opts = {
            'format': 'best[filesize<50M]/best[height<=480]/best',
            'outtmpl': '/tmp/video_%(id)s.%(ext)s',
            'max_filesize': 50000000,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if not info:
                return None
            
            video_path = ydl.prepare_filename(info)
            
            # Buscar archivo si cambió extensión
            if not os.path.exists(video_path):
                base = os.path.splitext(video_path)[0]
                for ext in ['.mp4', '.mkv', '.webm']:
                    if os.path.exists(base + ext):
                        video_path = base + ext
                        break
            
            if os.path.exists(video_path) and os.path.getsize(video_path) > 100000:
                size_mb = os.path.getsize(video_path) / 1024 / 1024
                log(f"Descargado: {size_mb:.1f}MB", 'exito')
                return video_path
            
            return None
            
    except Exception as e:
        error = str(e).lower()
        if "format" in error:
            log("Formato no disponible, probando con otro...", 'advertencia')
            # Intentar con cualquier formato disponible
            try:
                ydl_opts['format'] = 'worst/best'
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    video_path = ydl.prepare_filename(info)
                    if os.path.exists(video_path):
                        return video_path
            except:
                pass
        else:
            log(f"Error: {str(e)[:80]}", 'error')
        return None

def verificar_video(path):
    if not os.path.exists(path):
        return False
    if os.path.getsize(path) < 100000:
        return False
    return True

def publicar_facebook(titulo, descripcion, video_path, categoria):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Sin credenciales Facebook", 'error')
        return False
    
    hashtags = obtener_hashtags(categoria)
    mensaje = f"🎬 {titulo}\n\n{descripcion[:150]}{'...' if len(descripcion) > 150 else ''}\n\n{hashtags} #Video #Noticias\n\n— Verdad Hoy"
    
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
        
        with open(video_path, 'rb') as f:
            resp = requests.post(
                url,
                files={'file': f},
                data={'description': mensaje[:1990], 'access_token': FB_ACCESS_TOKEN},
                timeout=300
            )
        
        result = resp.json()
        
        if 'id' in result:
            log(f"✅ Publicado: {result['id']}", 'exito')
            return True
        else:
            log(f"Error FB: {result.get('error', {}).get('message', 'Unknown')}", 'error')
            return False
            
    except Exception as e:
        log(f"Error publicando: {e}", 'error')
        return False

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*60)
    print("🎬 BOT DE VIDEOS - VERDAD HOY")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    puede_proceder, estado = verificar_tiempo()
    if not puede_proceder:
        return True
    
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales", 'error')
        return False
    
    historial = cargar_historial()
    videos = buscar_todos()
    
    if not videos:
        log("No se encontraron videos", 'error')
        return False
    
    # Filtrar publicados
    videos = [v for v in videos if not ya_publicado(historial, v['url'], v['titulo'])]
    log(f"Nuevos: {len(videos)}")
    
    if not videos:
        log("No hay videos nuevos", 'advertencia')
        return False
    
    # Intentar publicar
    for intento, video in enumerate(videos[:5]):
        log(f"\nIntento {intento+1}: {video['titulo'][:50]}...")
        
        video_path = descargar_video(video['url'], video['tipo'])
        
        if not video_path:
            continue
        
        if not verificar_video(video_path):
            log("Video inválido", 'advertencia')
            os.remove(video_path) if os.path.exists(video_path) else None
            continue
        
        exito = publicar_facebook(
            video['titulo'],
            video.get('descripcion', ''),
            video_path,
            video['categoria']
        )
        
        # Limpiar
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
        except:
            pass
        
        if exito:
            guardar_historial(historial, video['url'], video['titulo'], video['fuente'])
            estado['ultima_publicacion'] = datetime.now().isoformat()
            guardar_json(ESTADO_PATH, estado)
            
            print("\n" + "="*60)
            log("✅ VIDEO PUBLICADO", 'exito')
            print(f"🎬 {video['titulo'][:60]}")
            print(f"🏢 {video['fuente']}")
            print("="*60)
            return True
    
    log("Todos los intentos fallaron", 'error')
    return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        exit(1)

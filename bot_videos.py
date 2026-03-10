#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Videos para Facebook - Verdad Hoy
Versión ULTRA SIMPLIFICADA - Usa yt-dlp para búsqueda y descarga directa
Fuentes: Reddit (con yt-dlp), Rumble (con yt-dlp), Búsquedas directas
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
# CATEGORÍAS
# =============================================================================

CATEGORIAS = {
    'conflictos': {
        'palabras': ['war', 'conflict', 'attack', 'military', 'combat', 'explosion', 
                     'ukraine', 'gaza', 'israel', 'palestine', 'syria', 'russia', 
                     'soldier', 'drone', 'missile', 'bombing', 'fighting'],
        'hashtags': '#Guerra #Conflicto #Militar #Urgente'
    },
    'narcotrafico': {
        'palabras': ['cartel', 'narco', 'drug', 'cocaine', 'fentanyl', 'mexico', 
                     'sicario', 'shooting', 'police', 'raid', 'seizure'],
        'hashtags': '#Narcotráfico #Seguridad #CrimenOrganizado'
    },
    'politica': {
        'palabras': ['protest', 'election', 'government', 'president', 'political', 
                     'riot', 'coup', 'corruption', 'sanctions'],
        'hashtags': '#Política #Internacional #Gobierno'
    },
    'desastres': {
        'palabras': ['earthquake', 'tsunami', 'hurricane', 'flood', 'fire', 
                     'disaster', 'accident', 'crash', 'emergency'],
        'hashtags': '#Desastre #Emergencia #Tragedia'
    }
}

TODAS_PALABRAS = []
for cat in CATEGORIAS.values():
    TODAS_PALABRAS.extend(cat['palabras'])

# =============================================================================
# UTILIDADES
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'video': '🎬'}
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
    except:
        return False

def generar_hash(texto):
    return hashlib.md5(texto.lower().strip().encode()).hexdigest()

def detectar_categoria(titulo):
    texto = titulo.lower()
    puntuaciones = {}
    for nombre, datos in CATEGORIAS.items():
        score = sum(1 for palabra in datos['palabras'] if palabra in texto)
        puntuaciones[nombre] = score
    mejor = max(puntuaciones, key=puntuaciones.get)
    return mejor if puntuaciones[mejor] > 0 else 'conflictos'

def obtener_hashtags(categoria):
    return CATEGORIAS.get(categoria, {}).get('hashtags', '#Noticias #Actualidad')

# =============================================================================
# HISTORIAL
# =============================================================================

def cargar_historial():
    default = {'urls': [], 'titulos': [], 'hashes': [], 'videos': []}
    return cargar_json(HISTORIAL_PATH, default)

def guardar_historial(historial, url, titulo, fuente):
    url_hash = generar_hash(url)
    historial.setdefault('urls', []).append(url)
    historial.setdefault('titulos', []).append(titulo[:100])
    historial.setdefault('hashes', []).append(url_hash)
    historial.setdefault('videos', []).append({
        'url': url, 'titulo': titulo[:100], 
        'fecha': datetime.now().isoformat(), 'fuente': fuente
    })
    for key in ['urls', 'titulos', 'hashes']:
        historial[key] = historial[key][-100:]
    historial['videos'] = historial['videos'][-100:]
    guardar_json(HISTORIAL_PATH, historial)

def ya_publicado(historial, url, titulo):
    if generar_hash(url) in historial.get('hashes', []):
        return True
    if url in historial.get('urls', []):
        return True
    titulo_simple = re.sub(r'[^\w]', '', titulo.lower())[:20]
    for t in historial.get('titulos', []):
        if re.sub(r'[^\w]', '', t.lower())[:20] == titulo_simple:
            return True
    return False

def verificar_tiempo():
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None})
    if not estado.get('ultima_publicacion'):
        return True, estado
    try:
        ultima = datetime.fromisoformat(estado['ultima_publicacion'])
        if (datetime.now() - ultima).total_seconds() / 60 < TIEMPO_ENTRE_PUBLICACIONES:
            return False, estado
    except:
        pass
    return True, estado

# =============================================================================
# BÚSQUEDA DE VIDEOS - SOLO MÉTODOS QUE FUNCIONAN
# =============================================================================

def buscar_reddit_ytdlp():
    """
    Busca videos en Reddit usando yt-dlp directamente
    Esto es más confiable que hacer scraping manual
    """
    videos = []
    
    subreddits = [
        'CombatFootage', 'war', 'UkraineWarVideoReport', 
        'NarcoFootage', 'CatastrophicFailure', 'PublicFreakout'
    ]
    
    for subreddit in random.sample(subreddits, min(4, len(subreddits))):
        try:
            log(f"Buscando en r/{subreddit}...", 'buscar')
            
            # Usar yt-dlp para listar videos del subreddit
            url = f"https://www.reddit.com/r/ {subreddit}/hot.json"
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'playlistend': 15,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=False)
                
                if result and 'entries' in result:
                    for entry in result['entries']:
                        if not entry:
                            continue
                        
                        titulo = entry.get('title', '')
                        video_url = entry.get('url', '')
                        
                        # Filtrar solo videos
                        if not any(x in video_url for x in ['v.redd.it', 'reddit.com']):
                            continue
                        
                        if len(titulo) < 10:
                            continue
                        
                        # Verificar relevancia
                        if any(p in titulo.lower() for p in TODAS_PALABRAS):
                            videos.append({
                                'titulo': titulo[:200],
                                'url': video_url,
                                'fuente': f'Reddit/r/{subreddit}',
                                'tipo': 'reddit',
                                'categoria': detectar_categoria(titulo)
                            })
                            
        except Exception as e:
            log(f"Error r/{subreddit}: {str(e)[:60]}", 'advertencia')
    
    log(f"Reddit: {len(videos)} videos", 'exito')
    return videos

def buscar_rumble_ytdlp():
    """
    Busca videos en canales de Rumble usando yt-dlp
    """
    videos = []
    
    canales = ['RT', 'AlJazeeraEnglish', 'Reuters', 'France24']
    
    for canal in random.sample(canales, min(3, len(canales))):
        try:
            log(f"Buscando en Rumble/{canal}...", 'buscar')
            
            url = f"https://rumble.com/c/ {canal}"
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'playlistend': 10,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=False)
                
                if result and 'entries' in result:
                    for entry in result['entries']:
                        if not entry:
                            continue
                        
                        titulo = entry.get('title', '')
                        video_url = entry.get('url', '')
                        
                        if any(p in titulo.lower() for p in TODAS_PALABRAS):
                            videos.append({
                                'titulo': titulo[:200],
                                'url': video_url,
                                'fuente': f'Rumble/{canal}',
                                'tipo': 'rumble',
                                'categoria': detectar_categoria(titulo)
                            })
                            
        except Exception as e:
            log(f"Error Rumble {canal}: {str(e)[:60]}", 'advertencia')
    
    log(f"Rumble: {len(videos)} videos", 'exito')
    return videos

def buscar_youtube_alternativo():
    """
    Busca videos en YouTube usando términos de búsqueda
    yt-dlp puede buscar directamente en YouTube sin API key
    """
    videos = []
    
    # Términos de búsqueda en inglés (más resultados)
    terminos = [
        'war footage 2024', 'military combat video', 'ukraine war video',
        'gaza conflict footage', 'police shootout', 'cartel mexico video',
        'breaking news video', 'drone footage war'
    ]
    
    termino = random.choice(terminos)
    
    try:
        log(f"Buscando en YouTube: '{termino}'...", 'buscar')
        
        # yt-dlp puede buscar directamente: ytsearch10:query
        search_url = f"ytsearch10: {termino}"
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(search_url, download=False)
            
            if result and 'entries' in result:
                for entry in result['entries']:
                    if not entry:
                        continue
                    
                    titulo = entry.get('title', '')
                    video_url = entry.get('url', '')
                    duration = entry.get('duration', 0)
                    
                    # Filtrar videos cortos (30s - 5min)
                    if duration < 30 or duration > 300:
                        continue
                    
                    if any(p in titulo.lower() for p in TODAS_PALABRAS):
                        videos.append({
                            'titulo': titulo[:200],
                            'url': video_url,
                            'fuente': 'YouTube/Search',
                            'tipo': 'youtube',
                            'categoria': detectar_categoria(titulo)
                        })
                        
    except Exception as e:
        log(f"Error YouTube: {str(e)[:60]}", 'advertencia')
    
    log(f"YouTube: {len(videos)} videos", 'exito')
    return videos

def buscar_todos():
    """Busca en todas las fuentes disponibles"""
    log("Iniciando búsqueda...", 'video')
    todos = []
    
    # Fuente 1: Reddit (más confiable)
    reddit = buscar_reddit_ytdlp()
    todos.extend(reddit)
    
    # Si Reddit no dio resultados, probar Rumble
    if len(todos) < 3:
        rumble = buscar_rumble_ytdlp()
        todos.extend(rumble)
    
    # Si aún faltan, probar YouTube
    if len(todos) < 3:
        youtube = buscar_youtube_alternativo()
        todos.extend(youtube)
    
    # Eliminar duplicados
    urls = set()
    unicos = []
    for v in todos:
        if v['url'] not in urls:
            urls.add(v['url'])
            unicos.append(v)
    
    log(f"Total únicos: {len(unicos)}", 'exito')
    return unicos

# =============================================================================
# DESCARGA DE VIDEO
# =============================================================================

def descargar_video(url, tipo):
    """Descarga video usando yt-dlp con múltiples estrategias"""
    log(f"Descargando [{tipo}]...", 'video')
    
    # Estrategia 1: Configuración estándar
    video_path = _descargar_intento(url, {
        'format': 'best[height<=720][filesize<80M]/best[filesize<80M]',
        'outtmpl': '/tmp/video_%(id)s.%(ext)s',
        'max_filesize': 80000000,
    })
    
    if video_path:
        return video_path
    
    # Estrategia 2: Más permisiva
    log("Reintentando...", 'advertencia')
    video_path = _descargar_intento(url, {
        'format': 'worst[filesize<100M]/best[filesize<100M]',
        'outtmpl': '/tmp/video_fallback_%(id)s.%(ext)s',
        'max_filesize': 100000000,
    })
    
    return video_path

def _descargar_intento(url, opts):
    """Intento de descarga con opciones específicas"""
    try:
        ydl_opts = {
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            **opts
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
            
            if os.path.exists(video_path) and os.path.getsize(video_path) > 500000:
                size_mb = os.path.getsize(video_path) / 1024 / 1024
                log(f"Descargado: {size_mb:.1f} MB", 'exito')
                return video_path
            
            return None
            
    except Exception as e:
        log(f"Error: {str(e)[:80]}", 'advertencia')
        return None

# =============================================================================
# PUBLICACIÓN
# =============================================================================

def publicar_facebook(titulo, descripcion, video_path, categoria):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Sin credenciales FB", 'error')
        return False
    
    if not os.path.exists(video_path):
        return False
    
    hashtags = obtener_hashtags(categoria)
    mensaje = f"🎬 {titulo}\n\n{descripcion[:150]}{'...' if len(descripcion) > 150 else ''}\n\n{hashtags} #Video #Noticias\n\n— Verdad Hoy"
    
    try:
        url = f"https://graph.facebook.com/v18.0/ {FB_PAGE_ID}/videos"
        
        with open(video_path, 'rb') as f:
            resp = requests.post(
                url,
                files={'file': ('video.mp4', f, 'video/mp4')},
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
        log(f"Error: {e}", 'error')
        return False

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*60)
    print("🎬 BOT DE VIDEOS - VERDAD HOY")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    puede, estado = verificar_tiempo()
    if not puede:
        log("Esperando intervalo...", 'advertencia')
        return True
    
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Faltan credenciales", 'error')
        return False
    
    historial = cargar_historial()
    log(f"Historial: {len(historial.get('videos', []))} videos")
    
    # Buscar videos
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
    for intento, video in enumerate(videos[:3], 1):
        log(f"\nIntento {intento}: {video['titulo'][:50]}...")
        
        video_path = descargar_video(video['url'], video['tipo'])
        
        if not video_path:
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

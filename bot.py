#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias Video para Facebook - V2.7
Correcciones: Cookies para YouTube y manejo de errores Facebook
"""

import os
import sys
import re
import hashlib
import json
import tempfile
import subprocess
import random
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    print("❌ ERROR: pip install requests")
    sys.exit(1)

try:
    import feedparser
    FEEDPARSER_OK = True
except ImportError:
    FEEDPARSER_OK = False

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_publicaciones.json')

# User agents rotativos para evitar detección
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0',
]

def get_random_ua():
    return random.choice(USER_AGENTS)

def log(msg, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍'}
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {iconos.get(tipo, 'ℹ️')} {msg}")

def cargar_json(ruta, default=None):
    default = default or {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                return json.loads(f.read().strip()) or default.copy()
        except:
            pass
    return default.copy()

def guardar_json(ruta, datos):
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"Error guardando: {e}", 'error')
        return False

# =============================================================================
# PALABRAS CLAVE
# =============================================================================

KEYWORDS = {
    'war': 10, 'guerra': 10, 'conflict': 10, 'conflicto': 10,
    'ukraine': 10, 'ucrania': 10, 'gaza': 10, 'israel': 10,
    'iran': 10, 'trump': 10, 'biden': 10, 'putin': 10,
    'missile': 10, 'misil': 10, 'attack': 10, 'ataque': 10,
    'live': 5, 'breaking': 8, 'urgent': 8, 'alert': 8,
}

def calcular_puntaje(titulo):
    t = titulo.lower()
    return sum(v for p, v in KEYWORDS.items() if p in t)

# =============================================================================
# BÚSQUEDA DE VIDEOS
# =============================================================================

def buscar_youtube():
    if not YOUTUBE_API_KEY:
        log("YOUTUBE_API_KEY no configurado", 'advertencia')
        return []
    
    videos = []
    queries = [
        'breaking news international live',
        'world news today',
        'war news live',
        'israel iran conflict news'
    ]
    
    for query in queries:
        try:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'eventType': 'live',  # 🆕 Buscar solo streams en vivo
                'maxResults': 10,
                'key': YOUTUBE_API_KEY,
            }
            
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            
            if 'error' in data:
                log(f"YouTube API Error: {data['error'].get('message', 'Unknown')}", 'error')
                continue
            
            for item in data.get('items', []):
                vid = item['id'].get('videoId')
                if not vid:
                    continue
                
                snip = item['snippet']
                titulo = snip.get('title', '')
                puntaje = calcular_puntaje(titulo)
                
                # Incluir videos con buen puntaje o en vivo
                if puntaje >= 3 or 'live' in titulo.lower():
                    videos.append({
                        'titulo': titulo,
                        'url': f"https://youtube.com/watch?v={vid}",
                        'video_id': vid,
                        'thumbnail': snip.get('thumbnails', {}).get('high', {}).get('url', ''),
                        'puntaje': puntaje + (10 if 'live' in titulo.lower() else 0),
                        'fuente': f"YouTube:{snip.get('channelTitle', 'Unknown')}",
                        'es_live': 'live' in titulo.lower()
                    })
                    
        except Exception as e:
            log(f"Error YouTube: {e}", 'error')
    
    # Eliminar duplicados por video_id
    vistos = set()
    unicos = []
    for v in videos:
        if v['video_id'] not in vistos:
            vistos.add(v['video_id'])
            unicos.append(v)
    
    log(f"YouTube: {len(unicos)} videos (después de filtrar)", 'info')
    return unicos

def buscar_rss():
    if not FEEDPARSER_OK:
        return []
    
    videos = []
    feeds = [
        'https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA',  # BBC
        'https://www.youtube.com/feeds/videos.xml?channel_id=UCzUV528KlngtCTr2gBCiNbQ',  # CNN
    ]
    
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            canal = feed.feed.get('title', 'Unknown')
            
            for entry in feed.entries[:3]:
                titulo = entry.get('title', '')
                link = entry.get('link', '')
                
                vid = None
                if 'v=' in link:
                    vid = link.split('v=')[1].split('&')[0]
                elif 'youtu.be/' in link:
                    vid = link.split('youtu.be/')[1].split('?')[0]
                
                if vid and calcular_puntaje(titulo) >= 5:
                    videos.append({
                        'titulo': titulo,
                        'url': link,
                        'video_id': vid,
                        'puntaje': calcular_puntaje(titulo),
                        'fuente': f"RSS:{canal}",
                        'thumbnail': f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
                    })
        except Exception as e:
            log(f"Error RSS: {e}", 'debug')
    
    log(f"RSS: {len(videos)} videos", 'info')
    return videos

# =============================================================================
# DESCARGA CON MÚLTIPLES ESTRATEGIAS Y HEADERS ROTATIVOS
# =============================================================================

def descargar_thumbnail(vid, url=None):
    """Descarga thumbnail"""
    urls = []
    if url:
        urls.append(url)
    urls.extend([
        f'https://img.youtube.com/vi/{vid}/maxresdefault.jpg',
        f'https://img.youtube.com/vi/{vid}/hqdefault.jpg',
    ])
    
    for u in urls:
        try:
            headers = {'User-Agent': get_random_ua()}
            r = requests.get(u, headers=headers, timeout=10)
            if r.status_code == 200 and len(r.content) > 1000:
                path = f'/tmp/thumb_{vid}.jpg'
                with open(path, 'wb') as f:
                    f.write(r.content)
                return path
        except:
            pass
    return None

def descargar_video_yt_dlp(url, vid):
    """
    🆕 CORREGIDO: Usar cookies y headers para evitar "Sign in to confirm you're not a bot"
    """
    try:
        # Verificar yt-dlp existe
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, timeout=5)
        if result.returncode != 0:
            return None, None
        
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"{vid}.mp4")
        
        # 🆕 NUEVO: Opciones para evitar detección de bot
        cmd = [
            'yt-dlp',
            '--user-agent', get_random_ua(),
            '--add-header', 'Accept-Language:en-US,en;q=0.9',
            '--add-header', 'Accept:text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            # Formatos que no requieren verificación
            '-f', 'best[height<=480][filesize<30M]/best[height<=360][filesize<20M]/worst[filesize<10M]',
            '-o', output_path,
            '--no-playlist',
            '--quiet',
            '--no-warnings',
            '--no-check-certificates',
            '--geo-bypass',
            '--extractor-args', 'youtube:player_skip=webpage,configs,js',  # 🆕 Saltar verificaciones
            '--extractor-args', 'youtube:player_client=android',  # 🆕 Usar cliente Android (menos restricciones)
            url
        ]
        
        log(f"   ⬇️ Intentando yt-dlp (con bypass)...", 'info')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0 and os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            log(f"   ✅ yt-dlp: {size:.1f}MB", 'exito')
            return output_path, 'yt-dlp'
        
        # Si falló, mostrar error
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        log(f"   ❌ yt-dlp: {error_msg[:150]}", 'debug')
        
        # Limpiar
        try:
            os.rmdir(temp_dir)
        except:
            pass
            
    except Exception as e:
        log(f"   ❌ yt-dlp excepción: {e}", 'debug')
    
    return None, None

def descargar_video_pytube_fixed(url, vid):
    """
    🆕 CORREGIDO: pytube con headers personalizados
    """
    try:
        from pytube import YouTube
        from pytube.innertube import _default_clients
        
        # 🆕 Parchear headers de pytube
        _default_clients['ANDROID']['context']['client']['clientVersion'] = '19.08.35'
        
        temp_dir = tempfile.mkdtemp()
        
        log(f"   ⬇️ Intentando pytube (fix)...", 'info')
        
        # Crear YouTube con headers personalizados
        yt = YouTube(
            url,
            use_oauth=False,
            allow_oauth_cache=False,
            on_progress_callback=None,
        )
        
        # Intentar obtener stream con menor calidad (más probable que funcione)
        stream = None
        try:
            # Primero intentar 360p
            stream = yt.streams.filter(
                progressive=True, 
                file_extension='mp4',
                res='360p'
            ).first()
        except:
            pass
        
        if not stream:
            try:
                stream = yt.streams.filter(
                    progressive=True,
                    file_extension='mp4'
                ).order_by('resolution').asc().first()  # 🆕 Menor resolución primero
            except:
                pass
        
        if stream:
            log(f"   📦 Stream encontrado: {stream.resolution}", 'debug')
            downloaded = stream.download(output_path=temp_dir, filename=vid)
            
            if os.path.exists(downloaded) and os.path.getsize(downloaded) > 10000:
                size = os.path.getsize(downloaded) / (1024*1024)
                log(f"   ✅ pytube: {size:.1f}MB", 'exito')
                return downloaded, 'pytube'
        
        try:
            os.rmdir(temp_dir)
        except:
            pass
            
    except Exception as e:
        log(f"   ❌ pytube error: {str(e)[:100]}", 'debug')
    
    return None, None

def descargar_video(url, vid):
    """Intenta múltiples estrategias"""
    # Estrategia 1: yt-dlp con bypass
    path, metodo = descargar_video_yt_dlp(url, vid)
    if path:
        return path, metodo
    
    # Estrategia 2: pytube fix
    path, metodo = descargar_video_pytube_fixed(url, vid)
    if path:
        return path, metodo
    
    # 🆕 Estrategia 3: Intentar con you-get (si está instalado)
    try:
        temp_dir = tempfile.mkdtemp()
        out = os.path.join(temp_dir, f"{vid}.mp4")
        cmd = ['you-get', '-o', temp_dir, '-O', vid, url]
        result = subprocess.run(cmd, capture_output=True, timeout=180)
        if result.returncode == 0 and os.path.exists(out):
            return out, 'you-get'
    except:
        pass
    
    return None, None

# =============================================================================
# PUBLICACIÓN FACEBOOK - CON MANEJO MEJORADO DE ERRORES
# =============================================================================

def verificar_token_facebook():
    """
    🆕 NUEVO: Verifica que el token sea válido antes de publicar
    """
    if not FB_ACCESS_TOKEN:
        return False, "FB_ACCESS_TOKEN no configurado"
    
    try:
        # Verificar token
        url = "https://graph.facebook.com/v18.0/me"
        params = {'access_token': FB_ACCESS_TOKEN, 'fields': 'id,name'}
        r = requests.get(url, params=params, timeout=10)
        result = r.json()
        
        if r.status_code == 200:
            log(f"   ✅ Token válido: {result.get('name', 'Unknown')}", 'exito')
            return True, None
        
        error = result.get('error', {})
        code = error.get('code', 'N/A')
        msg = error.get('message', 'Unknown error')
        
        if code == 190:
            return False, "Token expirado o aplicación eliminada. Crea nuevo token en https://developers.facebook.com/tools/explorer/"
        elif code == 200:
            return False, "Permisos insuficientes. Necesitas: pages_manage_posts"
        else:
            return False, f"Error {code}: {msg}"
            
    except Exception as e:
        return False, f"Error verificando token: {e}"

def publicar_enlace(titulo, desc, url_video, hashtags, thumb=None):
    """Publica enlace en Facebook"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales FB", 'error')
        return False
    
    # 🆕 Verificar token primero
    token_ok, error_msg = verificar_token_facebook()
    if not token_ok:
        log(f"❌ {error_msg}", 'error')
        return False
    
    msg = f"📰 {titulo}\n\n{desc}\n\n🔗 Ver video: {url_video}\n\n{hashtags}\n\n— 🌐 Verdad Hoy"
    
    log(f"   📤 Publicando enlace...", 'info')
    
    try:
        # Intentar con thumbnail primero
        if thumb and os.path.exists(thumb):
            log(f"   🖼️ Con thumbnail", 'debug')
            url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
            
            with open(thumb, 'rb') as f:
                files = {'file': ('thumb.jpg', f, 'image/jpeg')}
                data = {
                    'message': msg,
                    'access_token': FB_ACCESS_TOKEN,
                    'published': 'true'
                }
                r = requests.post(url, files=files, data=data, timeout=60)
        else:
            log(f"   🔗 Sin thumbnail", 'debug')
            url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed"
            data = {
                'message': msg,
                'link': url_video,
                'access_token': FB_ACCESS_TOKEN,
                'published': 'true'
            }
            r = requests.post(url, data=data, timeout=60)
        
        result = r.json()
        
        if r.status_code == 200 and 'id' in result:
            log(f"✅ Publicado: {result['id']}", 'exito')
            return True
        else:
            error = result.get('error', {})
            log(f"❌ Facebook Error {error.get('code', 'N/A')}: {error.get('message', 'Unknown')}", 'error')
            return False
            
    except Exception as e:
        log(f"❌ Error: {e}", 'error')
        return False

def publicar_video_nativo(titulo, desc, path, hashtags):
    """Publica video nativo"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        return False
    
    token_ok, error_msg = verificar_token_facebook()
    if not token_ok:
        log(f"❌ {error_msg}", 'error')
        return False
    
    msg = f"📰 {titulo}\n\n{desc}\n\n{hashtags}\n\n— 🌐 Verdad Hoy"
    
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
        
        with open(path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {
                'description': msg,
                'access_token': FB_ACCESS_TOKEN,
                'published': 'true'
            }
            r = requests.post(url, files=files, data=data, timeout=300)
        
        result = r.json()
        
        if r.status_code == 200 and 'id' in result:
            log(f"✅ Video publicado: {result['id']}", 'exito')
            return True
        else:
            log(f"❌ Error: {result.get('error', {}).get('message', 'Unknown')}", 'error')
            return False
            
    except Exception as e:
        log(f"❌ Error: {e}", 'error')
        return False

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*60)
    print("🎥 BOT NOTICIAS VIDEO V2.7")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    if not FB_PAGE_ID:
        log("❌ FB_PAGE_ID no configurado", 'error')
        return False
    
    # Verificar token al inicio
    token_ok, msg = verificar_token_facebook()
    if not token_ok:
        log(f"❌ {msg}", 'error')
        log("   Pasos para solucionar:", 'info')
        log("   1. Ve a https://developers.facebook.com/tools/explorer/", 'info')
        log("   2. Selecciona tu app (o crea una nueva)", 'info')
        log("   3. Genera token con permisos: pages_manage_posts, pages_read_engagement", 'info')
        log("   4. Copia el token a los secrets de GitHub como FB_ACCESS_TOKEN", 'info')
        return False
    
    # Cargar historial
    historial = cargar_json(HISTORIAL_PATH, {'urls': [], 'hashes': []})
    log(f"📊 Historial: {len(historial.get('urls', []))} items")
    
    # Buscar videos
    videos = buscar_youtube() + buscar_rss()
    log(f"🎥 Total: {len(videos)} videos")
    
    if not videos:
        log("ERROR: No hay videos", 'error')
        return False
    
    # Ordenar por puntaje
    videos.sort(key=lambda x: x.get('puntaje', 0), reverse=True)
    
    # Debug
    log("📋 Top videos:", 'debug')
    for i, v in enumerate(videos[:5]):
        live_tag = " [LIVE]" if v.get('es_live') else ""
        log(f"   {i+1}. [P{v.get('puntaje', 0)}]{live_tag} {v['titulo'][:50]}...", 'debug')
    
    # Seleccionar no publicado
    seleccionado = None
    for v in videos:
        url_base = v['url'].split('?')[0]
        historial_urls = [u.split('?')[0] for u in historial.get('urls', [])]
        if url_base not in historial_urls:
            seleccionado = v
            break
    
    if not seleccionado:
        log("⚠️ Sin videos nuevos, usando mejor disponible", 'advertencia')
        seleccionado = videos[0]
    
    log(f"\n🎬 Seleccionado (P{seleccionado['puntaje']}): {seleccionado['titulo'][:60]}...")
    
    # Descargas
    vid_id = seleccionado['video_id']
    
    log(f"   📥 Thumbnail...", 'info')
    thumb = descargar_thumbnail(vid_id, seleccionado.get('thumbnail'))
    
    log(f"   📥 Video (esto puede fallar por protección anti-bot)...", 'info')
    video_path, metodo = descargar_video(seleccionado['url'], vid_id)
    
    # Publicar
    hashtags = "#NoticiasEnVideo #ÚltimaHora #Mundo"
    exito = False
    
    if video_path:
        log(f"   ✅ Descargado via {metodo}, intentando video nativo...", 'info')
        exito = publicar_video_nativo(seleccionado['titulo'], '', video_path, hashtags)
        
        # Limpiar
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
                os.rmdir(os.path.dirname(video_path))
        except:
            pass
    
    if not exito:
        log(f"   📎 Fallback a enlace...", 'info')
        exito = publicar_enlace(seleccionado['titulo'], '', seleccionado['url'], hashtags, thumb)
    
    # Limpiar thumbnail
    if thumb and os.path.exists(thumb):
        try:
            os.remove(thumb)
        except:
            pass
    
    # Guardar
    if exito:
        historial['urls'].append(seleccionado['url'])
        historial['hashes'].append(hashlib.md5(seleccionado['titulo'].lower().encode()).hexdigest())
        guardar_json(HISTORIAL_PATH, historial)
        log("✅ ÉXITO", 'exito')
        return True
    else:
        log("❌ FALLÓ - No guardado en historial", 'error')
        return False

if __name__ == "__main__":
    try:
        sys.exit(0 if main() else 1)
    except Exception as e:
        log(f"💥 Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        sys.exit(1)

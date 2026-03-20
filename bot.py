#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias Video para Facebook - V2.6
Corrección de errores de publicación y logging detallado
"""

import os
import sys
import re
import hashlib
import json
import tempfile
import subprocess
from datetime import datetime, timedelta

# Dependencias
try:
    import requests
except ImportError:
    print("❌ ERROR: Instala requests: pip install requests")
    sys.exit(1)

try:
    import feedparser
    FEEDPARSER_OK = True
except ImportError:
    FEEDPARSER_OK = False
    print("⚠️ feedparser no disponible")

try:
    from difflib import SequenceMatcher
except ImportError:
    class SequenceMatcher:
        def ratio(self): return 0.0

# =============================================================================
# CONFIGURACIÓN Y VERIFICACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_publicaciones.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot.json')

def verificar_configuracion():
    """Verifica que todas las variables estén configuradas"""
    errores = []
    if not FB_PAGE_ID:
        errores.append("FB_PAGE_ID no configurado")
    if not FB_ACCESS_TOKEN:
        errores.append("FB_ACCESS_TOKEN no configurado")
    if not YOUTUBE_API_KEY:
        errores.append("YOUTUBE_API_KEY no configurado (opcional pero recomendado)")
    
    if errores:
        log("❌ ERRORES DE CONFIGURACIÓN:", 'error')
        for e in errores:
            log(f"   - {e}", 'error')
        log("   Asegúrate de configurar los secrets en GitHub:", 'info')
        log("   Settings -> Secrets and variables -> Actions -> New repository secret", 'info')
        return False
    return True

# Palabras clave
KEYWORDS = {
    'war': 10, 'guerra': 10, 'conflict': 10, 'conflicto': 10,
    'ukraine': 10, 'ucrania': 10, 'gaza': 10, 'israel': 10,
    'trump': 10, 'biden': 10, 'putin': 10, 'iran': 10,
    'missile': 10, 'misil': 10, 'attack': 10, 'ataque': 10,
    'oil': 8, 'petróleo': 8, 'warns': 8, 'advierte': 8,
}

def log(msg, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍'}
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {iconos.get(tipo, 'ℹ️')} {msg}")

def cargar_json(ruta, default=None):
    default = default or {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                contenido = f.read().strip()
                if not contenido:
                    return default.copy()
                return json.loads(contenido) or default.copy()
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
        log(f"Error guardando: {e}", 'error')
        return False

def calcular_puntaje(titulo):
    t = titulo.lower()
    puntaje = 0
    for palabra, valor in KEYWORDS.items():
        if palabra in t:
            puntaje += valor
    return puntaje

# =============================================================================
# BÚSQUEDA DE VIDEOS
# =============================================================================

def buscar_youtube():
    if not YOUTUBE_API_KEY:
        log("YOUTUBE_API_KEY no configurado", 'advertencia')
        return []
    videos = []
    try:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'q': 'breaking news international',
            'type': 'video',
            'maxResults': 15,
            'key': YOUTUBE_API_KEY,
            'publishedAfter': (datetime.now() - timedelta(hours=48)).isoformat("T") + "Z"
        }
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        
        if 'error' in data:
            log(f"YouTube API Error: {data['error'].get('message', 'Unknown')}", 'error')
            return []
        
        for item in data.get('items', []):
            vid = item['id'].get('videoId')
            if not vid:
                continue
            snip = item['snippet']
            titulo = snip.get('title', '')
            puntaje = calcular_puntaje(titulo)
            if puntaje >= 3:  # Reducido para más resultados
                videos.append({
                    'titulo': titulo,
                    'url': f"https://youtube.com/watch?v={vid}",
                    'video_id': vid,
                    'thumbnail': snip.get('thumbnails', {}).get('high', {}).get('url', ''),
                    'puntaje': puntaje,
                    'fuente': f"YouTube:{snip.get('channelTitle', 'Unknown')}"
                })
    except Exception as e:
        log(f"Error YouTube: {e}", 'error')
    log(f"YouTube: {len(videos)} videos", 'info')
    return videos

def buscar_rss():
    if not FEEDPARSER_OK:
        return []
    videos = []
    feeds = [
        'https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA',
        'https://www.youtube.com/feeds/videos.xml?channel_id=UCzUV528KlngtCTr2gBCiNbQ',
    ]
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            canal = feed.feed.get('title', 'Unknown')
            for entry in feed.entries[:5]:
                titulo = entry.get('title', '')
                link = entry.get('link', '')
                vid = None
                if 'v=' in link:
                    vid = link.split('v=')[1].split('&')[0]
                elif 'youtu.be/' in link:
                    vid = link.split('youtu.be/')[1].split('?')[0]
                
                if vid:
                    puntaje = calcular_puntaje(titulo)
                    if puntaje >= 3:
                        videos.append({
                            'titulo': titulo,
                            'url': link,
                            'video_id': vid,
                            'puntaje': puntaje,
                            'fuente': f"RSS:{canal}"
                        })
        except Exception as e:
            log(f"Error RSS: {e}", 'debug')
    log(f"RSS: {len(videos)} videos", 'info')
    return videos

# =============================================================================
# DESCARGA DE VIDEOS Y THUMBNAILS
# =============================================================================

def descargar_thumbnail(vid, url=None):
    """Descarga thumbnail con múltiples intentos"""
    urls = []
    if url:
        urls.append(url)
    urls.extend([
        f'https://img.youtube.com/vi/{vid}/maxresdefault.jpg',
        f'https://img.youtube.com/vi/{vid}/sddefault.jpg',
        f'https://img.youtube.com/vi/{vid}/hqdefault.jpg',
        f'https://img.youtube.com/vi/{vid}/mqdefault.jpg',
    ])
    
    for u in urls:
        try:
            r = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            if r.status_code == 200 and len(r.content) > 2000:
                path = f'/tmp/thumb_{vid}.jpg'
                with open(path, 'wb') as f:
                    f.write(r.content)
                log(f"   ✅ Thumbnail descargado ({len(r.content)} bytes)", 'debug')
                return path
        except Exception as e:
            log(f"   ❌ Thumbnail falló {u[:50]}: {e}", 'debug')
    return None

def descargar_video(url, vid):
    """Intenta descargar video con yt-dlp o pytube"""
    # Intentar yt-dlp
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, timeout=5)
        if result.returncode == 0:
            temp_dir = tempfile.mkdtemp()
            out = os.path.join(temp_dir, f"{vid}.mp4")
            cmd = ['yt-dlp', '-f', 'best[height<=720][filesize<50M]', '-o', out, '--quiet', '--no-warnings', url]
            result = subprocess.run(cmd, capture_output=True, timeout=180)
            if result.returncode == 0 and os.path.exists(out):
                size = os.path.getsize(out) / (1024*1024)
                log(f"   ✅ Video yt-dlp: {size:.1f}MB", 'exito')
                return out, 'yt-dlp'
            else:
                log(f"   ❌ yt-dlp error: {result.stderr.decode()[:100]}", 'debug')
    except Exception as e:
        log(f"   ❌ yt-dlp excepción: {e}", 'debug')
    
    # Intentar pytube
    try:
        from pytube import YouTube
        temp_dir = tempfile.mkdtemp()
        yt = YouTube(url)
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        if stream:
            downloaded = stream.download(output_path=temp_dir, filename=vid)
            if os.path.exists(downloaded):
                size = os.path.getsize(downloaded) / (1024*1024)
                log(f"   ✅ Video pytube: {size:.1f}MB", 'exito')
                return downloaded, 'pytube'
    except Exception as e:
        log(f"   ❌ pytube error: {e}", 'debug')
    
    return None, None

# =============================================================================
# PUBLICACIÓN FACEBOOK - CORREGIDA CON LOGGING DETALLADO
# =============================================================================

def publicar_video(titulo, desc, path, hashtags):
    """Publica video nativo en Facebook"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales FB", 'error')
        return False
    
    msg = f"📰 {titulo}\n\n{desc}\n\n{hashtags}\n\n— 🌐 Verdad Hoy"
    if len(msg) > 2000:
        msg = msg[:1900] + "...\n\n" + hashtags
    
    log(f"   📤 Subiendo video a Facebook...", 'info')
    log(f"   📄 Mensaje: {msg[:80]}...", 'debug')
    
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
        
        # Verificar archivo
        if not os.path.exists(path):
            log(f"   ❌ Archivo no existe: {path}", 'error')
            return False
        
        file_size = os.path.getsize(path)
        log(f"   📦 Tamaño: {file_size/1024/1024:.1f} MB", 'debug')
        
        with open(path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {
                'description': msg,
                'access_token': FB_ACCESS_TOKEN,
                'published': 'true'
            }
            
            r = requests.post(url, files=files, data=data, timeout=300)
            result = r.json()
            
            log(f"   📊 Status: {r.status_code}", 'debug')
            log(f"   📊 Respuesta: {json.dumps(result)[:200]}", 'debug')
            
            if r.status_code == 200 and 'id' in result:
                log(f"✅ Video publicado: {result['id']}", 'exito')
                return True
            else:
                error_msg = result.get('error', {}).get('message', 'Unknown error')
                error_code = result.get('error', {}).get('code', 'N/A')
                log(f"❌ Facebook Error {error_code}: {error_msg}", 'error')
                return False
                
    except requests.exceptions.Timeout:
        log("❌ Timeout subiendo video (300s)", 'error')
        return False
    except Exception as e:
        log(f"❌ Excepción publicando: {e}", 'error')
        return False

def publicar_link(titulo, desc, url_video, hashtags, thumb=None):
    """Publica como enlace con o sin thumbnail"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales FB", 'error')
        return False
    
    msg = f"📰 {titulo}\n\n{desc}\n\n🔗 Ver video: {url_video}\n\n{hashtags}\n\n— 🌐 Verdad Hoy"
    
    log(f"   📤 Publicando enlace...", 'info')
    log(f"   📄 Mensaje: {msg[:80]}...", 'debug')
    
    try:
        if thumb and os.path.exists(thumb):
            log(f"   🖼️ Con thumbnail: {thumb}", 'debug')
            url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
            with open(thumb, 'rb') as f:
                files = {'file': ('thumbnail.jpg', f, 'image/jpeg')}
                data = {'message': msg, 'access_token': FB_ACCESS_TOKEN}
                r = requests.post(url, files=files, data=data, timeout=60)
        else:
            log(f"   🔗 Solo enlace (sin thumbnail)", 'debug')
            url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed"
            data = {
                'message': msg,
                'link': url_video,
                'access_token': FB_ACCESS_TOKEN
            }
            r = requests.post(url, data=data, timeout=60)
        
        result = r.json()
        log(f"   📊 Status: {r.status_code}", 'debug')
        log(f"   📊 Respuesta: {json.dumps(result)[:200]}", 'debug')
        
        if r.status_code == 200 and 'id' in result:
            log(f"✅ Enlace publicado: {result['id']}", 'exito')
            return True
        else:
            error_msg = result.get('error', {}).get('message', 'Unknown error')
            error_code = result.get('error', {}).get('code', 'N/A')
            log(f"❌ Facebook Error {error_code}: {error_msg}", 'error')
            
            # Mostrar sugerencias según el error
            if error_code == 190:
                log("   💡 El token de acceso expiró. Genera uno nuevo en:", 'info')
                log("   https://developers.facebook.com/tools/explorer/", 'info')
            elif error_code == 200:
                log("   💡 Permisos insuficientes. El token necesita 'pages_manage_posts'", 'info')
            elif 'limit' in error_msg.lower():
                log("   💡 Límite de rate alcanzado. Espera antes de reintentar.", 'info')
            
            return False
            
    except requests.exceptions.Timeout:
        log("❌ Timeout publicando (60s)", 'error')
        return False
    except Exception as e:
        log(f"❌ Excepción: {e}", 'error')
        return False

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*60)
    print("🎥 BOT NOTICIAS VIDEO V2.6")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Verificar configuración
    if not verificar_configuracion():
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
    
    # Ordenar
    videos.sort(key=lambda x: x.get('puntaje', 0), reverse=True)
    
    # Debug: mostrar todos
    log("📋 Videos encontrados:", 'debug')
    for i, v in enumerate(videos[:5]):
        log(f"   {i+1}. [P{v.get('puntaje', 0)}] {v['titulo'][:60]}...", 'debug')
    
    # Seleccionar no publicado
    seleccionado = None
    for v in videos:
        url_norm = v['url'].split('?')[0]  # Normalizar URL
        historial_urls = [u.split('?')[0] for u in historial.get('urls', [])]
        if url_norm not in historial_urls:
            seleccionado = v
            break
    
    if not seleccionado:
        log("⚠️ Sin videos nuevos, usando el mejor disponible", 'advertencia')
        seleccionado = videos[0]
    
    log(f"\n🎬 Seleccionado (P{seleccionado['puntaje']}): {seleccionado['titulo'][:60]}...")
    log(f"   URL: {seleccionado['url'][:70]}...")
    
    # Descargas
    vid_id = seleccionado['video_id']
    log(f"   📥 Descargando thumbnail...", 'info')
    thumb = descargar_thumbnail(vid_id, seleccionado.get('thumbnail'))
    
    log(f"   📥 Descargando video...", 'info')
    video_path, metodo = descargar_video(seleccionado['url'], vid_id)
    
    # Publicar
    hashtags = "#NoticiasEnVideo #ÚltimaHora #Mundo #NoticiasInternacionales"
    exito = False
    tipo = 'link'
    
    if video_path:
        log(f"   ✅ Descargado via {metodo}, intentando video nativo...", 'info')
        exito = publicar_video(seleccionado['titulo'], '', video_path, hashtags)
        if exito:
            tipo = 'video'
        
        # Limpiar video
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
                os.rmdir(os.path.dirname(video_path))
        except:
            pass
    
    # Fallback a link
    if not exito:
        log(f"   📎 Fallback a enlace...", 'info')
        exito = publicar_link(seleccionado['titulo'], '', seleccionado['url'], hashtags, thumb)
    
    # Limpiar thumbnail
    if thumb and os.path.exists(thumb):
        try:
            os.remove(thumb)
        except:
            pass
    
    # Guardar en historial solo si tuvo éxito
    if exito:
        historial['urls'].append(seleccionado['url'])
        historial['hashes'].append(hashlib.md5(seleccionado['titulo'].lower().encode()).hexdigest())
        guardar_json(HISTORIAL_PATH, historial)
        log(f"️ ÉXITO - Guardado en historial", 'exito')
        return True
    else:
        log("❌ FALLÓ - No se guardará en historial", 'error')
        return False

if __name__ == "__main__":
    try:
        sys.exit(0 if main() else 1)
    except Exception as e:
        log(f"💥 Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        sys.exit(1)

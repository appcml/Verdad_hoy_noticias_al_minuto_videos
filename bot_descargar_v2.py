#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias Video para Facebook - V2.5
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

# Configuración
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_publicaciones.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot.json')

# Palabras clave
KEYWORDS = {
    'war': 10, 'guerra': 10, 'conflict': 10, 'conflicto': 10,
    'ukraine': 10, 'ucrania': 10, 'gaza': 10, 'israel': 10,
    'trump': 10, 'biden': 10, 'putin': 10, 'iran': 10,
    'missile': 10, 'misil': 10, 'attack': 10, 'ataque': 10,
}

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

def calcular_puntaje(titulo):
    t = titulo.lower()
    puntaje = 0
    for palabra, valor in KEYWORDS.items():
        if palabra in t:
            puntaje += valor
    return puntaje

def buscar_youtube():
    if not YOUTUBE_API_KEY:
        return []
    videos = []
    try:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'q': 'breaking news',
            'type': 'video',
            'maxResults': 10,
            'key': YOUTUBE_API_KEY,
            'publishedAfter': (datetime.now() - timedelta(hours=24)).isoformat("T") + "Z"
        }
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        for item in data.get('items', []):
            vid = item['id']['videoId']
            snip = item['snippet']
            titulo = snip.get('title', '')
            puntaje = calcular_puntaje(titulo)
            if puntaje >= 5:
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
        'https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA',  # BBC
    ]
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:3]:
                titulo = entry.get('title', '')
                link = entry.get('link', '')
                vid = link.split('v=')[1].split('&')[0] if 'v=' in link else None
                if vid:
                    puntaje = calcular_puntaje(titulo)
                    if puntaje >= 5:
                        videos.append({
                            'titulo': titulo,
                            'url': link,
                            'video_id': vid,
                            'puntaje': puntaje,
                            'fuente': 'RSS:BBC'
                        })
        except:
            pass
    log(f"RSS: {len(videos)} videos", 'info')
    return videos

def descargar_thumbnail(vid, url=None):
    urls = [url] if url else [] + [
        f'https://img.youtube.com/vi/{vid}/hqdefault.jpg',
        f'https://img.youtube.com/vi/{vid}/mqdefault.jpg',
    ]
    for u in urls:
        if not u:
            continue
        try:
            r = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            if r.status_code == 200 and len(r.content) > 1000:
                path = f'/tmp/thumb_{vid}.jpg'
                with open(path, 'wb') as f:
                    f.write(r.content)
                return path
        except:
            pass
    return None

def descargar_video(url, vid):
    # Intentar yt-dlp
    try:
        temp_dir = tempfile.mkdtemp()
        out = os.path.join(temp_dir, f"{vid}.mp4")
        cmd = ['yt-dlp', '-f', 'best[height<=720]', '-o', out, '--quiet', url]
        result = subprocess.run(cmd, capture_output=True, timeout=180)
        if result.returncode == 0 and os.path.exists(out):
            return out, 'yt-dlp'
    except:
        pass
    
    # Intentar pytube
    try:
        from pytube import YouTube
        temp_dir = tempfile.mkdtemp()
        out = os.path.join(temp_dir, f"{vid}.mp4")
        yt = YouTube(url)
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        if stream:
            downloaded = stream.download(output_path=temp_dir, filename=vid)
            if os.path.exists(downloaded):
                return downloaded, 'pytube'
    except:
        pass
    
    return None, None

def publicar_video(titulo, desc, path, hashtags):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        return False
    msg = f"📰 {titulo}\n\n{desc}\n\n{hashtags}\n\n— 🌐 Verdad Hoy"
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
        with open(path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {'description': msg, 'access_token': FB_ACCESS_TOKEN, 'published': 'true'}
            r = requests.post(url, files=files, data=data, timeout=300)
            result = r.json()
            if r.status_code == 200 and 'id' in result:
                log(f"✅ Video publicado: {result['id']}", 'exito')
                return True
    except Exception as e:
        log(f"Error publicando: {e}", 'error')
    return False

def publicar_link(titulo, desc, url_video, hashtags, thumb=None):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        return False
    msg = f"📰 {titulo}\n\n{desc}\n\n🔗 {url_video}\n\n{hashtags}\n\n— 🌐 Verdad Hoy"
    try:
        if thumb and os.path.exists(thumb):
            url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
            with open(thumb, 'rb') as f:
                files = {'file': ('thumb.jpg', f, 'image/jpeg')}
                data = {'message': msg, 'access_token': FB_ACCESS_TOKEN}
                r = requests.post(url, files=files, data=data, timeout=60)
        else:
            url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed"
            data = {'message': msg, 'link': url_video, 'access_token': FB_ACCESS_TOKEN}
            r = requests.post(url, data=data, timeout=60)
        
        result = r.json()
        if r.status_code == 200 and 'id' in result:
            log(f"✅ Link publicado: {result['id']}", 'exito')
            return True
    except:
        pass
    return False

def main():
    print("\n" + "="*50)
    print("🎥 BOT NOTICIAS VIDEO V2.5")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Faltan credenciales FB", 'error')
        return False
    
    # Cargar historial
    historial = cargar_json(HISTORIAL_PATH, {'urls': [], 'hashes': []})
    log(f"Historial: {len(historial.get('urls', []))} items")
    
    # Buscar videos
    videos = buscar_youtube() + buscar_rss()
    log(f"Total: {len(videos)} videos")
    
    if not videos:
        log("No hay videos", 'error')
        return False
    
    # Ordenar y filtrar
    videos.sort(key=lambda x: x.get('puntaje', 0), reverse=True)
    
    # Seleccionar
    seleccionado = None
    for v in videos:
        if v['url'] not in historial.get('urls', []):
            seleccionado = v
            break
    
    if not seleccionado:
        log("Sin videos nuevos", 'error')
        return False
    
    log(f"🎬 {seleccionado['titulo'][:50]}...")
    
    # Descargar
    vid_id = seleccionado['video_id']
    thumb = descargar_thumbnail(vid_id, seleccionado.get('thumbnail'))
    video_path, metodo = descargar_video(seleccionado['url'], vid_id)
    
    # Publicar
    hashtags = "#Noticias #ÚltimaHora #Mundo"
    exito = False
    
    if video_path:
        log(f"Descargado via {metodo}")
        exito = publicar_video(seleccionado['titulo'], '', video_path, hashtags)
        try:
            os.remove(video_path)
            os.rmdir(os.path.dirname(video_path))
        except:
            pass
    
    if not exito:
        log("Publicando como link...")
        exito = publicar_link(seleccionado['titulo'], '', seleccionado['url'], hashtags, thumb)
    
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
    
    return False

if __name__ == "__main__":
    try:
        sys.exit(0 if main() else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        sys.exit(1)

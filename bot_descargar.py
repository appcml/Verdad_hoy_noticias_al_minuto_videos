#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Descargador de Videos - V1.0
Solo descarga videos de YouTube y los guarda en carpeta temporal/designada
No publica nada en redes sociales
"""

import os
import sys
import re
import json
import subprocess
import shutil
import base64
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ ERROR: pip install requests")
    sys.exit(1)

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
YT_COOKIES_B64 = os.getenv('YT_COOKIES')

# Carpeta donde se guardarán los videos (puedes cambiarla)
CARPETA_DESCARGAS = os.getenv('CARPETA_VIDEOS', 'videos_pendientes')
MAX_VIDEOS_POR_EJECUCION = int(os.getenv('MAX_VIDEOS', '5'))
MAX_TAMANO_MB = int(os.getenv('MAX_TAMANO_MB', '100'))  # Límite de tamaño

# Crear carpeta si no existe
Path(CARPETA_DESCARGAS).mkdir(parents=True, exist_ok=True)

# =============================================================================
# LOGGING
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍'}
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {iconos.get(tipo, 'ℹ️')} {mensaje}")

# =============================================================================
# COOKIES
# =============================================================================

def preparar_cookies():
    """Prepara archivo de cookies desde base64"""
    if not YT_COOKIES_B64:
        log("No hay cookies configuradas", 'advertencia')
        return None
    
    try:
        cookies_content = base64.b64decode(YT_COOKIES_B64).decode('utf-8')
        cookies_path = os.path.join(CARPETA_DESCARGAS, '.cookies.txt')
        
        with open(cookies_path, 'w', encoding='utf-8') as f:
            f.write(cookies_content)
        
        return cookies_path
    except Exception as e:
        log(f"Error cookies: {e}", 'error')
        return None

# =============================================================================
# BÚSQUEDA DE VIDEOS
# =============================================================================

def buscar_videos_noticias():
    """Busca videos de noticias en YouTube"""
    if not YOUTUBE_API_KEY:
        log("ERROR: YOUTUBE_API_KEY no configurada", 'error')
        return []
    
    videos = []
    queries = [
        "noticias internacionales ultima hora",
        "breaking news today",
        "world news now",
        "conflict news video",
        "war footage news"
    ]
    
    for query in queries:
        try:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'videoDuration': 'short',  # < 4 minutos
                'order': 'date',
                'maxResults': 10,
                'key': YOUTUBE_API_KEY,
                'publishedAfter': (datetime.now().replace(hour=0, minute=0, second=0)).isoformat() + "Z"
            }
            
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            
            if 'items' in data:
                for item in data['items']:
                    video_id = item['id']['videoId']
                    snippet = item['snippet']
                    
                    videos.append({
                        'video_id': video_id,
                        'titulo': limpiar_texto(snippet.get('title', '')),
                        'descripcion': limpiar_texto(snippet.get('description', '')),
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                        'canal': snippet.get('channelTitle', ''),
                        'fecha_publicacion': snippet.get('publishedAt'),
                        'query_usada': query
                    })
                    
        except Exception as e:
            log(f"Error API YouTube: {e}", 'error')
            continue
    
    # Eliminar duplicados por video_id
    vistos = set()
    unicos = []
    for v in videos:
        if v['video_id'] not in vistos:
            vistos.add(v['video_id'])
            unicos.append(v)
    
    log(f"🔍 Encontrados {len(unicos)} videos únicos", 'info')
    return unicos

def limpiar_texto(texto):
    """Limpia texto HTML"""
    if not texto:
        return ""
    import html
    texto = html.unescape(texto)
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

# =============================================================================
# DESCARGA
# =============================================================================

def verificar_yt_dlp():
    """Verifica yt-dlp"""
    try:
        result = subprocess.run(['yt-dlp', '--version'], 
                              capture_output=True, text=True, timeout=10)
        log(f"yt-dlp: {result.stdout.strip()}", 'info')
        return True
    except:
        log("yt-dlp no instalado", 'error')
        return False

def ya_descargado(video_id):
    """Verifica si el video ya existe en la carpeta"""
    patron = os.path.join(CARPETA_DESCARGAS, f"*{video_id}*")
    import glob
    existe = glob.glob(patron)
    if existe:
        return True
    
    # También verificar en metadata
    json_path = os.path.join(CARPETA_DESCARGAS, f"{video_id}.json")
    return os.path.exists(json_path)

def descargar_video(video_info, cookies_path=None):
    """
    Descarga un video específico
    Retorna: True/False
    """
    video_id = video_info['video_id']
    url = video_info['url']
    
    # Verificar si ya existe
    if ya_descargado(video_id):
        log(f"⏭️ Ya descargado: {video_id}", 'advertencia')
        return False
    
    # Nombre base para archivos
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_base = f"{timestamp}_{video_id}"
    
    video_path = os.path.join(CARPETA_DESCARGAS, f"{nombre_base}.mp4")
    json_path = os.path.join(CARPETA_DESCARGAS, f"{video_id}.json")
    
    # Comando yt-dlp
    cmd = [
        'yt-dlp',
        '--format', 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
        '--output', video_path,
        '--merge-output-format', 'mp4',
        '--no-playlist',
        '--no-check-certificates',
        '--geo-bypass',
        '--retries', '5',
        '--fragment-retries', '5',
        '--skip-unavailable-fragments',
        '--no-warnings',
        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    ]
    
    if cookies_path and os.path.exists(cookies_path):
        cmd.extend(['--cookies', cookies_path])
        log(f"🔐 Usando cookies", 'debug')
    
    cmd.append(url)
    
    try:
        log(f"⬇️ Descargando: {video_id} | {video_info['titulo'][:50]}...", 'info')
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            error_msg = result.stderr
            if "bot" in error_msg.lower():
                log(f"🤖 Bloqueado por bot: {video_id}", 'error')
            elif "unavailable" in error_msg.lower():
                log(f"📛 No disponible: {video_id}", 'error')
            else:
                log(f"❌ Error: {error_msg[:100]}", 'error')
            return False
        
        # Verificar que se descargó
        if not os.path.exists(video_path):
            log(f"❌ Archivo no encontrado después de descarga", 'error')
            return False
        
        # Verificar tamaño
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        if size_mb > MAX_TAMANO_MB:
            log(f"⚠️ Muy grande ({size_mb:.1f}MB), eliminando", 'advertencia')
            os.remove(video_path)
            return False
        
        if size_mb < 0.5:
            log(f"⚠️ Muy pequeño ({size_mb:.1f}MB), posible error", 'advertencia')
            os.remove(video_path)
            return False
        
        # Guardar metadata
        metadata = {
            'video_id': video_id,
            'titulo': video_info['titulo'],
            'descripcion': video_info['descripcion'],
            'canal': video_info['canal'],
            'url_original': url,
            'thumbnail': video_info['thumbnail'],
            'fecha_descarga': datetime.now().isoformat(),
            'fecha_publicacion_original': video_info['fecha_publicacion'],
            'archivo_video': os.path.basename(video_path),
            'tamanio_mb': round(size_mb, 2),
            'estado': 'pendiente',  # pendiente | publicado | error
            'query_usada': video_info.get('query_usada', '')
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        log(f"✅ Guardado: {nombre_base}.mp4 ({size_mb:.1f} MB)", 'exito')
        return True
        
    except subprocess.TimeoutExpired:
        log(f"⏱️ Timeout: {video_id}", 'error')
        return False
    except Exception as e:
        log(f"❌ Error: {e}", 'error')
        return False

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*60)
    print("📥 BOT DESCARGADOR DE VIDEOS - V1.0")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Carpeta: {os.path.abspath(CARPETA_DESCARGAS)}")
    print("="*60)
    
    # Verificaciones
    if not YOUTUBE_API_KEY:
        log("ERROR: Falta YOUTUBE_API_KEY", 'error')
        return False
    
    if not verificar_yt_dlp():
        return False
    
    # Preparar cookies
    cookies_path = preparar_cookies()
    
    # Buscar videos
    videos = buscar_videos_noticias()
    
    if not videos:
        log("No se encontraron videos", 'advertencia')
        return False
    
    # Descargar hasta MAX_VIDEOS_POR_EJECUCION
    descargados = 0
    fallidos = 0
    
    for video in videos:
        if descargados >= MAX_VIDEOS_POR_EJECUCION:
            log(f"🛑 Límite alcanzado: {MAX_VIDEOS_POR_EJECUCION} videos", 'info')
            break
        
        if descargar_video(video, cookies_path):
            descargados += 1
        else:
            fallidos += 1
    
    # Limpiar cookies temporales
    if cookies_path and os.path.exists(cookies_path):
        try:
            os.remove(cookies_path)
        except:
            pass
    
    # Resumen
    print("\n" + "="*60)
    log(f"📊 RESUMEN: {descargados} descargados, {fallidos} fallidos", 'exito')
    
    # Listar videos en carpeta
    videos_existentes = [f for f in os.listdir(CARPETA_DESCARGAS) if f.endswith('.mp4')]
    log(f"📁 Total videos en carpeta: {len(videos_existentes)}", 'info')
    
    return descargados > 0

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

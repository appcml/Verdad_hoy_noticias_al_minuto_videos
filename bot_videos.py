#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Reels - Verdad Hoy v3.0 (DIAGNÓSTICO)
"""

import os
import sys
import json
import re
import hashlib
import random
import time
import subprocess
import requests
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Crear directorios primero
DATA_DIR = Path('data')
VIDEOS_DIR = DATA_DIR / 'videos'
REELS_DIR = DATA_DIR / 'reels'

for d in [DATA_DIR, VIDEOS_DIR, REELS_DIR]:
    d.mkdir(exist_ok=True)

# Cargar variables de entorno con verificación
def verificar_configuracion():
    """Verifica que todas las variables estén configuradas"""
    print("\n" + "="*70)
    print("🔍 VERIFICACIÓN DE CONFIGURACIÓN")
    print("="*70)
    
    config = {}
    errores = []
    
    # YouTube API Key
    config['YOUTUBE_API_KEY'] = os.getenv('YOUTUBE_API_KEY')
    if not config['YOUTUBE_API_KEY']:
        errores.append("YOUTUBE_API_KEY no está configurado")
    else:
        print(f"✅ YOUTUBE_API_KEY: {config['YOUTUBE_API_KEY'][:15]}...")
    
    # Facebook
    config['FB_ACCESS_TOKEN'] = os.getenv('FB_ACCESS_TOKEN')
    if not config['FB_ACCESS_TOKEN']:
        errores.append("FB_ACCESS_TOKEN no está configurado")
    else:
        print(f"✅ FB_ACCESS_TOKEN: {config['FB_ACCESS_TOKEN'][:20]}...")
    
    config['FB_PAGE_ID'] = os.getenv('FB_PAGE_ID')
    if not config['FB_PAGE_ID']:
        errores.append("FB_PAGE_ID no está configurado")
    else:
        print(f"✅ FB_PAGE_ID: {config['FB_PAGE_ID']}")
    
    # Opcional
    config['RAPIDAPI_KEY'] = os.getenv('RAPIDAPI_KEY')
    if config['RAPIDAPI_KEY']:
        print(f"✅ RAPIDAPI_KEY: {config['RAPIDAPI_KEY'][:15]}... (opcional)")
    else:
        print("ℹ️  RAPIDAPI_KEY no configurado (opcional)")
    
    if errores:
        print("\n❌ ERRORES ENCONTRADOS:")
        for error in errores:
            print(f"   • {error}")
        print("\n💡 SOLUCIÓN:")
        print("   1. Ve a tu repositorio en GitHub")
        print("   2. Settings → Secrets and variables → Actions")
        print("   3. Agrega los secrets faltantes")
        print("="*70)
        return None
    
    print("="*70)
    return config

# =============================================================================
# FUNCIONES PRINCIPALES (SIMPLIFICADAS)
# =============================================================================

def log(msg, tipo='info'):
    iconos = {'info': 'ℹ️', 'ok': '✅', 'error': '❌', 'warn': '⚠️'}
    print(f"{iconos.get(tipo, 'ℹ️')} {msg}", flush=True)

def buscar_noticia_youtube(config):
    """Busca una noticia reciente en YouTube"""
    log("Buscando noticias en YouTube...", 'info')
    
    # Términos de búsqueda para noticias de actualidad
    queries = [
        'breaking news today',
        'world news today',
        'war news 2024',
        'politics news today',
        'economy news'
    ]
    
    query = random.choice(queries)
    log(f"Query: '{query}'", 'info')
    
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': query,
        'type': 'video',
        'videoDuration': 'short',  # < 4 minutos
        'maxResults': 5,
        'order': 'relevance',
        'key': config['YOUTUBE_API_KEY']
    }
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        
        if 'error' in data:
            log(f"YouTube API Error: {data['error'].get('message')}", 'error')
            return None
        
        items = data.get('items', [])
        if not items:
            log("No se encontraron videos", 'warn')
            return None
        
        # Seleccionar el primero
        video = items[0]
        video_id = video['id']['videoId']
        
        log(f"Video encontrado: {video['snippet']['title'][:60]}", 'ok')
        
        return {
            'video_id': video_id,
            'titulo': video['snippet']['title'],
            'descripcion': video['snippet']['description'],
            'url': f"https://youtube.com/watch?v={video_id}"
        }
        
    except Exception as e:
        log(f"Error buscando: {str(e)[:80]}", 'error')
        return None

def descargar_video_yt(video_info, config):
    """Descarga video usando yt-dlp"""
    video_id = video_info['video_id']
    output_path = VIDEOS_DIR / f"video_{video_id}.mp4"
    
    log(f"Descargando video {video_id}...", 'info')
    
    cmd = [
        'yt-dlp',
        '-f', 'best[height<=720][filesize<50M]/worst',
        '--max-filesize', '50M',
        '-o', str(output_path),
        '--no-warnings',
        '--quiet',
        f"https://youtube.com/watch?v={video_id}"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            log(f"yt-dlp error: {result.stderr[:100]}", 'error')
            return None
        
        if output_path.exists() and output_path.stat().st_size > 1000000:
            size_mb = output_path.stat().st_size / (1024*1024)
            log(f"Descargado: {size_mb:.1f} MB", 'ok')
            return str(output_path)
        else:
            log("Archivo no encontrado o muy pequeño", 'error')
            return None
            
    except subprocess.TimeoutExpired:
        log("Timeout descargando video", 'error')
        return None
    except Exception as e:
        log(f"Error descarga: {str(e)[:80]}", 'error')
        return None

def publicar_facebook(video_path, titulo, config):
    """Publica video en Facebook"""
    log("Publicando en Facebook...", 'info')
    
    # Crear mensaje
    mensaje = f"""🎬 {titulo[:80]}{'...' if len(titulo) > 80 else ''}

📰 Noticia de última hora

#Noticias #Actualidad #Video #VerdadHoy"""
    
    url = f"https://graph.facebook.com/v18.0/{config['FB_PAGE_ID']}/videos"
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {
                'description': mensaje[:1990],
                'access_token': config['FB_ACCESS_TOKEN']
            }
            
            resp = requests.post(url, files=files, data=data, timeout=300)
            result = resp.json()
        
        if 'id' in result:
            log(f"✅ Publicado ID: {result['id']}", 'ok')
            return result['id']
        else:
            error = result.get('error', {}).get('message', 'Unknown')
            log(f"❌ Facebook error: {error[:100]}", 'error')
            return None
            
    except Exception as e:
        log(f"Error publicando: {str(e)[:80]}", 'error')
        return None

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*70)
    print("📱 BOT DE REELS - VERDAD HOY v3.0")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Verificar configuración
    config = verificar_configuracion()
    if not config:
        return False
    
    # Paso 1: Buscar video
    video_info = buscar_noticia_youtube(config)
    if not video_info:
        log("No se encontró video para publicar", 'error')
        return False
    
    # Paso 2: Descargar
    video_path = descargar_video_yt(video_info, config)
    if not video_path:
        log("No se pudo descargar el video", 'error')
        return False
    
    # Paso 3: Publicar
    post_id = publicar_facebook(video_path, video_info['titulo'], config)
    
    # Limpiar
    try:
        Path(video_path).unlink(missing_ok=True)
    except:
        pass
    
    if post_id:
        print("\n" + "="*70)
        print("✅ ÉXITO - VIDEO PUBLICADO")
        print(f"📱 Post ID: {post_id}")
        print(f"🎬 {video_info['titulo'][:60]}")
        print("="*70)
        return True
    else:
        log("No se pudo publicar", 'error')
        return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        print(f"\n💥 ERROR CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

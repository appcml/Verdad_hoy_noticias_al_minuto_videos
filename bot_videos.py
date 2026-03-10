#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Reels - Verdad Hoy
Publica videos de noticias automáticamente
"""

import os
import sys
import requests
import subprocess
import random
from datetime import datetime
from pathlib import Path

# Configuración
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def main():
    log("="*60)
    log("🎬 BOT DE REELS INICIADO")
    log("="*60)
    
    # Verificar variables
    if not all([YOUTUBE_API_KEY, FB_ACCESS_TOKEN, FB_PAGE_ID]):
        log("❌ ERROR: Faltan variables de entorno")
        log("   Revisa YOUTUBE_API_KEY, FB_ACCESS_TOKEN, FB_PAGE_ID")
        return False
    
    # Crear directorios
    Path('data/videos').mkdir(parents=True, exist_ok=True)
    
    # Buscar video en YouTube
    queries = ['breaking news', 'world news today', 'war news 2024', 'politics news']
    query = random.choice(queries)
    
    log(f"🔍 Buscando: {query}")
    
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': query,
        'type': 'video',
        'videoDuration': 'short',
        'maxResults': 3,
        'key': YOUTUBE_API_KEY
    }
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        
        if 'error' in data:
            log(f"❌ YouTube API Error: {data['error']['message']}")
            return False
        
        items = data.get('items', [])
        if not items:
            log("❌ No se encontraron videos")
            return False
        
        # Tomar el primer video
        video = items[0]
        video_id = video['id']['videoId']
        titulo = video['snippet']['title']
        
        log(f"✅ Video encontrado: {titulo[:50]}...")
        
        # Descargar
        video_path = f"data/videos/{video_id}.mp4"
        log("⬇️ Descargando...")
        
        cmd = [
            'yt-dlp', '-f', 'best[height<=720][filesize<50M]',
            '--max-filesize', '50M', '-o', video_path,
            '--no-warnings', '--quiet',
            f'https://youtube.com/watch?v={video_id}'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0 or not Path(video_path).exists():
            log("❌ Error descargando video")
            return False
        
        size_mb = Path(video_path).stat().st_size / (1024*1024)
        log(f"✅ Descargado: {size_mb:.1f} MB")
        
        # Publicar en Facebook
        log("📘 Publicando en Facebook...")
        
        mensaje = f"""🎬 {titulo[:80]}{'...' if len(titulo) > 80 else ''}

📰 Noticia de última hora

#Noticias #Actualidad #Video #VerdadHoy"""
        
        fb_url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
        
        with open(video_path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {'description': mensaje[:1990], 'access_token': FB_ACCESS_TOKEN}
            resp = requests.post(fb_url, files=files, data=data, timeout=300)
            result = resp.json()
        
        # Limpiar
        Path(video_path).unlink(missing_ok=True)
        
        if 'id' in result:
            log(f"✅ ¡PUBLICADO! ID: {result['id']}")
            log("="*60)
            return True
        else:
            error = result.get('error', {}).get('message', 'Unknown')
            log(f"❌ Error Facebook: {error[:100]}")
            return False
            
    except Exception as e:
        log(f"❌ Error: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    exit(0 if main() else 1)

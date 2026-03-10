#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Reels - Verdad Hoy v3.1
Usa RapidAPI para descargar videos (evita bloqueo de YouTube)
"""

import os
import sys
import requests
import random
from datetime import datetime
from pathlib import Path

# Configuración
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')  # NUEVO: Para descargar videos

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def descargar_con_rapidapi(video_id):
    """Descarga video usando RapidAPI (funciona en GitHub Actions)"""
    if not RAPIDAPI_KEY:
        log("❌ RAPIDAPI_KEY no configurado")
        return None
    
    log("⬇️ Descargando vía RapidAPI...")
    
    # API de descarga de YouTube
    url = "https://youtube-video-download-info.p.rapidapi.com/dl"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "youtube-video-download-info.p.rapidapi.com"
    }
    params = {"id": video_id}
    
    try:
        # Obtener link de descarga
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        data = resp.json()
        
        # Buscar formato MP4 720p o menor
        download_url = None
        if 'link' in data:
            # Elegir calidad media (720p o 480p)
            for quality in ['720p', '480p', '360p', 'mp4']:
                if quality in data['link']:
                    download_url = data['link'][quality][0]
                    break
        
        if not download_url:
            log("❌ No se encontró formato válido")
            return None
        
        # Descargar archivo
        video_path = f"data/videos/{video_id}.mp4"
        log(f"   Descargando archivo...")
        
        r = requests.get(download_url, timeout=120)
        if r.status_code == 200:
            Path(video_path).parent.mkdir(parents=True, exist_ok=True)
            with open(video_path, 'wb') as f:
                f.write(r.content)
            
            size_mb = len(r.content) / (1024*1024)
            log(f"✅ Descargado: {size_mb:.1f} MB")
            return video_path
        else:
            log(f"❌ Error descargando: {r.status_code}")
            return None
            
    except Exception as e:
        log(f"❌ Error RapidAPI: {str(e)[:80]}")
        return None

def main():
    log("="*60)
    log("🎬 BOT DE REELS INICIADO")
    log("="*60)
    
    # Verificar variables
    if not all([YOUTUBE_API_KEY, FB_ACCESS_TOKEN, FB_PAGE_ID]):
        log("❌ ERROR: Faltan variables de entorno básicas")
        return False
    
    if not RAPIDAPI_KEY:
        log("⚠️  ADVERTENCIA: RAPIDAPI_KEY no configurado")
        log("   El bot no podrá descargar videos de YouTube")
        log("   Suscríbete gratis en: rapidapi.com")
        return False
    
    # Buscar video en YouTube
    queries = ['breaking news', 'world news today', 'war news 2024']
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
        
        video = items[0]
        video_id = video['id']['videoId']
        titulo = video['snippet']['title']
        
        log(f"✅ Video: {titulo[:50]}...")
        
        # Descargar con RapidAPI
        video_path = descargar_con_rapidapi(video_id)
        if not video_path:
            return False
        
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
            log(f"❌ Facebook: {error[:100]}")
            return False
            
    except Exception as e:
        log(f"❌ Error: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    exit(0 if main() else 1)

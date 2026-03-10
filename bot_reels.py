#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Reels - Verdad Hoy v4.0
Monitorea páginas de Facebook y republica videos de noticias
"""

import os
import sys
import re
import requests
import subprocess
import random
from datetime import datetime, timedelta
from pathlib import Path

# Configuración
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')

# Páginas de noticias a monitorear (IDs de Facebook)
PAGINAS_NOTICIAS = [
    'bbcnews',           # BBC News
    'cnn',               # CNN
    'Reuters',           # Reuters
    'AlJazeera',         # Al Jazeera
    'france24english',   # France 24
    'RTnews',            # RT
    'cnnee',             # CNN Español
    'deutschewellenews', # DW
    'skynews',           # Sky News
    'abcnews',           # ABC News
]

# Palabras clave para filtrar noticias relevantes
PALABRAS_CLAVE = [
    'war', 'conflict', 'ukraine', 'gaza', 'israel', 'military', 'attack',
    'breaking', 'news', 'president', 'election', 'politics', 'economy',
    'crisis', 'sanctions', 'nato', 'russia', 'china', 'biden', 'trump'
]

DATA_DIR = Path('data')
VIDEOS_DIR = DATA_DIR / 'videos'
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

def log(msg, tipo='info'):
    iconos = {'info': 'ℹ️', 'ok': '✅', 'error': '❌', 'warn': '⚠️', 'fb': '📘'}
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {iconos.get(tipo, 'ℹ️')} {msg}", flush=True)

def obtener_videos_pagina(page_id, limite=5):
    """Obtiene videos recientes de una página de Facebook"""
    log(f"Revisando {page_id}...", 'fb')
    
    url = f"https://graph.facebook.com/v18.0/{page_id}/videos"
    params = {
        'access_token': FB_ACCESS_TOKEN,
        'fields': 'id,title,description,created_time,permalink_url,thumbnails',
        'limit': limite
    }
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        
        if 'error' in data:
            error_msg = data['error'].get('message', 'Unknown')
            if 'Page Public Content Access' in error_msg:
                log(f"⚠️ Página {page_id} requiere permisos especiales", 'warn')
            else:
                log(f"Error {page_id}: {error_msg[:60]}", 'error')
            return []
        
        videos = []
        for video in data.get('data', []):
            titulo = video.get('title', '') or video.get('description', '')[:100]
            descripcion = video.get('description', '')
            
            # Verificar si es contenido relevante
            texto_completo = (titulo + ' ' + descripcion).lower()
            es_relevante = any(palabra in texto_completo for palabra in PALABRAS_CLAVE)
            
            if es_relevante:
                videos.append({
                    'id': video['id'],
                    'titulo': titulo,
                    'descripcion': descripcion,
                    'fecha': video.get('created_time'),
                    'permalink': video.get('permalink_url'),
                    'pagina_origen': page_id
                })
        
        log(f"  {len(videos)} videos relevantes", 'ok')
        return videos
        
    except Exception as e:
        log(f"Error {page_id}: {str(e)[:60]}", 'error')
        return []

def buscar_video_noticia():
    """Busca videos de noticias en todas las páginas monitoreadas"""
    log("🔍 Buscando videos de noticias...", 'info')
    
    # Seleccionar 3 páginas aleatorias
    paginas = random.sample(PAGINAS_NOTICIAS, min(3, len(PAGINAS_NOTICIAS)))
    
    todos_videos = []
    for pagina in paginas:
        videos = obtener_videos_pagina(pagina)
        todos_videos.extend(videos)
        import time
        time.sleep(1)  # Evitar rate limits
    
    # Ordenar por fecha (más recientes primero)
    todos_videos.sort(key=lambda x: x['fecha'], reverse=True)
    
    if not todos_videos:
        log("❌ No se encontraron videos relevantes", 'error')
        return None
    
    # Seleccionar el más reciente
    video = todos_videos[0]
    log(f"✅ Seleccionado: {video['titulo'][:60]}...", 'ok')
    log(f"   De: {video['pagina_origen']}")
    
    return video

def descargar_video_facebook(video_id):
    """Descarga video de Facebook usando yt-dlp"""
    video_url = f"https://facebook.com/watch?v={video_id}"
    output_path = VIDEOS_DIR / f"fb_{video_id}.mp4"
    
    log("⬇️ Descargando video...")
    
    cmd = [
        'yt-dlp',
        '--no-playlist',
        '-f', 'best[height<=720][filesize<50M]/best[filesize<50M]/worst',
        '--max-filesize', '50M',
        '-o', str(output_path),
        '--no-warnings',
        '--quiet',
        '--socket-timeout', '30',
        '--retries', '2',
        video_url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            log(f"❌ yt-dlp error: {result.stderr[:100]}", 'error')
            return None
        
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024*1024)
            if size_mb > 1:  # Mínimo 1MB
                log(f"✅ Descargado: {size_mb:.1f} MB", 'ok')
                return str(output_path)
        
        log("❌ Archivo no encontrado o muy pequeño", 'error')
        return None
        
    except subprocess.TimeoutExpired:
        log("❌ Timeout descargando", 'error')
        return None
    except Exception as e:
        log(f"❌ Error: {str(e)[:80]}", 'error')
        return None

def generar_texto_reel(titulo_original, fuente):
    """Genera texto para el reel republicado"""
    # Limpiar título
    titulo = re.sub(r'http\S+', '', titulo_original)  # Quitar URLs
    titulo = re.sub(r'#\w+', '', titulo)  # Quitar hashtags
    titulo = titulo.strip()
    
    if len(titulo) > 150:
        titulo = titulo[:147] + "..."
    
    intros = [
        "🚨 Noticia de última hora",
        "📰 Información importante",
        "🌍 Desarrollo internacional",
        "⚡ Acontecimiento relevante",
    ]
    
    cierres = [
        "¿Qué opinas? Comenta 👇",
        "Comparte tu perspectiva 💬",
        "¿Crees que esto tendrá impacto? 🤔",
    ]
    
    texto = f"""{random.choice(intros)}

{titulo}

📡 Fuente: {fuente}

{random.choice(cierres)}

#Noticias #Actualidad #ÚltimaHora #VerdadHoy"""
    
    return texto[:1990]

def publicar_en_mi_pagina(video_path, texto):
    """Publica el video en tu página de Facebook"""
    log("📘 Publicando en tu página...", 'fb')
    
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {
                'description': texto,
                'access_token': FB_ACCESS_TOKEN
            }
            
            resp = requests.post(url, files=files, data=data, timeout=300)
            result = resp.json()
        
        if 'id' in result:
            log(f"✅ ¡PUBLICADO! ID: {result['id']}", 'ok')
            return result['id']
        else:
            error = result.get('error', {}).get('message', 'Unknown')
            log(f"❌ Facebook error: {error[:100]}", 'error')
            return None
            
    except Exception as e:
        log(f"❌ Error publicando: {str(e)[:80]}", 'error')
        return None

def main():
    log("="*60)
    log("🎬 BOT DE REELS - VERSIÓN FACEBOOK")
    log(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*60)
    
    # Verificar configuración
    if not FB_ACCESS_TOKEN or not FB_PAGE_ID:
        log("❌ Faltan FB_ACCESS_TOKEN o FB_PAGE_ID", 'error')
        return False
    
    # 1. Buscar video de noticias
    video = buscar_video_noticia()
    if not video:
        return False
    
    # 2. Descargar
    video_path = descargar_video_facebook(video['id'])
    if not video_path:
        log("No se pudo descargar, intentando otro...", 'warn')
        return False
    
    # 3. Generar texto
    texto = generar_texto_reel(video['titulo'], video['pagina_origen'])
    
    # 4. Publicar
    post_id = publicar_en_mi_pagina(video_path, texto)
    
    # 5. Limpiar
    try:
        Path(video_path).unlink(missing_ok=True)
    except:
        pass
    
    if post_id:
        log("="*60)
        log("✅ REPUBLICACIÓN EXITOSA")
        log(f"📱 Post ID: {post_id}")
        log(f"🎬 {video['titulo'][:50]}...")
        log("="*60)
        return True
    
    return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"💥 Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

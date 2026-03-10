#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Reels - Verdad Hoy v7.0 (Final Simplificado)
Busca noticias en Reddit y publica videos en Facebook
"""

import os
import sys
import subprocess
import random
import re
import json
from datetime import datetime
from pathlib import Path

# ============ CONFIGURACIÓN ============
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')

TEMP_DIR = Path('/tmp/videos_bot')
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Subreddits de noticias
SUBREDDITS = ['worldnews', 'news', 'politics', 'ukrainewar', 'israel', 'gaza']

# Palabras clave para filtrar
PALABRAS_CLAVE = [
    'war', 'ukraine', 'gaza', 'israel', 'conflict', 'military', 'attack',
    'breaking', 'trump', 'biden', 'russia', 'crisis', 'president', 'video'
]

def log(msg, tipo='info'):
    iconos = {'info': 'ℹ️', 'ok': '✅', 'error': '❌', 'warn': '⚠️', 'yt': '📺', 'fb': '📘', 'reddit': '🤖'}
    hora = datetime.now().strftime('%H:%M:%S')
    print(f"[{hora}] {iconos.get(tipo, 'ℹ️')} {msg}", flush=True)

def ejecutar(cmd, timeout=30):
    """Ejecuta comando con timeout"""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        log(f"Error: {str(e)[:50]}", 'error')
        return None

def buscar_reddit():
    """Busca videos en Reddit"""
    log("🔍 Buscando en Reddit...", 'reddit')
    
    subreddit = random.choice(SUBREDDITS)
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=15"
    
    cmd = ['curl', '-s', '-A', 'Mozilla/5.0', '-H', 'Accept: application/json', url]
    result = ejecutar(cmd, timeout=15)
    
    if not result or result.returncode != 0:
        return None
    
    try:
        posts = json.loads(result.stdout).get('data', {}).get('children', [])
        
        for post in posts:
            data = post.get('data', {})
            titulo = data.get('title', '')
            url_post = data.get('url', '')
            score = data.get('score', 0)
            
            # Buscar videos de YouTube relevantes
            if score > 30 and ('youtube.com' in url_post or 'youtu.be' in url_post):
                titulo_lower = titulo.lower()
                if any(p in titulo_lower for p in PALABRAS_CLAVE):
                    # Extraer ID de YouTube
                    match = re.search(r'(?:v=|youtu\.be\/|shorts\/)([a-zA-Z0-9_-]{11})', url_post)
                    if match:
                        video_id = match.group(1)
                        log(f"✅ Encontrado: {titulo[:50]}...", 'ok')
                        return {
                            'id': video_id,
                            'titulo': titulo,
                            'fuente': f"Reddit r/{subreddit}"
                        }
        
        log("⚠️ No se encontraron videos en Reddit", 'warn')
        return None
        
    except Exception as e:
        log(f"Error parseando: {str(e)[:50]}", 'error')
        return None

def buscar_youtube_backup():
    """Respaldo: busca directo en YouTube"""
    log("🔍 Buscando en YouTube...", 'yt')
    
    terminos = ['breaking news today', 'ukraine war latest', 'gaza news today']
    termino = random.choice(terminos)
    
    cmd = [
        'yt-dlp', f'ytsearch3:{termino}',
        '--match-filter', 'duration < 300',
        '--get-id', '--get-title',
        '--dateafter', 'now-2days',
        '--quiet'
    ]
    
    result = ejecutar(cmd, timeout=25)
    
    if result and result.returncode == 0:
        lineas = result.stdout.strip().split('\n')
        if len(lineas) >= 2:
            return {
                'id': lineas[0].strip(),
                'titulo': lineas[1].strip(),
                'fuente': 'YouTube Search'
            }
    
    return None

def descargar(video_info):
    """Descarga video de YouTube"""
    video_id = video_info['id']
    url = f"https://youtube.com/watch?v={video_id}"
    output_path = TEMP_DIR / f"video_{video_id}.mp4"
    
    output_path.unlink(missing_ok=True)
    log("⬇️ Descargando...", 'yt')
    
    cmd = [
        'yt-dlp',
        '-f', 'best[height<=720][filesize<25M]/worst[filesize<25M]',
        '--max-filesize', '25M',
        '-o', str(output_path),
        '--no-playlist', '--quiet',
        '--socket-timeout', '15',
        url
    ]
    
    result = ejecutar(cmd, timeout=90)
    
    if result and result.returncode == 0 and output_path.exists():
        size = output_path.stat().st_size / (1024*1024)
        if size > 0.5:
            log(f"✅ Descargado: {size:.1f} MB", 'ok')
            return str(output_path)
    
    return None

def generar_texto(titulo, fuente):
    """Genera texto para Facebook"""
    titulo = re.sub(r'[^\w\s\-.,;:¡!¿?áéíóúÁÉÍÓÚñÑ]', '', titulo)
    if len(titulo) > 120:
        titulo = titulo[:117] + "..."
    
    intros = ["🚨 ÚLTIMA HORA", "📰 NOTICIA IMPORTANTE", "🌍 DESARROLLO"]
    cierres = ["¿Qué opinas? 👇", "Comparte 📢", "¿Impactará? 🤔"]
    
    return f"""{random.choice(intros)}

{titulo}

📡 Fuente: {fuente}

{random.choice(cierres)}

#Noticias #Actualidad #VerdadHoy"""

def publicar(video_path, texto):
    """Publica en Facebook"""
    log("📘 Publicando...", 'fb')
    
    import requests
    
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {'description': texto, 'access_token': FB_ACCESS_TOKEN}
            
            resp = requests.post(url, files=files, data=data, timeout=180)
            result = resp.json()
        
        if 'id' in result:
            log(f"✅ Publicado: {result['id']}", 'ok')
            return result['id']
        else:
            log(f"❌ Error: {result.get('error', {}).get('message', 'Error')[:60]}", 'error')
            return None
            
    except Exception as e:
        log(f"❌ Error: {str(e)[:60]}", 'error')
        return None

def limpiar():
    """Limpia archivos temporales"""
    for f in TEMP_DIR.glob("*.mp4"):
        f.unlink(missing_ok=True)

def main():
    inicio = datetime.now()
    log("="*60)
    log("🎬 BOT VERDAD HOY v7.0")
    log(f"⏰ {inicio.strftime('%H:%M:%S')}")
    log("="*60)
    
    if not FB_ACCESS_TOKEN or not FB_PAGE_ID:
        log("❌ Faltan credenciales", 'error')
        return False
    
    limpiar()
    
    # 1. Buscar video (Reddit primero, YouTube backup)
    video = buscar_reddit()
    if not video:
        video = buscar_youtube_backup()
    
    if not video:
        log("❌ No se encontró video", 'error')
        return False
    
    # 2. Descargar
    video_path = descargar(video)
    if not video_path:
        return False
    
    # 3. Generar texto y publicar
    texto = generar_texto(video['titulo'], video['fuente'])
    post_id = publicar(video_path, texto)
    
    # 4. Limpiar
    limpiar()
    
    duracion = (datetime.now() - inicio).total_seconds()
    log("="*60)
    
    if post_id:
        log(f"✅ ÉXITO en {duracion:.0f}s - ID: {post_id}", 'ok')
        return True
    else:
        log(f"❌ Falló en {duracion:.0f}s", 'error')
        return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"💥 Error: {e}", 'error')
        exit(1)

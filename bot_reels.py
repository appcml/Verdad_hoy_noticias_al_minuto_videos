#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Reels - Verdad Hoy v6.0 (Reddit + YouTube)
Busca noticias virales en Reddit y descarga videos de YouTube
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

# Subreddits de noticias y política
SUBREDDITS = [
    'worldnews', 'news', 'politics', 'internationalpolitics',
    'geopolitics', 'conflict', 'ukrainewar', 'israel', 'gaza'
]

# Palabras clave para filtrar posts relevantes
PALABRAS_CLAVE = [
    'war', 'ukraine', 'gaza', 'israel', 'conflict', 'military', 'attack',
    'breaking', 'trump', 'biden', 'russia', 'crisis', 'news', 'president',
    'election', 'politics', 'world', 'video', 'watch', 'footage'
]

def log(msg, tipo='info'):
    iconos = {
        'info': 'ℹ️', 'ok': '✅', 'error': '❌', 'warn': '⚠️', 
        'yt': '📺', 'fb': '📘', 'reddit': '🤖', 'debug': '🔍'
    }
    hora = datetime.now().strftime('%H:%M:%S')
    print(f"[{hora}] {iconos.get(tipo, 'ℹ️')} {msg}", flush=True)

def ejecutar_comando(cmd, timeout=30):
    """Ejecuta comando con timeout"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result
    except subprocess.TimeoutExpired:
        log("⏰ Timeout", 'error')
        return None
    except Exception as e:
        log(f"❌ Error: {str(e)[:60]}", 'error')
        return None

def obtener_posts_reddit():
    """Obtiene posts hot de Reddit usando curl (sin API)"""
    log("🔍 Buscando noticias en Reddit...", 'reddit')
    
    subreddit = random.choice(SUBREDDITS)
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=25"
    
    cmd = [
        'curl', '-s', '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        '-H', 'Accept: application/json',
        url
    ]
    
    result = ejecutar_comando(cmd, timeout=15)
    
    if not result or result.returncode != 0:
        log(f"❌ Error conectando a Reddit", 'error')
        return []
    
    try:
        data = json.loads(result.stdout)
        posts = data.get('data', {}).get('children', [])
        
        videos_encontrados = []
        
        for post in posts:
            post_data = post.get('data', {})
            titulo = post_data.get('title', '')
            url_post = post_data.get('url', '')
            permalink = post_data.get('permalink', '')
            score = post_data.get('score', 0)
            
            # Verificar si es contenido relevante
            titulo_lower = titulo.lower()
            es_relevante = any(palabra in titulo_lower for palabra in PALABRAS_CLAVE)
            
            if es_relevante and score > 50:  # Más de 50 upvotes
                # Buscar si tiene video de YouTube
                if 'youtube.com' in url_post or 'youtu.be' in url_post:
                    videos_encontrados.append({
                        'titulo': titulo,
                        'url': url_post,
                        'score': score,
                        'subreddit': subreddit,
                        'reddit_url': f"https://reddit.com{permalink}"
                    })
                    log(f"  🎬 {titulo[:60]}... (Score: {score})", 'ok')
        
        log(f"✅ {len(videos_encontrados)} videos encontrados en r/{subreddit}", 'ok')
        return videos_encontrados
        
    except Exception as e:
        log(f"❌ Error parseando Reddit: {str(e)[:60]}", 'error')
        return []

def extraer_video_id(url):
    """Extrae ID de video de YouTube de una URL"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def buscar_video():
    """Busca video en Reddit y extrae info de YouTube"""
    posts = obtener_posts_reddit()
    
    if not posts:
        log("⚠️ No se encontraron posts, intentando método directo...", 'warn')
        return buscar_youtube_directo()
    
    # Ordenar por score (más populares primero)
    posts.sort(key=lambda x: x['score'], reverse=True)
    
    for post in posts[:5]:  # Probar los 5 más populares
        video_id = extraer_video_id(post['url'])
        
        if video_id:
            log(f"✅ Video seleccionado: {post['titulo'][:60]}...", 'ok')
            return {
                'id': video_id,
                'titulo': post['titulo'],
                'url': f'https://youtube.com/watch?v={video_id}',
                'fuente': f"Reddit r/{post['subreddit']}"
            }
    
    log("⚠️ Ningún post tenía video de YouTube válido", 'warn')
    return buscar_youtube_directo()

def buscar_youtube_directo():
    """Método de respaldo: busca en YouTube directamente"""
    log("🔍 Buscando directamente en YouTube...", 'yt')
    
    # Términos de búsqueda de noticias recientes
    terminos = [
        'breaking news today',
        'world news latest',
        'ukraine war latest',
        'gaza news today',
        'trump news today'
    ]
    
    termino = random.choice(terminos)
    
    cmd = [
        'yt-dlp',
        f'ytsearch5:{termino}',
        '--match-filter', 'duration < 300',  # Menos de 5 min
        '--get-id', '--get-title',
        '--dateafter', 'now-2days',
        '--quiet', '--no-warnings'
    ]
    
    result = ejecutar_comando(cmd, timeout=30)
    
    if not result or result.returncode != 0:
        return None
    
    lineas = result.stdout.strip().split('\n')
    if len(lineas) >= 2:
        video_id = lineas[0].strip()
        titulo = lineas[1].strip()
        
        if len(video_id) == 11:
            log(f"✅ Encontrado (directo): {titulo[:60]}...", 'ok')
            return {
                'id': video_id,
                'titulo': titulo,
                'url': f'https://youtube.com/watch?v={video_id}',
                'fuente': 'YouTube Search'
            }
    
    return None

def descargar_video(video_info):
    """Descarga el video de YouTube"""
    video_id = video_info['id']
    url = video_info['url']
    output_path = TEMP_DIR / f"video_{video_id}.mp4"
    
    output_path.unlink(missing_ok=True)
    
    log(f"⬇️ Descargando video...", 'yt')
    
    # Primero verificar si es un Short (formato diferente)
    cmd_info = ['yt-dlp', '--print', 'duration', url, '--quiet']
    result_info = ejecutar_comando(cmd_info, timeout=10)
    
    # Elegir formato según duración
    if result_info and result_info.stdout.strip():
        try:
            duracion = int(float(result_info.stdout.strip()))
            if duracion <= 60:
                # Short - usar formato específico
                formato = 'best[height<=1080][filesize<20M]'
                log(f"  📱 Detectado Short ({duracion}s)", 'info')
            else:
                # Video normal
                formato = 'best[height<=720][filesize<30M]'
                log(f"  🎥 Video normal ({duracion}s)", 'info')
        except:
            formato = 'best[filesize<30M]'
    else:
        formato = 'best[filesize<30M]'
    
    cmd = [
        'yt-dlp',
        '-f', formato,
        '--max-filesize', '30M',
        '-o', str(output_path),
        '--no-playlist', '--quiet', '--no-warnings',
        '--socket-timeout', '15',
        '--retries', '2',
        url
    ]
    
    result = ejecutar_comando(cmd, timeout=90)
    
    if result and result.returncode == 0 and output_path.exists():
        size_mb = output_path.stat().st_size / (1024*1024)
        if size_mb > 0.5:
            log(f"✅ Descargado: {size_mb:.1f} MB", 'ok')
            return str(output_path)
    
    log("❌ Error descargando video", 'error')
    return None

def generar_texto(titulo, fuente):
    """Genera texto atractivo para Facebook"""
    # Limpiar título
    titulo_limpio = re.sub(r'[^\w\s\-.,;:¡!¿?áéíóúÁÉÍÓÚñÑ]', '', titulo)
    if len(titulo_limpio) > 130:
        titulo_limpio = titulo_limpio[:127] + "..."
    
    intros = [
        "🚨 ÚLTIMA HORA", "📰 NOTICIA IMPORTANTE", 
        "🌍 DESARROLLO INTERNACIONAL", "⚡ INFORMACIÓN RELEVANTE"
    ]
    
    cierres = [
        "¿Qué opinas? Comenta 👇",
        "Comparte esta información 📢",
        "¿Crees que esto tendrá impacto? 🤔",
        "Mantente informado con Verdad Hoy 📱"
    ]
    
    texto = f"""{random.choice(intros)}

{titulo_limpio}

📡 Fuente: {fuente}

{random.choice(cierres)}

#Noticias #Actualidad #ÚltimaHora #VerdadHoy #NoticiasAlMinuto"""
    
    return texto[:1990]

def publicar_facebook(video_path, texto):
    """Publica el video en Facebook"""
    log("📘 Publicando en Facebook...", 'fb')
    
    import requests
    
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {
                'description': texto,
                'access_token': FB_ACCESS_TOKEN
            }
            
            resp = requests.post(url, files=files, data=data, timeout=180)
            result = resp.json()
        
        if 'id' in result:
            log(f"✅ ¡PUBLICADO! ID: {result['id']}", 'ok')
            return result['id']
        else:
            error = result.get('error', {}).get('message', 'Error desconocido')
            log(f"❌ Error Facebook: {error[:100]}", 'error')
            return None
            
    except Exception as e:
        log(f"❌ Error: {str(e)[:80]}", 'error')
        return None

def limpiar():
    """Limpia archivos temporales"""
    try:
        for f in TEMP_DIR.glob("*.mp4"):
            f.unlink(missing_ok=True)
    except:
        pass

def main():
    inicio = datetime.now()
    log("="*60)
    log("🎬 BOT VERDAD HOY v6.0 - Reddit + YouTube")
    log(f"⏰ {inicio.strftime('%H:%M:%S')}")
    log("="*60)
    
    # Verificar configuración
    if not FB_ACCESS_TOKEN or not FB_PAGE_ID:
        log("❌ Faltan FB_ACCESS_TOKEN o FB_PAGE_ID", 'error')
        return False
    
    limpiar()
    
    # 1. Buscar video (Reddit primero, YouTube como respaldo)
    video = buscar_video()
    if not video:
        log("❌ No se pudo encontrar ningún video", 'error')
        return False
    
    # 2. Descargar
    video_path = descargar_video(video)
    if not video_path:
        return False
    
    # 3. Generar texto
    texto = generar_texto(video['titulo'], video['fuente'])
    
    # 4. Publicar
    post_id = publicar_facebook(video_path, texto)
    
    # 5. Limpiar
    limpiar()
    
    # Resumen
    duracion = (datetime.now() - inicio).total_seconds()
    log("="*60)
    
    if post_id:
        log(f"✅ ÉXITO en {duracion:.0f} segundos", 'ok')
        log(f"📱 Post ID: {post_id}")
        log(f"🎬 {video['titulo'][:50]}...")
        log("="*60)
        return True
    else:
        log(f"❌ Falló después de {duracion:.0f}s", 'error')
        return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"💥 Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Reels - Verdad Hoy v5.0
Busca y republica videos de noticias de YouTube a Facebook
"""

import os
import sys
import subprocess
import random
import re
from datetime import datetime
from pathlib import Path

# ============ CONFIGURACIÓN ============
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')

# Carpeta temporal para videos
TEMP_DIR = Path('/tmp/videos_bot')
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Canales de YouTube de noticias (conflictos, política, actualidad)
CANALES_NOTICIAS = [
    'UC16niRr50-MSBwiO3YDb3RA',  # BBC News
    'UCupvZG-5ko_eiXAupbDfxWw',  # CNN
    'UChqUTb7kYRX8-EiaN3XFrSQ',  # Reuters
    'UCIvaYmXn910QMdemBG3v1pQ',  # Al Jazeera English
    'UCQfwfsi5VrQ8yKZ-UWmAEFg',  # France 24 English
    'UC4w_5ubHH91xYoqRxC9LAzw',  # DW News
    'UCoMdktPbSTixAyNGwb-UYkQ',  # Sky News
    'UCBi2mrWuNuyYy4gbM6fU18Q',  # ABC News
]

# Palabras clave para filtrar contenido relevante
PALABRAS_CLAVE = [
    'war', 'ukraine', 'gaza', 'israel', 'conflict', 'military', 'attack',
    'breaking', 'president', 'election', 'trump', 'biden', 'russia',
    'crisis', 'protest', 'sanctions', 'nato', 'china', 'iran'
]

def log(msg, tipo='info'):
    iconos = {'info': 'ℹ️', 'ok': '✅', 'error': '❌', 'warn': '⚠️', 'yt': '📺', 'fb': '📘'}
    hora = datetime.now().strftime('%H:%M:%S')
    print(f"[{hora}] {iconos.get(tipo, 'ℹ️')} {msg}", flush=True)

def buscar_video_youtube():
    """Busca un video reciente de noticias en YouTube"""
    log("🔍 Buscando video de noticias en YouTube...", 'yt')
    
    # Seleccionar canal aleatorio
    canal = random.choice(CANALES_NOTICIAS)
    
    # Comando yt-dlp para listar videos recientes
    cmd = [
        'yt-dlp',
        f'https://www.youtube.com/channel/{canal}/videos',
        '--playlist-end', '10',  # Revisar últimos 10 videos
        '--match-filter', 'duration < 300',  # Menos de 5 minutos
        '--get-id', '--get-title', '--get-duration',
        '--dateafter', 'now-2days',  # Solo últimos 2 días
        '--quiet'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0 or not result.stdout.strip():
            log("No se encontraron videos recientes, probando otro canal...", 'warn')
            return buscar_video_youtube()
        
        # Parsear resultados
        lineas = result.stdout.strip().split('\n')
        videos = []
        
        for i in range(0, len(lineas), 3):
            if i+2 < len(lineas):
                video_id = lineas[i].strip()
                titulo = lineas[i+1].strip()
                duracion = lineas[i+2].strip()
                
                # Verificar si es contenido relevante
                titulo_lower = titulo.lower()
                es_relevante = any(palabra in titulo_lower for palabra in PALABRAS_CLAVE)
                
                if es_relevante and len(video_id) == 11:  # ID válido de YouTube
                    videos.append({
                        'id': video_id,
                        'titulo': titulo,
                        'duracion': duracion,
                        'url': f'https://youtube.com/watch?v={video_id}'
                    })
        
        if not videos:
            log("No se encontraron videos relevantes, probando otro canal...", 'warn')
            return buscar_video_youtube()
        
        # Seleccionar el más relevante (primero de la lista)
        video = videos[0]
        log(f"✅ Video encontrado: {video['titulo'][:60]}...", 'ok')
        return video
        
    except Exception as e:
        log(f"Error buscando: {str(e)[:80]}", 'error')
        return None

def descargar_video(video_id):
    """Descarga el video de YouTube"""
    url = f"https://youtube.com/watch?v={video_id}"
    output_path = TEMP_DIR / f"video_{video_id}.mp4"
    
    log("⬇️ Descargando video...", 'yt')
    
    cmd = [
        'yt-dlp',
        '-f', 'best[height<=720][filesize<50M]/best[filesize<50M]',
        '--max-filesize', '50M',
        '-o', str(output_path),
        '--no-playlist',
        '--quiet',
        '--no-warnings',
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            log(f"Error descargando: {result.stderr[:100]}", 'error')
            return None
        
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024*1024)
            log(f"✅ Descargado: {size_mb:.1f} MB", 'ok')
            return str(output_path)
        
        return None
        
    except Exception as e:
        log(f"Error: {str(e)[:80]}", 'error')
        return None

def generar_texto(titulo_original):
    """Genera texto atractivo para Facebook"""
    # Limpiar título
    titulo = re.sub(r'[^\w\s\-.,;:¡!¿?áéíóúÁÉÍÓÚñÑ]', '', titulo_original)
    
    if len(titulo) > 120:
        titulo = titulo[:117] + "..."
    
    intros = [
        "🚨 ÚLTIMA HORA",
        "📰 NOTICIA IMPORTANTE",
        "🌍 DESARROLLO INTERNACIONAL",
        "⚡ INFORMACIÓN RELEVANTE",
    ]
    
    cierres = [
        "¿Qué opinas? Déjanos tu comentario 👇",
        "Comparte esta información 📢",
        "¿Crees que esto afectará la situación? 🤔",
    ]
    
    texto = f"""{random.choice(intros)}

{titulo}

{random.choice(cierres)}

#Noticias #Actualidad #ÚltimaHora #VerdadHoy #NoticiasAlMinuto"""
    
    return texto[:1990]

def publicar_en_facebook(video_path, texto):
    """Publica el video en la página de Facebook"""
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
            
            resp = requests.post(url, files=files, data=data, timeout=300)
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

def limpiar_temp():
    """Limpia archivos temporales antiguos"""
    try:
        for f in TEMP_DIR.glob("*.mp4"):
            f.unlink(missing_ok=True)
    except:
        pass

def main():
    log("="*60)
    log("🎬 BOT VERDAD HOY - YouTube → Facebook")
    log(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*60)
    
    # Verificar configuración
    if not FB_ACCESS_TOKEN or not FB_PAGE_ID:
        log("❌ Faltan FB_ACCESS_TOKEN o FB_PAGE_ID", 'error')
        return False
    
    limpiar_temp()
    
    # 1. Buscar video
    video = buscar_video_youtube()
    if not video:
        log("❌ No se pudo encontrar video", 'error')
        return False
    
    # 2. Descargar
    video_path = descargar_video(video['id'])
    if not video_path:
        return False
    
    # 3. Generar texto
    texto = generar_texto(video['titulo'])
    
    # 4. Publicar
    post_id = publicar_en_facebook(video_path, texto)
    
    # 5. Limpiar
    limpiar_temp()
    
    if post_id:
        log("="*60)
        log("✅ ¡PROCESO COMPLETADO EXITOSAMENTE!")
        log(f"📱 Post ID: {post_id}")
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

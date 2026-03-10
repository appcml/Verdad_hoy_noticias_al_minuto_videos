#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Reels - Verdad Hoy v5.2 (Con diagnóstico y URLs de canales corregidas)
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

TEMP_DIR = Path('/tmp/videos_bot')
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# URLs de canales de noticias (formato correcto para yt-dlp)
CANALES_NOTICIAS = [
    'https://www.youtube.com/@BBCNews/videos',
    'https://www.youtube.com/@CNN/videos',
    'https://www.youtube.com/@Reuters/videos',
    'https://www.youtube.com/@France24English/videos',
    'https://www.youtube.com/@SkyNews/videos',
    'https://www.youtube.com/@ABCNews/videos',
]

PALABRAS_CLAVE = [
    'war', 'ukraine', 'gaza', 'israel', 'conflict', 'military', 'attack',
    'breaking', 'trump', 'biden', 'russia', 'crisis', 'news', 'president',
    'election', 'politics', 'world', 'international'
]

def log(msg, tipo='info'):
    iconos = {'info': 'ℹ️', 'ok': '✅', 'error': '❌', 'warn': '⚠️', 'yt': '📺', 'fb': '📘', 'debug': '🔍'}
    hora = datetime.now().strftime('%H:%M:%S')
    print(f"[{hora}] {iconos.get(tipo, 'ℹ️')} {msg}", flush=True)

def ejecutar_comando(cmd, timeout=30):
    """Ejecuta comando y retorna resultado"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result
    except subprocess.TimeoutExpired:
        log("⏰ Timeout", 'error')
        return None
    except Exception as e:
        log(f"❌ Error: {str(e)[:60]}", 'error')
        return None

def buscar_video_youtube():
    """Busca video en YouTube con diagnóstico detallado"""
    log("🔍 Iniciando búsqueda en YouTube...", 'yt')
    
    # Mezclar canales para variar
    canales = CANALES_NOTICIAS.copy()
    random.shuffle(canales)
    
    for canal_url in canales[:3]:  # Probar máximo 3 canales
        log(f"📺 Revisando: {canal_url.split('/')[-2]}", 'yt')
        
        # Comando para obtener últimos videos (sin filtros estrictos primero)
        cmd = [
            'yt-dlp',
            canal_url,
            '--playlist-end', '5',
            '--get-id', '--get-title', '--get-duration',
            '--dateafter', 'now-3days',  # Últimos 3 días
            '--quiet', '--no-warnings'
        ]
        
        result = ejecutar_comando(cmd, timeout=25)
        
        if not result:
            log("  ⚠️ No respuesta del canal", 'warn')
            continue
            
        if result.returncode != 0:
            log(f"  ⚠️ Error yt-dlp: {result.stderr[:100]}", 'warn')
            continue
        
        if not result.stdout.strip():
            log("  ⚠️ Canal sin videos recientes", 'warn')
            continue
        
        lineas = result.stdout.strip().split('\n')
        log(f"  ✅ Encontrados {len(lineas)//3} videos", 'ok')
        
        # Mostrar los videos encontrados (para diagnóstico)
        for i in range(0, min(len(lineas), 15), 3):
            if i+2 >= len(lineas):
                continue
            video_id = lineas[i].strip()
            titulo = lineas[i+1].strip()
            duracion = lineas[i+2].strip()
            log(f"     🎬 {titulo[:50]}... ({duracion})", 'debug')
            
            # Verificar palabras clave
            titulo_lower = titulo.lower()
            if any(palabra in titulo_lower for palabra in PALABRAS_CLAVE):
                if len(video_id) == 11:
                    log(f"  ✅ VIDEO RELEVANTE: {titulo[:60]}", 'ok')
                    return {
                        'id': video_id,
                        'titulo': titulo,
                        'url': f'https://youtube.com/watch?v={video_id}'
                    }
        
        log("  ⚠️ Ningún video coincidió con palabras clave", 'warn')
    
    log("❌ No se encontró video relevante en ningún canal", 'error')
    return None

def descargar_video(video_info):
    """Descarga el video"""
    video_id = video_info['id']
    url = video_info['url']
    output_path = TEMP_DIR / f"video_{video_id}.mp4"
    
    output_path.unlink(missing_ok=True)
    
    log(f"⬇️ Descargando: {video_info['titulo'][:50]}...", 'yt')
    
    cmd = [
        'yt-dlp',
        '-f', 'best[height<=720][filesize<30M]/worst[filesize<30M]',
        '--max-filesize', '30M',
        '-o', str(output_path),
        '--no-playlist', '--quiet', '--no-warnings',
        '--socket-timeout', '15',
        '--retries', '2',
        url
    ]
    
    result = ejecutar_comando(cmd, timeout=60)
    
    if result and result.returncode == 0 and output_path.exists():
        size_mb = output_path.stat().st_size / (1024*1024)
        if size_mb > 0.5:
            log(f"✅ Descargado: {size_mb:.1f} MB", 'ok')
            return str(output_path)
    
    log("❌ Error en descarga", 'error')
    return None

def generar_texto(titulo):
    """Genera texto para Facebook"""
    titulo_limpio = re.sub(r'[^\w\s\-.,;:¡!¿?áéíóúÁÉÍÓÚñÑ]', '', titulo)
    if len(titulo_limpio) > 120:
        titulo_limpio = titulo_limpio[:117] + "..."
    
    intros = ["🚨 ÚLTIMA HORA", "📰 NOTICIA IMPORTANTE", "🌍 DESARROLLO"]
    cierres = ["¿Qué opinas? 👇", "Comparte 📢", "¿Impactará? 🤔"]
    
    return f"""{random.choice(intros)}

{titulo_limpio}

{random.choice(cierres)}

#Noticias #Actualidad #VerdadHoy"""

def publicar_facebook(video_path, texto):
    """Publica en Facebook"""
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
            
            resp = requests.post(url, files=files, data=data, timeout=120)
            result = resp.json()
        
        if 'id' in result:
            log(f"✅ ¡PUBLICADO! ID: {result['id']}", 'ok')
            return result['id']
        else:
            error = result.get('error', {}).get('message', 'Error desconocido')
            log(f"❌ Facebook error: {error[:100]}", 'error')
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
    log("🎬 BOT VERDAD HOY v5.2")
    log(f"⏰ {inicio.strftime('%H:%M:%S')}")
    log("="*60)
    
    # Verificar credenciales
    if not FB_ACCESS_TOKEN:
        log("❌ Falta FB_ACCESS_TOKEN", 'error')
        return False
    if not FB_PAGE_ID:
        log("❌ Falta FB_PAGE_ID", 'error')
        return False
    
    log("✅ Credenciales OK", 'ok')
    limpiar()
    
    # 1. Buscar video
    video = buscar_video_youtube()
    if not video:
        log("💡 Sugerencia: Las palabras clave pueden ser muy restrictivas", 'warn')
        log("💡 Intentando búsqueda más amplia...", 'info')
        
        # Segundo intento con palabras clave más amplias
        global PALABRAS_CLAVE
        PALABRAS_CLAVE = ['news', 'breaking', 'world', 'today', 'latest']
        video = buscar_video_youtube()
        
        if not video:
            return False
    
    # 2. Descargar
    video_path = descargar_video(video)
    if not video_path:
        return False
    
    # 3. Generar texto
    texto = generar_texto(video['titulo'])
    
    # 4. Publicar
    post_id = publicar_facebook(video_path, texto)
    
    # 5. Limpiar
    limpiar()
    
    # Resumen
    duracion = (datetime.now() - inicio).total_seconds()
    log("="*60)
    
    if post_id:
        log(f"✅ ÉXITO en {duracion:.0f}s - Post: {post_id}", 'ok')
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

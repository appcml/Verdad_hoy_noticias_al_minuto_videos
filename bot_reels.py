#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Reels - Verdad Hoy v5.1 (Optimizado)
YouTube → Facebook con timeouts estrictos
"""

import os
import sys
import subprocess
import random
import re
import signal
from datetime import datetime
from pathlib import Path

# ============ CONFIGURACIÓN ============
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')

TEMP_DIR = Path('/tmp/videos_bot')
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Timeouts estrictos (segundos)
TIMEOUT_BUSQUEDA = 20      # Máximo 20 segundos buscando
TIMEOUT_DESCARGA = 60      # Máximo 60 segundos descargando
TIMEOUT_PUBLICACION = 90   # Máximo 90 segundos publicando

# Canales de YouTube simplificados (los más confiables)
CANALES_NOTICIAS = [
    'UC16niRr50-MSBwiO3YDb3RA',  # BBC News
    'UCupvZG-5ko_eiXAupbDfxWw',  # CNN
    'UChqUTb7kYRX8-EiaN3XFrSQ',  # Reuters
    'UCQfwfsi5VrQ8yKZ-UWmAEFg',  # France 24
]

PALABRAS_CLAVE = [
    'war', 'ukraine', 'gaza', 'israel', 'conflict', 'military',
    'breaking', 'trump', 'biden', 'russia', 'crisis', 'attack'
]

def log(msg, tipo='info'):
    iconos = {'info': 'ℹ️', 'ok': '✅', 'error': '❌', 'warn': '⚠️', 'yt': '📺', 'fb': '📘'}
    hora = datetime.now().strftime('%H:%M:%S')
    print(f"[{hora}] {iconos.get(tipo, 'ℹ️')} {msg}", flush=True)

def ejecutar_comando(cmd, timeout, descripcion):
    """Ejecuta comando con timeout estricto"""
    log(f"⏱️ {descripcion} (max {timeout}s)...")
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        return result
    except subprocess.TimeoutExpired:
        log(f"⏰ Timeout en {descripcion}", 'error')
        return None
    except Exception as e:
        log(f"❌ Error en {descripcion}: {str(e)[:60]}", 'error')
        return None

def buscar_video_rapido():
    """Busca video con timeout estricto"""
    log("🔍 Buscando video...", 'yt')
    
    canal = random.choice(CANALES_NOTICIAS)
    
    # Comando simplificado y rápido
    cmd = [
        'yt-dlp',
        f'https://www.youtube.com/channel/{canal}/videos',
        '--playlist-end', '5',
        '--match-filter', 'duration < 180',  # Máximo 3 minutos
        '--get-id', '--get-title',
        '--dateafter', 'now-1day',  # Solo últimas 24 horas
        '--quiet', '--no-warnings'
    ]
    
    result = ejecutar_comando(cmd, TIMEOUT_BUSQUEDA, "búsqueda YouTube")
    
    if not result or result.returncode != 0:
        return None
    
    lineas = result.stdout.strip().split('\n')
    if len(lineas) < 2:
        return None
    
    # Tomar el primer video encontrado (más reciente)
    for i in range(0, min(len(lineas), 10), 2):
        if i+1 >= len(lineas):
            continue
            
        video_id = lineas[i].strip()
        titulo = lineas[i+1].strip()
        
        # Verificar relevancia
        titulo_lower = titulo.lower()
        if any(palabra in titulo_lower for palabra in PALABRAS_CLAVE):
            if len(video_id) == 11:
                log(f"✅ Encontrado: {titulo[:50]}...", 'ok')
                return {
                    'id': video_id,
                    'titulo': titulo,
                    'url': f'https://youtube.com/watch?v={video_id}'
                }
    
    log("⚠️ No encontrado relevante", 'warn')
    return None

def descargar_video_rapido(video_id):
    """Descarga con formato optimizado"""
    url = f"https://youtube.com/watch?v={video_id}"
    output_path = TEMP_DIR / f"video_{video_id}.mp4"
    
    # Eliminar si existe
    output_path.unlink(missing_ok=True)
    
    cmd = [
        'yt-dlp',
        '-f', 'worst[height>=360][filesize<20M]/best[filesize<20M]',  # Más pequeño posible
        '--max-filesize', '20M',
        '-o', str(output_path),
        '--no-playlist', '--quiet', '--no-warnings',
        '--socket-timeout', '10',
        '--retries', '1',
        url
    ]
    
    result = ejecutar_comando(cmd, TIMEOUT_DESCARGA, "descarga")
    
    if result and result.returncode == 0 and output_path.exists():
        size_mb = output_path.stat().st_size / (1024*1024)
        if size_mb > 0.5:  # Mínimo 500KB
            log(f"✅ Descargado: {size_mb:.1f} MB", 'ok')
            return str(output_path)
    
    return None

def generar_texto(titulo):
    """Texto rápido y efectivo"""
    titulo_limpio = re.sub(r'[^\w\s\-.,;:¡!¿?áéíóúÁÉÍÓÚñÑ]', '', titulo)
    if len(titulo_limpio) > 100:
        titulo_limpio = titulo_limpio[:97] + "..."
    
    intros = ["🚨 ÚLTIMA HORA", "📰 NOTICIA IMPORTANTE", "🌍 DESARROLLO"]
    cierres = ["¿Qué opinas? 👇", "Comparte 📢", "¿Impactará? 🤔"]
    
    return f"""{random.choice(intros)}

{titulo_limpio}

{random.choice(cierres)}

#Noticias #Actualidad #VerdadHoy"""

def publicar_rapido(video_path, texto):
    """Publicación con timeout"""
    log("📘 Publicando...", 'fb')
    
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    # Configurar session con timeouts
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=1)
    session.mount('https://', adapter)
    
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {'description': texto, 'access_token': FB_ACCESS_TOKEN}
            
            resp = session.post(
                url, 
                files=files, 
                data=data, 
                timeout=TIMEOUT_PUBLICACION
            )
            result = resp.json()
        
        if 'id' in result:
            log(f"✅ Publicado: {result['id']}", 'ok')
            return result['id']
        else:
            error = result.get('error', {}).get('message', 'Error')
            log(f"❌ Facebook: {error[:80]}", 'error')
            return None
            
    except requests.Timeout:
        log("⏰ Timeout subiendo a Facebook", 'error')
        return None
    except Exception as e:
        log(f"❌ Error: {str(e)[:80]}", 'error')
        return None

def limpiar():
    """Limpieza rápida"""
    try:
        for f in TEMP_DIR.glob("*.mp4"):
            f.unlink(missing_ok=True)
    except:
        pass

def main():
    inicio = datetime.now()
    log("="*50)
    log("🎬 BOT VERDAD HOY - Iniciando")
    log(f"⏰ {inicio.strftime('%H:%M:%S')}")
    log("="*50)
    
    if not FB_ACCESS_TOKEN or not FB_PAGE_ID:
        log("❌ Faltan credenciales", 'error')
        return False
    
    limpiar()
    
    # 1. Buscar (máx 20s)
    video = buscar_video_rapido()
    if not video:
        log("❌ No se encontró video", 'error')
        return False
    
    # 2. Descargar (máx 60s)
    video_path = descargar_video_rapido(video['id'])
    if not video_path:
        log("❌ No se pudo descargar", 'error')
        return False
    
    # 3. Generar texto (<1s)
    texto = generar_texto(video['titulo'])
    
    # 4. Publicar (máx 90s)
    post_id = publicar_rapido(video_path, texto)
    
    # 5. Limpiar
    limpiar()
    
    # Resumen
    fin = datetime.now()
    duracion = (fin - inicio).total_seconds()
    log("="*50)
    
    if post_id:
        log(f"✅ ÉXITO en {duracion:.0f} segundos")
        log(f"📱 Post: {post_id}")
        return True
    else:
        log(f"❌ Falló después de {duracion:.0f} segundos")
        return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"💥 Error crítico: {e}", 'error')
        exit(1)

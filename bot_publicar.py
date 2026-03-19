#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Descargador de Videos - V2.0 (Anti-Detección Mejorada)
Descarga videos de YouTube con rotación de agents, delays y reintentos
"""

import os
import sys
import re
import json
import subprocess
import shutil
import base64
import random
import time
from datetime import datetime
from pathlib import Path

# Rotación de User-Agents realistas
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0'
]

# Headers adicionales para parecer navegador real
ACCEPT_LANGUAGES = ['en-US,en;q=0.9', 'es-ES,es;q=0.9,en;q=0.8', 'en-GB,en;q=0.9']
ACCEPT_HEADERS = [
    'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
]

# CONFIGURACIÓN
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
YT_COOKIES_B64 = os.getenv('YT_COOKIES')

CARPETA_DESCARGAS = os.getenv('CARPETA_VIDEOS', 'videos_pendientes')
MAX_VIDEOS_POR_EJECUCION = int(os.getenv('MAX_VIDEOS', '3'))  # Reducido para no saturar
MAX_TAMANO_MB = int(os.getenv('MAX_TAMANO_MB', '100'))
DELAY_MIN = int(os.getenv('DELAY_MIN', '5'))   # Segundos mínimo entre descargas
DELAY_MAX = int(os.getenv('DELAY_MAX', '15'))  # Segundos máximo entre descargas
MAX_REINTENTOS = int(os.getenv('MAX_REINTENTOS', '3'))

Path(CARPETA_DESCARGAS).mkdir(parents=True, exist_ok=True)

# Archivo de estado para tracking
ESTADO_PATH = os.path.join(CARPETA_DESCARGAS, '.estado_descargas.json')

# =============================================================================
# LOGGING
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍'}
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {iconos.get(tipo, 'ℹ️')} {mensaje}")

# =============================================================================
# ESTADO Y CONTROL DE FLUJO
# =============================================================================

def cargar_estado():
    """Carga estado anterior para evitar descargas duplicadas entre ejecuciones"""
    if os.path.exists(ESTADO_PATH):
        try:
            with open(ESTADO_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {'videos_descargados': [], 'ultima_ejecucion': None, 'errores_consecutivos': 0}

def guardar_estado(estado):
    """Guarda estado actual"""
    estado['ultima_ejecucion'] = datetime.now().isoformat()
    with open(ESTADO_PATH, 'w', encoding='utf-8') as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)

def ya_descargado_estado(estado, video_id):
    """Verifica si ya fue descargado en ejecuciones previas"""
    return video_id in estado.get('videos_descargados', [])

# =============================================================================
# ANTI-DETECCIÓN: CONFIGURACIÓN DINÁMICA
# =============================================================================

def obtener_config_aleatoria():
    """Genera configuración aleatoria para cada descarga"""
    return {
        'user_agent': random.choice(USER_AGENTS),
        'accept_lang': random.choice(ACCEPT_LANGUAGES),
        'accept': random.choice(ACCEPT_HEADERS),
        'delay': random.randint(DELAY_MIN, DELAY_MAX)
    }

def preparar_cookies():
    """Prepara archivo de cookies desde base64 con validación"""
    if not YT_COOKIES_B64:
        log("No hay cookies configuradas", 'advertencia')
        return None

    try:
        cookies_content = base64.b64decode(YT_COOKIES_B64).decode('utf-8')

        # Validar formato Netscape
        if 'youtube.com' not in cookies_content and 'google.com' not in cookies_content:
            log("Cookies parecen inválidas (no contienen dominios de Google)", 'advertencia')

        cookies_path = os.path.join(CARPETA_DESCARGAS, f'.cookies_{random.randint(1000,9999)}.txt')

        with open(cookies_path, 'w', encoding='utf-8') as f:
            f.write(cookies_content)

        return cookies_path
    except Exception as e:
        log(f"Error cookies: {e}", 'error')
        return None

def limpiar_cookies_temporales():
    """Limpia archivos de cookies temporales"""
    for f in os.listdir(CARPETA_DESCARGAS):
        if f.startswith('.cookies_') and f.endswith('.txt'):
            try:
                os.remove(os.path.join(CARPETA_DESCARGAS, f))
            except:
                pass

# =============================================================================
# BÚSQUEDA DE VIDEOS (con filtros mejorados)
# =============================================================================

def buscar_videos_noticias():
    """Busca videos de noticias con queries rotativas"""
    if not YOUTUBE_API_KEY:
        log("ERROR: YOUTUBE_API_KEY no configurada", 'error')
        return []

    videos = []

    # Queries rotativas para variedad y evitar patrones
    queries_sets = [
        ["noticias internacionales ultima hora", "breaking news today"],
        ["world news now", "conflict news video"],
        ["war footage news", "international news today"],
        ["geopolitics news", "global conflicts update"],
        ["military news today", "political crisis news"]
    ]

    queries = random.choice(queries_sets)

    for query in queries:
        try:
            # Delay aleatorio entre búsquedas
            time.sleep(random.uniform(1, 3))

            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'videoDuration': 'short',  # < 4 minutos
                'order': 'date',
                'maxResults': 15,  # Más resultados para filtrar
                'key': YOUTUBE_API_KEY,
                'publishedAfter': (datetime.now().replace(hour=0, minute=0, second=0)).isoformat() + "Z"
            }

            import requests
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()

            if 'items' in data:
                for item in data['items']:
                    video_id = item['id']['videoId']
                    snippet = item['snippet']

                    # Filtros de calidad
                    titulo = snippet.get('title', '')

                    # Excluir videos de baja calidad o irrelevantes
                    palabras_excluir = ['reaction', 'react', 'gameplay', 'minecraft', 'fortnite', 
                                       'tutorial', 'unboxing', 'review', 'vs', 'versus']
                    if any(p in titulo.lower() for p in palabras_excluir):
                        continue

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

    # Eliminar duplicados y mezclar aleatoriamente
    vistos = set()
    unicos = []
    for v in videos:
        if v['video_id'] not in vistos:
            vistos.add(v['video_id'])
            unicos.append(v)

    random.shuffle(unicos)  # Mezclar para no siempre tomar los mismos

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
# DESCARGA CON ANTI-DETECCIÓN
# =============================================================================

def verificar_yt_dlp():
    """Verifica yt-dlp y actualiza si es necesario"""
    try:
        # Verificar versión
        result = subprocess.run(['yt-dlp', '--version'], 
                              capture_output=True, text=True, timeout=10)
        version = result.stdout.strip()
        log(f"yt-dlp versión: {version}", 'info')

        # Actualizar cada cierto tiempo (opcional)
        if random.random() < 0.1:  # 10% de probabilidad
            log("Verificando actualizaciones de yt-dlp...", 'info')
            subprocess.run(['yt-dlp', '-U'], capture_output=True, timeout=30)

        return True
    except Exception as e:
        log(f"yt-dlp no instalado o error: {e}", 'error')
        return False

def ya_descargado(video_id):
    """Verifica si el video ya existe en la carpeta"""
    patron = os.path.join(CARPETA_DESCARGAS, f"*{video_id}*")
    import glob
    existe = glob.glob(patron)
    if existe:
        return True

    json_path = os.path.join(CARPETA_DESCARGAS, f"{video_id}.json")
    return os.path.exists(json_path)

def descargar_video(video_info, cookies_path=None, intento=1):
    """
    Descarga un video con configuración anti-detección
    Retorna: (exito: bool, metadata: dict)
    """
    video_id = video_info['video_id']
    url = video_info['url']

    # Verificar si ya existe
    if ya_descargado(video_id):
        log(f"⏭️ Ya descargado: {video_id}", 'advertencia')
        return False, None

    # Configuración aleatoria para esta descarga
    config = obtener_config_aleatoria()

    # Delay anti-detención (aumenta con cada intento)
    delay = config['delay'] * intento
    log(f"⏳ Esperando {delay}s antes de descargar...", 'info')
    time.sleep(delay)

    # Nombre base para archivos
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_base = f"{timestamp}_{video_id}"

    video_path = os.path.join(CARPETA_DESCARGAS, f"{nombre_base}.mp4")
    json_path = os.path.join(CARPETA_DESCARGAS, f"{video_id}.json")

    # Comando yt-dlp mejorado con anti-detención
    cmd = [
        'yt-dlp',
        '--format', 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
        '--output', video_path,
        '--merge-output-format', 'mp4',
        '--no-playlist',
        '--no-check-certificates',
        '--geo-bypass',
        '--retries', '10',
        '--fragment-retries', '10',
        '--skip-unavailable-fragments',
        '--no-warnings',
        '--user-agent', config['user_agent'],
        '--add-header', f'Accept-Language:{config["accept_lang"]}',
        '--add-header', f'Accept:{config["accept"]}',
        '--add-header', 'Referer:https://www.youtube.com/',
        '--add-header', 'Origin:https://www.youtube.com',
        '--sleep-requests', str(random.randint(1, 3)),
        '--sleep-interval', str(random.randint(2, 5)),
        '--max-sleep-interval', '10',
        '--extractor-args', 'youtube:player_skip=webpage,configs,js',  # Más rápido, menos detectable
    ]

    if cookies_path and os.path.exists(cookies_path):
        cmd.extend(['--cookies', cookies_path])
        log(f"🔐 Usando cookies", 'debug')

    cmd.append(url)

    try:
        log(f"⬇️ Descargando (intento {intento}): {video_id} | {video_info['titulo'][:50]}...", 'info')
        log(f"   UA: {config['user_agent'][:50]}...", 'debug')

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            error_msg = result.stderr.lower()

            # Análisis de errores específicos
            if "bot" in error_msg or "automated" in error_msg:
                log(f"🤖 Detectado como bot: {video_id}", 'error')
                if intento < MAX_REINTENTOS:
                    log(f"🔄 Reintentando con otra configuración...", 'advertencia')
                    return descargar_video(video_info, cookies_path, intento + 1)

            elif "unavailable" in error_msg or "removed" in error_msg:
                log(f"📛 No disponible: {video_id}", 'error')

            elif "private" in error_msg:
                log(f"🔒 Video privado: {video_id}", 'error')

            elif "copyright" in error_msg or "blocked" in error_msg:
                log(f"©️ Bloqueado por copyright: {video_id}", 'error')

            elif "sign in" in error_msg or "login" in error_msg:
                log(f"🔐 Requiere login: {video_id}", 'error')
                if intento < MAX_REINTENTOS and cookies_path:
                    log(f"🔄 Reintentando sin cookies...", 'advertencia')
                    return descargar_video(video_info, None, intento + 1)
            else:
                log(f"❌ Error: {result.stderr[:150]}", 'error')

            return False, None

        # Verificar que se descargó
        if not os.path.exists(video_path):
            log(f"❌ Archivo no encontrado después de descarga", 'error')
            return False, None

        # Verificar tamaño
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        if size_mb > MAX_TAMANO_MB:
            log(f"⚠️ Muy grande ({size_mb:.1f}MB), eliminando", 'advertencia')
            os.remove(video_path)
            return False, None

        if size_mb < 0.5:
            log(f"⚠️ Muy pequeño ({size_mb:.1f}MB), posible error", 'advertencia')
            os.remove(video_path)
            return False, None

        # Crear metadata
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
            'query_usada': video_info.get('query_usada', ''),
            'config_usada': {
                'user_agent': config['user_agent'][:50] + '...',
                'delay_usado': delay
            }
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        log(f"✅ Guardado: {nombre_base}.mp4 ({size_mb:.1f} MB)", 'exito')
        return True, metadata

    except subprocess.TimeoutExpired:
        log(f"⏱️ Timeout: {video_id}", 'error')
        if intento < MAX_REINTENTOS:
            return descargar_video(video_info, cookies_path, intento + 1)
        return False, None

    except Exception as e:
        log(f"❌ Error: {e}", 'error')
        return False, None

# =============================================================================
# MAIN CON CONTROL DE FLUJO
# =============================================================================

def main():
    print("\n" + "="*60)
    print("📥 BOT DESCARGADOR DE VIDEOS - V2.0 (Anti-Detección)")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Carpeta: {os.path.abspath(CARPETA_DESCARGAS)}")
    print(f"🎲 Delays: {DELAY_MIN}-{DELAY_MAX}s | Reintentos: {MAX_REINTENTOS}")
    print("="*60)

    # Verificaciones
    if not YOUTUBE_API_KEY:
        log("ERROR: Falta YOUTUBE_API_KEY", 'error')
        return False

    if not verificar_yt_dlp():
        return False

    # Cargar estado
    estado = cargar_estado()
    log(f"📊 Estado cargado: {len(estado.get('videos_descargados', []))} videos previos")

    # Preparar cookies (una vez por ejecución)
    cookies_path = preparar_cookies()

    # Buscar videos
    videos = buscar_videos_noticias()

    if not videos:
        log("No se encontraron videos", 'advertencia')
        return False

    # Descargar hasta MAX_VIDEOS_POR_EJECUCION
    descargados = 0
    fallidos = 0
    exitosos_ids = []

    for video in videos:
        if descargados >= MAX_VIDEOS_POR_EJECUCION:
            log(f"🛑 Límite alcanzado: {MAX_VIDEOS_POR_EJECUCION} videos", 'info')
            break

        # Verificar en estado persistente
        if ya_descargado_estado(estado, video['video_id']):
            log(f"⏭️ En historial: {video['video_id']}", 'advertencia')
            continue

        exito, metadata = descargar_video(video, cookies_path)

        if exito:
            descargados += 1
            exitosos_ids.append(video['video_id'])
            estado['videos_descargados'].append(video['video_id'])
            estado['errores_consecutivos'] = 0  # Reset errores
        else:
            fallidos += 1
            estado['errores_consecutivos'] = estado.get('errores_consecutivos', 0) + 1

            # Si hay muchos errores consecutivos, parar
            if estado['errores_consecutivos'] >= 3:
                log("🛑 Demasiados errores consecutivos, deteniendo...", 'error')
                break

    # Guardar estado
    guardar_estado(estado)

    # Limpiar cookies temporales
    limpiar_cookies_temporales()

    # Resumen
    print("\n" + "="*60)
    log(f"📊 RESUMEN: {descargados} descargados, {fallidos} fallidos", 'exito')

    # Listar videos en carpeta
    videos_existentes = [f for f in os.listdir(CARPETA_DESCARGAS) if f.endswith('.mp4')]
    log(f"📁 Total videos en carpeta: {len(videos_existentes)}", 'info')

    if exitosos_ids:
        log(f"🎬 Videos nuevos: {', '.join(exitosos_ids)}", 'exito')

    return descargados > 0

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

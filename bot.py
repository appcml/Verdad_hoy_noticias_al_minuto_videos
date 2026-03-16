#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias VIDEO para Facebook - V2.3 CON COOKIES
- Descarga videos usando cookies de YouTube
- Fallback a enlace si falla la descarga
"""

import os
import sys
import re
import hashlib
import json
import tempfile
import subprocess
import shutil
import base64
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    print("❌ ERROR: 'requests' no instalado")
    sys.exit(1)

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
YT_COOKIES_B64 = os.getenv('YT_COOKIES')  # Cookies en base64

HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_publicaciones.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot.json')

TIEMPO_ENTRE_PUBLICACIONES = 60
VENTANA_DUPLICADOS_HORAS = 72
UMBRAL_SIMILITUD_TITULO = 0.85

# =============================================================================
# LOGGING
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍'}
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {iconos.get(tipo, 'ℹ️')} {mensaje}")

# =============================================================================
# COOKIES
# =============================================================================

def preparar_cookies():
    """
    Decodifica las cookies desde base64 y las guarda en archivo temporal
    Retorna: ruta al archivo cookies.txt o None
    """
    if not YT_COOKIES_B64:
        log("No hay cookies configuradas (YT_COOKIES)", 'advertencia')
        return None
    
    try:
        # Decodificar base64
        cookies_content = base64.b64decode(YT_COOKIES_B64).decode('utf-8')
        
        # Guardar en archivo temporal
        temp_dir = tempfile.gettempdir()
        cookies_path = os.path.join(temp_dir, 'youtube_cookies.txt')
        
        with open(cookies_path, 'w', encoding='utf-8') as f:
            f.write(cookies_content)
        
        log(f"✅ Cookies preparadas: {cookies_path}", 'debug')
        return cookies_path
        
    except Exception as e:
        log(f"❌ Error decodificando cookies: {e}", 'error')
        return None

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def cargar_json(ruta, default=None):
    if default is None:
        default = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                contenido = f.read().strip()
                return json.loads(contenido) if contenido else default.copy()
        except Exception as e:
            log(f"Error cargando JSON: {e}", 'error')
    return default.copy()

def guardar_json(ruta, datos):
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"Error guardando JSON: {e}", 'error')
        return False

def generar_hash(texto):
    if not texto:
        return ""
    texto_normalizado = re.sub(r'[^\w\s]', '', texto.lower().strip())
    texto_normalizado = re.sub(r'\s+', ' ', texto_normalizado)
    return hashlib.md5(texto_normalizado.encode()).hexdigest()

def limpiar_texto(texto):
    if not texto:
        return ""
    import html
    texto = html.unescape(texto)
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    texto = re.sub(r'https?://\S*', '', texto)
    return texto.strip()

# =============================================================================
# DESCARGA DE VIDEOS CON COOKIES
# =============================================================================

def verificar_yt_dlp():
    """Verifica si yt-dlp está instalado"""
    try:
        result = subprocess.run(['yt-dlp', '--version'], 
                              capture_output=True, text=True, timeout=10)
        version = result.stdout.strip()
        log(f"yt-dlp versión: {version}", 'info')
        return True
    except Exception as e:
        log(f"yt-dlp no disponible: {e}", 'error')
        return False

def descargar_video_youtube(video_url, video_id, cookies_path=None, max_altura=720):
    """
    Descarga video de YouTube usando cookies para evitar bloqueo de bot
    """
    temp_dir = tempfile.mkdtemp(prefix='fb_video_')
    output_template = os.path.join(temp_dir, f"{video_id}.%(ext)s")
    
    log(f"📁 Directorio temporal: {temp_dir}", 'debug')
    
    # Comando base
    cmd = [
        'yt-dlp',
        '--format', f'best[height<={max_altura}][ext=mp4]/best[height<={max_altura}]/best[ext=mp4]/best',
        '--output', output_template,
        '--merge-output-format', 'mp4',
        '--no-playlist',
        '--no-check-certificates',
        '--geo-bypass',
        '--retries', '5',
        '--fragment-retries', '5',
        '--skip-unavailable-fragments',
        '--quiet',
        '--no-warnings',
        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    # Agregar cookies si están disponibles
    if cookies_path and os.path.exists(cookies_path):
        cmd.extend(['--cookies', cookies_path])
        log("🔐 Usando cookies de autenticación", 'info')
    else:
        log("⚠️ Sin cookies - puede fallar por detección de bot", 'advertencia')
    
    cmd.append(video_url)
    
    try:
        log(f"⬇️ Descargando video: {video_id}", 'info')
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=180
        )
        
        # Verificar si fue exitoso
        if result.returncode != 0:
            error_msg = result.stderr
            
            # Detectar tipo de error
            if "bot" in error_msg.lower() or "sign in" in error_msg.lower():
                log("🤖 YouTube detectó bot (necesitas cookies válidas)", 'error')
            elif "unavailable" in error_msg.lower():
                log("📛 Video no disponible o restringido", 'error')
            else:
                log(f"❌ Error yt-dlp: {error_msg[:300]}", 'error')
            
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None
        
        # Buscar archivo descargado
        archivos = [f for f in os.listdir(temp_dir) if f.endswith(('.mp4', '.mkv', '.webm'))]
        
        if not archivos:
            log("❌ No se encontró archivo de video", 'error')
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None
        
        video_path = os.path.join(temp_dir, archivos[0])
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        
        log(f"✅ Descargado: {archivos[0]} ({size_mb:.1f} MB)", 'exito')
        
        # Verificar tamaño mínimo
        if size_mb < 0.5:
            log("⚠️ Archivo muy pequeño, posible error", 'advertencia')
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None
        
        return video_path
        
    except subprocess.TimeoutExpired:
        log("⏱️ Timeout en descarga (3 minutos)", 'error')
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None
    except Exception as e:
        log(f"❌ Error inesperado: {e}", 'error')
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None

# =============================================================================
# PUBLICACIÓN FACEBOOK
# =============================================================================

def publicar_video_nativo(titulo, descripcion, video_path, hashtags):
    """Publica video nativo en Facebook"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales Facebook", 'error')
        return False
    
    mensaje = f"📰 {titulo}\n\n{descripcion}\n\n{hashtags}\n\n— 🌐 Verdad Hoy"
    
    if len(mensaje) > 2200:
        mensaje = mensaje[:2100] + "...\n\n" + hashtags
    
    file_size = os.path.getsize(video_path)
    size_mb = file_size / (1024 * 1024)
    
    log(f"📤 Subiendo video nativo ({size_mb:.1f} MB)...", 'info')
    
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
    
    try:
        with open(video_path, 'rb') as video_file:
            files = {'file': ('video.mp4', video_file, 'video/mp4')}
            data = {
                'description': mensaje,
                'access_token': FB_ACCESS_TOKEN,
                'published': 'true'
            }
            
            response = requests.post(url, files=files, data=data, timeout=600)
            result = response.json()
            
            if response.status_code == 200 and 'id' in result:
                log(f"✅ Video nativo publicado: {result['id']}", 'exito')
                log("🎥 Las visualizaciones suman para tu página", 'exito')
                return True
            else:
                error = result.get('error', {})
                log(f"❌ Error Facebook: {error.get('message', 'Desconocido')}", 'error')
                return False
                
    except Exception as e:
        log(f"❌ Error subiendo: {e}", 'error')
        return False

def publicar_enlace_con_thumbnail(titulo, descripcion, url_video, thumbnail_url, hashtags):
    """
    Fallback: Publica enlace con thumbnail para mejor visualización
    """
    log("📎 Publicando como enlace con thumbnail...", 'info')
    
    mensaje = f"📰 {titulo}\n\n{descripcion}\n\n🔗 Ver video: {url_video}\n\n{hashtags}\n\n— 🌐 Verdad Hoy"
    
    try:
        # Descargar thumbnail
        thumb_path = None
        if thumbnail_url:
            try:
                resp = requests.get(thumbnail_url, timeout=10)
                if resp.status_code == 200:
                    temp_dir = tempfile.mkdtemp()
                    thumb_path = os.path.join(temp_dir, "thumb.jpg")
                    with open(thumb_path, 'wb') as f:
                        f.write(resp.content)
            except Exception as e:
                log(f"No se pudo descargar thumbnail: {e}", 'debug')
        
        # Publicar
        if thumb_path and os.path.exists(thumb_path):
            # Como foto con link (mejor visual)
            url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"
            with open(thumb_path, 'rb') as f:
                files = {'file': ('thumbnail.jpg', f, 'image/jpeg')}
                data = {
                    'message': mensaje,
                    'access_token': FB_ACCESS_TOKEN
                }
                resp = requests.post(url, files=files, data=data, timeout=60)
        else:
            # Solo enlace
            url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/feed"
            data = {
                'message': mensaje,
                'link': url_video,
                'access_token': FB_ACCESS_TOKEN
            }
            resp = requests.post(url, data=data, timeout=60)
        
        # Limpiar thumbnail
        if thumb_path:
            try:
                os.remove(thumb_path)
                os.rmdir(os.path.dirname(thumb_path))
            except:
                pass
        
        if resp.status_code == 200:
            log("✅ Enlace publicado (fallback)", 'exito')
            return True
        else:
            log(f"❌ Error: {resp.json().get('error', {}).get('message', 'Unknown')}", 'error')
            return False
            
    except Exception as e:
        log(f"❌ Error en fallback: {e}", 'error')
        return False

# =============================================================================
# BÚSQUEDA DE VIDEOS
# =============================================================================

def buscar_videos_youtube():
    """Busca videos recientes en YouTube"""
    if not YOUTUBE_API_KEY:
        log("YouTube API Key no configurada", 'advertencia')
        return []
    
    videos = []
    queries = [
        "noticias internacionales ultima hora",
        "breaking news today",
        "world news now"
    ]
    
    for query in queries:
        try:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'videoDuration': 'short',
                'order': 'date',
                'maxResults': 10,
                'key': YOUTUBE_API_KEY,
                'publishedAfter': (datetime.now() - timedelta(hours=24)).isoformat("T") + "Z"
            }
            
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            
            if 'items' in data:
                for item in data['items']:
                    video_id = item['id']['videoId']
                    snippet = item['snippet']
                    
                    videos.append({
                        'titulo': limpiar_texto(snippet.get('title', '')),
                        'descripcion': limpiar_texto(snippet.get('description', '')),
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'video_id': video_id,
                        'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                        'canal': snippet.get('channelTitle', ''),
                        'fecha': snippet.get('publishedAt')
                    })
                    
        except Exception as e:
            log(f"Error YouTube API: {e}", 'error')
            continue
    
    log(f"YouTube: {len(videos)} videos encontrados", 'info')
    return videos

# =============================================================================
# HISTORIAL
# =============================================================================

def cargar_historial():
    default = {
        'video_ids': [], 
        'hashes': [], 
        'timestamps': [],
        'estadisticas': {'total': 0, 'nativos': 0, 'links': 0}
    }
    return cargar_json(HISTORIAL_PATH, default)

def noticia_ya_publicada(historial, video_id, titulo):
    """Verifica duplicados"""
    if video_id in historial.get('video_ids', []):
        return True
    hash_tit = generar_hash(titulo)
    if hash_tit in historial.get('hashes', []):
        return True
    return False

def guardar_historial(historial, video_id, titulo, tipo='nativo'):
    historial['video_ids'].append(video_id)
    historial['hashes'].append(generar_hash(titulo))
    historial['timestamps'].append(datetime.now().isoformat())
    
    stats = historial.get('estadisticas', {'total': 0, 'nativos': 0, 'links': 0})
    stats['total'] += 1
    stats[tipo] = stats.get(tipo, 0) + 1
    historial['estadisticas'] = stats
    
    # Limitar tamaño
    for key in ['video_ids', 'hashes', 'timestamps']:
        if len(historial[key]) > 500:
            historial[key] = historial[key][-500:]
    
    guardar_json(HISTORIAL_PATH, historial)

# =============================================================================
# MAIN
# =============================================================================

def generar_hashtags(titulo, descripcion):
    texto = f"{titulo} {descripcion}".lower()
    hashtags = ['#NoticiasEnVideo', '#ÚltimaHora', '#VideoNoticias']
    
    temas = {
        'guerra|conflicto|ataque': '#ConflictoArmado',
        'ucrania|rusia': '#UcraniaRusia',
        'gaza|israel|palestina': '#IsraelGaza',
        'trump|biden': '#PolíticaGlobal',
        'economía': '#EconomíaMundial',
    }
    
    for patron, tag in temas.items():
        if re.search(patron, texto):
            hashtags.append(tag)
            break
    
    return ' '.join(hashtags)

def main():
    print("\n" + "="*60)
    print("🎥 BOT DE NOTICIAS VIDEO NATIVO - V2.3")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Verificar credenciales
    if not all([FB_PAGE_ID, FB_ACCESS_TOKEN, YOUTUBE_API_KEY]):
        log("ERROR: Faltan credenciales", 'error')
        return False
    
    # Verificar yt-dlp
    if not verificar_yt_dlp():
        log("ERROR: yt-dlp no está instalado", 'error')
        return False
    
    # PREPARAR COOKIES (NUEVO)
    cookies_path = preparar_cookies()
    
    # Cargar historial
    historial = cargar_historial()
    stats = historial.get('estadisticas', {})
    log(f"📊 Historial: {stats.get('total', 0)} total "
        f"({stats.get('nativos', 0)} nativos, {stats.get('links', 0)} links)", 'info')
    
    # Buscar videos
    videos = buscar_videos_youtube()
    
    if not videos:
        log("No se encontraron videos", 'error')
        return False
    
    # Seleccionar video nuevo
    video_sel = None
    for video in videos:
        vid_id = video.get('video_id')
        titulo = video.get('titulo', '')
        
        if noticia_ya_publicada(historial, vid_id, titulo):
            log(f"Omitiendo (ya publicado): {titulo[:50]}...", 'debug')
            continue
        
        video_sel = video
        log(f"🎬 Seleccionado: {titulo[:60]}...", 'info')
        break
    
    if not video_sel:
        log("No hay videos nuevos", 'advertencia')
        return False
    
    # Generar hashtags
    hashtags = generar_hashtags(video_sel['titulo'], video_sel.get('descripcion', ''))
    
    # INTENTAR DESCARGA NATIVA
    video_path = descargar_video_youtube(
        video_sel['url'], 
        video_sel['video_id'],
        cookies_path=cookies_path
    )
    
    exito = False
    tipo_pub = 'link'
    
    if video_path:
        # ÉXITO: Publicar nativo
        exito = publicar_video_nativo(
            video_sel['titulo'],
            video_sel.get('descripcion', ''),
            video_path,
            hashtags
        )
        if exito:
            tipo_pub = 'nativo'
        
        # Limpiar video temporal
        try:
            temp_dir = os.path.dirname(video_path)
            shutil.rmtree(temp_dir, ignore_errors=True)
            log("🗑️ Temporales limpiados", 'debug')
        except:
            pass
    else:
        # FALLBACK: Publicar como enlace
        log("Fallback a publicación de enlace...", 'advertencia')
        exito = publicar_enlace_con_thumbnail(
            video_sel['titulo'],
            video_sel.get('descripcion', ''),
            video_sel['url'],
            video_sel.get('thumbnail', ''),
            hashtags
        )
    
    # Limpiar cookies temporales
    if cookies_path and os.path.exists(cookies_path):
        try:
            os.remove(cookies_path)
        except:
            pass
    
    # Guardar historial
    if exito:
        guardar_historial(historial, video_sel['video_id'], video_sel['titulo'], tipo_pub)
        log(f"✅ ÉXITO ({tipo_pub.upper()}): {video_sel['titulo'][:50]}...", 'exito')
        return True
    else:
        log("❌ Falló la publicación", 'error')
        return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

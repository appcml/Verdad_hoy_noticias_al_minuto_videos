#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias VIDEO para Facebook - V2.2 NATIVO
- Descarga videos y publica nativamente
- Las visualizaciones suman para tu página
"""

import os
import sys
import re
import hashlib
import json
import tempfile
import subprocess
import shutil
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

HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_publicaciones.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot.json')

TIEMPO_ENTRE_PUBLICACIONES = 60  # minutos
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

def normalizar_url(url):
    if not url:
        return ""
    url = re.sub(r'\?.*$', '', url)
    url = re.sub(r'#.*$', '', url)
    url = re.sub(r'https?://(www\.)?', '', url)
    return url.lower().rstrip('/')

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
# DESCARGA DE VIDEOS
# =============================================================================

def verificar_yt_dlp():
    """Verifica si yt-dlp está instalado y disponible"""
    try:
        result = subprocess.run(['yt-dlp', '--version'], 
                              capture_output=True, text=True, timeout=10)
        version = result.stdout.strip()
        log(f"yt-dlp versión: {version}", 'info')
        return result.returncode == 0
    except Exception as e:
        log(f"yt-dlp no disponible: {e}", 'error')
        return False

def descargar_video_youtube(video_url, video_id, max_altura=720):
    """
    Descarga video de YouTube a carpeta temporal
    Retorna: ruta del archivo descargado o None
    """
    # Crear directorio temporal específico
    temp_dir = tempfile.mkdtemp(prefix='fb_video_')
    output_template = os.path.join(temp_dir, f"{video_id}.%(ext)s")
    
    log(f"📁 Directorio temporal: {temp_dir}", 'debug')
    
    # Comando optimizado para Facebook
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
        '--quiet',  # Menos verbose
        '--no-warnings',
        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        video_url
    ]
    
    try:
        log(f"⬇️ Descargando video: {video_id}", 'info')
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=180  # 3 minutos máximo
        )
        
        if result.returncode != 0:
            log(f"❌ Error yt-dlp: {result.stderr}", 'error')
            # Limpiar temporal
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None
        
        # Buscar el archivo descargado
        archivos = os.listdir(temp_dir)
        if not archivos:
            log("❌ No se encontró archivo descargado", 'error')
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None
        
        video_path = os.path.join(temp_dir, archivos[0])
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        
        log(f"✅ Descargado: {archivos[0]} ({size_mb:.1f} MB)", 'exito')
        
        # Verificar que sea un video válido
        if size_mb < 0.5:  # Menos de 500KB es sospechoso
            log("⚠️ Archivo muy pequeño, posible error", 'advertencia')
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None
            
        return video_path
        
    except subprocess.TimeoutExpired:
        log("⏱️ Timeout en descarga", 'error')
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None
    except Exception as e:
        log(f"❌ Error descarga: {e}", 'error')
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None

# =============================================================================
# PUBLICACIÓN NATIVA EN FACEBOOK
# =============================================================================

def publicar_video_nativo_facebook(titulo, descripcion, video_path, hashtags):
    """
    Publica video como archivo nativo en Facebook
    Las visualizaciones suman para tu página
    """
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("❌ Faltan credenciales Facebook", 'error')
        return False
    
    # Preparar mensaje
    mensaje = f"📰 {titulo}\n\n{descripcion}\n\n{hashtags}\n\n— 🌐 Verdad Hoy"
    
    # Truncar si es muy largo
    if len(mensaje) > 2200:
        mensaje = mensaje[:2100] + "...\n\n" + hashtags
    
    file_size = os.path.getsize(video_path)
    size_mb = file_size / (1024 * 1024)
    
    log(f"📤 Subiendo a Facebook ({size_mb:.1f} MB)...", 'info')
    
    # Endpoint de videos nativos
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
    
    try:
        with open(video_path, 'rb') as video_file:
            files = {
                'file': ('video.mp4', video_file, 'video/mp4')
            }
            data = {
                'description': mensaje,
                'access_token': FB_ACCESS_TOKEN,
                'published': 'true',
                'title': titulo[:255]  # Título opcional
            }
            
            # Timeout largo para videos grandes
            response = requests.post(
                url, 
                files=files, 
                data=data, 
                timeout=600  # 10 minutos
            )
            
            result = response.json()
            
            if response.status_code == 200 and 'id' in result:
                video_fb_id = result['id']
                log(f"✅ Video publicado nativamente: {video_fb_id}", 'exito')
                log(f"🎥 El video se reproduce en tu página (suma visualizaciones)", 'exito')
                return True
            else:
                error_msg = result.get('error', {}).get('message', 'Error desconocido')
                error_code = result.get('error', {}).get('code', 'N/A')
                log(f"❌ Error Facebook ({error_code}): {error_msg}", 'error')
                return False
                
    except requests.exceptions.Timeout:
        log("⏱️ Timeout subiendo a Facebook", 'error')
        return False
    except Exception as e:
        log(f"❌ Error publicando: {e}", 'error')
        return False

# =============================================================================
# BÚSQUEDA DE VIDEOS (Simplificada)
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
                'videoDuration': 'short',  # Videos cortos (< 4 min)
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
# HISTORIAL (Simplificado)
# =============================================================================

def cargar_historial():
    default = {
        'video_ids': [], 
        'hashes': [], 
        'timestamps': [],
        'estadisticas': {'total': 0}
    }
    return cargar_json(HISTORIAL_PATH, default)

def noticia_ya_publicada(historial, video_id, titulo):
    """Verifica si ya se publicó"""
    if video_id in historial.get('video_ids', []):
        return True
    
    hash_tit = generar_hash(titulo)
    if hash_tit in historial.get('hashes', []):
        return True
    
    return False

def guardar_historial(historial, video_id, titulo):
    historial['video_ids'].append(video_id)
    historial['hashes'].append(generar_hash(titulo))
    historial['timestamps'].append(datetime.now().isoformat())
    
    stats = historial.get('estadisticas', {'total': 0})
    stats['total'] += 1
    historial['estadisticas'] = stats
    
    # Mantener solo últimos 500
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
    print("🎥 BOT DE NOTICIAS VIDEO NATIVO - V2.2")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Verificar credenciales
    if not all([FB_PAGE_ID, FB_ACCESS_TOKEN, YOUTUBE_API_KEY]):
        log("ERROR: Faltan credenciales", 'error')
        return False
    
    # PASO 1: Verificar yt-dlp (CRÍTICO)
    if not verificar_yt_dlp():
        log("❌ CRÍTICO: yt-dlp no está instalado", 'error')
        log("ℹ️ El bot no puede descargar videos sin yt-dlp", 'info')
        return False
    
    # PASO 2: Cargar historial
    historial = cargar_historial()
    log(f"📊 Historial: {historial['estadisticas'].get('total', 0)} videos publicados", 'info')
    
    # PASO 3: Buscar videos
    videos = buscar_videos_youtube()
    
    if not videos:
        log("No se encontraron videos", 'error')
        return False
    
    # PASO 4: Seleccionar video nuevo
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
        log("No hay videos nuevos para publicar", 'advertencia')
        return False
    
    # PASO 5: Descargar video
    video_path = descargar_video_youtube(
        video_sel['url'], 
        video_sel['video_id'],
        max_altura=720
    )
    
    if not video_path:
        log("No se pudo descargar el video", 'error')
        return False
    
    # PASO 6: Publicar nativamente
    hashtags = generar_hashtags(video_sel['titulo'], video_sel.get('descripcion', ''))
    
    exito = publicar_video_nativo_facebook(
        video_sel['titulo'],
        video_sel.get('descripcion', ''),
        video_path,
        hashtags
    )
    
    # PASO 7: Limpieza (SIEMPRE ejecutar)
    try:
        temp_dir = os.path.dirname(video_path)
        shutil.rmtree(temp_dir, ignore_errors=True)
        log("🗑️ Archivos temporales eliminados", 'debug')
    except Exception as e:
        log(f"Error limpiando temporales: {e}", 'advertencia')
    
    # PASO 8: Guardar historial si fue exitoso
    if exito:
        guardar_historial(historial, video_sel['video_id'], video_sel['titulo'])
        log(f"✅ ÉXITO: Video publicado nativamente en tu página", 'exito')
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

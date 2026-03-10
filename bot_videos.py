#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Republicación de Videos de Facebook - Verdad Hoy
Monitorea páginas de noticias en FB, descarga videos y republica
"""

import os
import json
import re
import hashlib
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')

# Páginas de noticias a monitorear (IDs o nombres)
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
    'nbcnews',           # NBC News
    'cbsnews',           # CBS News
    'politico',          # Politico
    'axios',             # Axios
    'bloombergtv',       # Bloomberg
    'cnbc',              # CNBC
    'financialtimes',    # FT
    'wsj',               # Wall Street Journal
    'economist',         # The Economist
    'foreignpolicy',     # Foreign Policy
]

# Palabras clave para filtrar contenido relevante
PALABRAS_CLAVE = [
    'war', 'conflict', 'ukraine', 'gaza', 'israel', 'palestine', 'military',
    'attack', 'invasion', 'sanctions', 'economy', 'inflation', 'recession',
    'crisis', 'election', 'politics', 'government', 'biden', 'trump', 'putin',
    'china', 'russia', 'usa', 'nato', 'eu', 'trade', 'market', 'stock',
    'diplomacy', 'treaty', 'agreement', 'summit', 'protest', 'demonstration'
]

DATA_DIR = Path('data')
VIDEOS_DIR = DATA_DIR / 'videos'
HISTORIAL_PATH = DATA_DIR / 'historial.json'
ESTADO_PATH = DATA_DIR / 'estado.json'

DATA_DIR.mkdir(exist_ok=True)
VIDEOS_DIR.mkdir(exist_ok=True)

TIEMPO_ENTRE_PUBLICACIONES = 58  # minutos

# =============================================================================
# UTILIDADES
# =============================================================================

def log(msg, tipo='info'):
    iconos = {
        'info': 'ℹ️', 'ok': '✅', 'error': '❌', 
        'warn': '⚠️', 'video': '🎬', 'fb': '📘', 'news': '📰'
    }
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {iconos.get(tipo, 'ℹ️')} {msg}", flush=True)

def cargar_json(ruta, default=None):
    default = default or {}
    if ruta.exists():
        try:
            return json.loads(ruta.read_text(encoding='utf-8'))
        except:
            pass
    return default

def guardar_json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')

def generar_hash(texto):
    return hashlib.md5(str(texto).encode()).hexdigest()[:16]

def contiene_palabras_clave(texto):
    """Verifica si el texto contiene palabras clave relevantes"""
    if not texto:
        return False
    texto_lower = texto.lower()
    return any(palabra in texto_lower for palabra in PALABRAS_CLAVE)

def limpiar_nombre_archivo(texto):
    """Limpia texto para usar como nombre de archivo"""
    texto = re.sub(r'[^\w\s-]', '', texto)
    texto = re.sub(r'[-\s]+', '-', texto)
    return texto[:50].strip('-')

# =============================================================================
# FACEBOOK API - OBTENER PUBLICACIONES
# =============================================================================

def obtener_feed_pagina(page_id, limite=10):
    """
    Obtiene publicaciones recientes de una página de Facebook
    """
    if not FB_ACCESS_TOKEN:
        log("Sin FB_ACCESS_TOKEN", 'error')
        return []
    
    url = f"https://graph.facebook.com/v18.0/{page_id}/posts"
    params = {
        'access_token': FB_ACCESS_TOKEN,
        'fields': 'id,message,created_time,attachments{media_type,media,url,title,description},permalink_url,full_picture',
        'limit': limite
    }
    
    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        
        if 'error' in data:
            error_msg = data['error'].get('message', 'Unknown')
            if 'Page Public Content Access' in error_msg:
                log(f"Página {page_id} requiere permisos especiales", 'warn')
            else:
                log(f"Error API {page_id}: {error_msg[:60]}", 'error')
            return []
        
        publicaciones = []
        for post in data.get('data', []):
            post_id = post['id']
            mensaje = post.get('message', '')
            created_time = post.get('created_time')
            permalink = post.get('permalink_url', '')
            
            # Buscar video en attachments
            attachments = post.get('attachments', {}).get('data', [])
            video_info = None
            
            for att in attachments:
                media_type = att.get('media_type') or att.get('type', '')
                
                if 'video' in media_type.lower():
                    media = att.get('media', {})
                    video_url = media.get('source', '')  # URL directa del video
                    
                    if video_url:
                        video_info = {
                            'url': video_url,
                            'titulo': att.get('title', ''),
                            'descripcion': att.get('description', ''),
                            'preview': post.get('full_picture', '')
                        }
                        break
            
            if video_info:
                publicaciones.append({
                    'id': post_id,
                    'mensaje': mensaje,
                    'fecha': created_time,
                    'permalink': permalink,
                    'video': video_info,
                    'pagina_origen': page_id
                })
        
        return publicaciones
        
    except requests.Timeout:
        log(f"Timeout obteniendo {page_id}", 'warn')
        return []
    except Exception as e:
        log(f"Error {page_id}: {str(e)[:60]}", 'error')
        return []

def buscar_videos_todas_paginas():
    """Busca videos en todas las páginas configuradas"""
    log("🔍 Buscando videos en páginas de noticias...", 'news')
    todos_videos = []
    
    # Seleccionar páginas aleatorias para variedad (máximo 5 por ejecución)
    paginas_sample = random.sample(PAGINAS_NOTICIAS, min(5, len(PAGINAS_NOTICIAS)))
    
    for pagina in paginas_sample:
        log(f"Revisando {pagina}...", 'fb')
        videos = obtener_feed_pagina(pagina, limite=5)
        
        # Filtrar por palabras clave
        videos_relevantes = [v for v in videos if contiene_palabras_clave(v['mensaje'])]
        
        log(f"  {len(videos_relevantes)} videos relevantes", 'ok')
        todos_videos.extend(videos_relevantes)
        time.sleep(1)  # Respetar rate limits
    
    # Ordenar por fecha (más recientes primero)
    todos_videos.sort(key=lambda x: x['fecha'], reverse=True)
    
    log(f"Total videos encontrados: {len(todos_videos)}", 'ok')
    return todos_videos

# =============================================================================
# DESCARGA DE VIDEO
# =============================================================================

def descargar_video_fb(video_url, post_id, max_intentos=2):
    """
    Descarga video usando yt-dlp con manejo de errores
    """
    if not video_url:
        log("Sin URL de video", 'error')
        return None
    
    # Nombre único basado en post_id
    video_hash = generar_hash(post_id)
    output_template = VIDEOS_DIR / f"video_{video_hash}.%(ext)s"
    
    # Opciones para yt-dlp
    opciones = [
        'yt-dlp',
        '--no-playlist',
        '--format', 'best[height<=720][filesize<80M]/best[filesize<80M]/worst',
        '--max-filesize', '80M',
        '--output', str(output_template),
        '--no-warnings',
        '--quiet',
        '--socket-timeout', '30',
        '--retries', '2',
        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        video_url
    ]
    
    for intento in range(max_intentos):
        try:
            log(f"Descargando... (intento {intento + 1})", 'video')
            
            result = subprocess.run(
                opciones,
                capture_output=True,
                text=True,
                timeout=120  # 2 minutos máximo
            )
            
            if result.returncode != 0:
                log(f"Error yt-dlp: {result.stderr[:100]}", 'warn')
                continue
            
            # Buscar archivo descargado
            archivos = list(VIDEOS_DIR.glob(f"video_{video_hash}.*"))
            if archivos:
                video_path = archivos[0]
                size_mb = video_path.stat().st_size / (1024 * 1024)
                
                if size_mb < 1:  # Muy pequeño, probablemente error
                    video_path.unlink()
                    continue
                
                log(f"✓ Descargado: {size_mb:.1f} MB", 'ok')
                return str(video_path)
            
        except subprocess.TimeoutExpired:
            log("Timeout descargando video", 'warn')
        except Exception as e:
            log(f"Error descarga: {str(e)[:60]}", 'warn')
        
        time.sleep(2)
    
    return None

# =============================================================================
# PROCESAMIENTO DE TEXTO
# =============================================================================

def generar_nuevo_texto(mensaje_original, fuente):
    """
    Genera nuevo texto para la publicación republicada
    """
    if not mensaje_original:
        mensaje_original = "Video de actualidad internacional"
    
    # Limpiar mensaje original
    texto = re.sub(r'http\S+', '', mensaje_original)  # Quitar URLs
    texto = re.sub(r'#\w+', '', texto)  # Quitar hashtags
    texto = re.sub(r'@\w+', '', texto)  # Quitar menciones
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    # Limitar longitud
    if len(texto) > 200:
        texto = texto[:197] + "..."
    
    # Plantillas de contexto según contenido
    intros = [
        "🚨 Desarrollo de última hora",
        "📰 Información relevante del momento",
        "🌍 Situación internacional en desarrollo",
        "⚡ Acontecimiento importante",
        "📢 Noticia de impacto global",
    ]
    
    cierres = [
        "¿Qué opinas sobre esto? Comparte tu perspectiva. 👇",
        "Esto podría tener importantes consecuencias. ¿Qué crees? 🤔",
        "Situación que está generando debate internacional. 💬",
        "Desarrollo que hay que seguir de cerca. 📊",
        "¿Crees que esto cambiará el panorama actual? 🌐",
    ]
    
    intro = random.choice(intros)
    cierre = random.choice(cierres)
    
    nuevo_texto = f"""{intro}

{texto}

Fuente: {fuente}

{cierre}

#Actualidad #Noticias #Internacional #VerdadHoy"""
    
    return nuevo_texto[:1990]  # Límite de Facebook

# =============================================================================
# PUBLICACIÓN EN FACEBOOK
# =============================================================================

def republicar_video(video_path, texto):
    """
    Sube el video a tu página de Facebook
    """
    if not FB_ACCESS_TOKEN or not FB_PAGE_ID:
        log("Faltan credenciales de Facebook", 'error')
        return None
    
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {
                'description': texto,
                'access_token': FB_ACCESS_TOKEN
            }
            
            log("Subiendo a Facebook...", 'fb')
            resp = requests.post(url, files=files, data=data, timeout=300)
            result = resp.json()
        
        if 'id' in result:
            video_id = result['id']
            log(f"✓ Republicado ID: {video_id}", 'ok')
            return video_id
        else:
            error = result.get('error', {}).get('message', 'Error desconocido')
            log(f"Error FB: {error[:80]}", 'error')
            return None
            
    except Exception as e:
        log(f"Error publicando: {str(e)[:60]}", 'error')
        return None

# =============================================================================
# CONTROL Y HISTORIAL
# =============================================================================

def cargar_historial():
    return cargar_json(HISTORIAL_PATH, {
        'publicados': [],      # IDs de posts ya usados
        'hashes': [],          # Hashes de contenido
        'ultima_publicacion': None
    })

def ya_publicado(historial, post_id):
    """Verifica si ya republicamos este post"""
    return post_id in historial.get('publicados', [])

def guardar_registro(historial, post_original, nuevo_post_id):
    """Guarda registro de la republicación"""
    historial['publicados'].append(post_original['id'])
    historial['hashes'].append(generar_hash(post_original['id']))
    historial.setdefault('registros', []).append({
        'id_original': post_original['id'],
        'pagina_origen': post_original['pagina_origen'],
        'fecha_original': post_original['fecha'],
        'id_nuevo': nuevo_post_id,
        'fecha_republicacion': datetime.now().isoformat(),
        'titulo': post_original['mensaje'][:100] if post_original['mensaje'] else 'Sin título'
    })
    
    # Mantener solo últimos 100
    for key in ['publicados', 'hashes']:
        historial[key] = historial[key][-100:]
    historial['registros'] = historial['registros'][-50:]
    
    guardar_json(HISTORIAL_PATH, historial)

def verificar_tiempo_publicacion():
    """Verifica si ha pasado el tiempo mínimo entre publicaciones"""
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None})
    
    if not estado.get('ultima_publicacion'):
        return True, estado
    
    try:
        ultima = datetime.fromisoformat(estado['ultima_publicacion'])
        minutos = (datetime.now() - ultima).total_seconds() / 60
        return minutos >= TIEMPO_ENTRE_PUBLICACIONES, estado
    except:
        return True, estado

def limpiar_videos_antiguos(max_edad_horas=24):
    """Elimina videos temporales antiguos"""
    try:
        ahora = datetime.now()
        for archivo in VIDEOS_DIR.glob('video_*'):
            if archivo.is_file():
                stats = archivo.stat()
                edad = ahora - datetime.fromtimestamp(stats.st_mtime)
                if edad > timedelta(hours=max_edad_horas):
                    archivo.unlink()
        log("Limpieza de videos antiguos completada", 'info')
    except Exception as e:
        log(f"Error limpiando: {e}", 'warn')

# =============================================================================
# FLUJO PRINCIPAL
# =============================================================================

def main():
    inicio = time.time()
    
    print("\n" + "="*70)
    print("🎬 BOT DE REPUBLICACIÓN FB - VERDAD HOY")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # 1. Verificar tiempo entre publicaciones
    puede, estado = verificar_tiempo_publicacion()
    if not puede:
        log("⏳ Deben pasar 58 minutos entre publicaciones", 'warn')
        return True
    
    # 2. Cargar historial
    historial = cargar_historial()
    log(f"Historial: {len(historial.get('publicados', []))} videos ya republicados")
    
    # 3. Buscar videos en páginas de noticias
    videos = buscar_videos_todas_paginas()
    if not videos:
        log("No se encontraron videos relevantes", 'warn')
        return False
    
    # 4. Filtrar ya publicados
    videos_nuevos = [v for v in videos if not ya_publicado(historial, v['id'])]
    log(f"Videos nuevos: {len(videos_nuevos)}")
    
    if not videos_nuevos:
        log("No hay videos nuevos para republicar", 'info')
        return True
    
    # 5. Intentar republicar el primero que funcione
    for video in videos_nuevos[:3]:  # Máximo 3 intentos
        log(f"\n🎬 Procesando video de {video['pagina_origen']}...")
        
        # Descargar
        video_path = descargar_video_fb(
            video['video']['url'], 
            video['id']
        )
        
        if not video_path:
            log("No se pudo descargar, siguiente...", 'warn')
            continue
        
        # Generar texto
        nuevo_texto = generar_nuevo_texto(
            video['mensaje'], 
            video['pagina_origen']
        )
        
        # Republicar
        nuevo_id = republicar_video(video_path, nuevo_texto)
        
        # Limpiar archivo temporal
        try:
            Path(video_path).unlink()
        except:
            pass
        
        if nuevo_id:
            # Guardar registro
            guardar_registro(historial, video, nuevo_id)
            
            # Actualizar estado
            estado['ultima_publicacion'] = datetime.now().isoformat()
            guardar_json(ESTADO_PATH, estado)
            
            # Limpiar videos antiguos
            limpiar_videos_antiguos()
            
            tiempo_total = time.time() - inicio
            print("\n" + "="*70)
            log("✅ REPUBLICACIÓN EXITOSA")
            print(f"⏱️ Tiempo: {tiempo_total:.0f} segundos")
            print(f"📰 Origen: {video['pagina_origen']}")
            print(f"🔗 Post original: {video['permalink']}")
            print(f"📤 Nuevo post ID: {nuevo_id}")
            print("="*70)
            return True
        
        log("Falló la publicación, intentando siguiente...", 'warn')
    
    log("No se pudo republicar ningún video", 'error')
    return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except KeyboardInterrupt:
        log("Detenido por usuario", 'warn')
        exit(0)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

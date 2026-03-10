#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Reposteo de Videos de Noticias - Verdad Hoy
Monitorea páginas de Facebook, detecta videos nuevos y los republica
"""

import os
import json
import time
import re
import requests
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import yt_dlp

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Tokens de Facebook (Meta API)
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')

# Páginas de noticias a monitorear (IDs o nombres de usuario)
PAGINAS_NOTICIAS = [
    'bbcnews',           # BBC News
    'cnn',               # CNN
    'Reuters',           # Reuters
    'AlJazeera',         # Al Jazeera
    'france24',          # France 24
    'RTnews',            # RT
    'cnnee',             # CNN Español
    'actualidadrt',      # RT Español
]

# Configuración de tiempos
INTERVALO_MONITOREO = 10      # minutos entre chequeos
INTERVALO_PUBLICACION = 30    # minutos entre publicaciones
MAX_VIDEOS_POR_CICLO = 3      # máximo videos a procesar por ciclo

# Rutas
DATA_DIR = Path('data')
HISTORIAL_PATH = DATA_DIR / 'historial_publicaciones.json'
ESTADO_PATH = DATA_DIR / 'estado_bot.json'
VIDEOS_TEMP_DIR = DATA_DIR / 'temp_videos'

DATA_DIR.mkdir(exist_ok=True)
VIDEOS_TEMP_DIR.mkdir(exist_ok=True)

# =============================================================================
# UTILIDADES
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {
        'info': 'ℹ️', 'ok': '✅', 'error': '❌', 
        'warn': '⚠️', 'video': '🎬', 'fb': '📘', 'news': '📰'
    }
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {iconos.get(tipo, 'ℹ️')} {mensaje}", flush=True)

def generar_hash(texto):
    return hashlib.md5(texto.encode()).hexdigest()[:16]

def cargar_json(ruta, default=None):
    default = default or {}
    if ruta.exists():
        try:
            return json.loads(ruta.read_text(encoding='utf-8'))
        except Exception as e:
            log(f"Error cargando {ruta}: {e}", 'warn')
    return default

def guardar_json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')

# =============================================================================
# ETAPA 2: OBTENER PUBLICACIONES DE PÁGINAS
# =============================================================================

def obtener_publicaciones_pagina(page_id, limite=10):
    """
    Obtiene publicaciones recientes de una página de Facebook
    Usa la Graph API de Meta
    """
    if not FB_ACCESS_TOKEN:
        log("Sin FB_ACCESS_TOKEN", 'error')
        return []
    
    url = f"https://graph.facebook.com/v18.0/{page_id}/posts"
    params = {
        'access_token': FB_ACCESS_TOKEN,
        'fields': 'id,message,created_time,attachments{type,url,media},permalink_url',
        'limit': limite
    }
    
    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        
        if 'error' in data:
            log(f"Error API {page_id}: {data['error'].get('message', 'Unknown')}", 'error')
            return []
        
        publicaciones = []
        for post in data.get('data', []):
            # Verificar si tiene video
            tiene_video = False
            video_url = None
            
            attachments = post.get('attachments', {}).get('data', [])
            for att in attachments:
                if att.get('type') in ['video', 'video_inline', 'share']:
                    tiene_video = True
                    video_url = att.get('url') or att.get('media', {}).get('source')
                    break
            
            if tiene_video:
                publicaciones.append({
                    'id': post['id'],
                    'mensaje': post.get('message', ''),
                    'fecha': post['created_time'],
                    'permalink': post.get('permalink_url', ''),
                    'video_url': video_url,
                    'pagina_origen': page_id
                })
        
        return publicaciones
        
    except Exception as e:
        log(f"Error obteniendo {page_id}: {str(e)[:60]}", 'error')
        return []

def obtener_todas_publicaciones():
    """Obtiene publicaciones de todas las páginas monitoreadas"""
    log("Escaneando páginas de noticias...", 'news')
    todas = []
    
    for pagina in PAGINAS_NOTICIAS:
        pubs = obtener_publicaciones_pagina(pagina, limite=5)
        log(f"{pagina}: {len(pubs)} videos encontrados", 'fb')
        todas.extend(pubs)
        time.sleep(1)  # Respetar rate limits
    
    # Ordenar por fecha (más recientes primero)
    todas.sort(key=lambda x: x['fecha'], reverse=True)
    log(f"Total videos encontrados: {len(todas)}", 'ok')
    return todas

# =============================================================================
# ETAPA 3: FILTRADO DE CONTENIDO
# =============================================================================

def cargar_historial():
    return cargar_json(HISTORIAL_PATH, {
        'publicados': [],      # IDs de posts ya republicados
        'hashes': [],          # Hashes de contenido
        'ultima_publicacion': None
    })

def es_publicacion_valida(publicacion, historial):
    """
    Verifica si una publicación debe ser procesada:
    - No está en historial
    - Tiene mensaje (no solo video sin texto)
    - Es reciente (menos de 24 horas)
    """
    post_id = publicacion['id']
    
    # Ya fue publicado?
    if post_id in historial.get('publicados', []):
        return False
    
    # Tiene contenido textual?
    if not publicacion.get('mensaje') or len(publicacion['mensaje']) < 20:
        return False
    
    # Es reciente? (últimas 24 horas)
    try:
        fecha_post = datetime.fromisoformat(publicacion['fecha'].replace('Z', '+00:00'))
        if datetime.now().astimezone() - fecha_post > timedelta(hours=24):
            return False
    except:
        pass
    
    return True

def filtrar_videos_nuevos(publicaciones, historial):
    """Filtra solo publicaciones válidas y nuevas"""
    validas = []
    for pub in publicaciones:
        if es_publicacion_valida(pub, historial):
            validas.append(pub)
    
    log(f"Videos nuevos para procesar: {len(validas)}", 'ok')
    return validas[:MAX_VIDEOS_POR_CICLO]

# =============================================================================
# ETAPA 5: DESCARGA DEL VIDEO
# =============================================================================

def descargar_video_facebook(video_url, post_id):
    """
    Descarga video de Facebook usando yt-dlp
    Maneja tanto videos públicos como embeds
    """
    if not video_url:
        # Intentar construir URL desde post_id
        video_url = f"https://facebook.com/{post_id}"
    
    filename = f"video_{generar_hash(post_id)}"
    output_path = VIDEOS_TEMP_DIR / f"{filename}.%(ext)s"
    
    ydl_opts = {
        'format': 'best[height<=720][filesize<80M]/best[filesize<80M]',
        'outtmpl': str(output_path),
        'max_filesize': 80000000,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
        # Opciones específicas para Facebook
        'cookiesfrombrowser': None,  # No usar cookies por defecto
        'facebook_clip': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            
            if not info:
                return None
            
            # Obtener ruta final del archivo
            video_path = ydl.prepare_filename(info)
            
            # Verificar existencia
            if Path(video_path).exists():
                size_mb = Path(video_path).stat().st_size / (1024*1024)
                log(f"Video descargado: {size_mb:.1f} MB", 'ok')
                return video_path
            
            # Buscar con otras extensiones
            base = Path(video_path).stem
            for ext in ['.mp4', '.mkv', '.webm']:
                alt = VIDEOS_TEMP_DIR / f"{base}{ext}"
                if alt.exists():
                    return str(alt)
            
            return None
            
    except Exception as e:
        log(f"Error descargando video: {str(e)[:80]}", 'error')
        return None

# =============================================================================
# ETAPA 6: GENERACIÓN DEL TEXTO
# =============================================================================

def limpiar_texto_original(texto):
    """Limpia el texto original de hashtags y menciones excesivas"""
    if not texto:
        return ""
    
    # Remover URLs
    texto = re.sub(r'http\S+', '', texto)
    # Remover hashtags excesivos (mantener máximo 2)
    hashtags = re.findall(r'#\w+', texto)
    for ht in hashtags[2:]:
        texto = texto.replace(ht, '')
    # Remover menciones @
    texto = re.sub(r'@\w+', '', texto)
    # Limpiar espacios múltiples
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    return texto

def generar_texto_publicacion(mensaje_original, fuente):
    """
    Genera texto para la nueva publicación
    Estructura: Contexto + Resumen + Pregunta
    """
    # Limpiar texto original
    texto_limpio = limpiar_texto_original(mensaje_original)
    
    # Si es muy largo, resumir (primeros 150 caracteres + ...)
    if len(texto_limpio) > 150:
        resumen = texto_limpio[:150].rsplit(' ', 1)[0] + "..."
    else:
        resumen = texto_limpio
    
    # Plantillas de inicio
    intros = [
        "🚨 Noticia de última hora que está generando debate.",
        "📰 Información importante que debes conocer.",
        "🌍 Desarrollo reciente en la escena internacional.",
        "⚡ Acontecimiento relevante del momento.",
    ]
    
    # Plantillas de cierre
    preguntas = [
        "¿Qué opinas sobre esta situación? 💬",
        "¿Crees que esto tendrá mayores consecuencias? 🤔",
        "Comparte tu perspectiva en los comentarios. 👇",
        "¿Qué impacto crees que tendrá esto? 📢",
    ]
    
    intro = random.choice(intros)
    pregunta = random.choice(preguntas)
    
    texto_final = f"""{intro}

{resumen}

Fuente: {fuente}

{pregunta}

#Noticias #Actualidad #ÚltimaHora #VerdadHoy"""
    
    return texto_final

# =============================================================================
# ETAPA 7: PUBLICACIÓN EN TU PÁGINA
# =============================================================================

def publicar_video(video_path, mensaje):
    """
    Publica video en tu página de Facebook
    """
    if not FB_ACCESS_TOKEN or not FB_PAGE_ID:
        log("Faltan credenciales de Facebook", 'error')
        return None
    
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {
                'description': mensaje[:1990],  # Límite de caracteres
                'access_token': FB_ACCESS_TOKEN
            }
            
            log("Subiendo video a Facebook...", 'fb')
            resp = requests.post(url, files=files, data=data, timeout=300)
            result = resp.json()
        
        if 'id' in result:
            video_id = result['id']
            log(f"✅ Video publicado ID: {video_id}", 'ok')
            return video_id
        else:
            error_msg = result.get('error', {}).get('message', 'Error desconocido')
            log(f"❌ Error publicando: {error_msg}", 'error')
            return None
            
    except Exception as e:
        log(f"Error en publicación: {e}", 'error')
        return None

# =============================================================================
# ETAPA 8 & 9: CONTROL Y REGISTRO
# =============================================================================

def puede_publicar():
    """Verifica si ha pasado el tiempo mínimo entre publicaciones"""
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None})
    
    if not estado.get('ultima_publicacion'):
        return True, estado
    
    try:
        ultima = datetime.fromisoformat(estado['ultima_publicacion'])
        minutos = (datetime.now() - ultima).total_seconds() / 60
        return minutos >= INTERVALO_PUBLICACION, estado
    except:
        return True, estado

def guardar_en_historial(historial, publicacion_original, post_id_nuevo, video_path):
    """Registra la publicación para evitar duplicados"""
    registro = {
        'id_original': publicacion_original['id'],
        'fecha_original': publicacion_original['fecha'],
        'permalink_original': publicacion_original['permalink'],
        'pagina_origen': publicacion_original['pagina_origen'],
        'id_nuevo_post': post_id_nuevo,
        'fecha_reposteo': datetime.now().isoformat(),
        'texto_original': publicacion_original['mensaje'][:200]
    }
    
    historial['publicados'].append(publicacion_original['id'])
    historial['hashes'].append(generar_hash(publicacion_original['id']))
    historial.setdefault('registros', []).append(registro)
    
    # Mantener solo últimos 100
    historial['publicados'] = historial['publicados'][-100:]
    historial['hashes'] = historial['hashes'][-100:]
    historial['registros'] = historial['registros'][-50:]
    
    guardar_json(HISTORIAL_PATH, historial)

def limpiar_temporales():
    """Elimina videos temporales antiguos"""
    try:
        for archivo in VIDEOS_TEMP_DIR.glob('*'):
            if archivo.is_file():
                archivo.unlink()
        log("Carpeta temporal limpiada", 'info')
    except Exception as e:
        log(f"Error limpiando temporales: {e}", 'warn')

# =============================================================================
# FLUJO PRINCIPAL
# =============================================================================

def ciclo_bot():
    """Ejecuta un ciclo completo del bot"""
    print("\n" + "="*70)
    log("🤖 INICIANDO CICLO DE MONITOREO", 'info')
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # 1. Verificar si podemos publicar (control de frecuencia)
    puede, estado = puede_publicar()
    if not puede:
        log("⏳ Esperando intervalo de 30 minutos...", 'warn')
        return False
    
    # 2. Cargar historial
    historial = cargar_historial()
    log(f"Historial: {len(historial.get('publicados', []))} posts ya republicados")
    
    # 3. Obtener publicaciones de todas las páginas
    publicaciones = obtener_todas_publicaciones()
    if not publicaciones:
        log("No se encontraron publicaciones", 'warn')
        return False
    
    # 4. Filtrar videos nuevos
    videos_nuevos = filtrar_videos_nuevos(publicaciones, historial)
    if not videos_nuevos:
        log("No hay videos nuevos para republicar", 'info')
        return False
    
    # 5. Procesar cada video
    for pub in videos_nuevos:
        log(f"\n📰 Procesando: {pub['mensaje'][:60]}...")
        log(f"🔗 Fuente: {pub['pagina_origen']}", 'fb')
        
        # Descargar video
        video_path = descargar_video_facebook(pub['video_url'], pub['id'])
        if not video_path:
            log("No se pudo descargar el video, saltando...", 'warn')
            continue
        
        # Generar texto
        texto = generar_texto_publicacion(pub['mensaje'], pub['pagina_origen'])
        
        # Publicar
        nuevo_post_id = publicar_video(video_path, texto)
        
        # Limpiar temporal
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
        except:
            pass
        
        if nuevo_post_id:
            # Guardar en historial
            guardar_en_historial(historial, pub, nuevo_post_id, video_path)
            
            # Actualizar estado
            estado['ultima_publicacion'] = datetime.now().isoformat()
            guardar_json(ESTADO_PATH, estado)
            
            # Éxito - solo publicamos uno por ciclo
            print("\n" + "="*70)
            log("✅ REPUBLICACIÓN EXITOSA", 'ok')
            print(f"🎬 Video de: {pub['pagina_origen']}")
            print(f"📝 Texto: {texto[:100]}...")
            print(f"📊 Nuevo Post ID: {nuevo_post_id}")
            print("="*70)
            return True
        else:
            log("Falló la publicación, intentando siguiente...", 'warn')
    
    log("No se pudo publicar ningún video en este ciclo", 'error')
    return False

def main():
    """Ejecución continua del bot"""
    log("🚀 BOT DE REPUBLICACIÓN INICIADO", 'ok')
    log(f"⏱️  Monitoreo cada {INTERVALO_MONITOREO} minutos", 'info')
    log(f"📢 Publicación máxima cada {INTERVALO_PUBLICACION} minutos", 'info')
    
    while True:
        try:
            ciclo_bot()
            
            # Esperar hasta próximo ciclo
            log(f"😴 Durmiendo {INTERVALO_MONITOREO} minutos...", 'info')
            time.sleep(INTERVALO_MONITOREO * 60)
            
        except KeyboardInterrupt:
            log("🛑 Bot detenido por usuario", 'warn')
            break
        except Exception as e:
            log(f"💥 Error crítico: {e}", 'error')
            import traceback
            traceback.print_exc()
            time.sleep(60)  # Esperar 1 minuto antes de reintentar

if __name__ == "__main__":
    main()

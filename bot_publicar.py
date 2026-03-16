#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Publicador de Videos - V1.0
Toma videos descargados de la carpeta y los publica en Facebook
Luego mueve los publicados a carpeta de archivados
"""

import os
import sys
import json
import shutil
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ ERROR: pip install requests")
    sys.exit(1)

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

CARPETA_PENDIENTES = os.getenv('CARPETA_VIDEOS', 'videos_pendientes')
CARPETA_PUBLICADOS = os.getenv('CARPETA_PUBLICADOS', 'videos_publicados')

# Crear carpetas
Path(CARPETA_PENDIENTES).mkdir(parents=True, exist_ok=True)
Path(CARPETA_PUBLICADOS).mkdir(parents=True, exist_ok=True)

TIEMPO_ENTRE_PUBLICACIONES = int(os.getenv('TIEMPO_MINUTOS', '60'))

# =============================================================================
# LOGGING
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍'}
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {iconos.get(tipo, 'ℹ️')} {mensaje}")

# =============================================================================
# FUNCIONES
# =============================================================================

def cargar_json(ruta):
    """Carga archivo JSON"""
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None

def guardar_json(ruta, datos):
    """Guarda archivo JSON"""
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

def obtener_videos_pendientes():
    """
    Obtiene lista de videos pendientes de publicar
    Ordenados por fecha de descarga (más antiguos primero)
    """
    videos = []
    
    for archivo in os.listdir(CARPETA_PENDIENTES):
        if not archivo.endswith('.json'):
            continue
        
        json_path = os.path.join(CARPETA_PENDIENTES, archivo)
        metadata = cargar_json(json_path)
        
        if not metadata:
            continue
        
        if metadata.get('estado') != 'pendiente':
            continue
        
        video_id = metadata.get('video_id')
        video_filename = metadata.get('archivo_video')
        video_path = os.path.join(CARPETA_PENDIENTES, video_filename)
        
        # Verificar que existe el archivo de video
        if not os.path.exists(video_path):
            log(f"⚠️ Video no encontrado: {video_filename}", 'advertencia')
            metadata['estado'] = 'error'
            metadata['error'] = 'Archivo video no encontrado'
            guardar_json(json_path, metadata)
            continue
        
        videos.append({
            'metadata': metadata,
            'json_path': json_path,
            'video_path': video_path,
            'fecha_descarga': metadata.get('fecha_descarga', '')
        })
    
    # Ordenar por fecha de descarga (FIFO)
    videos.sort(key=lambda x: x['fecha_descarga'])
    
    return videos

def generar_hashtags(titulo, descripcion):
    """Genera hashtags relevantes"""
    texto = f"{titulo} {descripcion}".lower()
    hashtags = ['#NoticiasEnVideo', '#ÚltimaHora', '#VideoNoticias']
    
    temas = {
        'guerra|conflicto|ataque|military': '#ConflictoArmado',
        'ucrania|rusia|putin|zelensky': '#UcraniaRusia',
        'gaza|israel|palestina|hamas': '#IsraelGaza',
        'trump|biden|usa|eeuu': '#PolíticaUSA',
        'economía|mercados|inflación': '#EconomíaMundial',
        'china|taiwan': '#ChinaTaiwán',
        'iran|middle east|oriente': '#OrienteMedio',
    }
    
    for patron, tag in temas.items():
        if re.search(patron, texto):
            hashtags.append(tag)
            break
    
    return ' '.join(hashtags)

def publicar_en_facebook(metadata, video_path):
    """
    Publica video nativo en Facebook
    """
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales Facebook", 'error')
        return False
    
    titulo = metadata['titulo']
    descripcion = metadata.get('descripcion', '')
    hashtags = generar_hashtags(titulo, descripcion)
    
    mensaje = f"📰 {titulo}\n\n{descripcion}\n\n{hashtags}\n\n— 🌐 Verdad Hoy"
    
    if len(mensaje) > 2200:
        mensaje = mensaje[:2100] + "...\n\n" + hashtags
    
    file_size = os.path.getsize(video_path)
    size_mb = file_size / (1024 * 1024)
    
    log(f"📤 Publicando: {titulo[:50]}... ({size_mb:.1f} MB)", 'info')
    
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
                log(f"✅ Publicado: {result['id']}", 'exito')
                return True, result['id']
            else:
                error = result.get('error', {})
                log(f"❌ Error Facebook: {error.get('message', 'Unknown')}", 'error')
                return False, error.get('message', 'Unknown')
                
    except Exception as e:
        log(f"❌ Error: {e}", 'error')
        return False, str(e)

def archivar_video(video_info, fb_post_id=None, error_msg=None):
    """
    Mueve video y metadata a carpeta de publicados
    """
    try:
        # Actualizar metadata
        metadata = video_info['metadata']
        metadata['estado'] = 'publicado' if fb_post_id else 'error'
        metadata['fecha_publicacion'] = datetime.now().isoformat()
        metadata['facebook_post_id'] = fb_post_id
        if error_msg:
            metadata['error_mensaje'] = error_msg
        
        # Nombres de archivos destino
        video_filename = os.path.basename(video_info['video_path'])
        json_filename = os.path.basename(video_info['json_path'])
        
        # Mover video
        destino_video = os.path.join(CARPETA_PUBLICADOS, video_filename)
        shutil.move(video_info['video_path'], destino_video)
        
        # Guardar metadata actualizada
        destino_json = os.path.join(CARPETA_PUBLICADOS, json_filename)
        guardar_json(destino_json, metadata)
        
        # Eliminar JSON original
        os.remove(video_info['json_path'])
        
        log(f"📁 Archivado: {video_filename}", 'info')
        return True
        
    except Exception as e:
        log(f"❌ Error archivando: {e}", 'error')
        return False

def verificar_tiempo_ultima_publicacion():
    """Verifica si ha pasado suficiente tiempo desde la última publicación"""
    # Aquí puedes implementar lógica de control de tiempo
    # Por ahora, siempre permite publicar
    return True

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*60)
    print("📤 BOT PUBLICADOR DE VIDEOS - V1.0")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Pendientes: {os.path.abspath(CARPETA_PENDIENTES)}")
    print(f"📁 Publicados: {os.path.abspath(CARPETA_PUBLICADOS)}")
    print("="*60)
    
    # Verificar credenciales
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales Facebook", 'error')
        return False
    
    # Obtener videos pendientes
    pendientes = obtener_videos_pendientes()
    
    if not pendientes:
        log("No hay videos pendientes para publicar", 'info')
        return True  # No es error, simplemente no hay nada
    
    log(f"📋 Videos pendientes: {len(pendientes)}", 'info')
    
    # Publicar solo el primero (el más antiguo)
    video = pendientes[0]
    metadata = video['metadata']
    
    log(f"🎬 Siguiente: {metadata['titulo'][:60]}...", 'info')
    
    # Publicar
    exito, resultado = publicar_en_facebook(metadata, video['video_path'])
    
    if exito:
        # Archivar como publicado
        archivar_video(video, fb_post_id=resultado)
        log("✅ Proceso completado", 'exito')
    else:
        # Archivar como error (o dejar pendiente para reintentar)
        log("❌ Falló la publicación", 'error')
        # Opción: dejar pendiente para reintentar después
        # metadata['estado'] = 'error'
        # metadata['error'] = resultado
        # guardar_json(video['json_path'], metadata)
    
    # Resumen
    restantes = len(pendientes) - 1
    if restantes > 0:
        log(f"⏳ Quedan {restantes} videos pendientes", 'info')
    
    return exito

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

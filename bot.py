#!/usr/bin/env python3
import os
import sys
import re
import random
import requests
import subprocess
from datetime import datetime

# ============================================
# CONFIGURACIÓN
# ============================================
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

print(f"=== BOT DE NOTICIAS {datetime.now()} ===")
print(f"YouTube API: {'OK' if YOUTUBE_API_KEY else 'FALTA'}")
print(f"Facebook Page: {'OK' if FB_PAGE_ID else 'FALTA'}")
print(f"Facebook Token: {'OK' if FB_ACCESS_TOKEN else 'FALTA'}")

if not all([YOUTUBE_API_KEY, FB_PAGE_ID, FB_ACCESS_TOKEN]):
    print("ERROR: Faltan variables de entorno")
    sys.exit(1)

# ============================================
# FUNCIONES
# ============================================

def buscar_shorts():
    """Busca shorts de noticias en YouTube"""
    print("\n--- Buscando shorts ---")
    
    queries = [
        "noticias urgentes hoy",
        "ultima hora internacional",
        "breaking news",
        "conflicto hoy"
    ]
    
    encontrados = []
    
    for query in queries:
        if len(encontrados) >= 3:
            break
            
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'q': query,
            'type': 'video',
            'videoDuration': 'short',
            'order': 'date',
            'publishedAfter': (datetime.utcnow() - timedelta(hours=6)).isoformat("T") + "Z",
            'maxResults': 5,
            'key': YOUTUBE_API_KEY
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            
            for item in data.get('items', []):
                vid = item['id']['videoId']
                titulo = item['snippet']['title']
                
                # Verificar duración
                dur_url = "https://www.googleapis.com/youtube/v3/videos"
                dur_params = {'part': 'contentDetails', 'id': vid, 'key': YOUTUBE_API_KEY}
                dur_resp = requests.get(dur_url, params=dur_params, timeout=5)
                dur_data = dur_resp.json()
                
                if dur_data.get('items'):
                    dur_iso = dur_data['items'][0]['contentDetails']['duration']
                    # Parsear PT1M30S
                    match = re.match(r'PT(?:(\d+)M)?(?:(\d+)S)?', dur_iso)
                    mins = int(match.group(1) or 0)
                    secs = int(match.group(2) or 0)
                    total_secs = mins * 60 + secs
                    
                    if 15 <= total_secs <= 60:
                        encontrados.append({
                            'id': vid,
                            'titulo': titulo,
                            'url': f"https://youtube.com/shorts/{vid}"
                        })
                        print(f"  ✓ {vid}: {titulo[:50]}...")
                        
        except Exception as e:
            print(f"  Error en búsqueda: {e}")
            continue
    
    return encontrados

def descargar_video(video_id, url):
    """Descarga video con yt-dlp"""
    print(f"\n--- Descargando {video_id} ---")
    
    output = f"temp/{video_id}.mp4"
    
    # Borrar si existe
    if os.path.exists(output):
        os.remove(output)
    
    cmd = [
        'yt-dlp',
        '-f', 'best[height<=720]',
        '-o', output,
        '--quiet',
        '--no-warnings',
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0 and os.path.exists(output):
            size = os.path.getsize(output)
            print(f"  ✓ Descargado: {size/1024/1024:.1f} MB")
            return output
        else:
            print(f"  ✗ Error: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None

def crear_texto(titulo_original):
    """Crea nuevo título y descripción"""
    print("\n--- Creando texto ---")
    
    # Limpiar título
    limpio = re.sub(r'noticias|news|urgente|breaking|shorts|youtube', '', titulo_original, flags=re.I)
    limpio = limpio.strip()[:60]
    
    plantillas = [
        f"🔴 {limpio} | Última hora",
        f"⚡ {limpio} - Reporte inmediato",
        f"🚨 {limpio} | Desarrollo"
    ]
    
    nuevo_titulo = random.choice(plantillas)
    
    descripcion = f"""📰 Información actualizada

🔍 {limpio}

¿Qué opinas? Comenta 👇

#Noticias #Actualidad #ÚltimaHora"""
    
    print(f"  Título: {nuevo_titulo[:50]}...")
    return {'titulo': nuevo_titulo, 'descripcion': descripcion}

def publicar_facebook(video_path, contenido):
    """Sube video a Facebook"""
    print("\n--- Publicando en Facebook ---")
    
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
    
    mensaje = f"{contenido['titulo']}\n\n{contenido['descripcion']}"
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': f}
            data = {
                'description': mensaje,
                'access_token': FB_ACCESS_TOKEN
            }
            
            resp = requests.post(url, files=files, data=data, timeout=300)
            result = resp.json()
            
            print(f"  Respuesta: {result}")
            
            if 'id' in result:
                print(f"  ✓✓✓ PUBLICADO: {result['id']}")
                return True
            else:
                print(f"  ✗ Error: {result.get('error', 'Desconocido')}")
                return False
                
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

# ============================================
# EJECUCIÓN PRINCIPAL
# ============================================

from datetime import timedelta

def main():
    # Crear carpeta temp
    os.makedirs('temp', exist_ok=True)
    
    # 1. Buscar
    videos = buscar_shorts()
    if not videos:
        print("No se encontraron videos")
        return
    
    # 2. Intentar descargar y publicar el primero que funcione
    for video in videos:
        print(f"\n{'='*50}")
        print(f"Procesando: {video['titulo'][:50]}...")
        
        # Descargar
        archivo = descargar_video(video['id'], video['url'])
        if not archivo:
            continue
        
        # Crear texto
        contenido = crear_texto(video['titulo'])
        
        # Publicar
        exito = publicar_facebook(archivo, contenido)
        
        # Limpiar
        if os.path.exists(archivo):
            os.remove(archivo)
            print(f"  Archivo temporal eliminado")
        
        if exito:
            print(f"\n{'='*50}")
            print("¡PUBLICACIÓN EXITOSA!")
            return
    
    print("\nNo se pudo publicar ningún video")

if __name__ == "__main__":
    main()

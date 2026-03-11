#!/usr/bin/env python3
import os
import sys
import re
import random
import requests
import subprocess
from datetime import datetime, timedelta

# ============================================
# CONFIGURACIÓN
# ============================================
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

print(f"\n{'='*60}")
print(f"INICIO: {datetime.now()}")
print(f"{'='*60}")

print(f"\n[CONFIGURACIÓN]")
print(f"  YOUTUBE_API_KEY: {'✓ Configurada' if YOUTUBE_API_KEY else '✗ FALTA'} ({len(YOUTUBE_API_KEY) if YOUTUBE_API_KEY else 0} chars)")
print(f"  FB_PAGE_ID: {'✓ Configurada' if FB_PAGE_ID else '✗ FALTA'}")
print(f"  FB_ACCESS_TOKEN: {'✓ Configurada' if FB_ACCESS_TOKEN else '✗ FALTA'} ({len(FB_ACCESS_TOKEN) if FB_ACCESS_TOKEN else 0} chars)")

if not all([YOUTUBE_API_KEY, FB_PAGE_ID, FB_ACCESS_TOKEN]):
    print("\n✗ ERROR: Faltan variables de entorno")
    sys.exit(1)

print("\n✓ Todas las variables configuradas")

# ============================================
# PASO 1: BUSCAR SHORTS
# ============================================

def buscar_shorts():
    print(f"\n{'='*60}")
    print("PASO 1: BUSCANDO SHORTS EN YOUTUBE")
    print(f"{'='*60}")
    
    queries = [
        "noticias urgentes hoy",
        "ultima hora internacional", 
        "breaking news today",
        "conflicto mundial hoy"
    ]
    
    encontrados = []
    
    for query in queries:
        print(f"\n  Buscando: '{query}'")
        
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
            print(f"    URL: {url}")
            print(f"    Params: {params}")
            
            resp = requests.get(url, params=params, timeout=15)
            print(f"    Status: {resp.status_code}")
            
            if resp.status_code != 200:
                print(f"    ✗ Error HTTP: {resp.text[:200]}")
                continue
                
            data = resp.json()
            items = data.get('items', [])
            print(f"    Resultados: {len(items)}")
            
            for i, item in enumerate(items):
                try:
                    vid = item['id']['videoId']
                    titulo = item['snippet']['title']
                    print(f"\n    [{i+1}] Video ID: {vid}")
                    print(f"        Título: {titulo[:60]}...")
                    
                    # Verificar duración
                    dur_url = "https://www.googleapis.com/youtube/v3/videos"
                    dur_params = {
                        'part': 'contentDetails',
                        'id': vid,
                        'key': YOUTUBE_API_KEY
                    }
                    
                    print(f"        Verificando duración...")
                    dur_resp = requests.get(dur_url, params=dur_params, timeout=10)
                    dur_data = dur_resp.json()
                    
                    if not dur_data.get('items'):
                        print(f"        ✗ No se pudo obtener duración")
                        continue
                    
                    dur_iso = dur_data['items'][0]['contentDetails']['duration']
                    print(f"        Duración ISO: {dur_iso}")
                    
                    # Parsear duración
                    match = re.match(r'PT(?:(\d+)M)?(?:(\d+)S)?', dur_iso)
                    mins = int(match.group(1) or 0)
                    secs = int(match.group(2) or 0)
                    total_secs = mins * 60 + secs
                    print(f"        Duración: {total_secs} segundos")
                    
                    if 15 <= total_secs <= 60:
                        video_data = {
                            'id': vid,
                            'titulo': titulo,
                            'url': f"https://youtube.com/shorts/{vid}",
                            'duracion': total_secs
                        }
                        encontrados.append(video_data)
                        print(f"        ✓ AÑADIDO (duración válida)")
                    else:
                        print(f"        ✗ Descartado (duración inválida)")
                        
                except Exception as e:
                    print(f"    ✗ Error procesando item: {e}")
                    continue
                    
        except Exception as e:
            print(f"    ✗ Error en búsqueda: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n{'='*60}")
    print(f"TOTAL ENCONTRADOS: {len(encontrados)} shorts")
    print(f"{'='*60}")
    
    for i, v in enumerate(encontrados, 1):
        print(f"  {i}. [{v['id']}] {v['titulo'][:50]}... ({v['duracion']}s)")
    
    return encontrados

# ============================================
# PASO 2: DESCARGAR
# ============================================

def descargar_video(video):
    print(f"\n{'='*60}")
    print(f"PASO 2: DESCARGANDO VIDEO")
    print(f"{'='*60}")
    print(f"  ID: {video['id']}")
    print(f"  URL: {video['url']}")
    
    os.makedirs('temp', exist_ok=True)
    output = f"temp/{video['id']}.mp4"
    
    # Borrar si existe
    if os.path.exists(output):
        print(f"  Eliminando archivo anterior...")
        os.remove(output)
    
    cmd = [
        'yt-dlp',
        '-f', 'best[height<=720]',
        '-o', output,
        '--no-check-certificates',
        '--quiet',
        '--no-warnings',
        video['url']
    ]
    
    print(f"\n  Comando: {' '.join(cmd)}")
    print(f"  Ejecutando descarga...")
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=180
        )
        
        print(f"  Return code: {result.returncode}")
        
        if result.stderr:
            print(f"  Stderr: {result.stderr[:500]}")
        
        if result.returncode == 0 and os.path.exists(output):
            size = os.path.getsize(output)
            print(f"\n  ✓ ÉXITO")
            print(f"    Archivo: {output}")
            print(f"    Tamaño: {size:,} bytes ({size/1024/1024:.2f} MB)")
            return output
        else:
            print(f"\n  ✗ FALLO")
            print(f"    Archivo existe: {os.path.exists(output)}")
            return None
            
    except subprocess.TimeoutExpired:
        print(f"\n  ✗ TIMEOUT (3 minutos)")
        return None
    except Exception as e:
        print(f"\n  ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================
# PASO 3: CREAR TEXTO
# ============================================

def crear_texto(titulo_original):
    print(f"\n{'='*60}")
    print("PASO 3: CREANDO TEXTO")
    print(f"{'='*60}")
    print(f"  Original: {titulo_original[:60]}...")
    
    # Limpiar
    limpio = re.sub(r'noticias|news|urgente|breaking|shorts|youtube|video', '', titulo_original, flags=re.I)
    limpio = limpio.strip()[:50]
    print(f"  Limpio: {limpio}")
    
    plantillas = [
        f"🔴 {limpio} | Última hora",
        f"⚡ {limpio} - Desarrollo",
        f"🚨 {limpio} | Alerta"
    ]
    
    nuevo_titulo = random.choice(plantillas)
    
    descripcion = f"""📰 Información actualizada

🔍 {limpio}

¿Qué opinas? Comenta 👇

#Noticias #Actualidad #ÚltimaHora #Viral"""
    
    print(f"\n  ✓ Nuevo título: {nuevo_titulo}")
    print(f"  ✓ Descripción creada ({len(descripcion)} chars)")
    
    return {
        'titulo': nuevo_titulo,
        'descripcion': descripcion
    }

# ============================================
# PASO 4: PUBLICAR EN FACEBOOK
# ============================================

def publicar_facebook(video_path, contenido):
    print(f"\n{'='*60}")
    print("PASO 4: PUBLICANDO EN FACEBOOK")
    print(f"{'='*60}")
    
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
    print(f"  URL API: {url}")
    print(f"  Page ID: {FB_PAGE_ID}")
    
    mensaje = f"{contenido['titulo']}\n\n{contenido['descripcion']}"
    print(f"\n  Mensaje a publicar:")
    print(f"  {'-'*40}")
    print(f"  {mensaje[:200]}...")
    print(f"  {'-'*40}")
    
    # Verificar archivo
    if not os.path.exists(video_path):
        print(f"\n  ✗ ERROR: No existe el archivo {video_path}")
        return False
    
    size = os.path.getsize(video_path)
    print(f"\n  Archivo: {video_path}")
    print(f"  Tamaño: {size:,} bytes")
    
    if size == 0:
        print(f"  ✗ ERROR: Archivo vacío")
        return False
    
    if size > 500 * 1024 * 1024:  # 500 MB límite
        print(f"  ✗ ERROR: Archivo muy grande (>500MB)")
        return False
    
    print(f"\n  Enviando a Facebook...")
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': ('video.mp4', f, 'video/mp4')}
            data = {
                'description': mensaje,
                'access_token': FB_ACCESS_TOKEN
            }
            
            print(f"  Subiendo... (puede tomar varios minutos)")
            resp = requests.post(url, files=files, data=data, timeout=600)
            
            print(f"\n  Status code: {resp.status_code}")
            print(f"  Respuesta: {resp.text[:500]}")
            
            result = resp.json()
            
            if 'id' in result:
                post_id = result['id']
                video_id = result.get('video_id', 'N/A')
                print(f"\n  {'='*60}")
                print(f"  ✓✓✓ ÉXITO TOTAL ✓✓✓")
                print(f"  Post ID: {post_id}")
                print(f"  Video ID: {video_id}")
                print(f"  URL: https://facebook.com/{post_id}")
                print(f"  {'='*60}")
                return True
            else:
                error = result.get('error', {})
                print(f"\n  ✗ ERROR DE FACEBOOK:")
                print(f"    Code: {error.get('code', 'N/A')}")
                print(f"    Message: {error.get('message', 'Desconocido')}")
                print(f"    Type: {error.get('type', 'N/A')}")
                return False
                
    except requests.exceptions.Timeout:
        print(f"\n  ✗ TIMEOUT (10 minutos)")
        return False
    except Exception as e:
        print(f"\n  ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================
# EJECUCIÓN PRINCIPAL
# ============================================

def main():
    print(f"\n{'#'*60}")
    print("#" + " "*58 + "#")
    print("#" + "   BOT DE NOTICIAS - MODO DIAGNÓSTICO   ".center(58) + "#")
    print("#" + " "*58 + "#")
    print(f"{'#'*60}")
    
    # PASO 1: Buscar
    videos = buscar_shorts()
    
    if not videos:
        print(f"\n{'='*60}")
        print("RESULTADO: No se encontraron videos")
        print(f"{'='*60}")
        return
    
    # Intentar con cada video hasta que uno funcione
    for i, video in enumerate(videos, 1):
        print(f"\n{'#'*60}")
        print(f"### INTENTO {i} DE {len(videos)}")
        print(f"{'#'*60}")
        
        # PASO 2: Descargar
        archivo = descargar_video(video)
        if not archivo:
            print("  Saltando al siguiente video...")
            continue
        
        # PASO 3: Crear texto
        contenido = crear_texto(video['titulo'])
        
        # PASO 4: Publicar
        exito = publicar_facebook(archivo, contenido)
        
        # Limpiar
        if os.path.exists(archivo):
            os.remove(archivo)
            print(f"\n  Archivo temporal eliminado")
        
        if exito:
            print(f"\n{'='*60}")
            print("RESULTADO: PUBLICACIÓN EXITOSA")
            print(f"{'='*60}")
            return
        else:
            print(f"\n  Falló publicación, intentando siguiente...")
    
    print(f"\n{'='*60}")
    print("RESULTADO: No se pudo publicar ningún video")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()

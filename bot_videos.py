#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias con Video - Verdad Hoy
Arquitectura: NewsAPI → YouTube → Descarga → Publicación
"""

import os
import json
import random
import hashlib
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
import requests
import yt_dlp

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

# Rutas de almacenamiento
BASE_DIR = Path('data')
VIDEOS_DIR = BASE_DIR / 'videos'
NOTICIAS_DIR = BASE_DIR / 'noticias'
HISTORIAL_PATH = BASE_DIR / 'historial.json'
ESTADO_PATH = BASE_DIR / 'estado.json'

TIEMPO_ENTRE_PUBLICACIONES = 58  # minutos

# Crear carpetas
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
NOTICIAS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# CATEGORÍAS Y PALABRAS CLAVE
# =============================================================================

CATEGORIAS = {
    'conflictos': {
        'keywords': ['war', 'conflict', 'attack', 'military', 'combat', 'ukraine', 
                    'gaza', 'israel', 'palestine', 'syria', 'drone', 'missile'],
        'query': 'war OR conflict OR military OR ukraine OR gaza',
        'hashtags': '#Guerra #Conflicto #Militar #Urgente'
    },
    'seguridad': {
        'keywords': ['crime', 'police', 'shooting', 'arrest', 'cartel', 'drug'],
        'query': 'crime OR police OR shooting OR security',
        'hashtags': '#Seguridad #Crimen #Policía'
    },
    'desastres': {
        'keywords': ['earthquake', 'flood', 'fire', 'disaster', 'emergency'],
        'query': 'earthquake OR flood OR disaster OR emergency',
        'hashtags': '#Desastre #Emergencia #Tragedia'
    }
}

# =============================================================================
# UTILIDADES
# =============================================================================

def log(msg, tipo='info'):
    iconos = {
        'info': 'ℹ️', 'ok': '✅', 'error': '❌', 
        'warn': '⚠️', 'video': '🎬', 'news': '📰'
    }
    print(f"{iconos.get(tipo, 'ℹ️')} {msg}", flush=True)

def generar_hash(texto):
    return hashlib.md5(texto.lower().encode()).hexdigest()[:12]

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

def detectar_categoria(texto):
    texto = texto.lower()
    scores = {cat: sum(1 for k in info['keywords'] if k in texto) 
              for cat, info in CATEGORIAS.items()}
    mejor = max(scores, key=scores.get)
    return mejor if scores[mejor] > 0 else 'conflictos'

# =============================================================================
# 1. BUSCAR NOTICIAS (NewsAPI)
# =============================================================================

def buscar_noticias_newsapi():
    """Busca noticias reales de última hora"""
    if not NEWS_API_KEY:
        log("Sin NEWS_API_KEY", 'error')
        return []
    
    # Rotar categorías para variedad
    categoria = random.choice(list(CATEGORIAS.keys()))
    query = CATEGORIAS[categoria]['query']
    
    url = "https://newsapi.org/v2/everything"
    params = {
        'q': query,
        'language': 'en',
        'sortBy': 'publishedAt',
        'pageSize': 20,
        'from': (datetime.now() - timedelta(hours=48)).strftime('%Y-%m-%d'),
        'apiKey': NEWS_API_KEY
    }
    
    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        
        if data.get('status') != 'ok':
            log(f"NewsAPI error: {data.get('message')}", 'error')
            return []
        
        noticias = []
        for art in data.get('articles', []):
            # Solo noticias con contenido sustancial
            if len(art.get('title', '')) < 10:
                continue
                
            noticias.append({
                'titulo': art['title'],
                'descripcion': art.get('description', ''),
                'contenido': art.get('content', ''),
                'url': art['url'],
                'fuente': art['source']['name'],
                'fecha': art['publishedAt'],
                'imagen': art.get('urlToImage', ''),
                'categoria': detectar_categoria(art['title'] + ' ' + art.get('description', ''))
            })
        
        log(f"NewsAPI: {len(noticias)} noticias [{categoria}]", 'ok')
        return noticias
        
    except Exception as e:
        log(f"Error NewsAPI: {e}", 'error')
        return []

# =============================================================================
# 2. BUSCAR VIDEO RELACIONADO (YouTube)
# =============================================================================

def buscar_video_youtube(titulo_noticia, descripcion):
    """
    Busca video relacionado en YouTube usando términos de la noticia
    """
    # Limpiar y crear query de búsqueda
    palabras = re.findall(r'\b\w{4,}\b', titulo_noticia.lower())
    palabras = [p for p in palabras if p not in ['this', 'that', 'with', 'from', 'have', 'been']]
    
    if len(palabras) < 3:
        return None
    
    # Tomar las 4-6 palabras más relevantes
    query = ' '.join(palabras[:6]) + ' video'
    
    search_url = f"ytsearch5:{query}"
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(search_url, download=False)
            
            if not result or 'entries' not in result:
                return None
            
            # Filtrar videos recientes y relevantes
            for entry in result['entries']:
                if not entry:
                    continue
                
                duracion = entry.get('duration', 0)
                
                # Videos entre 30 segundos y 4 minutos
                if 30 < duracion < 240:
                    return {
                        'titulo': entry.get('title', ''),
                        'url': entry.get('url', ''),
                        'duracion': duracion,
                        'id': entry.get('id', '')
                    }
        
        return None
        
    except Exception as e:
        log(f"Error búsqueda YouTube: {e}", 'warn')
        return None

# =============================================================================
# 3. DESCARGAR VIDEO
# =============================================================================

def descargar_video_youtube(video_info, noticia_id):
    """Descarga video de YouTube a carpeta local"""
    video_id = video_info['id']
    url = video_info['url']
    
    # Nombre de archivo basado en noticia para trazabilidad
    filename = f"{noticia_id}_{video_id}"
    output_path = VIDEOS_DIR / f"{filename}.%(ext)s"
    
    ydl_opts = {
        'format': 'best[height<=720][filesize<50M]/best[filesize<50M]',
        'outtmpl': str(output_path),
        'max_filesize': 50000000,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = ydl.prepare_filename(info)
            
            # Verificar que existe
            if Path(downloaded_path).exists():
                size_mb = Path(downloaded_path).stat().st_size / (1024*1024)
                log(f"Descargado: {size_mb:.1f}MB", 'ok')
                return downloaded_path
            
            # Buscar con otras extensiones
            base = Path(downloaded_path).stem
            for ext in ['.mp4', '.mkv', '.webm']:
                alt_path = VIDEOS_DIR / f"{base}{ext}"
                if alt_path.exists():
                    return str(alt_path)
            
            return None
            
    except Exception as e:
        log(f"Error descarga: {str(e)[:60]}", 'warn')
        return None

# =============================================================================
# 4. GUARDAR NOTICIA
# =============================================================================

def guardar_noticia(noticia, video_path, video_info):
    """Guarda el texto de la noticia con metadatos del video"""
    
    noticia_data = {
        'titulo': noticia['titulo'],
        'descripcion': noticia['descripcion'],
        'contenido': noticia['contenido'],
        'url_noticia': noticia['url'],
        'fuente': noticia['fuente'],
        'fecha_noticia': noticia['fecha'],
        'categoria': noticia['categoria'],
        'video': {
            'titulo_video': video_info['titulo'],
            'url_video': video_info['url'],
            'duracion': video_info['duracion'],
            'archivo_local': video_path,
            'descargado_en': datetime.now().isoformat()
        },
        'publicado': False,
        'fecha_procesamiento': datetime.now().isoformat()
    }
    
    # Guardar como JSON
    noticia_id = generar_hash(noticia['titulo'])
    ruta_json = NOTICIAS_DIR / f"{noticia_id}.json"
    guardar_json(ruta_json, noticia_data)
    
    log(f"Noticia guardada: {ruta_json.name}", 'ok')
    return noticia_id, ruta_json

# =============================================================================
# 5. PUBLICAR EN FACEBOOK
# =============================================================================

def publicar_facebook(noticia, video_path, categoria):
    """Publica video con contexto de noticia"""
    
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Sin credenciales FB", 'error')
        return False
    
    hashtags = CATEGORIAS.get(categoria, {}).get('hashtags', '#Noticias')
    
    # Crear mensaje enriquecido
    mensaje = f"""🚨 {noticia['titulo']}

📰 {noticia['descripcion'][:200]}{'...' if len(noticia['descripcion']) > 200 else ''}

🔗 Fuente: {noticia['fuente']}

{hashtags} #ÚltimaHora #Video #Noticias #Actualidad

— Verdad Hoy"""
    
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
        
        with open(video_path, 'rb') as f:
            resp = requests.post(
                url,
                files={'file': ('video.mp4', f, 'video/mp4')},
                data={
                    'description': mensaje[:1990],
                    'access_token': FB_ACCESS_TOKEN
                },
                timeout=300
            )
        
        result = resp.json()
        
        if 'id' in result:
            log(f"Publicado ID: {result['id']}", 'ok')
            return result['id']
        else:
            log(f"Error FB: {result.get('error', {}).get('message', 'Unknown')}", 'error')
            return False
            
    except Exception as e:
        log(f"Error publicación: {e}", 'error')
        return False

# =============================================================================
# HISTORIAL Y CONTROL
# =============================================================================

def cargar_historial():
    return cargar_json(HISTORIAL_PATH, {'urls': [], 'hashes': [], 'publicados': []})

def ya_procesado(historial, url):
    url_hash = generar_hash(url)
    return url_hash in historial.get('hashes', [])

def agregar_a_historial(historial, noticia, video_url, post_id):
    url_hash = generar_hash(noticia['url'])
    historial['hashes'].append(url_hash)
    historial['urls'].append(noticia['url'])
    historial['publicados'].append({
        'fecha': datetime.now().isoformat(),
        'titulo': noticia['titulo'][:80],
        'post_id': post_id,
        'video_url': video_url
    })
    # Mantener solo últimos 100
    historial['hashes'] = historial['hashes'][-100:]
    historial['urls'] = historial['urls'][-100:]
    historial['publicados'] = historial['publicados'][-50:]
    guardar_json(HISTORIAL_PATH, historial)

def verificar_tiempo():
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None})
    if not estado.get('ultima_publicacion'):
        return True, estado
    
    try:
        ultima = datetime.fromisoformat(estado['ultima_publicacion'])
        minutos = (datetime.now() - ultima).total_seconds() / 60
        return minutos >= TIEMPO_ENTRE_PUBLICACIONES, estado
    except:
        return True, estado

# =============================================================================
# FLUJO PRINCIPAL
# =============================================================================

def main():
    print("\n" + "="*60)
    print("🎬 BOT NOTICIAS + VIDEO - VERDAD HOY")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Verificar tiempo
    puede_publicar, estado = verificar_tiempo()
    if not puede_publicar:
        log("Esperando intervalo de 58 minutos...", 'warn')
        return True
    
    # Cargar historial
    historial = cargar_historial()
    log(f"Historial: {len(historial.get('publicados', []))} publicados")
    
    # 1. Buscar noticias
    noticias = buscar_noticias_newsapi()
    if not noticias:
        log("Sin noticias disponibles", 'error')
        return False
    
    # 2. Procesar noticias hasta encontrar una con video
    for noticia in noticias[:5]:  # Revisar top 5
        if ya_procesado(historial, noticia['url']):
            continue
        
        log(f"\n📰 {noticia['titulo'][:60]}...")
        
        # 3. Buscar video relacionado
        video = buscar_video_youtube(noticia['titulo'], noticia['descripcion'])
        if not video:
            log("No se encontró video relacionado", 'warn')
            continue
        
        log(f"🎬 Video: {video['titulo'][:50]}...")
        
        # 4. Descargar video
        noticia_id = generar_hash(noticia['titulo'])
        video_path = descargar_video_youtube(video, noticia_id)
        
        if not video_path:
            log("Falló descarga del video", 'warn')
            continue
        
        # 5. Guardar noticia + video
        guardar_noticia(noticia, video_path, video)
        
        # 6. Publicar
        post_id = publicar_facebook(noticia, video_path, noticia['categoria'])
        
        if post_id:
            agregar_a_historial(historial, noticia, video['url'], post_id)
            estado['ultima_publicacion'] = datetime.now().isoformat()
            guardar_json(ESTADO_PATH, estado)
            
            print("\n" + "="*60)
            print("✅ PUBLICACIÓN EXITOSA")
            print(f"📰 {noticia['titulo'][:60]}")
            print(f"🎬 {video['titulo'][:60]}")
            print(f"📁 Guardado en: data/")
            print("="*60)
            return True
        else:
            log("Falló publicación, intentando siguiente...", 'warn')
    
    log("No se pudo publicar ninguna noticia", 'error')
    return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

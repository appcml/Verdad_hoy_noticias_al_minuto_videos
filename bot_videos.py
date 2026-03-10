#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Videos para Facebook - Verdad Hoy
Fuentes: Reddit, TikTok (sin login), Twitter/X, Vimeo, Bitchute, Rumble
PLUS: Descarga de FB/IG usando yt-dlp con cookies o APIs de descarga
"""

import requests
import feedparser
import re
import hashlib
import json
import os
import random
import time
import subprocess
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote
import yt_dlp

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_videos.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot.json')

# Opcional: Cookies para descargar de FB/IG (formato Netscape o cookies.txt)
COOKIES_PATH = os.getenv('COOKIES_PATH', None)  # 'data/cookies.txt'

TIEMPO_ENTRE_PUBLICACIONES = 58

# =============================================================================
# CATEGORÍAS
# =============================================================================

CATEGORIAS = {
    'conflictos': {
        'palabras': ['guerra', 'conflicto', 'ataque', 'bombardeo', 'invasión', 'misil', 
                     'batalla', 'ucrania', 'rusia', 'gaza', 'palestina', 'israel', 
                     'hamás', 'siria', 'militar', 'soldados', 'dron', 'combate'],
        'hashtags': '#Guerra #Conflicto #Militar'
    },
    'narcotrafico': {
        'palabras': ['narcotráfico', 'cártel', 'droga', 'cocaína', 'fentanilo', 
                     'narco', 'sicario', 'decomiso', 'sinaloa', 'jalisco', 'cjng', 'balacera'],
        'hashtags': '#Narcotráfico #Seguridad #CrimenOrganizado'
    },
    'politica': {
        'palabras': ['gobierno', 'presidente', 'elecciones', 'política', 'protesta', 
                     'golpe', 'corrupción', 'onu', 'diplomacia', 'sanciones'],
        'hashtags': '#Política #Internacional #Gobierno'
    },
    'desastres': {
        'palabras': ['terremoto', 'tsunami', 'huracán', 'inundación', 'incendio', 
                     'desastre', 'tragedia', 'accidente', 'víctimas', 'evacuación'],
        'hashtags': '#Desastre #Emergencia #Tragedia'
    }
}

TODAS_PALABRAS = []
for cat in CATEGORIAS.values():
    TODAS_PALABRAS.extend(cat['palabras'])

# =============================================================================
# FUENTES ABIERTAS (Sin autenticación)
# =============================================================================

# Subreddits de video
REDDIT_SUBREDDITS = [
    'CombatFootage', 'war', 'UkraineWarVideoReport', 'syriancivilwar',
    'NarcoFootage', 'ActualPublicFreakouts', 'CatastrophicFailure', 'worldnews'
]

# Canales de Rumble (alternativa a YouTube)
RUMBLE_CHANNELS = [
    'RT', 'AlJazeeraEnglish', 'Reuters', 'France24', 'TRTWorld'
]

# Canales de Bitchute (contenido sin censura)
BITCHUTE_CHANNELS = [
    'timcast', 'styxhexenhammer666'  # Canales de noticias/independientes
]

# Búsquedas de Twitter/X (públicas)
TWITTER_SEARCH_TERMS = [
    'war footage', 'military combat', 'breaking news video', 
    'conflict zone', 'drone footage war'
]

# TikTok tags de noticias (públicos)
TIKTOK_TAGS = [
    'war', 'military', 'news', 'breakingnews', 'conflict'
]

# =============================================================================
# UTILIDADES
# =============================================================================

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'video': '🎬'}
    print(f"{iconos.get(tipo, 'ℹ️')} {mensaje}")

def cargar_json(ruta, default=None):
    if default is None:
        default = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return default

def guardar_json(ruta, datos):
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"Error guardando: {e}", 'error')
        return False

def generar_hash(texto):
    return hashlib.md5(texto.lower().strip().encode()).hexdigest()

def detectar_categoria(titulo, descripcion=''):
    texto = f"{titulo} {descripcion}".lower()
    puntuaciones = {}
    for nombre, datos in CATEGORIAS.items():
        score = sum(1 for palabra in datos['palabras'] if palabra in texto)
        puntuaciones[nombre] = score
    return max(puntuaciones, key=puntuaciones.get) if max(puntuaciones.values()) > 0 else 'conflictos'

def obtener_hashtags(categoria):
    return CATEGORIAS.get(categoria, {}).get('hashtags', '#Noticias #Actualidad')

# =============================================================================
# HISTORIAL
# =============================================================================

def cargar_historial():
    default = {'urls': [], 'titulos': [], 'hashes': [], 'videos': []}
    historial = cargar_json(HISTORIAL_PATH, default)
    log(f"Historial: {len(historial.get('videos', []))} videos")
    return historial

def guardar_historial(historial, url, titulo, fuente):
    url_hash = generar_hash(url)
    historial.setdefault('urls', []).append(url)
    historial.setdefault('titulos', []).append(titulo[:100])
    historial.setdefault('hashes', []).append(url_hash)
    historial.setdefault('videos', []).append({
        'url': url, 'titulo': titulo[:100], 
        'fecha': datetime.now().isoformat(), 'fuente': fuente
    })
    for key in ['urls', 'titulos', 'hashes']:
        historial[key] = historial[key][-100:]
    historial['videos'] = historial['videos'][-100:]
    guardar_json(HISTORIAL_PATH, historial)

def ya_publicado(historial, url, titulo):
    if generar_hash(url) in historial.get('hashes', []):
        return True
    if url in historial.get('urls', []):
        return True
    titulo_simple = re.sub(r'[^\w]', '', titulo.lower())[:30]
    for t in historial.get('titulos', []):
        if re.sub(r'[^\w]', '', t.lower())[:30] == titulo_simple:
            return True
    return False

def verificar_tiempo():
    estado = cargar_json(ESTADO_PATH, {'ultima_publicacion': None})
    if not estado.get('ultima_publicacion'):
        return True, estado
    try:
        ultima = datetime.fromisoformat(estado['ultima_publicacion'])
        transcurrido = (datetime.now() - ultima).total_seconds() / 60
        if transcurrido < TIEMPO_ENTRE_PUBLICACIONES:
            log(f"Esperando {TIEMPO_ENTRE_PUBLICACIONES - transcurrido:.0f} min", 'advertencia')
            return False, estado
    except:
        pass
    return True, estado

# =============================================================================
# BÚSQUEDA EN FUENTES ABIERTAS
# =============================================================================

def buscar_reddit():
    """Busca videos en subreddits de noticias/conflictos"""
    videos = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for subreddit in random.sample(REDDIT_SUBREDDITS, min(4, len(REDDIT_SUBREDDITS))):
        try:
            time.sleep(2)
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=15"
            resp = requests.get(url, headers=headers, timeout=15)
            
            if resp.status_code != 200:
                continue
                
            data = resp.json()
            if 'data' not in data:
                continue
                
            for post in data['data']['children']:
                post_data = post['data']
                
                # Solo videos
                if not post_data.get('is_video') and 'v.redd.it' not in post_data.get('url', ''):
                    continue
                
                titulo = post_data.get('title', '')
                if not any(p in titulo.lower() for p in TODAS_PALABRAS):
                    continue
                
                videos.append({
                    'titulo': titulo,
                    'url': f"https://www.reddit.com{post_data.get('permalink', '')}",
                    'video_url': post_data.get('url') if 'v.redd.it' in post_data.get('url', '') else None,
                    'fuente': f'Reddit/r/{subreddit}',
                    'tipo': 'reddit',
                    'categoria': detectar_categoria(titulo)
                })
        except Exception as e:
            log(f"Reddit error: {str(e)[:50]}", 'advertencia')
    
    log(f"Reddit: {len(videos)} videos", 'video')
    return videos

def buscar_rumble():
    """Busca videos en Rumble (plataforma alternativa)"""
    videos = []
    
    try:
        # Rumble tiene una API pública básica
        canales = random.sample(RUMBLE_CHANNELS, min(3, len(RUMBLE_CHANNELS)))
        
        for canal in canales:
            try:
                url = f"https://rumble.com/c/{canal}"
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                resp = requests.get(url, headers=headers, timeout=15)
                
                if resp.status_code == 200:
                    # Extraer videos de la página
                    pattern = r'https://rumble\.com/v[a-zA-Z0-9]+-[^\"]+'
                    matches = list(set(re.findall(pattern, resp.text)))
                    
                    for match in matches[:5]:
                        try:
                            # Obtener título de la URL
                            titulo = match.split('-', 1)[1].replace('-', ' ').title()
                            
                            if any(p in titulo.lower() for p in TODAS_PALABRAS):
                                videos.append({
                                    'titulo': titulo[:100],
                                    'url': match,
                                    'fuente': f'Rumble/{canal}',
                                    'tipo': 'rumble',
                                    'categoria': detectar_categoria(titulo)
                                })
                        except:
                            continue
            except:
                continue
    except Exception as e:
        log(f"Rumble error: {str(e)[:50]}", 'advertencia')
    
    log(f"Rumble: {len(videos)} videos", 'video')
    return videos

def buscar_bitchute():
    """Busca videos en Bitchute"""
    videos = []
    
    try:
        for canal in random.sample(BITCHUTE_CHANNELS, min(2, len(BITCHUTE_CHANNELS))):
            try:
                url = f"https://www.bitchute.com/channel/{canal}/"
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                resp = requests.get(url, headers=headers, timeout=15)
                
                if resp.status_code == 200:
                    # Extraer IDs de video
                    pattern = r'/video/([a-zA-Z0-9]+)/'
                    matches = list(set(re.findall(pattern, resp.text)))
                    
                    for video_id in matches[:5]:
                        video_url = f"https://www.bitchute.com/video/{video_id}/"
                        # El título está en el HTML, simplificamos
                        titulo = f"Video {video_id}"
                        
                        videos.append({
                            'titulo': titulo,
                            'url': video_url,
                            'fuente': f'Bitchute/{canal}',
                            'tipo': 'bitchute',
                            'categoria': 'conflictos'
                        })
            except:
                continue
    except Exception as e:
        log(f"Bitchute error: {str(e)[:50]}", 'advertencia')
    
    log(f"Bitchute: {len(videos)} videos", 'video')
    return videos

def buscar_tiktok():
    """Busca videos en TikTok por tags (públicos)"""
    videos = []
    
    try:
        # TikTok tiene un endpoint no oficial para búsqueda
        tag = random.choice(TIKTOK_TAGS)
        url = f"https://www.tiktok.com/tag/{tag}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.tiktok.com/'
        }
        
        resp = requests.get(url, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            # Extraer URLs de video
            pattern = r'https://www\.tiktok\.com/@[\w\.]+/video/\d+'
            matches = list(set(re.findall(pattern, resp.text)))
            
            for match in matches[:5]:
                videos.append({
                    'titulo': f'TikTok {tag}',
                    'url': match,
                    'fuente': 'TikTok',
                    'tipo': 'tiktok',
                    'categoria': detectar_categoria(tag)
                })
    except Exception as e:
        log(f"TikTok error: {str(e)[:50]}", 'advertencia')
    
    log(f"TikTok: {len(videos)} videos", 'video')
    return videos

def buscar_newsapi():
    """Busca noticias y extrae URLs de video si existen"""
    videos = []
    if not NEWS_API_KEY:
        return videos
    
    try:
        # Buscar noticias recientes
        terminos = ['war', 'conflict', 'military', 'attack', 'drone footage']
        query = random.choice(terminos)
        
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                'q': query,
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 20,
                'apiKey': NEWS_API_KEY
            },
            timeout=15
        )
        
        data = resp.json()
        if data.get('status') == 'ok':
            for art in data.get('articles', []):
                titulo = art.get('title', '')
                url = art.get('url', '')
                
                if '[Removed]' in titulo or not url:
                    continue
                
                # Verificar si es relevante
                if any(p in titulo.lower() for p in TODAS_PALABRAS):
                    # Intentar detectar si tiene video (por dominio)
                    dominio = urlparse(url).netloc.lower()
                    
                    # Algunos sitios de noticias tienen video
                    sitios_con_video = ['bbc.com', 'reuters.com', 'aljazeera.com', 
                                       'france24.com', 'rt.com', 'cnn.com']
                    
                    if any(s in dominio for s in sitios_con_video):
                        videos.append({
                            'titulo': titulo,
                            'url': url,  # yt-dlp extraerá el video de la página
                            'fuente': art.get('source', {}).get('name', 'News'),
                            'tipo': 'news_site',
                            'categoria': detectar_categoria(titulo)
                        })
    except Exception as e:
        log(f"NewsAPI error: {str(e)[:50]}", 'advertencia')
    
    log(f"NewsAPI: {len(videos)} noticias", 'video')
    return videos

def buscar_todos():
    """Busca en todas las fuentes"""
    log("Buscando videos...", 'video')
    videos = []
    
    # Fuentes principales
    videos.extend(buscar_reddit())
    videos.extend(buscar_rumble())
    
    # Fuentes secundarias si faltan
    if len(videos) < 5:
        videos.extend(buscar_bitchute())
    if len(videos) < 5:
        videos.extend(buscar_tiktok())
    if len(videos) < 3:
        videos.extend(buscar_newsapi())
    
    # Eliminar duplicados
    urls_vistas = set()
    unicos = []
    for v in videos:
        if v['url'] not in urls_vistas:
            urls_vistas.add(v['url'])
            unicos.append(v)
    
    log(f"Total únicos: {len(unicos)}", 'exito')
    return unicos

# =============================================================================
# DESCARGA DE VIDEO (Múltiples métodos)
# =============================================================================

def descargar_con_ytdlp(url, tipo):
    """
    Descarga usando yt-dlp con múltiples configuraciones
    """
    log(f"Descargando {tipo}...", 'video')
    
    # Configuración base
    ydl_opts = {
        'format': 'best[filesize<80M]/best[height<=720]/best',
        'outtmpl': '/tmp/video_%(id)s.%(ext)s',
        'max_filesize': 80000000,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    }
    
    # Agregar cookies si existen (para FB/IG)
    if COOKIES_PATH and os.path.exists(COOKIES_PATH):
        ydl_opts['cookiefile'] = COOKIES_PATH
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if not info:
                return None
            
            video_path = ydl.prepare_filename(info)
            
            # Buscar archivo si cambió extensión
            if not os.path.exists(video_path):
                base = os.path.splitext(video_path)[0]
                for ext in ['.mp4', '.mkv', '.webm']:
                    if os.path.exists(base + ext):
                        video_path = base + ext
                        break
            
            if os.path.exists(video_path) and os.path.getsize(video_path) > 500000:
                size_mb = os.path.getsize(video_path) / 1024 / 1024
                log(f"Descargado: {size_mb:.1f}MB", 'exito')
                return video_path
            
            return None
            
    except Exception as e:
        error_msg = str(e).lower()
        
        # Si falla por formato, intentar con opciones más permisivas
        if "format" in error_msg or "requested format" in error_msg:
            log("Reintentando con formato alternativo...", 'advertencia')
            try:
                ydl_opts['format'] = 'worst[filesize<80M]/best[filesize<80M]'
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    video_path = ydl.prepare_filename(info)
                    if os.path.exists(video_path):
                        return video_path
            except:
                pass
        
        log(f"Error yt-dlp: {str(e)[:80]}", 'error')
        return None

def descargar_facebook_externo(url):
    """
    Intenta descargar de Facebook usando servicios externos (savefrom, etc.)
    NOTA: Estos servicios cambian constantemente y pueden bloquear bots
    """
    log("Intentando descarga externa de Facebook...", 'video')
    
    # Lista de APIs/servicios de descarga (pueden dejar de funcionar)
    servicios = [
        # SaveFrom API no oficial (puede no funcionar)
        {
            'url': 'https://sssavefrom.net/api/convert',
            'method': 'POST',
            'data': {'url': url}
        },
        # FDownloader API
        {
            'url': 'https://fdownloader.net/api/ajaxSearch',
            'method': 'POST',
            'data': {'q': url, 'vt': 'facebook'}
        }
    ]
    
    for servicio in servicios:
        try:
            if servicio['method'] == 'POST':
                resp = requests.post(
                    servicio['url'], 
                    data=servicio['data'], 
                    timeout=30,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
            else:
                resp = requests.get(
                    servicio['url'], 
                    params=servicio.get('params', {}),
                    timeout=30
                )
            
            if resp.status_code == 200:
                data = resp.json()
                
                # Extraer URL de descarga (varía según el servicio)
                download_url = None
                
                if 'url' in data:
                    download_url = data['url']
                elif 'data' in data and 'url' in data['data']:
                    download_url = data['data']['url']
                elif 'links' in data:
                    # Algunos devuelven lista de calidades
                    links = data['links']
                    if isinstance(links, list) and len(links) > 0:
                        download_url = links[0].get('url')
                    elif isinstance(links, dict):
                        download_url = list(links.values())[0].get('url')
                
                if download_url:
                    # Descargar el archivo
                    video_resp = requests.get(download_url, timeout=120, stream=True)
                    if video_resp.status_code == 200:
                        video_path = f"/tmp/fb_video_{int(time.time())}.mp4"
                        with open(video_path, 'wb') as f:
                            for chunk in video_resp.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        if os.path.exists(video_path) and os.path.getsize(video_path) > 500000:
                            log("Descargado vía servicio externo", 'exito')
                            return video_path
            
        except Exception as e:
            log(f"Servicio falló: {str(e)[:50]}", 'advertencia')
            continue
    
    return None

def descargar_video(url, tipo):
    """
    Función principal de descarga con múltiples métodos
    """
    # Método 1: yt-dlp (funciona con Reddit, Rumble, Bitchute, TikTok, y FB/IG si hay cookies)
    video_path = descargar_con_ytdlp(url, tipo)
    if video_path:
        return video_path
    
    # Método 2: Para Facebook/IG específicamente, intentar servicios externos
    if 'facebook.com' in url or 'instagram.com' in url:
        video_path = descargar_facebook_externo(url)
        if video_path:
            return video_path
    
    return None

# =============================================================================
# PUBLICACIÓN
# =============================================================================

def publicar_facebook(titulo, descripcion, video_path, categoria):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Sin credenciales FB", 'error')
        return False
    
    if not os.path.exists(video_path):
        log("Video no existe", 'error')
        return False
    
    hashtags = obtener_hashtags(categoria)
    mensaje = f"🎬 {titulo}\n\n{descripcion[:150]}{'...' if len(descripcion) > 150 else ''}\n\n{hashtags} #Video #Noticias\n\n— Verdad Hoy"
    
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
        
        with open(video_path, 'rb') as f:
            resp = requests.post(
                url,
                files={'file': ('video.mp4', f, 'video/mp4')},
                data={'description': mensaje[:1990], 'access_token': FB_ACCESS_TOKEN},
                timeout=300
            )
        
        result = resp.json()
        
        if 'id' in result:
            log(f"✅ Publicado: {result['id']}", 'exito')
            return True
        else:
            error = result.get('error', {}).get('message', str(result))
            log(f"Error FB: {error}", 'error')
            return False
            
    except Exception as e:
        log(f"Error: {e}", 'error')
        return False

# =============================================================================
# MAIN
# =============================================================================

def limpiar_temporales():
    """Limpia archivos temporales"""
    try:
        import glob
        for f in glob.glob('/tmp/video_*'):
            try:
                os.remove(f)
            except:
                pass
        for f in glob.glob('/tmp/fb_video_*'):
            try:
                os.remove(f)
            except:
                pass
    except:
        pass

def main():
    print("\n" + "="*60)
    print("🎬 BOT DE VIDEOS - VERDAD HOY")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    puede_proceder, estado = verificar_tiempo()
    if not puede_proceder:
        return True
    
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales", 'error')
        return False
    
    limpiar_temporales()
    historial = cargar_historial()
    videos = buscar_todos()
    
    if not videos:
        log("No se encontraron videos", 'error')
        return False
    
    # Filtrar publicados
    videos = [v for v in videos if not ya_publicado(historial, v['url'], v['titulo'])]
    log(f"Nuevos: {len(videos)}")
    
    if not videos:
        log("No hay videos nuevos", 'advertencia')
        return False
    
    # Intentar publicar
    for intento, video in enumerate(videos[:5]):
        log(f"\nIntento {intento+1}: {video['titulo'][:50]}...")
        
        video_path = descargar_video(video['url'], video['tipo'])
        
        if not video_path:
            continue
        
        # Verificar tamaño
        if os.path.getsize(video_path) < 500000:
            log("Video muy pequeño", 'advertencia')
            os.remove(video_path)
            continue
        
        exito = publicar_facebook(
            video['titulo'],
            video.get('descripcion', ''),
            video_path,
            video['categoria']
        )
        
        # Limpiar
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
        except:
            pass
        
        if exito:
            guardar_historial(historial, video['url'], video['titulo'], video['fuente'])
            estado['ultima_publicacion'] = datetime.now().isoformat()
            guardar_json(ESTADO_PATH, estado)
            
            print("\n" + "="*60)
            log("✅ VIDEO PUBLICADO", 'exito')
            print(f"🎬 {video['titulo'][:60]}")
            print(f"🏢 {video['fuente']}")
            print(f"📂 {video['categoria']}")
            print("="*60)
            return True
    
    log("Todos los intentos fallaron", 'error')
    return False

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

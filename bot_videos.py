#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Videos para Facebook - Verdad Hoy
Publica videos de noticias cada 1 hora
Fuentes: Dailymotion, Vimeo, Reddit, Twitter/X (si disponible), y URLs directas
"""

import requests
import feedparser
import re
import hashlib
import json
import os
import random
import subprocess
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import yt_dlp

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_videos.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot.json')

TIEMPO_ENTRE_PUBLICACIONES = 58  # minutos

# =============================================================================
# CATEGORÍAS
# =============================================================================

CATEGORIAS = {
    'conflictos_guerra': {
        'palabras': [
            'guerra', 'conflicto', 'ataque', 'bombardeo', 'invasión', 'ofensiva', 'misil',
            'batalla', 'combate', 'enfrentamiento', 'tensión internacional', 'sanciones',
            'embargo', 'crisis diplomática', 'guerra civil', 'rebelión', 'insurgencia',
            'terrorismo', 'ataque terrorista', 'extremista', 'yihadista', 'talibán',
            'isis', 'al qaeda', 'guerrilla', 'paramilitar', 'milicia', 'ejército',
            'soldados', 'tropas', 'despliegue militar', 'base militar', 'arsenal',
            'armas', 'destrucción', 'masacre', 'genocidio', 'crímenes de guerra',
            'ucrania', 'rusia', 'gaza', 'palestina', 'israel', 'hamás', 'líbano', 'hezbolá',
            'siria', 'irak', 'afganistán', 'yemen', 'myanmar', 'sudán', 'etiopía', 'somalia',
            'mali', 'níger', 'burkina faso', 'haití', 'dron', 'drones', 'ucav', 'misil balístico',
            'artillería', 'tanque', 'blindado', 'helicóptero', 'caza', 'bombardero',
        ],
        'hashtags': ['#Guerra', '#Conflicto', '#Militar']
    },
    
    'narcotrafico': {
        'palabras': [
            'narcotráfico', 'droga', 'cártel', 'cartel', 'tráfico de drogas', 'cocaína',
            'marihuana', 'fentanilo', 'metanfetamina', 'laboratorio clandestino',
            'narco', 'narcotraficante', 'capo', 'jefe de cartel', 'sicario', 'ejecución',
            'balacera', 'enfrentamiento armado', 'decomiso', 'incautación', 'tonelada',
            'ruta del narcotráfico', 'lavado de dinero', 'narcobloqueo', 'narcotúnel',
            'sinaloa', 'jalisco', 'cjng', 'golfo', 'zetas', 'michoacana', 'tijuana',
            'colombia', 'méxico', 'perú', 'bolivia', 'honduras', 'guatemala', 'el salvador',
        ],
        'hashtags': ['#Narcotráfico', '#Seguridad', '#CrimenOrganizado']
    },
    
    'politica_internacional': {
        'palabras': [
            'gobierno', 'presidente', 'elecciones', 'política', 'político', 'congreso',
            'parlamento', 'senado', 'ministro', 'canciller', 'embajador', 'diplomacia',
            'cumbre', 'g20', 'g7', 'onu', 'otan', 'unión europea', 'brexit',
            'impeachment', 'corrupción', 'protesta', 'manifestación', 'huelga',
            'golpe de estado', 'crisis política', 'dimisión', 'renuncia', 'fraude electoral',
            'oposición', 'partido político', 'campaña electoral', 'debate', 'discurso',
        ],
        'hashtags': ['#Política', '#Internacional', '#Gobierno']
    },
    
    'crisis_economica': {
        'palabras': [
            'crisis económica', 'recesión', 'inflación', 'devaluación', 'quiebra',
            'bancarrota', 'crisis financiera', 'colapso económico', 'deuda',
            'fmi', 'bm', 'reserva federal', 'bce', 'crisis bancaria', 'corralito',
            'deuda soberana', 'crisis de deuda', 'rescate económico', 'austeridad',
            'desempleo', 'paro', 'crisis laboral', 'huelga general', 'protesta social',
        ],
        'hashtags': ['#Economía', '#Crisis', '#Finanzas']
    },
    
    'desastres_tragedias': {
        'palabras': [
            'terremoto', 'tsunami', 'huracán', 'tornado', 'inundación', 'incendio',
            'sequía', 'hambruna', 'epidemia', 'pandemia', 'accidente', 'tragedia',
            'desastre natural', 'catástrofe', 'emergencia', 'evacuación', 'rescate',
            'derrumbe', 'explosión', 'accidente aéreo', 'accidente marítimo',
            'víctimas', 'muertos', 'heridos', 'desaparecidos', 'damnificados',
        ],
        'hashtags': ['#Desastre', '#Emergencia', '#Tragedia']
    },
    
    'violencia_crimen': {
        'palabras': [
            'violencia', 'homicidio', 'asesinato', 'masacre', 'ejecución', 'secuestro',
            'extorsión', 'tráfico de personas', 'tráfico de armas', 'contrabando',
            'crimen organizado', 'pandilla', 'mara', 'prisión', 'fuga', 'motín',
            'robo', 'atraco', 'asalto', 'agresión', 'detenido', 'arrestado',
            'operativo policial', 'redada', 'allanamiento', 'persecución',
        ],
        'hashtags': ['#Violencia', '#Crimen', '#Seguridad']
    }
}

TODAS_PALABRAS = []
for cat in CATEGORIAS.values():
    TODAS_PALABRAS.extend(cat['palabras'])

# =============================================================================
# FUENTES DE VIDEO ESTABLES (Sin YouTube)
# =============================================================================

# RSS de video que funcionan bien
RSS_FEEDS_VIDEO = [
    # BBC Video (funciona bien)
    'https://feeds.bbci.co.uk/news/video_and_audio/world/rss.xml ',
    
    # Reuters Video
    'https://www.reutersagency.com/feed/?best-topics=world&format=mrss ',
    
    # AP Video (Associated Press)
    'https://api.ap.org/media/v/content/feed?format=mrss ',
]

# Canales de Dailymotion de noticias (más permisivo que YouTube)
DAILYMOTION_CHANNELS = [
    'euronews', 'france24', 'rt', 'trtworld', 'cgtn', 'aljazeera', 'afp', 'reuters'
]

# Subreddits de video de conflictos
REDDIT_SUBREDDITS = [
    'CombatFootage', 'war', 'syriancivilwar', 'UkraineWarVideoReport', 
    'NarcoFootage', 'ActualPublicFreakouts', 'CatastrophicFailure'
]

# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def log(mensaje, tipo='info'):
    """Imprime mensajes con formato"""
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍', 'video': '🎬'}
    icono = iconos.get(tipo, 'ℹ️')
    print(f"{icono} {mensaje}")

def cargar_json(ruta, default=None):
    """Carga un archivo JSON"""
    if default is None:
        default = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error cargando {ruta}: {e}", 'error')
    return default

def guardar_json(ruta, datos):
    """Guarda datos en archivo JSON"""
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"Error guardando {ruta}: {e}", 'error')
        return False

def generar_hash(texto):
    """Genera hash MD5"""
    return hashlib.md5(texto.lower().strip().encode()).hexdigest()

def detectar_categoria(titulo, descripcion):
    """Detecta la categoría de una noticia"""
    texto = f"{titulo} {descripcion}".lower()
    
    puntuaciones = {}
    for nombre_categoria, datos in CATEGORIAS.items():
        score = sum(1 for palabra in datos['palabras'] if palabra in texto)
        puntuaciones[nombre_categoria] = score
    
    if max(puntuaciones.values()) > 0:
        return max(puntuaciones, key=puntuaciones.get)
    
    return 'conflictos_guerra'

def obtener_hashtags_categoria(categoria):
    """Obtiene hashtags de una categoría"""
    return ' '.join(CATEGORIAS.get(categoria, {}).get('hashtags', ['#Noticias', '#Actualidad']))

# =============================================================================
# GESTIÓN DE HISTORIAL Y ESTADO
# =============================================================================

def cargar_historial():
    """Carga el historial de videos"""
    default = {
        'urls': [], 
        'titulos': [], 
        'hashes': [], 
        'ultima_publicacion': None, 
        'videos': []
    }
    historial = cargar_json(HISTORIAL_PATH, default)
    log(f"Historial cargado: {len(historial.get('videos', []))} videos")
    return historial

def guardar_historial(historial, url, titulo, video_path, fuente_tipo='dailymotion'):
    """Guarda un video en el historial"""
    url_hash = generar_hash(url)
    
    historial.setdefault('urls', []).append(url)
    historial.setdefault('titulos', []).append(titulo[:100])
    historial.setdefault('hashes', []).append(url_hash)
    historial.setdefault('videos', []).append({
        'url': url,
        'titulo': titulo[:100],
        'fecha': datetime.now().isoformat(),
        'archivo': os.path.basename(video_path) if video_path else None,
        'fuente': fuente_tipo
    })
    historial['ultima_publicacion'] = datetime.now().isoformat()
    
    for key in ['urls', 'titulos', 'hashes']:
        historial[key] = historial[key][-200:]
    historial['videos'] = historial['videos'][-200:]
    
    guardar_json(HISTORIAL_PATH, historial)
    log(f"Video guardado en historial [{fuente_tipo}]", 'exito')

def noticia_ya_publicada(historial, url, titulo):
    """Verifica si ya fue publicada"""
    url_hash = generar_hash(url)
    
    if url_hash in historial.get('hashes', []):
        return True
    if url in historial.get('urls', []):
        return True
    
    titulo_simple = re.sub(r'[^\w]', '', titulo.lower())[:30]
    for t in historial.get('titulos', []):
        t_simple = re.sub(r'[^\w]', '', t.lower())[:30]
        if titulo_simple == t_simple:
            return True
    
    return False

def cargar_estado():
    """Carga el estado del bot"""
    default = {
        'ultima_publicacion': None,
        'total_publicadas': 0,
        'ultima_fuente': None,
        'ultima_categoria': None
    }
    return cargar_json(ESTADO_PATH, default)

def guardar_estado(estado):
    """Guarda el estado del bot"""
    guardar_json(ESTADO_PATH, estado)

def verificar_tiempo_ultima_publicacion(estado):
    """Verifica si ya pasó el tiempo mínimo"""
    if not estado.get('ultima_publicacion'):
        return True, 0, 0
    
    try:
        ultima = datetime.fromisoformat(estado['ultima_publicacion'])
        ahora = datetime.now()
        transcurrido = (ahora - ultima).total_seconds() / 60
        
        if transcurrido < TIEMPO_ENTRE_PUBLICACIONES:
            faltan = TIEMPO_ENTRE_PUBLICACIONES - transcurrido
            return False, transcurrido, faltan
        
        return True, transcurrido, 0
        
    except Exception as e:
        return True, 0, 0

# =============================================================================
# BÚSQUEDA DE VIDEOS EN FUENTES ALTERNATIVAS
# =============================================================================

def buscar_videos_dailymotion():
    """
    Busca videos en Dailymotion de canales de noticias
    Dailymotion es más permisivo que YouTube para descargas
    """
    videos = []
    
    try:
        # API pública de Dailymotion (no requiere auth para búsqueda básica)
        for canal in random.sample(DAILYMOTION_CHANNELS, 4):
            try:
                # Buscar videos del canal
                search_terms = ['war', 'conflict', 'attack', 'military', 'narcotraffic', 'police']
                termino = random.choice(search_terms)
                
                url_api = f"https://api.dailymotion.com/videos?owners={canal}&search={termino}&limit=10&sort=recent&fields=id,title,description,url,created_time,duration"
                
                resp = requests.get(url_api, timeout=15)
                data = resp.json()
                
                if 'list' in data:
                    for video in data['list']:
                        titulo = video.get('title', '')
                        descripcion = video.get('description', '')
                        duracion = video.get('duration', 0)
                        
                        # Filtrar por relevancia
                        es_relevante = any(p in f"{titulo} {descripcion}".lower() for p in TODAS_PALABRAS)
                        
                        # Priorizar videos cortos (30s - 5min)
                        if es_relevante and 30 <= duracion <= 300:
                            categoria = detectar_categoria(titulo, descripcion)
                            
                            videos.append({
                                'titulo': titulo,
                                'descripcion': descripcion[:300],
                                'url': f"https://www.dailymotion.com/video/ {video['id']}",
                                'fuente': f'Dailymotion/{canal}',
                                'fecha': video.get('created_time', ''),
                                'duracion': duracion,
                                'puntaje': 10 if categoria in ['conflictos_guerra', 'narcotrafico'] else 7,
                                'tipo_url': 'dailymotion',
                                'categoria': categoria,
                                'id_video': video['id']
                            })
                            
            except Exception as e:
                log(f"Error Dailymotion {canal}: {str(e)[:50]}", 'advertencia')
                continue
                
    except Exception as e:
        log(f"Error general Dailymotion: {str(e)[:50]}", 'advertencia')
    
    log(f"Dailymotion: {len(videos)} videos", 'video')
    return videos

def buscar_videos_reddit():
    """
    Busca videos en subreddits de conflictos
    Reddit tiene mucho contenido de video de calidad
    """
    videos = []
    
    try:
        # Reddit JSON API (pública, no requiere auth para lectura)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        for subreddit in random.sample(REDDIT_SUBREDDITS, 3):
            try:
                url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=15"
                resp = requests.get(url, headers=headers, timeout=15)
                data = resp.json()
                
                if 'data' in data and 'children' in data['data']:
                    for post in data['data']['children']:
                        post_data = post['data']
                        
                        # Solo posts con video
                        if not post_data.get('is_video') and 'v.redd.it' not in post_data.get('url', ''):
                            continue
                        
                        titulo = post_data.get('title', '')
                        
                        # Verificar relevancia
                        es_relevante = any(p in titulo.lower() for p in TODAS_PALABRAS)
                        
                        if es_relevante:
                            # Obtener URL del video
                            video_url = post_data.get('url', '')
                            
                            # Si es video de Reddit directo
                            if 'v.redd.it' in video_url or post_data.get('is_video'):
                                categoria = detectar_categoria(titulo, '')
                                
                                videos.append({
                                    'titulo': titulo,
                                    'descripcion': post_data.get('selftext', '')[:300],
                                    'url': f"https://www.reddit.com{post_data.get('permalink', '')}",
                                    'video_url_directa': video_url if 'v.redd.it' in video_url else None,
                                    'fuente': f'Reddit/r/{subreddit}',
                                    'fecha': datetime.fromtimestamp(post_data.get('created_utc', 0)).isoformat(),
                                    'puntaje': 9,
                                    'tipo_url': 'reddit',
                                    'categoria': categoria,
                                    'reddit_id': post_data.get('id')
                                })
                                
            except Exception as e:
                log(f"Error Reddit {subreddit}: {str(e)[:50]}", 'advertencia')
                continue
                
    except Exception as e:
        log(f"Error general Reddit: {str(e)[:50]}", 'advertencia')
    
    log(f"Reddit: {len(videos)} videos", 'video')
    return videos

def buscar_videos_newsapi_con_filtro():
    """
    Busca noticias con video en NewsAPI, pero solo procesa las que tienen video descargable
    """
    videos = []
    if not NEWS_API_KEY:
        log("NewsAPI no configurado", 'advertencia')
        return videos
    
    # Buscar noticias de video específicamente
    terminos = [
        'site:youtube.com war conflict', 'site:youtube.com military',
        'site:dailymotion.com news conflict', 'site:liveleak.com',
        'war footage video', 'military operation video'
    ]
    
    for termino in random.sample(terminos, 2):
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything ",
                params={
                    'q': termino,
                    'language': 'en',
                    'sortBy': 'publishedAt',
                    'pageSize': 15,
                    'apiKey': NEWS_API_KEY
                },
                timeout=15
            )
            data = resp.json()
            
            if data.get('status') == 'ok':
                for art in data.get('articles', []):
                    titulo = art.get('title', '')
                    url = art.get('url', '')
                    
                    if not titulo or '[Removed]' in titulo:
                        continue
                    
                    # Solo procesar si la URL es de una plataforma de video conocida
                    es_video_url = any(v in url.lower() for v in [
                        'youtube.com', 'youtu.be', 'dailymotion.com', 
                        'vimeo.com', 'rumble.com', 'bitchute.com'
                    ])
                    
                    if es_video_url:
                        categoria = detectar_categoria(titulo, art.get('description', ''))
                        
                        videos.append({
                            'titulo': titulo,
                            'descripcion': art.get('description', ''),
                            'url': url,
                            'fuente': art.get('source', {}).get('name', 'NewsAPI'),
                            'fecha': art.get('publishedAt', ''),
                            'puntaje': 8 if categoria in ['conflictos_guerra', 'narcotrafico'] else 5,
                            'tipo_url': 'newsapi_video',
                            'categoria': categoria
                        })
                        
        except Exception as e:
            log(f"Error NewsAPI: {str(e)[:50]}", 'advertencia')
    
    log(f"NewsAPI (filtrado): {len(videos)} videos", 'info')
    return videos

def buscar_videos_rss_simple():
    """
    RSS simplificado - solo busca enlaces directos de video en feeds
    """
    videos = []
    
    for feed_url in RSS_FEEDS_VIDEO[:2]:  # Solo 2 para no saturar
        try:
            feed = feedparser.parse(feed_url)
            fuente = feed.feed.get('title', 'RSS')
            
            for entry in feed.entries[:3]:
                titulo = entry.get('title', '')
                if not titulo:
                    continue
                
                # Buscar media content con URL directa de video
                video_url = None
                
                if hasattr(entry, 'media_content'):
                    for media in entry.media_content:
                        url = media.get('url', '')
                        # Solo si es URL directa de video
                        if any(ext in url.lower() for ext in ['.mp4', '.m3u8', 'video']):
                            video_url = url
                            break
                
                # Si encontramos video directo
                if video_url:
                    categoria = detectar_categoria(titulo, entry.get('summary', ''))
                    
                    videos.append({
                        'titulo': titulo,
                        'descripcion': entry.get('summary', ''),
                        'url': video_url,  # URL directa del video
                        'fuente': fuente,
                        'fecha': entry.get('published', ''),
                        'puntaje': 7,
                        'tipo_url': 'rss_directo',
                        'categoria': categoria
                    })
                    
        except Exception as e:
            continue
    
    log(f"RSS (directo): {len(videos)} videos", 'info')
    return videos

def buscar_todos_videos():
    """Busca videos en todas las fuentes disponibles"""
    log("Iniciando búsqueda de videos...", 'video')
    
    todos_videos = []
    
    # Fuente 1: Dailymotion (más estable, no bloquea)
    todos_videos.extend(buscar_videos_dailymotion())
    
    # Fuente 2: Reddit (mucho contenido de conflictos)
    if len(todos_videos) < 5:
        todos_videos.extend(buscar_videos_reddit())
    
    # Fuente 3: NewsAPI con filtro de video
    if len(todos_videos) < 5:
        todos_videos.extend(buscar_videos_newsapi_con_filtro())
    
    # Fuente 4: RSS con videos directos
    if len(todos_videos) < 3:
        todos_videos.extend(buscar_videos_rss_simple())
    
    # Eliminar duplicados por URL
    urls_vistas = set()
    videos_unicos = []
    for v in todos_videos:
        url = v['url']
        if url and url not in urls_vistas:
            urls_vistas.add(url)
            videos_unicos.append(v)
    
    log(f"Total videos únicos: {len(videos_unicos)}", 'exito')
    return videos_unicos

# =============================================================================
# DESCARGA DE VIDEOS
# =============================================================================

def descargar_video(url, tipo_fuente='dailymotion', info_extra=None):
    """
    Descarga video según la fuente
    """
    if not url:
        return None, None
    
    log(f"Descargando desde {tipo_fuente}: {url[:60]}...", 'video')
    
    try:
        # Configuración base
        ydl_opts = {
            'format': 'best[height>=720][ext=mp4][filesize<100M]/best[height>=720][filesize<100M]/best[ext=mp4][filesize<100M]/best[filesize<100M]',
            'outtmpl': '/tmp/video_%(id)s_%(height)s.%(ext)s',
            'max_filesize': 100000000,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }
        }
        
        # Configuración específica por fuente
        if tipo_fuente == 'reddit':
            ydl_opts['format'] = 'best[filesize<100M]/best'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return None, None
            
            # Verificar duración
            duracion = info.get('duration', 0)
            if duracion > 300:  # 5 minutos máximo
                log(f"Video muy largo ({duracion}s)", 'advertencia')
                return None, info
            
            # Descargar
            ydl.download([url])
            
            # Encontrar archivo
            video_path = ydl.prepare_filename(info)
            
            if not os.path.exists(video_path):
                base = os.path.splitext(video_path)[0]
                for ext in ['.mp4', '.mkv', '.webm']:
                    if os.path.exists(base + ext):
                        video_path = base + ext
                        break
            
            if os.path.exists(video_path) and os.path.getsize(video_path) > 500000:
                size_mb = os.path.getsize(video_path) / 1024 / 1024
                log(f"Descargado: {size_mb:.1f} MB", 'exito')
                return video_path, info
            
            return None, info
            
    except Exception as e:
        log(f"Error descarga: {str(e)[:80]}", 'error')
        return None, None

def verificar_video(video_path):
    """Verifica que el video sea válido"""
    try:
        if not os.path.exists(video_path):
            return False, "No existe"
        
        size = os.path.getsize(video_path)
        if size < 500000:  # Menos de 500KB
            return False, "Muy pequeño"
        
        # Verificar con ffprobe
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration',
            '-of', 'json', video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        info = json.loads(result.stdout)
        
        if 'streams' in info and info['streams']:
            stream = info['streams'][0]
            height = stream.get('height', 0)
            duration = float(stream.get('duration', 0))
            
            log(f"Video: {height}p | {duration:.1f}s", 'debug')
            
            if height < 480:  # Calidad mínima aceptable
                return False, f"Baja calidad ({height}p)"
            
            if duration > 300:
                return recortar_video(video_path, 180)
            
            return True, video_path
        
        return False, "No se pudo analizar"
        
    except Exception as e:
        log(f"Error verificación: {e}", 'advertencia')
        return True, video_path  # Asumir OK

def recortar_video(video_path, duracion=180):
    """Recorta video"""
    try:
        output = video_path.replace('.mp4', '_cut.mp4')
        
        cmd = [
            'ffmpeg', '-y', '-i', video_path,
            '-t', str(duracion),
            '-c:v', 'libx264', '-preset', 'fast',
            '-c:a', 'aac', '-b:a', '128k',
            output
        ]
        
        subprocess.run(cmd, capture_output=True, timeout=120)
        
        if os.path.exists(output):
            os.remove(video_path)
            return True, output
        
        return False, "No se pudo recortar"
        
    except Exception as e:
        return False, str(e)

# =============================================================================
# PUBLICACIÓN EN FACEBOOK
# =============================================================================

def publicar_video(titulo, descripcion, video_path, categoria):
    """Publica video en Facebook"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Faltan credenciales", 'error')
        return False
    
    if not os.path.exists(video_path):
        log("Archivo no existe", 'error')
        return False
    
    hashtags = obtener_hashtags_categoria(categoria)
    
    mensaje = f"""🎬 {titulo}

{descripcion[:250]}{"..." if len(descripcion) > 250 else ""}

{hashtags} #Video #Noticias

— Verdad Hoy: Noticias al minuto"""
    
    if len(mensaje) > 2000:
        mensaje = mensaje[:1990] + "..."
    
    size_mb = os.path.getsize(video_path) / 1024 / 1024
    log(f"Subiendo a Facebook ({size_mb:.1f} MB)...", 'video')
    
    try:
        url = f"https://graph.facebook.com/v18.0/ {FB_PAGE_ID}/videos"
        
        with open(video_path, 'rb') as f:
            resp = requests.post(
                url,
                files={'file': f},
                data={
                    'description': mensaje,
                    'access_token': FB_ACCESS_TOKEN
                },
                timeout=600
            )
        
        result = resp.json()
        
        if resp.status_code == 200 and 'id' in result:
            log(f"✅ Publicado: {result['id']}", 'exito')
            return True
        else:
            error = result.get('error', {}).get('message', str(result))
            log(f"Error Facebook: {error}", 'error')
            return False
            
    except Exception as e:
        log(f"Error: {e}", 'error')
        return False

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def main():
    """Función principal"""
    print("\n" + "="*70)
    print("🎬 BOT DE VIDEOS - VERDAD HOY")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  Frecuencia: cada ~{TIEMPO_ENTRE_PUBLICACIONES+2} minutos")
    print("="*70)
    
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales Facebook", 'error')
        return False
    
    log("Credenciales OK")
    
    estado = cargar_estado()
    puede_publicar, transcurrido, faltan = verificar_tiempo_ultima_publicacion(estado)
    
    if not puede_publicar:
        log(f"⏳ Esperando {faltan:.0f} minutos", 'advertencia')
        return True
    
    log("✅ Iniciando búsqueda", 'exito')
    
    historial = cargar_historial()
    
    # Buscar videos
    videos = buscar_todos_videos()
    
    if not videos:
        log("No se encontraron videos", 'error')
        return False
    
    # Filtrar ya publicados
    videos_nuevos = [v for v in videos if not noticia_ya_publicada(historial, v['url'], v['titulo'])]
    log(f"Nuevos: {len(videos_nuevos)} de {len(videos)}")
    
    candidatos = videos_nuevos if videos_nuevos else videos
    
    # Evitar misma fuente
    ultima_fuente = estado.get('ultima_fuente', '')
    diferentes = [v for v in candidatos if v['fuente'] != ultima_fuente]
    if diferentes:
        candidatos = diferentes
    
    # Ordenar por puntaje
    candidatos.sort(key=lambda x: x.get('puntaje', 0), reverse=True)
    
    # Intentar descargar y publicar
    for intento, video_info in enumerate(candidatos[:5]):
        log(f"\nIntento {intento+1}: {video_info['titulo'][:50]}...")
        log(f"Fuente: {video_info['fuente']} | Tipo: {video_info['tipo_url']}")
        
        # Descargar según tipo
        tipo = video_info.get('tipo_url', 'dailymotion')
        video_path, info = descargar_video(
            video_info['url'], 
            tipo,
            video_info
        )
        
        if not video_path:
            log("No se pudo descargar, siguiente...", 'advertencia')
            continue
        
        # Verificar
        ok, resultado = verificar_video(video_path)
        
        if not ok:
            log(f"Rechazado: {resultado}", 'advertencia')
            try:
                os.remove(video_path)
            except:
                pass
            continue
        
        if isinstance(resultado, str) and resultado != video_path:
            video_path = resultado
        
        # Publicar
        exito = publicar_video(
            video_info['titulo'],
            video_info.get('descripcion', ''),
            video_path,
            video_info.get('categoria', 'conflictos_guerra')
        )
        
        # Limpiar
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
        except:
            pass
        
        if exito:
            # Guardar
            guardar_historial(
                historial, 
                video_info['url'], 
                video_info['titulo'], 
                video_path,
                video_info.get('tipo_url', 'dailymotion')
            )
            
            # Actualizar estado
            estado['ultima_publicacion'] = datetime.now().isoformat()
            estado['ultima_fuente'] = video_info['fuente']
            estado['ultima_categoria'] = video_info.get('categoria', 'conflictos_guerra')
            estado['total_publicadas'] = estado.get('total_publicadas', 0) + 1
            guardar_estado(estado)
            
            print("\n" + "="*70)
            log("VIDEO PUBLICADO", 'exito')
            print(f"🎬 {video_info['titulo'][:50]}...")
            print(f"🏢 {video_info['fuente']}")
            print(f"📂 {video_info.get('categoria', 'conflictos_guerra')}")
            print(f"📊 Total: {estado['total_publicadas']}")
            print(f"⏰ Próximo: {(datetime.now() + timedelta(hours=1)).strftime('%H:%M')}")
            print("="*70)
            return True
        
        log("Falló, intentando siguiente...", 'advertencia')
    
    log("Todos los intentos fallaron", 'error')
    return False

if __name__ == "__main__":
    try:
        resultado = main()
        exit(0 if resultado else 1)
    except KeyboardInterrupt:
        log("Interrumpido", 'advertencia')
        exit(1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

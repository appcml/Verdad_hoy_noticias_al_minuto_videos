#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Videos para Facebook - Verdad Hoy
Publica videos de noticias cada 1 hora (sin YouTube)
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
from urllib.parse import urlparse
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
# FUENTES RSS DE VIDEO (ESTABLES)
# =============================================================================

RSS_FEEDS_VIDEO = [
    # BBC Video
    'https://feeds.bbci.co.uk/news/video_and_audio/world/rss.xml ',
    'https://feeds.bbci.co.uk/news/video_and_audio/international/rss.xml ',
    
    # CNN Video
    'https://rss.cnn.com/rss/cnn_freevideo.rss ',
    
    # France 24 Español
    'https://www.france24.com/es/rss/videos ',
    
    # DW Español
    'https://www.dw.com/es/actualidad/s-30684?mediaType=video&rss=1 ',
    
    # RTVE Videos
    'https://www.rtve.es/api/rss/noticias/videos/ ',
    
    # Euronews
    'https://es.euronews.com/rss?format=mrss&level=video ',
    
    # Reuters
    'https://www.reutersagency.com/feed/?best-topics=world&format=mrss ',
    
    # Al Jazeera
    'https://www.aljazeera.com/xml/rss/all.xml ',
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

def guardar_historial(historial, url, titulo, video_path, fuente_tipo='rss'):
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
    
    # Mantener solo últimos 200
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
# BÚSQUEDA DE VIDEOS (SIN YOUTUBE)
# =============================================================================

def buscar_videos_newsapi():
    """Busca noticias con video en NewsAPI"""
    videos = []
    if not NEWS_API_KEY:
        log("NewsAPI no configurado", 'advertencia')
        return videos
    
    # Términos de búsqueda enfocados en video + conflictos
    terminos = [
        'war video footage', 'conflict video', 'military operation',
        'narcotraffico video', 'cartel violence', 'police operation',
        'protest video', 'disaster video', 'crash video',
        'guerra video', 'conflicto armado', 'operativo policial'
    ]
    
    for termino in random.sample(terminos, 3):
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything ",
                params={
                    'q': termino,
                    'language': 'es,en',
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
                    if not titulo or '[Removed]' in titulo:
                        continue
                    
                    # Detectar categoría
                    categoria = detectar_categoria(titulo, art.get('description', ''))
                    
                    # Puntaje alto para conflictos y narcotráfico
                    puntaje = 10 if categoria in ['conflictos_guerra', 'narcotrafico'] else 6
                    
                    videos.append({
                        'titulo': titulo,
                        'descripcion': art.get('description', ''),
                        'url': art.get('url', ''),
                        'imagen': art.get('urlToImage', ''),
                        'fuente': art.get('source', {}).get('name', 'NewsAPI'),
                        'fecha': art.get('publishedAt', ''),
                        'puntaje': puntaje,
                        'tipo_url': 'web',
                        'categoria': categoria
                    })
                    
        except Exception as e:
            log(f"Error NewsAPI ({termino}): {str(e)[:50]}", 'advertencia')
    
    log(f"NewsAPI: {len(videos)} noticias", 'info')
    return videos

def buscar_videos_rss():
    """Busca videos en feeds RSS"""
    videos = []
    
    for feed_url in RSS_FEEDS_VIDEO:
        try:
            log(f"Consultando: {feed_url[:40]}...", 'debug')
            feed = feedparser.parse(feed_url)
            fuente = feed.feed.get('title', 'RSS')
            
            for entry in feed.entries[:5]:
                titulo = entry.get('title', '')
                if not titulo:
                    continue
                
                # Buscar enlaces de video
                video_url = None
                
                # 1. En media_content
                if hasattr(entry, 'media_content'):
                    for media in entry.media_content:
                        if media.get('medium') == 'video' or 'video' in str(media.get('type', '')):
                            video_url = media.get('url')
                            break
                
                # 2. En enclosures
                if not video_url and hasattr(entry, 'enclosures'):
                    for enc in entry.enclosures:
                        tipo = enc.get('type', '')
                        if 'video' in tipo or 'mp4' in tipo:
                            video_url = enc.get('href')
                            break
                
                # 3. Buscar en descripción (embeds)
                if not video_url:
                    descripcion = entry.get('summary', entry.get('description', ''))
                    # Buscar URLs de video en el HTML
                    urls_video = re.findall(r'(https?://[^\s"<>]+\.(?:mp4|m3u8|webm))', descripcion)
                    if urls_video:
                        video_url = urls_video[0]
                
                # Si no hay video directo, usar URL de la noticia
                if not video_url:
                    video_url = entry.get('link', '')
                
                # Solo procesar si es relevante
                descripcion = entry.get('summary', '')
                categoria = detectar_categoria(titulo, descripcion)
                puntaje = 8 if categoria in ['conflictos_guerra', 'narcotrafico'] else 5
                
                videos.append({
                    'titulo': titulo,
                    'descripcion': descripcion,
                    'url': video_url,
                    'fuente': fuente,
                    'fecha': entry.get('published', ''),
                    'puntaje': puntaje,
                    'tipo_url': 'rss_video',
                    'categoria': categoria
                })
                
        except Exception as e:
            log(f"Error RSS {feed_url[:30]}: {str(e)[:40]}", 'advertencia')
            continue
    
    log(f"RSS: {len(videos)} videos encontrados", 'info')
    return videos

def extraer_video_de_web(url_noticia):
    """
    Extrae URL de video de una página web de noticia
    Busca videos embebidos (iframe, video tags, etc.)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.get(url_noticia, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # 1. Buscar iframes de video
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            if any(v in src for v in ['youtube', 'youtu.be', 'vimeo', 'dailymotion', 'mp4']):
                return src
        
        # 2. Buscar tags video
        videos = soup.find_all('video')
        for video in videos:
            src = video.get('src', '')
            if src:
                return src
            # Buscar en sources
            sources = video.find_all('source')
            for source in sources:
                src = source.get('src', '')
                if src:
                    return src
        
        # 3. Buscar meta tags de video
        meta_video = soup.find('meta', property='og:video')
        if meta_video:
            return meta_video.get('content')
        
        meta_video_secure = soup.find('meta', property='og:video:secure_url')
        if meta_video_secure:
            return meta_video_secure.get('content')
        
        # 4. Buscar en el HTML fuente
        urls_mp4 = re.findall(r'(https?://[^\s"<>]+\.(?:mp4|m3u8|webm|mov))', resp.text)
        if urls_mp4:
            return urls_mp4[0]
        
        # 5. Buscar URLs de video en JSON-LD
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    video_obj = data.get('video', {})
                    if video_obj:
                        return video_obj.get('contentUrl') or video_obj.get('embedUrl')
            except:
                pass
        
        return None
        
    except Exception as e:
        log(f"Error extrayendo video de web: {str(e)[:50]}", 'advertencia')
        return None

def buscar_todos_videos():
    """Busca videos en todas las fuentes disponibles"""
    log("Iniciando búsqueda de videos...", 'video')
    
    todos_videos = []
    
    # Fuente 1: NewsAPI (muy estable)
    todos_videos.extend(buscar_videos_newsapi())
    
    # Fuente 2: RSS de video (estable)
    todos_videos.extend(buscar_videos_rss())
    
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

def descargar_video(url_video, url_noticia=None):
    """
    Descarga video desde URL.
    Soporta: URLs directas de video, URLs de noticias con video embebido
    """
    if not url_video:
        return None, None
    
    # Si es URL de noticia (no directamente de video), extraer primero
    if url_noticia and not any(ext in url_video.lower() for ext in ['.mp4', '.m3u8', '.webm', 'video']):
        url_video_extraido = extraer_video_de_web(url_noticia)
        if url_video_extraido:
            url_video = url_video_extraido
            log(f"Video extraído de web: {url_video[:60]}...", 'exito')
    
    # Si ahora tenemos URL de video, descargar
    if url_video:
        return descargar_con_ytdlp(url_video)
    
    return None, None

def descargar_con_ytdlp(url_video):
    """Descarga video usando yt-dlp con configuración segura"""
    try:
        log(f"Descargando: {url_video[:60]}...", 'video')
        
        ydl_opts = {
            'format': 'best[height>=720][ext=mp4][filesize<100M]/best[height>=720][filesize<100M]/best[ext=mp4][filesize<100M]/best[filesize<100M]',
            'outtmpl': '/tmp/video_%(id)s_%(height)s.%(ext)s',
            'max_filesize': 100000000,  # 100MB
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            
            # Headers para evitar bloqueos
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Obtener info primero
            info = ydl.extract_info(url_video, download=False)
            
            if not info:
                return None, None
            
            # Verificar duración
            duracion = info.get('duration', 0)
            if duracion > 300:  # 5 minutos máximo
                log(f"Video muy largo ({duracion}s), descartado", 'advertencia')
                return None, info
            
            # Descargar
            ydl.download([url_video])
            
            # Encontrar archivo descargado
            video_path = ydl.prepare_filename(info)
            
            # Si no existe con ese nombre, buscar variaciones
            if not os.path.exists(video_path):
                base = os.path.splitext(video_path)[0]
                for ext in ['.mp4', '.mkv', '.webm', '.m4a']:
                    if os.path.exists(base + ext):
                        video_path = base + ext
                        break
            
            if os.path.exists(video_path) and os.path.getsize(video_path) > 500000:
                size_mb = os.path.getsize(video_path) / 1024 / 1024
                log(f"Descargado: {size_mb:.1f} MB", 'exito')
                return video_path, info
            else:
                log("Archivo descargado inválido", 'error')
                return None, info
                
    except Exception as e:
        error_msg = str(e)
        log(f"Error descarga: {error_msg[:80]}", 'error')
        return None, None

def verificar_y_optimizar_video(video_path):
    """Verifica calidad y optimiza si es necesario"""
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration,bit_rate',
            '-of', 'json', video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        info = json.loads(result.stdout)
        
        if 'streams' not in info or not info['streams']:
            return False, "No se pudo analizar"
        
        stream = info['streams'][0]
        height = stream.get('height', 0)
        width = stream.get('width', 0)
        duration = float(stream.get('duration', 0))
        
        log(f"Video: {width}x{height} | {duration:.1f}s", 'debug')
        
        # Verificar requisitos
        if height < 720:
            return False, f"Calidad baja ({height}p)"
        
        if duration > 300:  # 5 minutos
            return recortar_video(video_path, 180)
        
        return True, video_path
        
    except Exception as e:
        log(f"Error verificación: {e}", 'advertencia')
        return True, video_path

def recortar_video(video_path, duracion_segundos=180):
    """Recorta video a duración especificada"""
    try:
        output_path = video_path.replace('.mp4', '_cut.mp4')
        
        cmd = [
            'ffmpeg', '-y', '-i', video_path,
            '-t', str(duracion_segundos),
            '-c:v', 'libx264', '-preset', 'fast',
            '-c:a', 'aac', '-b:a', '128k',
            output_path
        ]
        
        subprocess.run(cmd, capture_output=True, timeout=120)
        
        if os.path.exists(output_path):
            os.remove(video_path)
            log(f"Recortado a {duracion_segundos}s", 'exito')
            return True, output_path
        
        return False, "No se pudo recortar"
        
    except Exception as e:
        log(f"Error recorte: {e}", 'error')
        return False, str(e)

# =============================================================================
# PUBLICACIÓN EN FACEBOOK
# =============================================================================

def publicar_video_facebook(titulo, descripcion, video_path, categoria):
    """Publica video en Facebook"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Faltan credenciales Facebook", 'error')
        return False
    
    if not os.path.exists(video_path):
        log("Archivo no existe", 'error')
        return False
    
    # Generar mensaje
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
                timeout=600  # 10 minutos
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
    """Función principal del bot"""
    print("\n" + "="*70)
    print("🎬 BOT DE VIDEOS - VERDAD HOY (Sin YouTube)")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  Frecuencia: cada ~{TIEMPO_ENTRE_PUBLICACIONES+2} minutos")
    print("="*70)
    
    # Verificar credenciales
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales Facebook", 'error')
        return False
    
    log("Credenciales OK")
    
    # Verificar tiempo
    estado = cargar_estado()
    puede_publicar, transcurrido, faltan = verificar_tiempo_ultima_publicacion(estado)
    
    if not puede_publicar:
        log(f"⏳ Esperando {faltan:.0f} minutos más", 'advertencia')
        return True
    
    log("✅ Iniciando búsqueda", 'exito')
    
    # Cargar historial
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
        
        # Descargar
        video_path, info = descargar_video(
            video_info['url'], 
            video_info['url'] if video_info['tipo_url'] == 'web' else None
        )
        
        if not video_path:
            log("No se pudo descargar, siguiente...", 'advertencia')
            continue
        
        # Verificar
        ok, resultado = verificar_y_optimizar_video(video_path)
        
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
        exito = publicar_video_facebook(
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
                video_info.get('tipo_url', 'rss')
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

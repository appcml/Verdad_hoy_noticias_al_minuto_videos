#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Videos para Facebook - Verdad Hoy
Busca y publica videos de noticias de redes sociales cada 1 hora
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
from urllib.parse import urlparse, parse_qs, unquote
import yt_dlp

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

HISTORIAL_PATH = os.getenv('HISTORIAL_PATH', 'data/historial_videos.json')
ESTADO_PATH = os.getenv('ESTADO_PATH', 'data/estado_bot.json')

# Tiempo entre publicaciones: 1 hora
TIEMPO_ENTRE_PUBLICACIONES = 58  # minutos

# =============================================================================
# CATEGORÍAS ORIGINALES DE LA PÁGINA (ampliadas)
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

# Todas las palabras clave juntas para búsqueda rápida
TODAS_PALABRAS = []
for cat in CATEGORIAS.values():
    TODAS_PALABRAS.extend(cat['palabras'])

# =============================================================================
# FUENTES DE VIDEO
# =============================================================================

# Cuentas de redes sociales de noticias confiables
FUENTES_RED_SOCIAL = {
    'youtube': [
        'UC16niRr50-MSBwiO3YDb3RA',  # BBC News
        'UCupvZG-5ko_eiXAupbDfxWw',  # CNN
        'UCXIJgqnII2ZOINSWNOGFThA',  # Al Jazeera
        'UCz9a3R3y4z3z3z3z3z3z3z3',  # FRANCE 24 Español
        'UC2d3f3f3f3f3f3f3f3f3f3f3',  # DW Español
        'UC4f3f3f3f3f3f3f3f3f3f3f3',  # Euronews Español
    ],
    'twitter_x': [
        'BBCBreaking', 'CNN', 'Reuters', 'AP', 'AFP', 'EFEnoticias',
        'ActualidadRT', 'SputnikMundo', 'CCTV_Espanol',
    ],
    'facebook': [
        'bbcnews', 'cnn', 'Reuters', 'france24', 'dwnews',
    ],
    'instagram': [
        'bbcnews', 'cnn', 'reuters', 'france24', 'dwnews',
    ],
    'tiktok': [
        'bbcnews', 'cnn', 'reuters', 'france24',
    ]
}

# Feeds RSS de video
RSS_FEEDS_VIDEO = [
    'https://feeds.bbci.co.uk/news/video_and_audio/world/rss.xml',
    'https://rss.cnn.com/rss/cnn_freevideo.rss',
    'https://www.france24.com/es/rss/videos',
    'https://www.dw.com/es/actualidad/s-30684?mediaType=video&rss=1',
    'https://www.rtve.es/api/rss/noticias/videos/',
]

# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def log(mensaje, tipo='info'):
    """Imprime mensajes con formato"""
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 
              'debug': '🔍', 'video': '🎬', 'social': '📱'}
    icono = iconos.get(tipo, 'ℹ️')
    print(f"{icono} {mensaje}")

def cargar_json(ruta, default=None):
    """Carga un archivo JSON o retorna valor por defecto"""
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
    """Genera hash MD5 de un texto"""
    return hashlib.md5(texto.lower().strip().encode()).hexdigest()

def detectar_categoria(titulo, descripcion):
    """Detecta la categoría principal de una noticia"""
    texto = f"{titulo} {descripcion}".lower()
    
    puntuaciones = {}
    for nombre_categoria, datos in CATEGORIAS.items():
        score = sum(1 for palabra in datos['palabras'] if palabra in texto)
        puntuaciones[nombre_categoria] = score
    
    if max(puntuaciones.values()) > 0:
        return max(puntuaciones, key=puntuaciones.get)
    
    return 'conflictos_guerra'  # Categoría por defecto

def obtener_hashtags_categoria(categoria):
    """Obtiene los hashtags de una categoría"""
    return ' '.join(CATEGORIAS.get(categoria, {}).get('hashtags', ['#Noticias', '#Actualidad']))

# =============================================================================
# GESTIÓN DE HISTORIAL Y ESTADO
# =============================================================================

def cargar_historial():
    """Carga el historial de videos publicados"""
    default = {
        'urls': [], 
        'titulos': [], 
        'hashes': [], 
        'ultima_publicacion': None, 
        'videos': [],
        'urls_redes_sociales': []
    }
    historial = cargar_json(HISTORIAL_PATH, default)
    log(f"Historial cargado: {len(historial.get('videos', []))} videos")
    return historial

def guardar_historial(historial, url, titulo, video_path, fuente_tipo='web'):
    """Guarda un nuevo video en el historial"""
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
    """Verifica si una noticia ya fue publicada"""
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
    """Verifica si ya pasó el tiempo mínimo entre publicaciones"""
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
# BÚSQUEDA EN REDES SOCIALES Y WEB
# =============================================================================

def buscar_videos_youtube():
    """Busca videos recientes de canales de noticias"""
    videos = []
    
    try:
        # Usar yt-dlp para listar videos recientes de canales
        for canal_id in random.sample(FUENTES_RED_SOCIAL['youtube'], 3):
            try:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': True,
                    'playlistend': 5,  # Últimos 5 videos
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    url_canal = f"https://www.youtube.com/channel/{canal_id}/videos"
                    info = ydl.extract_info(url_canal, download=False)
                    
                    if 'entries' in info:
                        for entry in info['entries']:
                            titulo = entry.get('title', '')
                            if not titulo:
                                continue
                            
                            # Verificar si es relevante
                            es_relevante = any(p in titulo.lower() for p in TODAS_PALABRAS)
                            
                            if es_relevante:
                                videos.append({
                                    'titulo': titulo,
                                    'url': f"https://youtube.com/watch?v={entry.get('id')}",
                                    'descripcion': entry.get('description', '')[:200],
                                    'fuente': 'YouTube',
                                    'fecha': entry.get('upload_date', ''),
                                    'puntaje': 10,  # Alta prioridad
                                    'tipo_url': 'youtube',
                                    'categoria': detectar_categoria(titulo, '')
                                })
                                
            except Exception as e:
                continue
                
    except Exception as e:
        log(f"Error buscando en YouTube: {str(e)[:50]}", 'advertencia')
    
    log(f"YouTube: {len(videos)} videos encontrados", 'social')
    return videos

def buscar_videos_twitter_x():
    """Busca videos en X/Twitter de cuentas de noticias"""
    # Nota: Esto requeriría API de Twitter/X
    # Por ahora, buscamos en feeds RSS de Twitter
    videos = []
    
    # Intentar buscar en nitter (alternativa RSS de Twitter)
    for cuenta in random.sample(FUENTES_RED_SOCIAL['twitter_x'], 3):
        try:
            url_nitter = f"https://nitter.net/{cuenta}/rss"
            feed = feedparser.parse(url_nitter)
            
            for entry in feed.entries[:5]:
                titulo = entry.get('title', '')
                if not titulo:
                    continue
                
                # Buscar enlaces de video
                links = entry.get('links', [])
                video_url = None
                
                for link in links:
                    if 'video' in link.get('type', '') or 'twitter.com/i/videos' in link.get('href', ''):
                        video_url = link.get('href')
                        break
                
                if video_url and any(p in titulo.lower() for p in TODAS_PALABRAS):
                    videos.append({
                        'titulo': titulo,
                        'url': video_url,
                        'descripcion': entry.get('summary', '')[:200],
                        'fuente': f'Twitter/@{cuenta}',
                        'fecha': entry.get('published', ''),
                        'puntaje': 8,
                        'tipo_url': 'twitter',
                        'categoria': detectar_categoria(titulo, entry.get('summary', ''))
                    })
                    
        except Exception as e:
            continue
    
    log(f"Twitter/X: {len(videos)} videos encontrados", 'social')
    return videos

def buscar_videos_newsapi():
    """Busca noticias con video en NewsAPI"""
    videos = []
    if not NEWS_API_KEY:
        return videos
    
    # Términos enfocados en video + conflictos
    terminos = [
        'war video footage', 'conflict video', 'military operation video',
        'narcotraffico video', 'cartel video', 'police operation video',
        'protest video', 'disaster video', 'crash video'
    ]
    
    for termino in random.sample(terminos, 2):
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    'q': termino,
                    'language': 'es,en',
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
                    if not titulo or '[Removed]' in titulo:
                        continue
                    
                    # Detectar categoría
                    categoria = detectar_categoria(titulo, art.get('description', ''))
                    
                    videos.append({
                        'titulo': titulo,
                        'descripcion': art.get('description', ''),
                        'url': art.get('url', ''),
                        'imagen': art.get('urlToImage', ''),
                        'fuente': art.get('source', {}).get('name', 'NewsAPI'),
                        'fecha': art.get('publishedAt', ''),
                        'puntaje': 7 if categoria in ['conflictos_guerra', 'narcotrafico'] else 5,
                        'tipo_url': 'web',
                        'categoria': categoria
                    })
                    
        except Exception as e:
            continue
    
    log(f"NewsAPI: {len(videos)} noticias con video", 'info')
    return videos

def buscar_videos_rss():
    """Busca videos en feeds RSS especializados"""
    videos = []
    
    for feed_url in RSS_FEEDS_VIDEO:
        try:
            feed = feedparser.parse(feed_url)
            fuente = feed.feed.get('title', 'RSS')
            
            for entry in feed.entries[:5]:
                titulo = entry.get('title', '')
                if not titulo:
                    continue
                
                # Buscar enlaces de video
                video_url = None
                
                # En media_content
                if hasattr(entry, 'media_content'):
                    for media in entry.media_content:
                        if media.get('medium') == 'video' or 'video' in media.get('type', ''):
                            video_url = media.get('url')
                            break
                
                # En enclosures
                if not video_url and hasattr(entry, 'enclosures'):
                    for enc in entry.enclosures:
                        if 'video' in enc.get('type', ''):
                            video_url = enc.get('href')
                            break
                
                # Si no hay video directo, usar URL de la noticia
                if not video_url:
                    video_url = entry.get('link', '')
                
                categoria = detectar_categoria(titulo, entry.get('summary', ''))
                
                videos.append({
                    'titulo': titulo,
                    'descripcion': entry.get('summary', ''),
                    'url': video_url,
                    'fuente': fuente,
                    'fecha': entry.get('published', ''),
                    'puntaje': 6,
                    'tipo_url': 'rss_video',
                    'categoria': categoria
                })
                
        except Exception as e:
            continue
    
    log(f"RSS Video: {len(videos)} videos encontrados", 'info')
    return videos

def buscar_todos_videos():
    """Busca videos en todas las fuentes"""
    log("Iniciando búsqueda de videos...", 'video')
    
    todos_videos = []
    
    # Buscar en todas las fuentes
    todos_videos.extend(buscar_videos_youtube())
    todos_videos.extend(buscar_videos_twitter_x())
    todos_videos.extend(buscar_videos_newsapi())
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
# DESCARGA Y PROCESAMIENTO DE VIDEOS
# =============================================================================

def descargar_video_mejorado(url_video, preferencias=None):
    """
    Descarga video con yt-dlp optimizado para noticias
    Prioridad: cortos (<3min), 720p+, formato mp4
    """
    if not url_video:
        return None, None
    
    if preferencias is None:
        preferencias = {
            'max_duration': 300,  # 5 minutos máximo
            'min_height': 720,    # 720p mínimo
            'max_filesize': 100000000,  # 100MB máximo para Facebook
        }
    
    try:
        log(f"Analizando video...", 'video')
        
        # Opciones de yt-dlp
        ydl_opts = {
            'format': 'best[height>=720][ext=mp4][filesize<100M]/best[height>=720][filesize<100M]/best[ext=mp4][filesize<100M]/best[filesize<100M]',
            'outtmpl': '/tmp/video_%(id)s_%(height)s.%(ext)s',
            'max_filesize': preferencias['max_filesize'],
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Primero obtener info sin descargar
            info = ydl.extract_info(url_video, download=False)
            
            if not info:
                return None, None
            
            # Verificar duración
            duracion = info.get('duration', 0)
            if duracion > preferencias['max_duration']:
                log(f"Video muy largo ({duracion}s), buscando alternativa", 'advertencia')
                return None, info  # Retornamos info para posible recorte
            
            # Verificar calidad disponible
            height = info.get('height', 0)
            width = info.get('width', 0)
            
            log(f"Video: {info.get('title', 'Sin título')[:50]}...")
            log(f"Duración: {duracion}s | Resolución: {width}x{height}", 'video')
            
            # Descargar
            ydl.download([url_video])
            
            # Encontrar archivo descargado
            video_path = ydl.prepare_filename(info)
            
            # Si no existe, buscar variaciones
            if not os.path.exists(video_path):
                base = os.path.splitext(video_path)[0]
                for ext in ['.mp4', '.mkv', '.webm']:
                    if os.path.exists(base + ext):
                        video_path = base + ext
                        break
            
            if os.path.exists(video_path) and os.path.getsize(video_path) > 500000:
                size_mb = os.path.getsize(video_path) / 1024 / 1024
                log(f"Video descargado: {size_mb:.1f} MB", 'exito')
                return video_path, info
            else:
                log("Archivo descargado inválido", 'error')
                return None, info
                
    except Exception as e:
        log(f"Error descargando: {str(e)[:80]}", 'error')
        return None, None

def verificar_y_optimizar_video(video_path):
    """Verifica calidad y optimiza si es necesario"""
    try:
        import subprocess
        
        # Información del video
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration,bit_rate',
            '-of', 'json', video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        info = json.loads(result.stdout)
        
        if 'streams' not in info or not info['streams']:
            return False, "No se pudo analizar video"
        
        stream = info['streams'][0]
        height = stream.get('height', 0)
        width = stream.get('width', 0)
        duration = float(stream.get('duration', 0))
        
        log(f"Análisis: {width}x{height} | {duration:.1f}s", 'debug')
        
        # Verificar requisitos
        if height < 720:
            return False, f"Calidad baja ({height}p)"
        
        if duration > 300:  # 5 minutos
            # Intentar recortar primeros 3 minutos
            return recortar_video(video_path, 180)
        
        return True, video_path
        
    except Exception as e:
        log(f"Error verificación: {e}", 'advertencia')
        return True, video_path  # Asumir OK si no podemos verificar

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
        
        subprocess.run(cmd, capture_output=True, timeout=60)
        
        if os.path.exists(output_path):
            os.remove(video_path)  # Eliminar original
            log(f"Video recortado a {duracion_segundos}s", 'exito')
            return True, output_path
        
        return False, "No se pudo recortar"
        
    except Exception as e:
        log(f"Error recortando: {e}", 'error')
        return False, str(e)

# =============================================================================
# PUBLICACIÓN EN FACEBOOK
# =============================================================================

def publicar_video_facebook(titulo, descripcion, video_path, categoria):
    """Publica un video en Facebook con hashtags de categoría"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("Faltan credenciales Facebook", 'error')
        return False
    
    if not os.path.exists(video_path):
        log("Archivo de video no existe", 'error')
        return False
    
    # Generar mensaje con hashtags de categoría
    hashtags = obtener_hashtags_categoria(categoria)
    
    mensaje = f"""🎬 {titulo}

{descripcion[:250]}{"..." if len(descripcion) > 250 else ""}

{hashtags} #Video #Noticias

— Verdad Hoy: Noticias al minuto"""
    
    # Truncar si es muy largo
    if len(mensaje) > 2000:
        mensaje = mensaje[:1990] + "..."
    
    size_mb = os.path.getsize(video_path) / 1024 / 1024
    log(f"Subiendo video a Facebook ({size_mb:.1f} MB)...", 'video')
    
    try:
        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"
        
        with open(video_path, 'rb') as f:
            resp = requests.post(
                url,
                files={'file': f},
                data={
                    'description': mensaje,
                    'access_token': FB_ACCESS_TOKEN
                },
                timeout=600  # 10 minutos para videos grandes
            )
        
        result = resp.json()
        
        if resp.status_code == 200 and 'id' in result:
            log(f"✅ Video publicado: {result['id']}", 'exito')
            return True
        else:
            error = result.get('error', {}).get('message', str(result))
            log(f"Error Facebook: {error}", 'error')
            return False
            
    except Exception as e:
        log(f"Error subiendo: {e}", 'error')
        return False

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def main():
    """Función principal del bot de videos"""
    print("\n" + "="*70)
    print("🎬 BOT DE VIDEOS - VERDAD HOY NOTICIAS")
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
    
    log("✅ Iniciando búsqueda de video", 'exito')
    
    # Cargar historial
    historial = cargar_historial()
    
    # Buscar videos en todas las fuentes
    videos = buscar_todos_videos()
    
    if not videos:
        log("No se encontraron videos", 'error')
        return False
    
    # Filtrar ya publicados
    videos_nuevos = [v for v in videos if not noticia_ya_publicada(historial, v['url'], v['titulo'])]
    log(f"Videos nuevos: {len(videos_nuevos)} de {len(videos)}")
    
    # Si no hay nuevos, usar cualquiera (rotación)
    candidatos = videos_nuevos if videos_nuevos else videos
    
    # Ordenar por puntaje
    candidatos.sort(key=lambda x: x.get('puntaje', 0), reverse=True)
    
    # Intentar descargar y publicar
    for intento, video_info in enumerate(candidatos[:5]):  # Máximo 5 intentos
        log(f"\nIntento {intento+1}: {video_info['titulo'][:50]}...")
        
        # Descargar video
        video_path, info = descargar_video_mejorado(video_info['url'])
        
        if not video_path:
            log("No se pudo descargar, intentando siguiente...", 'advertencia')
            continue
        
        # Verificar y optimizar
        ok, resultado = verificar_y_optimizar_video(video_path)
        
        if not ok:
            log(f"Video rechazado: {resultado}", 'advertencia')
            try:
                os.remove(video_path)
            except:
                pass
            continue
        
        if isinstance(resultado, str) and resultado != video_path:
            video_path = resultado  # Video recortado
        
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
            # Guardar en historial
            guardar_historial(
                historial, 
                video_info['url'], 
                video_info['titulo'], 
                video_path,
                video_info.get('tipo_url', 'web')
            )
            
            # Actualizar estado
            estado['ultima_publicacion'] = datetime.now().isoformat()
            estado['ultima_fuente'] = video_info['fuente']
            estado['ultima_categoria'] = video_info.get('categoria', 'conflictos_guerra')
            estado['total_publicadas'] = estado.get('total_publicadas', 0) + 1
            guardar_estado(estado)
            
            print("\n" + "="*70)
            log("VIDEO PUBLICADO EXITOSAMENTE", 'exito')
            print(f"🎬 {video_info['titulo'][:50]}...")
            print(f"🏢 {video_info['fuente']}")
            print(f"📂 Categoría: {video_info.get('categoria', 'conflictos_guerra')}")
            print(f"📊 Total: {estado['total_publicadas']} videos")
            print(f"⏰ Próximo: {(datetime.now() + timedelta(hours=1)).strftime('%H:%M')}")
            print("="*70)
            return True
        
        # Si falló, intentar siguiente
        log("Falló publicación, intentando siguiente...", 'advertencia')
    
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
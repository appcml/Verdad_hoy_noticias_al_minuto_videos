#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias Video - V2.3
Alternativas LEGALES para descarga de videos cuando yt-dlp falla
"""

import os
import sys
import re
import hashlib
import json
import tempfile
import subprocess
import base64
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

# ... [imports anteriores se mantienen] ...

# =============================================================================
# 🆕 NUEVO: SISTEMA DE DESCARGA CON MÚLTIPLES ESTRATEGIAS LEGALES
# =============================================================================

class VideoDownloader:
    """
    Gestor de descargas con múltiples estrategias legales
    Orden de intentos:
    1. yt-dlp (mejor opción)
    2. youtube_dl (alternativa similar)
    3. Descarga directa via pytube (solo para videos sin restricción)
    4. FFmpeg + stream directo (para HLS streams)
    5. Fallback a publicación como enlace
    """
    
    def __init__(self):
        self.estrategias_disponibles = self._verificar_estrategias()
        self.ultima_estrategia_usada = None
    
    def _verificar_estrategias(self):
        """Verifica qué herramientas están disponibles"""
        estrategias = {
            'yt_dlp': False,
            'youtube_dl': False,
            'pytube': False,
            'ffmpeg': False,
            'requests_directo': False
        }
        
        # Verificar yt-dlp
        try:
            result = subprocess.run(['yt-dlp', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            estrategias['yt_dlp'] = result.returncode == 0
            if estrategias['yt_dlp']:
                log("✅ yt-dlp disponible", 'debug')
        except:
            pass
        
        # Verificar youtube-dl
        try:
            result = subprocess.run(['youtube-dl', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            estrategias['youtube_dl'] = result.returncode == 0
            if estrategias['youtube_dl']:
                log("✅ youtube-dl disponible", 'debug')
        except:
            pass
        
        # Verificar pytube
        try:
            from pytube import YouTube
            estrategias['pytube'] = True
            log("✅ pytube disponible", 'debug')
        except ImportError:
            pass
        
        # Verificar ffmpeg
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            estrategias['ffmpeg'] = result.returncode == 0
            if estrategias['ffmpeg']:
                log("✅ ffmpeg disponible", 'debug')
        except:
            pass
        
        # requests siempre disponible si tenemos el módulo
        estrategias['requests_directo'] = True
        
        return estrategias
    
    def descargar(self, video_url, video_id, max_intentos=3):
        """
        Intenta descargar usando múltiples estrategias en orden
        """
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"{video_id}.mp4")
        
        estrategias_orden = [
            ('yt_dlp', self._descargar_yt_dlp),
            ('youtube_dl', self._descargar_youtube_dl),
            ('pytube', self._descargar_pytube),
            ('ffmpeg_hls', self._descargar_ffmpeg_hls),
            ('requests_directo', self._descargar_requests_directo)
        ]
        
        intentos = 0
        for nombre, funcion in estrategias_orden:
            if not self.estrategias_disponibles.get(nombre):
                continue
            
            if intentos >= max_intentos:
                break
            
            intentos += 1
            log(f"   🔄 Intento {intentos}/{max_intentos}: {nombre}", 'info')
            
            try:
                resultado = funcion(video_url, output_path, video_id)
                if resultado and os.path.exists(resultado) and os.path.getsize(resultado) > 1024:
                    self.ultima_estrategia_usada = nombre
                    log(f"   ✅ Éxito con {nombre}", 'exito')
                    return resultado
            except Exception as e:
                log(f"   ❌ {nombre} falló: {str(e)[:100]}", 'debug')
                continue
        
        # Limpiar directorio vacío si falló todo
        try:
            os.rmdir(temp_dir)
        except:
            pass
        
        return None
    
    def _descargar_yt_dlp(self, url, output_path, video_id):
        """Estrategia 1: yt-dlp (la mejor)"""
        cmd = [
            'yt-dlp',
            '--format', 'best[height<=720][ext=mp4]/best[height<=720]/best',
            '--merge-output-format', 'mp4',
            '--output', output_path,
            '--no-playlist',
            '--quiet',
            '--no-warnings',
            '--no-check-certificates',  # Útil en algunos entornos
            '--geo-bypass',  # Intenta bypass de restricciones geográficas
            url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0 and os.path.exists(output_path):
            return output_path
        
        # Intentar con formato diferente si falló
        cmd_alt = [
            'yt-dlp',
            '-f', 'mp4/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--output', output_path,
            '--no-playlist', '--quiet',
            url
        ]
        
        result = subprocess.run(cmd_alt, capture_output=True, text=True, timeout=180)
        return output_path if (result.returncode == 0 and os.path.exists(output_path)) else None
    
    def _descargar_youtube_dl(self, url, output_path, video_id):
        """Estrategia 2: youtube-dl (alternativa a yt-dlp)"""
        cmd = [
            'youtube-dl',
            '-f', 'best[height<=720]',
            '--merge-output-format', 'mp4',
            '-o', output_path,
            '--no-playlist',
            '--quiet',
            '--no-check-certificate',
            url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return output_path if (result.returncode == 0 and os.path.exists(output_path)) else None
    
    def _descargar_pytube(self, url, output_path, video_id):
        """Estrategia 3: pytube (solo para videos sin restricciones)"""
        try:
            from pytube import YouTube
            
            yt = YouTube(url)
            
            # Filtrar stream progresivo (video+audio juntos)
            stream = yt.streams.filter(
                progressive=True, 
                file_extension='mp4',
                res='720p'
            ).first()
            
            if not stream:
                # Intentar con 480p
                stream = yt.streams.filter(
                    progressive=True,
                    file_extension='mp4'
                ).order_by('resolution').desc().first()
            
            if stream:
                temp_file = stream.download(output_path=os.path.dirname(output_path), 
                                          filename=video_id)
                
                # Renombrar si es necesario
                if temp_file != output_path:
                    os.rename(temp_file, output_path)
                
                return output_path
            
            return None
            
        except Exception as e:
            log(f"pytube error: {str(e)[:100]}", 'debug')
            return None
    
    def _descargar_ffmpeg_hls(self, url, output_path, video_id):
        """
        Estrategia 4: FFmpeg para streams HLS/m3u8
        Útil cuando yt-dlp extrae el stream pero no puede descargarlo
        """
        if not self.estrategias_disponibles['ffmpeg']:
            return None
        
        try:
            # Primero intentar obtener URL directa del stream con yt-dlp
            cmd_get_url = ['yt-dlp', '-g', '-f', 'best[height<=720]', url]
            result = subprocess.run(cmd_get_url, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0 or not result.stdout.strip():
                return None
            
            stream_url = result.stdout.strip().split('\n')[0]
            
            # Descargar con ffmpeg
            cmd = [
                'ffmpeg',
                '-i', stream_url,
                '-c', 'copy',
                '-bsf:a', 'aac_adtstoasc',
                '-movflags', 'faststart',
                '-y',  # Sobrescribir
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return output_path if (result.returncode == 0 and os.path.exists(output_path)) else None
            
        except Exception as e:
            log(f"ffmpeg error: {str(e)[:100]}", 'debug')
            return None
    
    def _descargar_requests_directo(self, url, output_path, video_id):
        """
        Estrategia 5: Descarga directa de URL conocida
        Solo funciona si tenemos URL directa del video (raro en YouTube)
        """
        # Esta estrategia es más útil para videos de otras fuentes (Twitter, etc.)
        # que expongan URL directa
        
        try:
            # Intentar obtener URL directa
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0'
            }
            
            # Para URLs directas de video (no YouTube)
            if any(x in url for x in ['.mp4', '.mov', '.webm', 'video.twimg.com']):
                resp = requests.get(url, headers=headers, stream=True, timeout=120)
                
                if resp.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    return output_path
            
            return None
            
        except Exception as e:
            log(f"requests error: {str(e)[:100]}", 'debug')
            return None


# =============================================================================
# 🆕 NUEVO: DESCARGA DE THUMBNAILS CON MÚLTIPLES FUENTES
# =============================================================================

class ThumbnailDownloader:
    """Gestor de descargas de thumbnails con múltiples fuentes"""
    
    def __init__(self):
        self.fuentes_youtube = [
            'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg',
            'https://img.youtube.com/vi/{video_id}/sddefault.jpg',
            'https://img.youtube.com/vi/{video_id}/hqdefault.jpg',
            'https://img.youtube.com/vi/{video_id}/mqdefault.jpg',
            'https://img.youtube.com/vi/{video_id}/default.jpg',
        ]
    
    def descargar(self, url_primaria, video_id, fuente='youtube'):
        """
        Intenta descargar thumbnail de múltiples fuentes
        """
        # Si nos dieron URL directa, intentar primero
        if url_primaria:
            resultado = self._intentar_descarga(url_primaria, video_id)
            if resultado:
                return resultado
        
        # Intentar fuentes alternativas de YouTube
        if fuente == 'youtube' or 'youtube' in str(url_primaria):
            for url_template in self.fuentes_youtube:
                url = url_template.format(video_id=video_id)
                resultado = self._intentar_descarga(url, video_id)
                if resultado:
                    log(f"   ✅ Thumbnail desde: {url.split('/')[-2]}", 'debug')
                    return resultado
        
        return None
    
    def _intentar_descarga(self, url, video_id):
        """Intenta descargar una URL específica"""
        try:
            resp = requests.get(
                url, 
                headers={'User-Agent': 'Mozilla/5.0'}, 
                timeout=10,
                allow_redirects=True
            )
            
            # Verificar que no sea el thumbnail de "no disponible" de YouTube
            if resp.status_code == 200 and len(resp.content) > 1000:
                # YouTube devuelve un placeholder de 1.2KB para videos sin thumbnail
                if len(resp.content) < 2000 and 'youtube' in url:
                    # Podría ser placeholder, verificar más estrictamente
                    pass  # Continuar de todos modos
                
                temp_path = f'/tmp/thumb_{video_id}_{hashlib.md5(url.encode()).hexdigest()[:6]}.jpg'
                with open(temp_path, 'wb') as f:
                    f.write(resp.content)
                
                # Verificar que sea imagen válida
                try:
                    if PIL_DISPONIBLE:
                        from PIL import Image
                        img = Image.open(temp_path)
                        img.verify()  # Verifica integridad
                    return temp_path
                except:
                    os.remove(temp_path)
                    return None
                    
        except Exception as e:
            pass
        
        return None


# =============================================================================
# INTEGRACIÓN EN EL BOT PRINCIPAL
# =============================================================================

def descargar_video_con_fallback(video_url, video_id, thumbnail_url=None):
    """
    Función principal de descarga con múltiples estrategias
    """
    downloader = VideoDownloader()
    thumb_downloader = ThumbnailDownloader()
    
    # Descargar video
    video_path = downloader.descargar(video_url, video_id, max_intentos=4)
    
    # Descargar thumbnail (independiente del video)
    thumbnail_path = None
    if thumbnail_url or video_id:
        thumbnail_path = thumb_downloader.descargar(thumbnail_url, video_id)
    
    return video_path, thumbnail_path, downloader.ultima_estrategia_usada


# =============================================================================
# ACTUALIZACIÓN DE LA FUNCIÓN PRINCIPAL
# =============================================================================

def main():
    print("\n" + "="*60)
    print("🎥 BOT DE NOTICIAS VIDEO - V2.3 (Multi-Descarga)")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # ... [código anterior de verificación de credenciales y tiempo] ...
    
    # Inicializar descargadores
    video_downloader = VideoDownloader()
    estrategias = video_downloader.estrategias_disponibles
    
    log(f"📥 Estrategias de descarga disponibles:", 'info')
    for nombre, disponible in estrategias.items():
        log(f"   {'✅' if disponible else '❌'} {nombre}", 'debug')
    
    # ... [código de búsqueda de videos] ...
    
    # En la sección de publicación:
    if video_sel and video_sel.get('video_id'):
        video_id = video_sel['video_id']
        
        log(f"   📥 Intentando descargar video...", 'info')
        video_path, thumbnail_path, estrategia_usada = descargar_video_con_fallback(
            video_sel['url'], 
            video_id,
            video_sel.get('thumbnail')
        )
        
        if video_path:
            log(f"   ✅ Descargado vía {estrategia_usada}", 'exito')
            # Intentar publicar video nativo...
            exito = publicar_video_facebook(...)
            
            if not exito and thumbnail_path:
                log("   🔄 Fallback a enlace con thumbnail", 'advertencia')
                exito = publicar_enlace_video_facebook(...)
        else:
            log("   ⚠️ No se pudo descargar video, usando solo enlace", 'advertencia')
            # Usar solo thumbnail si lo tenemos
            if not thumbnail_path and video_sel.get('thumbnail'):
                thumb_dl = ThumbnailDownloader()
                thumbnail_path = thumb_dl.descargar(video_sel['thumbnail'], video_id)
            
            exito = publicar_enlace_video_facebook(...)
    
    # ... [resto del código] ...

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from .utils import log

class VideoDownloader:
    def __init__(self):
        self.download_path = '/tmp/videos'
        os.makedirs(self.download_path, exist_ok=True)
    
    def descargar_con_ytdlp(self, url):
        """Descarga video usando yt-dlp"""
        log(f"Iniciando descarga de: {url[:60]}...", 'info')
        
        try:
            import yt_dlp
            
            # Extraer ID para nombre de archivo
            video_id = re.search(r'(?:v=|videos\/|reel\/|fb\.watch\/|share\/v\/)(\w+)', url)
            video_id = video_id.group(1) if video_id else 'unknown'
            
            output_file = f"{self.download_path}/fb_{video_id}.mp4"
            log(f"Archivo destino: {output_file}", 'debug')
            
            ydl_opts = {
                'format': 'best[height<=720]',
                'outtmpl': output_file,
                'quiet': True,
                'no_warnings': True,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            }
            
            log("Ejecutando yt-dlp...", 'info')
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                log(f"Info obtenida: {info.get('title', 'Sin título')[:50]}", 'info')
                
                if os.path.exists(output_file):
                    size = os.path.getsize(output_file)
                    log(f"Archivo existe: {size/1024/1024:.1f} MB", 'info')
                    
                    if size > 100000:
                        log(f"✅ Descarga exitosa", 'exito')
                        return {
                            'archivo': output_file,
                            'titulo_original': info.get('title', 'Video'),
                            'descripcion': info.get('description', '')[:200],
                            'duracion': info.get('duration', 0),
                            'url_fuente': url
                        }
                    else:
                        log("Archivo muy pequeño", 'error')
                        return None
                else:
                    log("Archivo no creado", 'error')
                    return None
                    
        except Exception as e:
            log(f"Error en descarga: {str(e)[:200]}", 'error')
            import traceback
            traceback.print_exc()
            return None
    
    def limpiar(self, archivo):
        try:
            if archivo and os.path.exists(archivo):
                os.remove(archivo)
                log("Archivo temporal eliminado", 'debug')
        except Exception as e:
            log(f"Error limpiando: {e}", 'advertencia')

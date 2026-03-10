#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import subprocess
import json
from .utils import log

class VideoDownloader:
    def __init__(self):
        self.download_path = '/tmp/videos'
        os.makedirs(self.download_path, exist_ok=True)
    
    def extraer_video_id(self, url):
        """Extrae ID de video de URL de Facebook"""
        patterns = [
            r'facebook\.com\/watch\/?\?v=(\d+)',
            r'facebook\.com\/\w+\/videos\/(\d+)',
            r'fb\.watch\/(\w+)',
            r'reel\/(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def descargar_con_ytdlp(self, url):
        """
        Descarga video usando yt-dlp (mejor que FDownloader)
        Soporta Reels, videos normales, live
        """
        video_id = self.extraer_video_id(url)
        if not video_id:
            log(f"No se pudo extraer ID de: {url}", 'error')
            return None
        
        output_file = f"{self.download_path}/fb_{video_id}.mp4"
        
        # Configuración optimizada para Facebook
        ydl_opts = {
            'format': 'best[height<=720]',  # Calidad 720p máx (rápido subir)
            'outtmpl': output_file,
            'quiet': True,
            'no_warnings': True,
            'cookiesfrombrowser': None,  # Sin cookies = solo públicos
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Obtener datos del video
                titulo = info.get('title', 'Video sin título')
                descripcion = info.get('description', '')[:200]
                duracion = info.get('duration', 0)
                
                if os.path.exists(output_file) and os.path.getsize(output_file) > 100000:
                    log(f"✅ Video descargado: {duracion}s, {os.path.getsize(output_file)/1024/1024:.1f}MB", 'exito')
                    return {
                        'archivo': output_file,
                        'titulo_original': titulo,
                        'descripcion': descripcion,
                        'duracion': duracion,
                        'url_fuente': url
                    }
                else:
                    log("Archivo descargado muy pequeño o corrupto", 'error')
                    return None
                    
        except Exception as e:
            log(f"Error yt-dlp: {str(e)[:100]}", 'error')
            return None
    
    def limpiar_video(self, archivo):
        """Elimina video temporal"""
        try:
            if archivo and os.path.exists(archivo):
                os.remove(archivo)
                log("Video temporal eliminado", 'debug')
        except:
            pass

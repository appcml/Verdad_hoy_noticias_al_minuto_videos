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
            log(f"Arch

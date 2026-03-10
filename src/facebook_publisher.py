#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import os
from .utils import log

class FacebookPublisher:
    def __init__(self):
        self.page_id = os.getenv('FB_PAGE_ID')
        self.access_token = os.getenv('FB_ACCESS_TOKEN')
        self.api_version = "v18.0"
    
    def publicar_video(self, video_path, titulo_data, video_info):
        """
        Publica video con título viral generado
        """
        if not self.page_id or not self.access_token:
            log("Faltan credenciales de Facebook", 'error')
            return False
        
        # Preparar mensaje completo
        mensaje = f"{titulo_data['titulo']}\n\n"
        mensaje += f"{titulo_data['descripcion']}\n\n"
        mensaje += f"📹 Fuente original: {video_info['url_fuente']}\n"
        mensaje += f"⏱️ Duración: {int(video_info['duracion'])} segundos\n\n"
        mensaje += titulo_data['hashtags']
        
        # Truncar si es necesario
        if len(mensaje) > 2000:
            mensaje = mensaje[:1997] + "..."
        
        log(f"Subiendo video... ({os.path.getsize(video_path)/1024/1024:.1f}MB)", 'facebook')
        
        try:
            url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}/videos"
            
            with open(video_path, 'rb') as video_file:
                files = {'file': video_file}
                data = {
                    'description': mensaje,
                    'access_token': self.access_token,
                }
                
                # Si es Reel (menos de 90 seg)
                if video_info['duracion'] < 90:
                    data['reels_placements'] = '["feed","reel"]'
                    log("Publicando como Reel para mayor alcance", 'info')
                
                response = requests.post(url, files=files, data=data, timeout=120)
            
            result = response.json()
            
            if response.status_code == 200 and 'id' in result:
                video_id = result['id']
                log(f"✅ Video publicado: {video_id}", 'exito')
                return {
                    'success': True,
                    'video_id': video_id,
                    'url': f"https://facebook.com/watch/?v={video_id}"
                }
            else:
                error = result.get('error', {}).get('message', 'Error desconocido')
                log(f"❌ Error Facebook: {error}", 'error')
                return {'success': False, 'error': error}
                
        except Exception as e:
            log(f"❌ Error subiendo video: {e}", 'error')
            return {'success': False, 'error': str(e)}

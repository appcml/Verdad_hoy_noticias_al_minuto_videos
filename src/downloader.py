import yt_dlp
import os
from datetime import datetime

class ShortsDownloader:
    def __init__(self, temp_dir="temp"):
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)
    
    def descargar_short(self, video_info):
        """
        Descarga Short a carpeta temporal
        Retorna ruta del archivo o None si falla
        """
        
        video_id = video_info['video_id']
        output_path = os.path.join(self.temp_dir, f"{video_id}.mp4")
        
        # Si ya existe, no descargar de nuevo
        if os.path.exists(output_path):
            return output_path
        
        ydl_opts = {
            'format': 'best[height<=1080]',  # Máx 1080p para Shorts
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_info['url']])
                
            if os.path.exists(output_path):
                # Agregar metadato de descarga
                video_info['archivo_local'] = output_path
                video_info['fecha_descarga'] = datetime.now().isoformat()
                video_info['tamanio_mb'] = os.path.getsize(output_path) / (1024 * 1024)
                return output_path
                
        except Exception as e:
            print(f"Error descargando {video_id}: {e}")
            return None
    
    def limpiar_antiguos(self, horas_max=24):
        """Elimina videos descargados hace más de X horas"""
        ahora = datetime.now()
        eliminados = []
        
        for archivo in os.listdir(self.temp_dir):
            if not archivo.endswith('.mp4'):
                continue
                
            ruta = os.path.join(self.temp_dir, archivo)
            fecha_mod = datetime.fromtimestamp(os.path.getmtime(ruta))
            horas_diferencia = (ahora - fecha_mod).total_seconds() / 3600
            
            if horas_diferencia > horas_max:
                os.remove(ruta)
                eliminados.append(archivo)
        
        return eliminados

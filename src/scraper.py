import requests
import re
from datetime import datetime, timedelta

class ShortsScraper:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"
        
    def buscar_shorts_noticias(self, max_results=15):
        """
        Busca Shorts de noticias de última hora
        Rota queries para maximizar resultados
        """
        
        # Queries rotativas por hora del día
        hora_actual = datetime.now().hour
        queries_sets = [
            ["noticias urgentes hoy", "ultima hora internacional", "breaking news"],
            ["conflicto armado hoy", "guerra actual", "crisis mundial"],
            ["desastre natural hoy", "terremoto", "inundacion"],
            ["politica internacional", "elecciones", "gobierno"],
            ["narcotrafico noticias", "seguridad", "crimen organizado"],
            ["economia mundial", "crisis economica", "mercados"]
        ]
        
        # Seleccionar set de queries según la hora
        queries = queries_sets[hora_actual % len(queries_sets)]
        
        shorts_encontrados = []
        ids_vistos = set()
        
        for query in queries:
            if len(shorts_encontrados) >= max_results:
                break
            
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'videoDuration': 'short',
                'order': 'date',
                'publishedAfter': (datetime.utcnow() - timedelta(hours=2)).isoformat("T") + "Z",
                'maxResults': 10,
                'key': self.api_key
            }
            
            try:
                response = requests.get(
                    f"{self.base_url}/search", 
                    params=params,
                    timeout=10
                )
                data = response.json()
                
                for item in data.get('items', []):
                    video_id = item['id']['videoId']
                    
                    if video_id in ids_vistos:
                        continue
                    
                    # Verificar duración real
                    duracion = self.obtener_duracion(video_id)
                    if duracion and 15 <= duracion <= 60:  # Entre 15s y 60s
                        ids_vistos.add(video_id)
                        shorts_encontrados.append({
                            'video_id': video_id,
                            'titulo': item['snippet']['title'],
                            'canal': item['snippet']['channelTitle'],
                            'url': f"https://youtube.com/shorts/{video_id}",
                            'thumbnail': item['snippet']['thumbnails']['high']['url'],
                            'fecha_publicacion': item['snippet']['publishedAt'],
                            'duracion_segundos': duracion
                        })
                        
            except Exception as e:
                print(f"Error en query '{query}': {e}")
                continue
        
        return shorts_encontrados[:max_results]
    
    def obtener_duracion(self, video_id):
        params = {
            'part': 'contentDetails',
            'id': video_id,
            'key': self.api_key
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/videos", 
                params=params,
                timeout=5
            )
            data = response.json()
            
            if data.get('items'):
                duration_iso = data['items'][0]['contentDetails']['duration']
                return self.parse_duration(duration_iso)
        except:
            pass
        return None
    
    @staticmethod
    def parse_duration(duration):
        match = re.match(r'PT(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match:
            return 0
        minutes = int(match.group(1) or 0)
        seconds = int(match.group(2) or 0)
        return minutes * 60 + seconds

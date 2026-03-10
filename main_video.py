#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.video_downloader import VideoDownloader
from src.generador_titulos import GeneradorTitulosViral
from src.facebook_publisher import FacebookPublisher
from src.utils import log, guardar_json, cargar_json
from datetime import datetime

def procesar_video_facebook(url_video):
    """
    Proceso completo: Descargar → Generar título → Publicar
    """
    print("\n" + "="*70)
    print("🎬 VERDAD HOY - Procesador de Videos")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # 1. Descargar video
    log(f"📥 Descargando video de: {url_video[:60]}...", 'info')
    downloader = VideoDownloader()
    video_data = downloader.descargar_con_ytdlp(url_video)
    
    if not video_data:
        log("❌ No se pudo descargar el video", 'error')
        return False
    
    # 2. Generar título viral
    log("✨ Generando título atractivo...", 'viral')
    generador = GeneradorTitulosViral()
    titulo_data = generador.generar_titulo(
        video_data['titulo_original'],
        video_data['descripcion'],
        video_data['duracion']
    )
    
    log(f"📝 Título generado: {titulo_data['titulo']}", 'exito')
    log(f"🏷️ Tema detectado: {titulo_data['tema_detectado']}", 'info')
    
    # 3. Publicar en Facebook
    log("📘 Publicando en Facebook...", 'facebook')
    publisher = FacebookPublisher()
    resultado = publisher.publicar_video(
        video_data['archivo'],
        titulo_data,
        video_data
    )
    
    # 4. Limpiar
    downloader.limpiar_video(video_data['archivo'])
    
    # 5. Guardar registro
    if resultado['success']:
        historial = cargar_json('data/historial_videos.json', {'videos': []})
        historial['videos'].append({
            'fecha': datetime.now().isoformat(),
            'url_fuente': url_video,
            'titulo_generado': titulo_data['titulo'],
            'video_id': resultado['video_id'],
            'tema': titulo_data['tema_detectado']
        })
        guardar_json('data/historial_videos.json', historial)
        
        print("\n" + "="*70)
        log("✅ VIDEO PUBLICADO EXITOSAMENTE", 'exito')
        print(f"🎬 {titulo_data['titulo']}")
        print(f"🔗 {resultado['url']}")
        print("="*70)
        return True
    
    return False

if __name__ == "__main__":
    # Verificar argumento (URL del video)
    if len(sys.argv) < 2:
        print("Uso: python main_video.py <URL_DE_VIDEO_FACEBOOK>")
        print("Ejemplo: python main_video.py https://fb.watch/abc123/")
        sys.exit(1)
    
    url = sys.argv[1]
    
    try:
        exit(0 if procesar_video_facebook(url) else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

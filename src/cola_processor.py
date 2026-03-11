#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from datetime import datetime
from .video_downloader import VideoDownloader
from .generador_titulos import GeneradorTitulosViral
from .facebook_publisher import FacebookPublisher
from .utils import log, cargar_json, guardar_json

class ProcesadorCola:
    def __init__(self):
        self.cola_path = 'data/cola_videos.json'
        self.historial_path = 'data/historial_videos.json'
        os.makedirs('data', exist_ok=True)
        os.makedirs('/tmp/videos', exist_ok=True)
    
    def agregar_a_cola(self, url, fuente="manual"):
        """Agrega URL a la cola"""
        cola = cargar_json(self.cola_path, {'pendientes': [], 'procesados': []})
        
        # Verificar duplicados
        for item in cola['pendientes']:
            if item['url'] == url:
                log("URL ya en cola", 'advertencia')
                return False
        
        historial = cargar_json(self.historial_path, {'videos': []})
        for video in historial['videos'][-20:]:
            if video.get('url_fuente') == url:
                log("URL ya procesada", 'advertencia')
                return False
        
        nuevo = {
            'url': url,
            'fuente': fuente,
            'agregado': datetime.now().isoformat(),
            'id': hash(url) % 100000
        }
        
        cola['pendientes'].append(nuevo)
        guardar_json(self.cola_path, cola)
        log(f"✅ Agregado a cola", 'exito')
        return True
    
    def procesar_siguiente(self):
        """Procesa un video de la cola"""
        cola = cargar_json(self.cola_path, {'pendientes': [], 'procesados': []})
        
        if not cola['pendientes']:
            return None, "cola_vacia"
        
        item = cola['pendientes'][0]
        url = item['url']
        
        log(f"🎬 Procesando: {url[:50]}...", 'info')
        
        # Descargar
        downloader = VideoDownloader()
        video_data = downloader.descargar_con_ytdlp(url)
        
        if not video_data:
            cola['pendientes'].remove(item)
            item['error'] = 'descarga_fallida'
            cola['procesados'].append(item)
            guardar_json(self.cola_path, cola)
            return False, "descarga_fallida"
        
        # Generar título
        generador = GeneradorTitulosViral()
        titulo_data = generador.generar_titulo(
            video_data['titulo_original'],
            video_data['descripcion'],
            video_data['duracion']
        )
        
        # Publicar
        publisher = FacebookPublisher()
        resultado = publisher.publicar_video(video_data, titulo_data, video_data)
        
        # Limpiar
        downloader.limpiar(video_data['archivo'])
        
        # Mover a procesados
        cola['pendientes'].remove(item)
        item['resultado'] = resultado
        cola['procesados'].append(item)
        guardar_json(self.cola_path, cola)
        
        # Guardar historial
        if resultado['success']:
            historial = cargar_json(self.historial_path, {'videos': []})
            historial['videos'].append({
                'fecha': datetime.now().isoformat(),
                'url_fuente': url,
                'titulo': titulo_data['titulo'],
                'video_id': resultado.get('video_id')
            })
            guardar_json(self.historial_path, historial)
            return True, "publicado"
        
        return False, "publicacion_fallida"
    
    def procesar_todos(self):
        """Procesa todos los pendientes"""
        procesados = 0
        while True:
            success, estado = self.procesar_siguiente()
            if estado == "cola_vacia":
                break
            if success:
                procesados += 1
            time.sleep(3)
        return procesados

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integrador: Bot Descargador → Bot Noticias
Procesa videos pendientes y genera publicaciones en Facebook
"""

import os
import sys
import json
import subprocess
import random
from datetime import datetime
from pathlib import Path

# CONFIGURACIÓN
CARPETA_VIDEOS = os.getenv('CARPETA_VIDEOS', 'videos_pendientes')
CARPETA_PUBLICADOS = os.getenv('CARPETA_PUBLICADOS', 'videos_publicados')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')

# Crear carpetas
Path(CARPETA_PUBLICADOS).mkdir(parents=True, exist_ok=True)

def log(mensaje, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍'}
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {iconos.get(tipo, 'ℹ️')} {mensaje}")

def obtener_videos_pendientes():
    """Obtiene videos pendientes de publicar"""
    pendientes = []

    if not os.path.exists(CARPETA_VIDEOS):
        return pendientes

    for archivo in os.listdir(CARPETA_VIDEOS):
        if archivo.endswith('.json') and not archivo.startswith('.'):
            json_path = os.path.join(CARPETA_VIDEOS, archivo)
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                if metadata.get('estado') == 'pendiente':
                    video_id = metadata.get('video_id')
                    # Buscar archivo de video correspondiente
                    video_path = None
                    for vfile in os.listdir(CARPETA_VIDEOS):
                        if vfile.endswith('.mp4') and video_id in vfile:
                            video_path = os.path.join(CARPETA_VIDEOS, vfile)
                            break

                    if video_path and os.path.exists(video_path):
                        metadata['video_path'] = video_path
                        metadata['json_path'] = json_path
                        pendientes.append(metadata)
            except Exception as e:
                log(f"Error leyendo {archivo}: {e}", 'error')

    # Ordenar por fecha de descarga (más antiguos primero)
    pendientes.sort(key=lambda x: x.get('fecha_descarga', ''))
    return pendientes

def generar_nota_prensa(metadata):
    """Genera una nota de prensa a partir del metadata del video"""
    titulo = metadata.get('titulo', '')
    descripcion = metadata.get('descripcion', '')
    canal = metadata.get('canal', 'Fuente desconocida')

    # Limpiar y formatear
    titulo = titulo.strip()
    descripcion = descripcion.strip()

    # Generar contenido tipo noticia
    lineas = [
        f"📹 VIDEO EXCLUSIVO",
        f"",
        f"🎬 {titulo}",
        f"",
    ]

    # Añadir descripción si es relevante
    if len(descripcion) > 50 and descripcion != titulo:
        # Cortar descripción larga
        desc_corta = descripcion[:300] + "..." if len(descripcion) > 300 else descripcion
        lineas.extend([
            f"📝 Contexto:",
            f"{desc_corta}",
            f"",
        ])

    # Añadir fuente y metadatos
    lineas.extend([
        f"──────────────────────────────",
        f"📡 Fuente: {canal}",
        f"⏰ Publicado originalmente: {metadata.get('fecha_publicacion_original', 'Fecha desconocida')[:10]}",
        f"📥 Descargado: {metadata.get('fecha_descarga', '')[:10]}",
        f"",
        f"🔗 URL original: {metadata.get('url_original', '')}",
    ])

    return '\n'.join(lineas)

def generar_hashtags(titulo):
    """Genera hashtags relevantes"""
    titulo_lower = titulo.lower()
    hashtags = ['#VideoNoticias', '#ÚltimaHora', '#NoticiasInternacionales']

    temas = {
        'guerra|conflicto|ataque|bombardeo': '#ConflictoArmado',
        'ucrania|rusia|putin|zelensky': '#UcraniaRusia',
        'gaza|israel|hamas|palestina': '#IsraelGaza',
        'trump|biden|eeuu|estados unidos': '#EEUU',
        'economía|inflación|crisis|mercados': '#EconomíaGlobal',
        'china|taiwán|beijing': '#ChinaTaiwán',
        'francia|alemania|españa|italia': '#Europa',
        'onu|otan|union europea': '#Diplomacia'
    }

    for patron, hashtag in temas.items():
        if any(p in titulo_lower for p in patron.split('|')):
            if hashtag not in hashtags:
                hashtags.append(hashtag)

    hashtags.append('#Mundo')
    return ' '.join(hashtags)

def publicar_video_facebook(metadata, nota_prensa, hashtags):
    """Publica el video en Facebook con la nota de prensa"""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        log("ERROR: Faltan credenciales de Facebook", 'error')
        return False

    video_path = metadata.get('video_path')
    if not video_path or not os.path.exists(video_path):
        log(f"ERROR: Video no encontrado: {video_path}", 'error')
        return False

    # Preparar mensaje
    mensaje = f"{nota_prensa}\n\n{hashtags}\n\n— 🌐 Agencia de Noticias | VideoVerdad"

    # Truncar si es muy largo
    if len(mensaje) > 2000:
        lineas = nota_prensa.split('\n')
        nota_corta = ""
        for linea in lineas:
            if len(nota_corta + linea + "\n") < 1500:
                nota_corta += linea + "\n"
            else:
                break
        mensaje = f"{nota_corta}\n[...]\n\n{hashtags}\n\n— 🌐 Agencia de Noticias"

    try:
        import requests

        log(f"📤 Publicando video: {metadata.get('video_id')}")
        log(f"   Tamaño: {os.path.getsize(video_path) / (1024*1024):.1f} MB")

        url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/videos"

        with open(video_path, 'rb') as video_file:
            files = {'file': ('video.mp4', video_file, 'video/mp4')}
            data = {
                'description': mensaje,
                'access_token': FB_ACCESS_TOKEN
            }

            response = requests.post(url, files=files, data=data, timeout=120)
            result = response.json()

        if 'id' in result:
            log(f"✅ Video publicado ID: {result['id']}", 'exito')
            return True
        else:
            error = result.get('error', {}).get('message', 'Error desconocido')
            log(f"❌ Error Facebook: {error}", 'error')
            return False

    except Exception as e:
        log(f"❌ Error publicando: {e}", 'error')
        return False

def mover_a_publicados(metadata):
    """Mueve el video a la carpeta de publicados"""
    try:
        video_path = metadata.get('video_path')
        json_path = metadata.get('json_path')
        video_id = metadata.get('video_id')

        if video_path and os.path.exists(video_path):
            destino_video = os.path.join(CARPETA_PUBLICADOS, os.path.basename(video_path))
            os.rename(video_path, destino_video)

        if json_path and os.path.exists(json_path):
            # Actualizar estado en el JSON
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['estado'] = 'publicado'
            data['fecha_publicacion'] = datetime.now().isoformat()

            destino_json = os.path.join(CARPETA_PUBLICADOS, os.path.basename(json_path))
            with open(destino_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.remove(json_path)

        log(f"📁 Movido a publicados: {video_id}")
        return True
    except Exception as e:
        log(f"Error moviendo archivos: {e}", 'error')
        return False

def marcar_error(metadata):
    """Marca el video como error"""
    try:
        json_path = metadata.get('json_path')
        if json_path and os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['estado'] = 'error'
            data['fecha_error'] = datetime.now().isoformat()
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def main():
    print("\n" + "="*60)
    print("🔗 INTEGRADOR: Videos → Facebook")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Videos: {CARPETA_VIDEOS}")
    print(f"📁 Publicados: {CARPETA_PUBLICADOS}")
    print("="*60)

    # Obtener videos pendientes
    pendientes = obtener_videos_pendientes()
    log(f"📊 Videos pendientes: {len(pendientes)}")

    if not pendientes:
        log("No hay videos para publicar")
        return True

    publicados = 0
    errores = 0

    for video_meta in pendientes:
        video_id = video_meta.get('video_id', 'unknown')
        log(f"\n🎬 Procesando: {video_id}")
        log(f"   Título: {video_meta.get('titulo', '')[:60]}...")

        # Generar nota de prensa
        nota = generar_nota_prensa(video_meta)
        hashtags = generar_hashtags(video_meta.get('titulo', ''))

        log(f"   📝 Nota generada: {len(nota)} caracteres")

        # Publicar
        if publicar_video_facebook(video_meta, nota, hashtags):
            # Mover a publicados
            if mover_a_publicados(video_meta):
                publicados += 1
                # Delay entre publicaciones
                delay = random.randint(30, 60)
                log(f"⏳ Esperando {delay}s antes de siguiente...")
                import time
                time.sleep(delay)
        else:
            marcar_error(video_meta)
            errores += 1

    print("\n" + "="*60)
    log(f"📊 RESUMEN: {publicados} publicados, {errores} errores", 'exito')

    return publicados > 0

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        log(f"Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

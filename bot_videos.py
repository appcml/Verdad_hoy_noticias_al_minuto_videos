#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Reels - Verdad Hoy v2.1 (DEBUG)
Versión con diagnóstico completo de errores
"""

import os
import sys
import json
import re
import hashlib
import random
import time
import subprocess
import requests
import feedparser
import traceback
from datetime import datetime, timedelta
from pathlib import Path

# =============================================================================
# VERIFICACIÓN DE DEPENDENCIAS AL INICIO
# =============================================================================

def verificar_dependencias():
    """Verifica que todo esté instalado correctamente"""
    errores = []
    
    # Verificar Python version
    if sys.version_info < (3, 7):
        errores.append("Python 3.7+ requerido")
    
    # Verificar módulos
    modulos_requeridos = ['requests', 'feedparser']
    for modulo in modulos_requeridos:
        try:
            __import__(modulo)
        except ImportError:
            errores.append(f"Módulo '{modulo}' no instalado. Ejecuta: pip install {modulo}")
    
    # Verificar yt-dlp
    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        errores.append("yt-dlp no instalado. Ejecuta: pip install yt-dlp")
    
    # Verificar ffmpeg (opcional pero recomendado)
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  ADVERTENCIA: ffmpeg no instalado (necesario para formato 9:16)")
    
    if errores:
        print("\n" + "="*60)
        print("❌ ERRORES DE DEPENDENCIAS:")
        for e in errores:
            print(f"   • {e}")
        print("="*60 + "\n")
        return False
    return True

# =============================================================================
# CONFIGURACIÓN Y VALIDACIÓN
# =============================================================================

def cargar_configuracion():
    """Carga y valida todas las variables de entorno"""
    config = {
        'YOUTUBE_API_KEY': os.getenv('YOUTUBE_API_KEY'),
        'RAPIDAPI_KEY': os.getenv('RAPIDAPI_KEY'),
        'FB_ACCESS_TOKEN': os.getenv('FB_ACCESS_TOKEN'),
        'FB_PAGE_ID': os.getenv('FB_PAGE_ID'),
    }
    
    # Validar campos obligatorios
    faltantes = []
    if not config['YOUTUBE_API_KEY']:
        faltantes.append('YOUTUBE_API_KEY')
    if not config['FB_ACCESS_TOKEN']:
        faltantes.append('FB_ACCESS_TOKEN')
    if not config['FB_PAGE_ID']:
        faltantes.append('FB_PAGE_ID')
    
    if faltantes:
        print("\n" + "="*60)
        print("❌ VARIABLES DE ENTORNO FALTANTES:")
        for var in faltantes:
            print(f"   • {var}")
        print("\n💡 Agrega estos secrets en GitHub:")
        print("   Settings → Secrets and variables → Actions → New repository secret")
        print("="*60 + "\n")
        return None
    
    # Mostrar configuración (ocultando parte de las keys por seguridad)
    print("\n" + "="*60)
    print("✅ CONFIGURACIÓN CARGADA:")
    for key, value in config.items():
        if value:
            masked = value[:10] + "..." + value[-4:] if len(value) > 20 else "***"
            print(f"   • {key}: {masked}")
        else:
            print(f"   • {key}: (no configurado - opcional)")
    print("="*60 + "\n")
    
    return config

# =============================================================================
# RESTO DEL CÓDIGO (igual que antes pero con más logs de error)
# =============================================================================

# [Aquí va todo el código anterior: CATEGORIAS, FEEDS_RSS, funciones de utilidad, etc.]

# Copiar desde el código anterior las secciones:
# - CATEGORIAS
# - FEEDS_RSS  
# - Utilidades (log, cargar_json, guardar_json, etc.)
# - obtener_noticias_rss
# - buscar_video_youtube_api
# - descargar_video
# - convertir_a_reel
# - publicar_reel
# - etc.

# ... [mantener todo el código anterior] ...

# =============================================================================
# MAIN CON MANEJO COMPLETO DE ERRORES
# =============================================================================

def main():
    print("\n" + "="*70)
    print("📱 BOT DE REELS - MODO DEBUG")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # 1. Verificar dependencias
    if not verificar_dependencias():
        return False
    
    # 2. Cargar configuración
    config = cargar_configuracion()
    if not config:
        return False
    
    # 3. Crear directorios
    try:
        DATA_DIR = Path('data')
        VIDEOS_DIR = DATA_DIR / 'videos'
        REELS_DIR = DATA_DIR / 'reels'
        for d in [DATA_DIR, VIDEOS_DIR, REELS_DIR]:
            d.mkdir(exist_ok=True)
        print(f"✅ Directorios creados: {DATA_DIR}")
    except Exception as e:
        print(f"❌ Error creando directorios: {e}")
        return False
    
    # 4. Verificar conectividad básica
    print("\n🌐 Verificando conectividad...")
    try:
        resp = requests.get('https://www.google.com', timeout=10)
        print(f"   ✓ Internet OK (status: {resp.status_code})")
    except Exception as e:
        print(f"   ❌ Sin conexión a internet: {e}")
        return False
    
    # 5. Verificar YouTube API
    print("\n🔑 Verificando YouTube API...")
    try:
        test_url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'q': 'test',
            'type': 'video',
            'maxResults': 1,
            'key': config['YOUTUBE_API_KEY']
        }
        resp = requests.get(test_url, params=params, timeout=10)
        data = resp.json()
        
        if 'error' in data:
            error = data['error']
            print(f"   ❌ YouTube API Error: {error.get('message', 'Unknown')}")
            if error.get('code') == 400:
                print("   💡 La API key es inválida o no tiene YouTube Data API habilitado")
            elif error.get('code') == 403:
                print("   💡 Cuota excedida o API no habilitada")
            return False
        else:
            print("   ✓ YouTube API OK")
    except Exception as e:
        print(f"   ❌ Error conectando a YouTube API: {e}")
        return False
    
    # 6. Verificar Facebook API
    print("\n📘 Verificando Facebook API...")
    try:
        url = f"https://graph.facebook.com/v18.0/me"
        params = {'access_token': config['FB_ACCESS_TOKEN']}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        if 'error' in data:
            print(f"   ❌ Facebook Error: {data['error'].get('message', 'Unknown')}")
            print("   💡 El token puede estar expirado o ser inválido")
            return False
        else:
            print(f"   ✓ Facebook API OK (User: {data.get('name', 'Unknown')})")
    except Exception as e:
        print(f"   ❌ Error conectando a Facebook: {e}")
        return False
    
    # 7. Verificar página de Facebook
    print(f"\n📄 Verificando Página {config['FB_PAGE_ID']}...")
    try:
        url = f"https://graph.facebook.com/v18.0/{config['FB_PAGE_ID']}"
        params = {
            'access_token': config['FB_ACCESS_TOKEN'],
            'fields': 'name,access_token'
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        if 'error' in data:
            print(f"   ❌ Error: {data['error'].get('message', 'Unknown')}")
            print("   💡 Verifica que el FB_PAGE_ID sea correcto")
            return False
        else:
            print(f"   ✓ Página OK: {data.get('name', 'Unknown')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    print("\n" + "="*70)
    print("🚀 TODAS LAS VERIFICACIONES PASARON - INICIANDO BOT")
    print("="*70)
    
    # Aquí continúa el flujo normal del bot...
    # [Insertar el resto del código de main() del script anterior]
    
    return True

if __name__ == "__main__":
    try:
        exit(0 if main() else 1)
    except Exception as e:
        print("\n" + "="*70)
        print("💥 ERROR CRÍTICO NO MANEJADO:")
        print(f"   {type(e).__name__}: {e}")
        print("\n📋 TRACEBACK COMPLETO:")
        traceback.print_exc()
        print("="*70)
        exit(1)

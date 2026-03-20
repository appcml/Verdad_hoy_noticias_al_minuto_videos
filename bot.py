#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Noticias Video - V3.0 MODO SOLO YOUTUBE
Recopila videos de noticias y los guarda en archivo para revisión manual
O publica en: Twitter/X, Telegram, Discord, etc.
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timedelta
import requests

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')

# Modos de salida
MODO_GUARDAR_ARCHIVO = True  # Guarda en JSON para revisión
MODO_TELEGRAM = False        # Publicar en Telegram (necesita BOT_TOKEN)
MODO_DISCORD = False         # Publicar en Discord (necesita WEBHOOK_URL)
MODO_TWITTER = False         # Publicar en Twitter/X (necesita API keys)

# Configuración de servicios alternativos
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

OUTPUT_PATH = 'videos_encontrados.json'
HISTORIAL_PATH = 'data/historial_videos.json'

# =============================================================================
# PALABRAS CLAVE
# =============================================================================

KEYWORDS = {
    'war': 10, 'guerra': 10, 'conflict': 10, 'conflicto': 10,
    'ukraine': 10, 'ucrania': 10, 'gaza': 10, 'israel': 10,
    'iran': 10, 'trump': 10, 'biden': 10, 'putin': 10,
    'missile': 10, 'misil': 10, 'attack': 10, 'ataque': 10,
    'live': 5, 'breaking': 8, 'urgent': 8, 'alert': 8,
    'oil': 8, 'petróleo': 8, 'nuclear': 10, 'irán': 10,
}

def log(msg, tipo='info'):
    iconos = {'info': 'ℹ️', 'exito': '✅', 'error': '❌', 'advertencia': '⚠️', 'debug': '🔍'}
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {iconos.get(tipo, 'ℹ️')} {msg}")

def cargar_json(ruta, default=None):
    default = default or {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                return json.loads(f.read().strip()) or default.copy()
        except:
            pass
    return default.copy()

def guardar_json(ruta, datos):
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"Error guardando: {e}", 'error')
        return False

def calcular_puntaje(titulo):
    t = titulo.lower()
    return sum(v for p, v in KEYWORDS.items() if p in t)

# =============================================================================
# BÚSQUEDA DE VIDEOS
# =============================================================================

def buscar_youtube():
    if not YOUTUBE_API_KEY:
        log("YOUTUBE_API_KEY no configurado", 'error')
        return []
    
    videos = []
    queries = [
        'breaking news international live',
        'world news today war conflict',
        'israel iran gaza news live',
        'trump biden political news',
    ]
    
    for query in queries:
        try:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'maxResults': 15,
                'key': YOUTUBE_API_KEY,
                'order': 'date',
                'publishedAfter': (datetime.now() - timedelta(hours=48)).isoformat("T") + "Z"
            }
            
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            
            if 'error' in data:
                log(f"YouTube API Error: {data['error'].get('message', 'Unknown')}", 'error')
                continue
            
            for item in data.get('items', []):
                vid = item['id'].get('videoId')
                if not vid:
                    continue
                
                snip = item['snippet']
                titulo = snip.get('title', '')
                puntaje = calcular_puntaje(titulo)
                
                # Incluir si tiene buen puntaje o es reciente (últimas 6 horas)
                published = snip.get('publishedAt', '')
                es_reciente = False
                try:
                    pub_time = datetime.fromisoformat(published.replace('Z', '+00:00'))
                    es_reciente = (datetime.now(pub_time.tzinfo) - pub_time) < timedelta(hours=6)
                except:
                    pass
                
                if puntaje >= 5 or (puntaje >= 3 and es_reciente):
                    videos.append({
                        'titulo': titulo,
                        'url': f"https://youtube.com/watch?v={vid}",
                        'video_id': vid,
                        'thumbnail': f"https://img.youtube.com/vi/{vid}/hqdefault.jpg",
                        'puntaje': puntaje,
                        'fuente': snip.get('channelTitle', 'Unknown'),
                        'publicado': published,
                        'descripcion': snip.get('description', '')[:200],
                        'encontrado_en': datetime.now().isoformat()
                    })
                    
        except Exception as e:
            log(f"Error YouTube: {e}", 'error')
    
    # Eliminar duplicados
    vistos = set()
    unicos = []
    for v in sorted(videos, key=lambda x: x['puntaje'], reverse=True):
        if v['video_id'] not in vistos:
            vistos.add(v['video_id'])
            unicos.append(v)
    
    log(f"YouTube: {len(unicos)} videos únicos", 'info')
    return unicos

# =============================================================================
# PUBLICACIÓN ALTERNATIVAS
# =============================================================================

def publicar_telegram(video):
    """Publica en Telegram si está configurado"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    
    try:
        mensaje = f"""🔴 <b>{video['titulo']}</b>

📊 Puntaje: {video['puntaje']}/100
📺 Fuente: {video['fuente']}
⏰ Publicado: {video['publicado'][:10]}

🔗 {video['url']}

🤖 Bot de Noticias Automático"""
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': mensaje,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False
        }
        
        # Intentar enviar foto primero
        try:
            url_photo = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            photo_data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'photo': video['thumbnail'],
                'caption': mensaje[:1024],  # Límite de caption
                'parse_mode': 'HTML'
            }
            r = requests.post(url_photo, data=photo_data, timeout=30)
            if r.status_code == 200:
                log(f"✅ Telegram (con foto): {video['video_id']}", 'exito')
                return True
        except:
            pass
        
        # Fallback a mensaje de texto
        r = requests.post(url, data=data, timeout=30)
        if r.status_code == 200:
            log(f"✅ Telegram: {video['video_id']}", 'exito')
            return True
        else:
            log(f"❌ Telegram error: {r.text[:100]}", 'error')
            
    except Exception as e:
        log(f"❌ Telegram excepción: {e}", 'error')
    
    return False

def publicar_discord(video):
    """Publica en Discord via Webhook"""
    if not DISCORD_WEBHOOK_URL:
        return False
    
    try:
        embed = {
            "title": video['titulo'][:256],
            "url": video['url'],
            "color": 0xff0000,
            "thumbnail": {"url": video['thumbnail']},
            "fields": [
                {"name": "Fuente", "value": video['fuente'], "inline": True},
                {"name": "Puntaje", "value": str(video['puntaje']), "inline": True},
                {"name": "Video ID", "value": video['video_id'], "inline": True}
            ],
            "footer": {"text": f"Bot Noticias • {datetime.now().strftime('%Y-%m-%d %H:%M')}"},
            "image": {"url": video['thumbnail']}
        }
        
        payload = {
            "content": "🔴 **Nueva noticia de última hora**",
            "embeds": [embed]
        }
        
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)
        
        if r.status_code in [200, 204]:
            log(f"✅ Discord: {video['video_id']}", 'exito')
            return True
        else:
            log(f"❌ Discord error: {r.status_code} {r.text[:100]}", 'error')
            
    except Exception as e:
        log(f"❌ Discord excepción: {e}", 'error')
    
    return False

def guardar_para_revision(videos):
    """Guarda videos en archivo para revisión manual"""
    if not videos:
        return False
    
    try:
        # Cargar existentes
        existentes = cargar_json(OUTPUT_PATH, [])
        
        # Agregar nuevos al inicio
        nuevos = videos + existentes
        
        # Limitar a últimos 50
        nuevos = nuevos[:50]
        
        guardar_json(OUTPUT_PATH, nuevos)
        log(f"💾 Guardados {len(videos)} videos en {OUTPUT_PATH}", 'exito')
        
        # También crear archivo markdown para fácil lectura
        md_content = f"# Videos de Noticias - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        for i, v in enumerate(videos[:10], 1):
            md_content += f"## {i}. {v['titulo']}\n"
            md_content += f"- **Puntaje:** {v['puntaje']}\n"
            md_content += f"- **Fuente:** {v['fuente']}\n"
            md_content += f"- **URL:** {v['url']}\n"
            md_content += f"- **Thumbnail:** {v['thumbnail']}\n\n"
        
        with open('videos_para_revisar.md', 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        return True
    except Exception as e:
        log(f"Error guardando: {e}", 'error')
        return False

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*60)
    print("🎥 BOT NOTICIAS VIDEO V3.0 - MODO YOUTUBE")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Verificar API Key
    if not YOUTUBE_API_KEY:
        log("❌ YOUTUBE_API_KEY no configurado", 'error')
        log("   Configúralo en GitHub Secrets", 'info')
        return False
    
    # Cargar historial
    historial = cargar_json(HISTORIAL_PATH, {'videos': []})
    videos_historial = [v['video_id'] for v in historial.get('videos', [])]
    log(f"📊 Historial: {len(videos_historial)} videos previos")
    
    # Buscar videos
    videos = buscar_youtube()
    
    if not videos:
        log("⚠️ No se encontraron videos nuevos", 'advertencia')
        return False
    
    # Filtrar no publicados
    videos_nuevos = []
    for v in videos:
        if v['video_id'] not in videos_historial:
            videos_nuevos.append(v)
    
    log(f"🆕 Videos nuevos: {len(videos_nuevos)}")
    
    if not videos_nuevos:
        log("ℹ️ Todos los videos ya estaban en el historial", 'info')
        return True
    
    # Mostrar top 5
    log("📋 Top videos encontrados:", 'info')
    for i, v in enumerate(videos_nuevos[:5], 1):
        log(f"   {i}. [P{v['puntaje']}] {v['titulo'][:60]}...", 'info')
        log(f"      URL: {v['url']}", 'debug')
    
    # Seleccionar el mejor
    mejor = videos_nuevos[0]
    log(f"\n🎬 SELECCIONADO: {mejor['titulo'][:70]}...")
    log(f"   Puntaje: {mejor['puntaje']} | Fuente: {mejor['fuente']}")
    
    # Intentar publicar en servicios configurados
    publicado_en = []
    
    if MODO_TELEGRAM:
        if publicar_telegram(mejor):
            publicado_en.append('Telegram')
    
    if MODO_DISCORD:
        if publicar_discord(mejor):
            publicado_en.append('Discord')
    
    # Siempre guardar para revisión
    if MODO_GUARDAR_ARCHIVO:
        if guardar_para_revision([mejor]):
            publicado_en.append('Archivo JSON')
    
    # Guardar en historial
    if publicado_en:
        historial['videos'].append({
            'video_id': mejor['video_id'],
            'titulo': mejor['titulo'],
            'publicado_en': publicado_en,
            'fecha': datetime.now().isoformat()
        })
        # Mantener solo últimos 100
        historial['videos'] = historial['videos'][-100:]
        guardar_json(HISTORIAL_PATH, historial)
        
        log(f"✅ ÉXITO - Publicado en: {', '.join(publicado_en)}", 'exito')
        return True
    else:
        log("❌ No se pudo publicar en ningún servicio", 'error')
        return False

if __name__ == "__main__":
    try:
        sys.exit(0 if main() else 1)
    except Exception as e:
        log(f"💥 Error crítico: {e}", 'error')
        import traceback
        traceback.print_exc()
        sys.exit(1)

import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from src.scraper import ShortsScraper
from src.downloader import ShortsDownloader
from src.redactor import ContentRedactor
from src.publisher import FacebookPublisher
from src.database import VideosDB

load_dotenv()

def main():
    print(f"🚀 Iniciando bot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Inicializar
    scraper = ShortsScraper(os.getenv('YOUTUBE_API_KEY'))
    downloader = ShortsDownloader()
    redactor = ContentRedactor()
    publisher = FacebookPublisher(
        os.getenv('FB_PAGE_ID'),
        os.getenv('FB_ACCESS_TOKEN')
    )
    db = VideosDB()
    
    # === FASE 1: BUSCAR Y DESCARGAR ===
    print("\n🔍 FASE 1: Buscando Shorts relevantes...")
    
    # Buscar cada hora, pero solo videos de última hora
    shorts = scraper.buscar_shorts_noticias(max_results=10)
    print(f"   Encontrados: {len(shorts)} nuevos Shorts")
    
    descargados_hoy = 0
    for short in shorts:
        # Verificar si ya existe
        if db.existe_video(short['video_id']):
            continue
            
        archivo = downloader.descargar_short(short)
        if archivo:
            db.guardar_descargado(short)
            descargados_hoy += 1
            print(f"   ✓ Descargado: {short['video_id']}")
    
    print(f"   Total nuevos descargados: {descargados_hoy}")
    
    # === FASE 2: PUBLICAR (1 por hora) ===
    print("\n📤 FASE 2: Publicando en Facebook...")
    
    # Obtener el video más reciente pendiente
    video = db.obtener_siguiente_pendiente()
    
    if not video:
        print("   ℹ️ No hay videos pendientes para publicar")
        return
    
    # Verificar que no se haya publicado hace poco (anti-spam)
    ultima_publicacion = db.obtener_ultima_publicacion()
    if ultima_publicacion:
        minutos_desde_ultima = (datetime.now() - ultima_publicacion).total_seconds() / 60
        if minutos_desde_ultima < 45:  # Mínimo 45 minutos entre publicaciones
            print(f"   ⏱️ Esperando... Última publicación hace {int(minutos_desde_ultima)} minutos")
            return
    
    # Reescribir contenido
    print(f"   Procesando: {video['titulo_original'][:60]}...")
    contenido = redactor.reescribir(video['titulo_original'], 'general')
    
    # Publicar
    resultado = publisher.publicar_video(video['archivo_local'], contenido)
    
    if resultado['success']:
        db.marcar_publicado(video['video_id'], resultado['post_id'])
        print(f"   ✅ PUBLICADO: {contenido['titulo_nuevo'][:50]}...")
        print(f"   🔗 URL: {resultado['permalink']}")
    else:
        print(f"   ❌ ERROR: {resultado['error']}")
        db.marcar_error(video['video_id'], resultado['error'])
    
    # === FASE 3: LIMPIEZA ===
    print("\n🧹 FASE 3: Limpieza...")
    
    # Limpiar archivos locales de videos ya publicados
    publicados = db.obtener_publicados_antiguos(horas=2)
    for vid in publicados:
        if vid['archivo_local'] and os.path.exists(vid['archivo_local']):
            os.remove(vid['archivo_local'])
            db.limpiar_archivo_local(vid['video_id'])
            print(f"   🗑️ Eliminado local: {vid['video_id']}")
    
    # Limpiar archivos huérfanos (más de 24h)
    eliminados = downloader.limpiar_antiguos(horas_max=24)
    print(f"   Archivos huérfanos eliminados: {len(eliminados)}")
    
    # === REPORTE ===
    print("\n📊 REPORTE:")
    stats = db.obtener_estadisticas()
    for estado, cantidad in stats.items():
        print(f"   {estado}: {cantidad}")
    
    pendientes = db.contar_pendientes()
    print(f"   🕐 Videos en cola: {pendientes}")

if __name__ == "__main__":
    main()

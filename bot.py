import os
import sys
from datetime import datetime

# Verificar variables de entorno
print(f"=== Verificando configuración ===")
print(f"Fecha: {datetime.now()}")

required_vars = ['YOUTUBE_API_KEY', 'FB_PAGE_ID', 'FB_ACCESS_TOKEN']
missing = [v for v in required_vars if not os.getenv(v)]
if missing:
    print(f"ERROR: Faltan variables: {missing}")
    sys.exit(1)

print("✓ Todas las variables de entorno configuradas")

# Importar módulos
try:
    from src.scraper import ShortsScraper
    from src.downloader import ShortsDownloader
    from src.redactor import ContentRedactor
    from src.publisher import FacebookPublisher
    print("✓ Módulos importados correctamente")
except ImportError as e:
    print(f"ERROR importando módulos: {e}")
    sys.exit(1)

def main():
    print("\n=== FASE 1: BUSCAR SHORTS ===")
    scraper = ShortsScraper(os.getenv('YOUTUBE_API_KEY'))
    shorts = scraper.buscar_shorts_noticias(max_results=3)
    print(f"Encontrados: {len(shorts)} shorts")
    
    if not shorts:
        print("No se encontraron shorts, terminando")
        return
    
    for i, s in enumerate(shorts, 1):
        print(f"  {i}. {s['titulo'][:60]}...")
    
    print("\n=== FASE 2: DESCARGAR ===")
    downloader = ShortsDownloader()
    
    descargados = []
    for short in shorts:
        print(f"Descargando {short['video_id']}...")
        archivo = downloader.descargar_short(short)
        if archivo:
            descargados.append({**short, 'archivo': archivo})
            print(f"  ✓ Descargado: {archivo}")
        else:
            print(f"  ✗ Falló descarga")
    
    if not descargados:
        print("No se descargó ningún video, terminando")
        return
    
    print("\n=== FASE 3: PUBLICAR ===")
    redactor = ContentRedactor()
    publisher = FacebookPublisher(
        os.getenv('FB_PAGE_ID'),
        os.getenv('FB_ACCESS_TOKEN')
    )
    
    # Publicar solo el primero
    video = descargados[0]
    print(f"Procesando: {video['titulo'][:50]}...")
    
    contenido = redactor.reescribir(video['titulo'], 'general')
    print(f"Título nuevo: {contenido['titulo_nuevo'][:50]}...")
    
    resultado = publisher.publicar_video(video['archivo'], contenido)
    
    if resultado.get('success'):
        print(f"✓ PUBLICADO: {resultado.get('permalink', 'OK')}")
    else:
        print(f"✗ ERROR: {resultado.get('error', 'Desconocido')}")
    
    print("\n=== LIMPIEZA ===")
    eliminados = downloader.limpiar_antiguos(horas_max=0)  # Limpiar todo
    print(f"Eliminados: {len(eliminados)} archivos")
    
    print("\n=== COMPLETADO ===")

if __name__ == "__main__":
    main()

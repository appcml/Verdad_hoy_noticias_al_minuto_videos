import os
import sys
import traceback
from datetime import datetime

print(f"=== INICIO {datetime.now()} ===")

# Paso 1: Variables de entorno
print("\n1. Verificando variables...")
try:
    yt_key = os.getenv('YOUTUBE_API_KEY')
    fb_page = os.getenv('FB_PAGE_ID')
    fb_token = os.getenv('FB_ACCESS_TOKEN')
    
    print(f"   YOUTUBE_API_KEY: {'✓' if yt_key else '✗'} ({len(yt_key) if yt_key else 0} chars)")
    print(f"   FB_PAGE_ID: {'✓' if fb_page else '✗'}")
    print(f"   FB_ACCESS_TOKEN: {'✓' if fb_token else '✗'} ({len(fb_token) if fb_token else 0} chars)")
    
    if not all([yt_key, fb_page, fb_token]):
        print("ERROR: Faltan variables de entorno")
        sys.exit(1)
except Exception as e:
    print(f"ERROR en variables: {e}")
    traceback.print_exc()
    sys.exit(1)

# Paso 2: Importar módulos
print("\n2. Importando módulos...")
try:
    print("   - Intentando importar src.scraper...")
    from src.scraper import ShortsScraper
    print("     ✓ scraper importado")
    
    print("   - Intentando importar src.downloader...")
    from src.downloader import ShortsDownloader
    print("     ✓ downloader importado")
    
    print("   - Intentando importar src.redactor...")
    from src.redactor import ContentRedactor
    print("     ✓ redactor importado")
    
    print("   - Intentando importar src.publisher...")
    from src.publisher import FacebookPublisher
    print("     ✓ publisher importado")
    
except Exception as e:
    print(f"ERROR importando: {e}")
    traceback.print_exc()
    sys.exit(1)

# Paso 3: Crear instancias
print("\n3. Creando instancias...")
try:
    print("   - Creando scraper...")
    scraper = ShortsScraper(yt_key)
    print("     ✓ scraper creado")
    
    print("   - Creando downloader...")
    downloader = ShortsDownloader()
    print("     ✓ downloader creado")
    
    print("   - Creando redactor...")
    redactor = ContentRedactor()
    print("     ✓ redactor creado")
    
    print("   - Creando publisher...")
    publisher = FacebookPublisher(fb_page, fb_token)
    print("     ✓ publisher creado")
    
except Exception as e:
    print(f"ERROR creando instancias: {e}")
    traceback.print_exc()
    sys.exit(1)

# Paso 4: Buscar videos
print("\n4. Buscando shorts...")
try:
    shorts = scraper.buscar_shorts_noticias(max_results=2)
    print(f"   ✓ Encontrados: {len(shorts)} shorts")
    for i, s in enumerate(shorts, 1):
        print(f"     {i}. {s.get('titulo', 'N/A')[:50]}...")
except Exception as e:
    print(f"ERROR buscando: {e}")
    traceback.print_exc()
    sys.exit(1)

if not shorts:
    print("No se encontraron videos, terminando")
    sys.exit(0)

# Paso 5: Descargar
print("\n5. Descargando...")
try:
    video = shorts[0]
    print(f"   Descargando {video.get('video_id')}...")
    archivo = downloader.descargar_short(video)
    if archivo:
        print(f"   ✓ Descargado: {archivo}")
    else:
        print("   ✗ Falló descarga")
        sys.exit(1)
except Exception as e:
    print(f"ERROR descargando: {e}")
    traceback.print_exc()
    sys.exit(1)

# Paso 6: Reescribir
print("\n6. Reescribiendo contenido...")
try:
    contenido = redactor.reescribir(video.get('titulo', ''), 'general')
    print(f"   ✓ Título nuevo: {contenido.get('titulo_nuevo', 'N/A')[:50]}...")
except Exception as e:
    print(f"ERROR reescribiendo: {e}")
    traceback.print_exc()
    sys.exit(1)

# Paso 7: Publicar
print("\n7. Publicando en Facebook...")
try:
    resultado = publisher.publicar_video(archivo, contenido)
    if resultado.get('success'):
        print(f"   ✓ PUBLICADO: {resultado.get('post_id')}")
    else:
        print(f"   ✗ ERROR: {resultado.get('error')}")
        sys.exit(1)
except Exception as e:
    print(f"ERROR publicando: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== ÉXITO ===")
sys.exit(0)

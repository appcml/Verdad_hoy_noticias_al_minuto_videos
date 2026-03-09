# Bot de Videos - Verdad Hoy Noticias al Minuto

Bot automatizado que busca y publica videos de noticias de conflictos internacionales, narcotráfico, política y desastres en Facebook.

## Características

- 🔍 Busca videos en YouTube, Twitter/X, NewsAPI y RSS
- 🎬 Prioriza videos cortos (&lt; 5 min) en calidad 720p+
- 🏷️ Categoriza automáticamente (guerra, narcotráfico, política, etc.)
- ⏰ Publica automáticamente cada 1 hora
- 📊 Mantiene historial para evitar duplicados

## Categorías

- Conflictos y Guerra
- Narcotráfico
- Política Internacional
- Crisis Económica
- Desastres y Tragedias
- Violencia y Crimen

## Configuración

Variables de entorno necesarias:
- `FB_PAGE_ID`: ID de la página de Facebook
- `FB_ACCESS_TOKEN`: Token de acceso de Facebook
- `NEWS_API_KEY`: (Opcional) API key de NewsAPI

## Instalación

1. Clonar repositorio
2. Instalar dependencias: `pip install -r requirements.txt`
3. Configurar variables de entorno
4. Ejecutar: `python bot_videos.py`

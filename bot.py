import os
import json
import random
import datetime
from googleapiclient.discovery import build
import yt_dlp

# cargar configuración
with open("config.json") as f:
    config = json.load(f)

API_KEY = config["youtube_api_key"]
MAX_VIDEOS = config["max_videos"]
DIAS_BORRAR = config["dias_borrar"]
TEMAS = config["temas"]

CARPETA = "videos"
HISTORIAL = "historial.json"

if not os.path.exists(CARPETA):
    os.makedirs(CARPETA)

if not os.path.exists(HISTORIAL):
    with open(HISTORIAL,"w") as f:
        json.dump([],f)

youtube = build("youtube","v3",developerKey=API_KEY)

def cargar_historial():
    with open(HISTORIAL) as f:
        return json.load(f)

def guardar_historial(data):
    with open(HISTORIAL,"w") as f:
        json.dump(data,f)

def buscar_videos():

    tema=random.choice(TEMAS)

    print("Buscando noticias sobre:",tema)

    ayer=(datetime.datetime.utcnow()-datetime.timedelta(days=1)).isoformat("T")+"Z"

    request=youtube.search().list(
        q=tema,
        part="snippet",
        type="video",
        order="date",
        maxResults=MAX_VIDEOS,
        publishedAfter=ayer
    )

    response=request.execute()

    urls=[]

    for item in response["items"]:

        video_id=item["id"]["videoId"]

        url="https://www.youtube.com/watch?v="+video_id

        urls.append(url)

    return urls


def descargar_video(url):

    opciones={
        "outtmpl": "videos/%(title)s.%(ext)s",
        "format": "mp4"
    }

    with yt_dlp.YoutubeDL(opciones) as ydl:
        ydl.download([url])


def borrar_videos_antiguos():

    ahora=datetime.datetime.now()

    for archivo in os.listdir(CARPETA):

        ruta=os.path.join(CARPETA,archivo)

        tiempo=datetime.datetime.fromtimestamp(os.path.getmtime(ruta))

        dias=(ahora-tiempo).days

        if dias>DIAS_BORRAR:

            os.remove(ruta)

            print("Video eliminado:",archivo)


def main():

    historial=cargar_historial()

    urls=buscar_videos()

    for url in urls:

        if url in historial:
            continue

        try:

            print("Descargando:",url)

            descargar_video(url)

            historial.append(url)

        except Exception as e:

            print("Error:",e)

    guardar_historial(historial)

    borrar_videos_antiguos()

    print("Proceso terminado")


if __name__=="__main__":
    main()

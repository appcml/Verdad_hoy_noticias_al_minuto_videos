import random
from datetime import datetime

class ContentRedactor:
    def __init__(self):
        self.plantillas = {
            'mañana': [  # 6-12h
                "🌅 {tema} | Primera edición",
                "📰 Despertando con: {tema}",
                "☕ {tema} - Reporte matutino"
            ],
            'tarde': [  # 12-18h
                "🌤️ {tema} | Actualización",
                "📢 Último momento: {tema}",
                "⚡ {tema} - En desarrollo"
            ],
            'noche': [  # 18-24h
                "🌙 {tema} | Cierre de jornada",
                "🔴 {tema} - Reporte vespertino",
                "📺 {tema} | Noticia nocturna"
            ],
            'madrugada': [  # 0-6h
                "🌃 {tema} | Alerta nocturna",
                "🚨 {tema} - Urgente",
                "⚠️ {tema} | Última hora"
            ]
        }
        
        self.emojis = ['🔴', '⚡', '🚨', '💥', '📢', '⚠️', '🔥']
    
    def reescribir(self, titulo_original, categoria='general'):
        # Detectar franja horaria
        hora = datetime.now().hour
        if 6 <= hora < 12:
            franja = 'mañana'
        elif 12 <= hora < 18:
            franja = 'tarde'
        elif 18 <= hora < 24:
            franja = 'noche'
        else:
            franja = 'madrugada'
        
        # Limpiar título
        tema = self.extraer_tema(titulo_original)
        
        # Seleccionar plantilla según hora
        plantilla = random.choice(self.plantillas[franja])
        titulo_nuevo = plantilla.format(tema=tema)
        
        # Descripción variada
        descripcion = self.generar_descripcion(franja, tema)
        
        # Hashtags
        hashtags = self.generar_hashtags(categoria, tema)
        
        return {
            'titulo_original': titulo_original,
            'titulo_nuevo': titulo_nuevo,
            'descripcion': descripcion,
            'hashtags': hashtags,
            'franja_horaria': franja
        }
    
    def extraer_tema(self, titulo):
        palabras_basura = [
            'noticias', 'news', 'urgente', 'ultima hora', 'breaking',
            'shorts', 'video', 'youtube', 'hoy', 'ahora', 'live'
        ]
        
        palabras = titulo.lower().split()
        limpio = [p for p in palabras if p not in palabras_basura and len(p) > 2]
        
        return ' '.join(limpio[:6]).title() if limpio else "Información de Última Hora"
    
    def generar_descripcion(self, franja, tema):
        intros = {
            'mañana': "Comenzamos el día con información importante:",
            'tarde': "Actualización del mediodía:",
            'noche': "Cerramos la jornada con esta noticia:",
            'madrugada': "Alerta en horas de la madrugada:"
        }
        
        cuerpo = f"{intros[franja]}\n\n🔍 {tema}\n\n¿Qué opinas? Comenta 👇"
        return cuerpo
    
    def generar_hashtags(self, categoria, tema):
        base = ['#Noticias', '#Actualidad', '#Viral', '#ÚltimaHora']
        
        if categoria == 'guerra':
            base.extend(['#Conflicto', '#Internacional'])
        elif categoria == 'desastre':
            base.extend(['#Emergencia', '#DesastreNatural'])
        elif categoria == 'politica':
            base.extend(['#Política', '#Gobierno'])
        
        # Hashtag del tema
        tema_tag = tema.replace(' ', '')[:15]
        if len(tema_tag) > 3:
            base.append(f"#{tema_tag}")
        
        return ' '.join(base[:6])  # Máximo 6 hashtags

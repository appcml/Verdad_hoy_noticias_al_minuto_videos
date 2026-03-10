#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random
import re
from .utils import log

class GeneradorTitulosViral:
    """
    Genera títulos atractivos basados en el contenido del video
    """
    
    PLANTILLAS_HOOK = [
        "🚨 {titulo} - Esto cambia todo",
        "😱 {titulo} - No vas a creer lo que pasó",
        "🔥 {titulo} - Se volvió viral por esto",
        "⚠️ ALERTA: {titulo}",
        "💥 {titulo} - El video que todos hablan",
        "👀 MIRA: {titulo}",
        "🛑 {titulo} - Antes de que lo borren",
        "🤯 REVELADO: {titulo}",
    ]
    
    EMOCIONES = {
        'shock': ['😱', '🤯', '💀', '⚠️'],
        'urgente': ['🚨', '🔥', '⏰', '⚡'],
        'misterio': ['👀', '🕵️', '🔍', '🤫'],
        'politica': ['🇨🇱', '🗳️', '⚖️', '📢'],
        'humor': ['😂', '🤣', '💀', '🔥'],
    }
    
    def __init__(self):
        self.palabras_clave_temas = {
            'politica': ['presidente', 'gobierno', 'ministro', 'ley', 'congreso', 'corrupcion'],
            'economia': ['precio', 'dolar', 'inflacion', 'crisis', 'impuesto'],
            'social': ['protesta', 'marcha', 'manifestacion', 'pueblo', 'ciudadanos'],
            'internacional': ['eeuu', 'china', 'rusia', 'guerra', 'biden', 'trump'],
            'viral': ['insolito', 'increible', 'sorprendente', 'viral', 'tendencia'],
        }
    
    def analizar_contenido(self, titulo_original, descripcion):
        """Detecta el tema principal del video"""
        texto_completo = f"{titulo_original} {descripcion}".lower()
        
        puntuaciones = {}
        for tema, palabras in self.palabras_clave_temas.items():
            score = sum(2 for p in palabras if p in texto_completo)
            if score > 0:
                puntuaciones[tema] = score
        
        if puntuaciones:
            return max(puntuaciones, key=puntuaciones.get)
        return 'viral'
    
    def generar_titulo(self, titulo_original, descripcion, duracion):
        """Genera título viral optimizado para engagement"""
        
        # Limpiar título original
        titulo_limpio = self._limpiar_texto(titulo_original)
        
        # Detectar tema
        tema = self.analizar_contenido(titulo_original, descripcion)
        
        # Seleccionar plantilla según tema y duración
        if duracion < 60:
            tipo = "SHORT"
            plantillas = [
                "⚡ {titulo} - Corto pero impactante",
                "👀 {titulo} - En solo {duracion}s",
                "🔥 {titulo} - Tendencia viral",
            ]
        else:
            tipo = "VIDEO"
            plantillas = self.PLANTILLAS_HOOK
        
        # Seleccionar y formatear
        plantilla = random.choice(plantillas)
        titulo_nuevo = plantilla.format(
            titulo=titulo_limpio[:60],
            duracion=int(duracion)
        )
        
        # Añadir emoji de tema
        emojis_tema = self.EMOCIONES.get(tema, ['🔥'])
        if not any(e in titulo_nuevo for e in emojis_tema):
            titulo_nuevo = f"{random.choice(emojis_tema)} {titulo_nuevo}"
        
        # Añadir hashtags contextuales
        hashtags = self._generar_hashtags(tema)
        
        return {
            'titulo': titulo_nuevo[:100],  # Límite Facebook
            'descripcion': self._crear_descripcion(descripcion, tema),
            'hashtags': hashtags,
            'tema_detectado': tema,
            'tipo': tipo
        }
    
    def _limpiar_texto(self, texto):
        """Limpia y mejora el texto"""
        if not texto:
            return "Video viral"
        
        # Eliminar URLs, menciones, hashtags del original
        texto = re.sub(r'http\S+', '', texto)
        texto = re.sub(r'@\w+', '', texto)
        texto = re.sub(r'#\w+', '', texto)
        texto = re.sub(r'\s+', ' ', texto)
        
        # Capitalizar primera letra
        texto = texto.strip().capitalize()
        
        return texto[:80]
    
    def _crear_descripcion(self, descripcion_original, tema):
        """Crea descripción atractiva"""
        if not descripcion_original:
            descripcion_original = "Contenido exclusivo que está dando de qué hablar."
        
        # Limpiar
        desc = self._limpiar_texto(descripcion_original)
        
        # Añadir llamada a la acción según tema
        ctas = {
            'politica': "¿Estás de acuerdo? Comenta tu opinión 👇",
            'economia': "Esto nos afecta a todos. Comparte 🔄",
            'social': "El pueblo se manifiesta. Tu voz cuenta 💬",
            'internacional': "El mundo está cambiando. Mantente informado 🌍",
            'viral': "¿Qué te pareció? Reacciona 👍",
        }
        
        cta = ctas.get(tema, "Comparte si te impactó 🔁")
        
        return f"{desc}\n\n{cta}"
    
    def _generar_hashtags(self, tema):
        """Genera hashtags relevantes"""
        base = {
            'politica': ['#Chile', '#Politica', '#Noticias'],
            'economia': ['#Economia', '#Chile', '#Actualidad'],
            'social': ['#Chile', '#Social', '#Noticias'],
            'internacional': ['#Internacional', '#Mundo', '#Noticias'],
            'viral': ['#Viral', '#Tendencia', '#Video'],
        }
        
        tags = base.get(tema, ['#Noticias', '#Actualidad'])
        tags.extend(['#VerdadHoy', '#NoticiasAlMinuto', '#Comparte'])
        
        return ' '.join(tags)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import hashlib
from datetime import datetime

def log(mensaje, tipo='info'):
    iconos = {
        'info': 'ℹ️', 
        'exito': '✅', 
        'error': '❌', 
        'advertencia': '⚠️', 
        'viral': '🔥', 
        'facebook': '📘'
    }
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {iconos.get(tipo, 'ℹ️')} {mensaje}")

def cargar_json(ruta, default=None):
    if default is None:
        default = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default
    return default

def guardar_json(ruta, datos):
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"Error guardando JSON: {e}", 'error')
        return False

def generar_hash(texto):
    return hashlib.md5(texto.encode()).hexdigest()[:12]

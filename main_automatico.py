#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cola_processor import ProcesadorCola
from src.utils import log

def main():
    print("\n" + "="*70)
    print("🤖 VERDAD HOY - Bot Automático")
    print("="*70)
    
    procesador = ProcesadorCola()
    
    # Agregar URLs de argumentos
    urls = sys.argv[1:]
    if urls:
        log(f"Agregando {len(urls)} URLs...", 'info')
        agregados = 0
        for url in urls[:15]:  # Máximo 15
            if procesador.agregar_a_cola(url, "usuario"):
                agregados += 1
        log(f"Agregados: {agregados}", 'exito')
    
    # Procesar cola (máximo 15)
    log("Procesando videos...", 'info')
    cantidad = 0
    while cantidad < 15:
        success, estado = procesador.procesar_siguiente()
        if estado == "cola_vacia":
            break
        if success:
            cantidad += 1
    
    log(f"Videos procesados: {cantidad}", 'exito' if cantidad > 0 else 'advertencia')
    return True

if __name__ == "__main__":
    try:
        main()
        exit(0)
    except Exception as e:
        log(f"Error: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

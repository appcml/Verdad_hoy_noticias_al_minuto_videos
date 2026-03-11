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
    
    # Si hay URL como argumento, agregar a cola
    if len(sys.argv) > 1:
        url = sys.argv[1]
        log(f"Agregando: {url[:60]}...", 'info')
        procesador.agregar_a_cola(url, "usuario")
    
    # Procesar cola
    log("Procesando videos...", 'info')
    cantidad = procesador.procesar_todos()
    
    log(f"Videos procesados: {cantidad}", 'exito' if cantidad > 0 else 'advertencia')
    return cantidad > 0

if __name__ == "__main__":
    try:
        exit(0 if main() else 0)  # 0 = OK, no es error si no hay videos
    except Exception as e:
        log(f"Error: {e}", 'error')
        import traceback
        traceback.print_exc()
        exit(1)

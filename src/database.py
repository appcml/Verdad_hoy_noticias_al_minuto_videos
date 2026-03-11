import sqlite3
from datetime import datetime, timedelta
import os

class VideosDB:
    def __init__(self, db_path="data/videos.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT UNIQUE,
                titulo_original TEXT,
                titulo_nuevo TEXT,
                descripcion TEXT,
                categoria TEXT,
                url_youtube TEXT,
                archivo_local TEXT,
                post_id_facebook TEXT,
                estado TEXT DEFAULT 'pendiente',
                error_msg TEXT,
                fecha_descarga TIMESTAMP,
                fecha_publicacion TIMESTAMP,
                vistas_facebook INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def existe_video(self, video_id):
        """Verifica si un video ya fue procesado"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT 1 FROM videos WHERE video_id = ?', (video_id,))
        existe = c.fetchone() is not None
        conn.close()
        return existe
    
    def guardar_descargado(self, info):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO videos 
            (video_id, titulo_original, url_youtube, archivo_local, estado, fecha_descarga)
            VALUES (?, ?, ?, ?, 'pendiente', ?)
        ''', (
            info['video_id'],
            info['titulo'],
            info['url'],
            info.get('archivo_local'),
            datetime.now()
        ))
        
        conn.commit()
        conn.close()
    
    def obtener_siguiente_pendiente(self):
        """Obtiene el video pendiente más antiguo (FIFO)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT * FROM videos 
            WHERE estado = 'pendiente' 
            AND archivo_local IS NOT NULL
            ORDER BY fecha_descarga ASC
            LIMIT 1
        ''')
        
        row = c.fetchone()
        conn.close()
        
        if row:
            columns = [description[0] for description in c.description]
            return dict(zip(columns, row))
        return None
    
    def contar_pendientes(self):
        """Cuantos videos hay en cola"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM videos WHERE estado = 'pendiente'")
        count = c.fetchone()[0]
        conn.close()
        return count
    
    def obtener_ultima_publicacion(self):
        """Fecha de la última publicación exitosa"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT fecha_publicacion FROM videos 
            WHERE estado = 'publicado' 
            ORDER BY fecha_publicacion DESC 
            LIMIT 1
        ''')
        
        row = c.fetchone()
        conn.close()
        
        if row and row[0]:
            return datetime.fromisoformat(row[0])
        return None
    
    def marcar_publicado(self, video_id, post_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            UPDATE videos 
            SET estado = 'publicado', 
                post_id_facebook = ?,
                fecha_publicacion = ?
            WHERE video_id = ?
        ''', (post_id, datetime.now(), video_id))
        
        conn.commit()
        conn.close()
    
    def marcar_error(self, video_id, error_msg):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            UPDATE videos 
            SET estado = 'error', 
                error_msg = ?
            WHERE video_id = ?
        ''', (error_msg, video_id))
        
        conn.commit()
        conn.close()
    
    def obtener_publicados_antiguos(self, horas=2):
        """Videos publicados hace X horas (para limpiar archivos locales)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        tiempo_limite = datetime.now() - timedelta(hours=horas)
        
        c.execute('''
            SELECT video_id, archivo_local FROM videos 
            WHERE estado = 'publicado' 
            AND fecha_publicacion < ?
            AND archivo_local IS NOT NULL
        ''', (tiempo_limite,))
        
        resultados = [{'video_id': row[0], 'archivo_local': row[1]} 
                     for row in c.fetchall()]
        conn.close()
        return resultados
    
    def limpiar_archivo_local(self, video_id):
        """Marca archivo local como eliminado"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('UPDATE videos SET archivo_local = NULL WHERE video_id = ?', (video_id,))
        conn.commit()
        conn.close()
    
    def obtener_estadisticas(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT estado, COUNT(*) FROM videos GROUP BY estado')
        stats = dict(c.fetchall())
        conn.close()
        return stats

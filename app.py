from flask import Flask, render_template, jsonify, request
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import pandas as pd

app = Flask(__name__)

# Configuración de la base de datos
DB_CONFIG = {
    'host': 'raspi-db.cti0wcg6q365.us-east-1.rds.amazonaws.com',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'Clave_raspi$',
    'port': 5432
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_data')
def get_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener el último registro
        cursor.execute("""
            SELECT fecha as timestamp, valor as value 
            FROM public.tension 
            ORDER BY fecha DESC 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return jsonify({
                'current_value': float(result['value']),
                'timestamp': result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            })
        return jsonify({'error': 'No data found'})
    
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/get_historical_data')
def get_historical_data():
    try:
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT fecha as timestamp, valor as value 
            FROM public.tension 
            WHERE fecha BETWEEN %s AND %s 
            ORDER BY fecha ASC
        """
        
        cursor.execute(query, (start_date, end_date))
        results = cursor.fetchall()
        
        timestamps = [row['timestamp'].strftime('%Y-%m-%d %H:%M:%S') for row in results]
        values = [float(row['value']) for row in results]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'timestamps': timestamps,
            'values': values
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/get_latest_data')
def get_latest_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Obtener los últimos 100 registros para el modo tiempo real
        cursor.execute("""
            SELECT fecha as timestamp, valor as value 
            FROM public.tension 
            ORDER BY fecha DESC 
            LIMIT 100
        """)
        
        results = cursor.fetchall()
        results.reverse()  # Invertir para orden cronológico
        
        timestamps = [row['timestamp'].strftime('%Y-%m-%d %H:%M:%S') for row in results]
        values = [float(row['value']) for row in results]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'timestamps': timestamps,
            'values': values
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)

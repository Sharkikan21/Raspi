from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import csv

# Flask basic setup
app = Flask(__name__)

# Database connection configuration
DB_CONFIG = {
    'host': 'raspi-db.cti0wcg6q365.us-east-1.rds.amazonaws.com',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'Clave_raspi$',
    'port': 5432
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# Route to display table contents
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def get_db_data():
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        query = 'SELECT * FROM public.tension'
        params = []
        
        if fecha_inicio and fecha_fin:
            query += ' WHERE fecha BETWEEN %s AND %s'
            # Convertir las fechas al formato correcto para PostgreSQL
            fecha_inicio = datetime.fromisoformat(fecha_inicio).strftime('%Y-%m-%d %H:%M:%S')
            fecha_fin = datetime.fromisoformat(fecha_fin).strftime('%Y-%m-%d %H:%M:%S')
            params = [fecha_inicio, fecha_fin]
        
        query += ' ORDER BY fecha DESC'
        
        conn = get_db_connection()
        # Using pandas to create HTML table with parameters
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df.to_html(classes='table table-striped', index=False)
    except Exception as e:
        print(f"Database error: {e}")
        return f"<p>Error: {str(e)}</p>"

@app.route('/get_data')
def get_data():
    try:
        with open('datos_tension_generados.csv', 'r') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)  # Saltar la cabecera
            data = list(csv_reader)
            if data:
                last_row = data[-1]
                # Obtener los últimos 100 registros para el gráfico
                last_100_rows = data[-100:] if len(data) > 100 else data
                
                return jsonify({
                    'current_value': float(last_row[1]),
                    'timestamp': last_row[0],
                    'historical_data': {
                        'timestamps': [row[0] for row in last_100_rows],
                        'values': [float(row[1]) for row in last_100_rows]
                    }
                })
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)

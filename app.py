from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

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
        format_type = request.args.get('format', 'html')
        after_timestamp = request.args.get('after_timestamp')  # Para tiempo real
        
        query = 'SELECT * FROM public.tension'
        params = []
        
        if after_timestamp:
            # Para tiempo real: obtener solo datos nuevos después del último timestamp
            query += ' WHERE fecha > %s'
            params = [after_timestamp]
        elif fecha_inicio and fecha_fin:
            # Para modo histórico: filtrar por rango de fechas
            query += ' WHERE fecha BETWEEN %s AND %s'
            fecha_inicio = datetime.fromisoformat(fecha_inicio).strftime('%Y-%m-%d %H:%M:%S')
            fecha_fin = datetime.fromisoformat(fecha_fin).strftime('%Y-%m-%d %H:%M:%S')
            params = [fecha_inicio, fecha_fin]
        
        query += ' ORDER BY fecha DESC'
        
        if after_timestamp:
            # Para tiempo real: limitar a los últimos N registros
            query += ' LIMIT 50'
        
        conn = get_db_connection()
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if format_type == 'json':
            data = {
                'fechas': df['fecha'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                'pesos': df['peso_kilbf'].tolist()
            }
            return jsonify(data)
        else:
            return df.to_html(classes='table table-striped', index=False)
            
    except Exception as e:
        print(f"Database error: {e}")
        return f"<p>Error: {str(e)}</p>"

if __name__ == '__main__':
    app.run(debug=True)

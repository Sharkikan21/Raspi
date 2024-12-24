from flask import Flask, render_template, request, jsonify
import pandas as pd
import psycopg2
from datetime import datetime

app = Flask(__name__)

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

@app.route('/data')
def get_db_data():
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        format_type = request.args.get('format', 'html')
        after_timestamp = request.args.get('after_timestamp')
        limit = request.args.get('limit')

        query = 'SELECT * FROM public.tension'
        params = []

        if after_timestamp:
            query += ' WHERE fecha > %s'
            params.append(after_timestamp)
        elif fecha_inicio and fecha_fin:
            query += ' WHERE fecha BETWEEN %s AND %s'
            fecha_inicio = datetime.fromisoformat(fecha_inicio).strftime('%Y-%m-%d %H:%M:%S')
            fecha_fin = datetime.fromisoformat(fecha_fin).strftime('%Y-%m-%d %H:%M:%S')
            params.extend([fecha_inicio, fecha_fin])

        query += ' ORDER BY fecha DESC'

        if limit:
            query += f' LIMIT {int(limit)}'
        elif after_timestamp:
            query += ' LIMIT 50'

        conn = get_db_connection()
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        if format_type == 'json':
            data = {
                'fechas': df['fecha'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                'perno_1': df['perno_1'].tolist(),
                'perno_2': df['perno_2'].tolist(),
                'perno_3': df['perno_3'].tolist(),
                'perno_4': df['perno_4'].tolist(),
                'perno_5': df['perno_5'].tolist()
            }
            return jsonify(data)
        else:
            return df.to_html(classes='table table-striped', index=False)

    except Exception as e:
        print(f"Database error: {e}")
        return f"<p>Error: {str(e)}</p>"

if __name__ == '__main__':
    app.run(debug=True)

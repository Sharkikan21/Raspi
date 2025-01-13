from flask import Flask, redirect, render_template, request, jsonify, session, url_for
import pandas as pd
import psycopg2
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_caching import Cache

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # Mejor si viene de variables de entorno

DB_CONFIG = {
    'host': 'raspi-db.cti0wcg6q365.us-east-1.rds.amazonaws.com',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'Clave_raspi$',
    'port': 5432
}

# Configurar Flask-Caching
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# Decorator para proteger rutas
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if session['role'] == 'admin':
        raspberry_id = request.args.get('raspberry_id')
        if not raspberry_id:
            return render_template('raspberry_selector.html')
        session['selected_raspberry'] = raspberry_id
    return render_template('index.html')

@app.route('/data')
@login_required
def get_db_data():
    try:
        # Parámetros de la consulta
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        after_timestamp = request.args.get('after_timestamp')
        format_type = request.args.get('format', 'html')

        # Clave de cache específica por usuario y Raspberry
        cache_key = f"data_user_{session['user_id']}_raspberry_{session.get('selected_raspberry')}"

        # Recuperar datos del cache si no hay filtros
        cached_data = cache.get(cache_key)
        if cached_data and not (fecha_inicio or fecha_fin or after_timestamp):
            print("Usando datos cacheados")
            return jsonify(cached_data) if format_type == 'json' else render_template('data_table.html', data=cached_data)

        # Construir la consulta a la base de datos
        conn = get_db_connection()
        params = [int(session.get('selected_raspberry'))]
        query = "SELECT * FROM public.tension WHERE raspberry_id = %s"

        if after_timestamp:
            query += " AND fecha > %s"
            params.append(after_timestamp)
        elif fecha_inicio and fecha_fin:
            query += " AND fecha BETWEEN %s AND %s"
            params.append(fecha_inicio)
            params.append(fecha_fin)

        query += " ORDER BY fecha ASC"

        # Ejecutar la consulta
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        # Renombrar columnas
        column_mapping = {
            'id': 'Numero',
            'fecha': 'Fecha',
            'perno_1': 'Dato 1',
            'perno_2': 'Dato 2',
            'perno_3': 'Dato 3',
            'perno_4': 'Dato 4',
            'perno_5': 'Dato 5',
            'raspberry_id': 'ID'
        }
        df = df.rename(columns=column_mapping)

        # Preparar los datos en formato JSON
        data = {
            'fechas': df['Fecha'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            'mediciones': df['Dato 1'].fillna("").tolist()
        }

        # Actualizar el cache con los nuevos datos
        cache.set(cache_key, data)
        return jsonify(data) if format_type == 'json' else render_template('data_table.html', data=df)

    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/data/realtime')
@login_required
def get_realtime_data():
    try:
        # Clave de cache para el usuario y Raspberry seleccionada
        cache_key = f"data_user_{session['user_id']}_raspberry_{session.get('selected_raspberry')}"

        # Obtener el último timestamp del cache
        cached_data = cache.get(cache_key) or {'fechas': [], 'mediciones': []}
        last_timestamp = cached_data['fechas'][-1] if cached_data['fechas'] else None

        # Si no hay datos previos, devolver mensaje vacío
        if not last_timestamp:
            return jsonify({'fechas': [], 'mediciones': []})

        # Consultar nuevos datos en la base
        conn = get_db_connection()
        query = "SELECT * FROM public.tension WHERE raspberry_id = %s AND fecha > %s ORDER BY fecha ASC"
        params = [int(session.get('selected_raspberry')), last_timestamp]
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        # Renombrar columnas
        column_mapping = {
            'id': 'Numero',
            'fecha': 'Fecha',
            'perno_1': 'Dato 1',
            'perno_2': 'Dato 2',
            'perno_3': 'Dato 3',
            'perno_4': 'Dato 4',
            'perno_5': 'Dato 5',
            'raspberry_id': 'ID'
        }
        df = df.rename(columns=column_mapping)

        # Si no hay nuevos datos, devolver mensaje vacío
        if df.empty:
            return jsonify({'fechas': [], 'mediciones': []})

        # Agregar nuevos datos al cache
        new_data = {
            'fechas': df['Fecha'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            'mediciones': df['Dato 1'].fillna("").tolist()
        }
        cached_data['fechas'].extend(new_data['fechas'])
        cached_data['mediciones'].extend(new_data['mediciones'])

        # Actualizar cache
        cache.set(cache_key, cached_data)

        # Devolver solo los datos nuevos
        return jsonify(new_data)

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return render_template('login.html', error='Faltan credenciales')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT u.id, u.password, r.name AS role 
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.username = %s
            """, (username,))
            user = cursor.fetchone()

            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['role'] = user[2]
                return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', error='Credenciales incorrectas')

        except Exception as e:
            return render_template('login.html', error=f'Error: {str(e)}')

        finally:
            cursor.close()
            conn.close()

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

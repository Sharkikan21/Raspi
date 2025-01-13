from flask import Flask, redirect, render_template, request, jsonify, session, url_for
from flask_caching import Cache
import pandas as pd
import psycopg2
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # Mejor si viene de variables de entorno

# Configuración del caché
cache = Cache(app, config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300  # 5 minutos
})

DB_CONFIG = {
    'host': 'raspi-db.cti0wcg6q365.us-east-1.rds.amazonaws.com',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'Clave_raspi$',
    'port': 5432
}

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
        format_type = request.args.get('format', 'html')
        after_timestamp = request.args.get('after_timestamp')
        is_initial_load = request.args.get('initial_load', 'false') == 'true'

        # Obtener el nombre de usuario
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id = %s", (session['user_id'],))
        username = cursor.fetchone()[0]
        cursor.close()

        # Clave única para el caché basada en el usuario y raspberry
        cache_key = f"data_{username}"
        if session.get('role') == 'admin' and session.get('selected_raspberry'):
            cache_key += f"_{session['selected_raspberry']}"

        if is_initial_load:
            # Limpiar caché anterior para este usuario
            cache.delete(cache_key)
            df = get_initial_data(username)
            cache.set(cache_key, df)
        else:
            # Obtener datos del caché
            df = cache.get(cache_key)
            if df is None or after_timestamp:
                # Si no hay caché o se solicitan nuevos datos
                df = get_new_data(username, after_timestamp)
                if not after_timestamp:
                    cache.set(cache_key, df)
                elif df is not None and not df.empty:
                    cached_df = cache.get(cache_key)
                    if cached_df is not None:
                        df = pd.concat([cached_df, df]).drop_duplicates()
                        cache.set(cache_key, df)

        if df is None or df.empty:
            return jsonify({'error': 'No data available'}) if format_type == 'json' else "<p>No hay datos disponibles</p>"

        # Procesar datos según el usuario
        if username == 'test':
            return process_test_user_data(df, format_type)
        else:
            return process_normal_user_data(df, format_type)

    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'error': str(e)}) if format_type == 'json' else f"<p>Error: {str(e)}</p>"

def get_initial_data(username):
    # Obtener todos los datos iniciales
    conn = get_db_connection()
    query = build_query(username)
    df = pd.read_sql_query(query, conn, params=get_query_params(username))
    conn.close()
    return process_dataframe(df)

def get_new_data(username, after_timestamp):
    # Obtener solo los nuevos datos después del timestamp
    if after_timestamp:
        conn = get_db_connection()
        query = build_query(username, after_timestamp)
        df = pd.read_sql_query(query, conn, params=get_query_params(username, after_timestamp))
        conn.close()
        return process_dataframe(df)
    return None

def build_query(username, after_timestamp=None):
    base_query = """
        SELECT t.* FROM public.tension t
        JOIN user_raspberry ur ON t.raspberry_id = ur.raspberry_id
        WHERE ur.user_id = %s
    """
    if after_timestamp:
        base_query += " AND t.fecha > %s"
    base_query += " ORDER BY t.fecha ASC"
    return base_query

def get_query_params(username, after_timestamp=None):
    params = [session['user_id']]
    if after_timestamp:
        params.append(after_timestamp)
    return params

def process_dataframe(df):
    # Procesar el DataFrame (renombrar columnas, etc.)
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
    return df.rename(columns=column_mapping)

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

@app.route('/get_raspberries')
@login_required
def get_raspberries():
    if session['role'] != 'admin':
        return jsonify({'error': 'Acceso no autorizado'}), 403
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT raspberry_id 
            FROM tension 
            WHERE raspberry_id IS NOT NULL 
            ORDER BY raspberry_id
        """)
        raspberries = [row[0] for row in cursor.fetchall()]
        return jsonify({'raspberries': raspberries})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)

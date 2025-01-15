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
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        format_type = request.args.get('format', 'html')
        after_timestamp = request.args.get('after_timestamp')
        limit = request.args.get('limit')

        # Base query según el rol del usuario
        if session['role'] == 'admin':
            if 'selected_raspberry' in session:
                # Siempre filtrar por la raspberry seleccionada para admins
                base_query = 'SELECT * FROM public.tension WHERE raspberry_id = %s'
                params = [int(session['selected_raspberry'])]
            else:
                return jsonify({'error': 'No raspberry selected'}), 400
        else:
            base_query = """
                SELECT t.* FROM public.tension t
                JOIN user_raspberry ur ON t.raspberry_id = ur.raspberry_id
                WHERE ur.user_id = %s
            """
            params = [session['user_id']]

        # Agregar condiciones adicionales
        if after_timestamp:
            base_query += ' AND fecha > %s'
            params.append(after_timestamp)
        elif fecha_inicio and fecha_fin:
            base_query += ' AND fecha >= %s AND fecha <= %s'
            try:
                fecha_inicio = datetime.fromisoformat(fecha_inicio.replace('Z', '+00:00'))
                fecha_fin = datetime.fromisoformat(fecha_fin.replace('Z', '+00:00'))
                fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59, microsecond=999999)
                params.extend([fecha_inicio.strftime('%Y-%m-%d %H:%M:%S'),
                             fecha_fin.strftime('%Y-%m-%d %H:%M:%S')])
            except ValueError as e:
                print(f"Error parsing dates: {e}")
                return jsonify({'error': 'Invalid date format'}), 400

        # Ordenar por fecha
        if format_type == 'html':
            base_query += ' ORDER BY fecha DESC'
        else:
            base_query += ' ORDER BY fecha ASC'

        if not fecha_inicio and not fecha_fin:
            if limit:
                base_query += f' LIMIT {int(limit)}'
            elif after_timestamp:
                base_query += ' LIMIT 50'

        conn = get_db_connection()
        df = pd.read_sql_query(base_query, conn, params=params)
        conn.close()

        # Manejar valores nulos y formatear datos
        numeric_columns = ['perno_1', 'perno_2', 'perno_3', 'perno_4', 'perno_5']
        
        # Identificar columnas con todos los valores nulos o cero
        columnas_validas = []
        for col in numeric_columns:
            if df[col].notna().any() and (df[col] != 0).any():
                columnas_validas.append(col)
                df[col] = df[col].apply(lambda x: float(f"{x:.2f}") if pd.notna(x) else 0)

        # Renombrar las columnas antes de convertir a HTML
        if format_type == 'html':
            # Crear un diccionario para renombrar las columnas
            column_names = {
                'fecha': 'Fecha y Hora',
                'perno_1': 'Dato 1',
                'perno_2': 'Dato 2',
                'perno_3': 'Dato 3',
                'perno_4': 'Dato 4',
                'perno_5': 'Dato 5',
                'raspberry_id': 'ID Raspberry'
            }
            
            # Renombrar las columnas
            df = df.rename(columns=column_names)
            
            return df.to_html(classes='table table-striped', index=False)
        else:
            # Para formato JSON mantener los nombres originales
            data = {
                'fechas': df['fecha'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                'isAdmin': session['role'] == 'admin'
            }
            # Solo incluir columnas válidas en el JSON
            for col in columnas_validas:
                data[col] = df[col].tolist()
            if session['role'] == 'admin':
                data['raspberry_ids'] = df['raspberry_id'].tolist()
            return jsonify(data)

    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'error': str(e)}) if format_type == 'json' else f"<p>Error: {str(e)}</p>"


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

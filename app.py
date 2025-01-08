from flask import Flask, redirect, render_template, request, jsonify, session, url_for
import pandas as pd
import psycopg2
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # Mejor si viene de variables de entorno

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

        # Obtener el nombre de usuario para verificar si es "Raspi"
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id = %s", (session['user_id'],))
        username = cursor.fetchone()[0]
        cursor.close()

        # Base query según el rol del usuario
        if session['role'] == 'admin':
            if 'selected_raspberry' in session:
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
            base_query += ' AND fecha > %s' if 'WHERE' in base_query else ' WHERE fecha > %s'
            params.append(after_timestamp)
        elif fecha_inicio and fecha_fin:
            base_query += ' AND fecha BETWEEN %s AND %s' if 'WHERE' in base_query else ' WHERE fecha BETWEEN %s AND %s'
            try:
                # Convertir las fechas a UTC
                fecha_inicio = datetime.fromisoformat(fecha_inicio.replace('Z', '+00:00'))
                fecha_fin = datetime.fromisoformat(fecha_fin.replace('Z', '+00:00'))
                # Asegurar que la fecha final sea el último momento del día
                fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                params.extend([
                    fecha_inicio.strftime('%Y-%m-%d %H:%M:%S'),
                    fecha_fin.strftime('%Y-%m-%d %H:%M:%S')
                ])
            except ValueError as e:
                print(f"Error parsing dates: {e}")
                return jsonify({'error': 'Invalid date format'}), 400

        # Ordenar por fecha
        base_query += ' ORDER BY fecha'  # Cambiado de DESC a ASC para mantener el orden cronológico

        # Solo aplicar límites en tiempo real
        if not fecha_inicio and not fecha_fin:
            if limit:
                base_query += f' LIMIT {int(limit)}'
            elif after_timestamp:
                base_query += ' LIMIT 50'

        print(f"Query: {base_query}")  # Para debugging
        print(f"Params: {params}")     # Para debugging

        conn = get_db_connection()
        df = pd.read_sql_query(base_query, conn, params=params)
        conn.close()

        # Renombrar las columnas
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

        if username == 'Raspi':
            # Filtrar datos que son distintos de cero y no son NaN
            df = df[df['Dato 1'].notna() & (df['Dato 1'] != 0)]
            
            if format_type == 'json':
                data = {
                    'fechas': df['Fecha'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                    'medicion': df['Dato 1'].apply(lambda x: float(f"{x:.2f}")).tolist(),
                    'isRaspiUser': True
                }
                return jsonify(data)
            else:
                # Para la tabla, mostrar solo las columnas necesarias
                df = df[['Fecha', 'Dato 1']]  # Removido 'Numero' e 'ID'
                df.columns = ['Fecha', 'Medición']  # Renombrar columnas
                df['Medición'] = df['Dato 1'].apply(lambda x: float(f"{x:.2f}"))
                df = df.sort_values('Fecha', ascending=False)  # Ordenar por fecha más reciente
                return df.to_html(classes='table table-striped', index=False)
        else:
            if format_type == 'json':
                data = {
                    'fechas': df['Fecha'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                    'perno_1': df['Dato 1'].fillna("").apply(lambda x: float(f"{x:.2f}") if x != "" else "").tolist(),
                    'perno_2': df['Dato 2'].fillna("").apply(lambda x: float(f"{x:.2f}") if x != "" else "").tolist(),
                    'perno_3': df['Dato 3'].fillna("").apply(lambda x: float(f"{x:.2f}") if x != "" else "").tolist(),
                    'perno_4': df['Dato 4'].fillna("").apply(lambda x: float(f"{x:.2f}") if x != "" else "").tolist(),
                    'perno_5': df['Dato 5'].fillna("").apply(lambda x: float(f"{x:.2f}") if x != "" else "").tolist(),
                    'isRaspiUser': False
                }
                return jsonify(data)
            else:
                # Para la tabla, dejar los NaN como espacios vacíos
                numeric_columns = ['Dato 1', 'Dato 2', 'Dato 3', 'Dato 4', 'Dato 5']
                for col in numeric_columns:
                    df[col] = df[col].apply(lambda x: f"{float(x):.2f}" if pd.notna(x) and x != 0 else "")
                return df.to_html(classes='table table-striped', index=False)

    except Exception as e:
        print(f"Database error: {e}")
        return f"<p>Error: {str(e)}</p>"

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

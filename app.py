from flask import Flask, redirect, render_template, request, jsonify, session, url_for, flash
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

@app.route('/admin/create_user', methods=['GET', 'POST'])
@login_required
def create_user():
    # Verificar si el usuario es admin
    if not session.get('role') == 'admin':
        flash('No tienes permisos para acceder a esta página', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        raspberry_id = request.form.get('raspberry_id')

        # Validaciones básicas
        if not username or not password or not raspberry_id:
            flash('Todos los campos son requeridos', 'error')
            return render_template('create_user.html')

        # Verificar si el usuario ya existe
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    flash('El nombre de usuario ya existe', 'error')
                    return render_template('create_user.html')

                # Verificar si el raspberry_id existe y está disponible
                cursor.execute("SELECT id FROM user_raspberry WHERE raspberry_id = %s", (raspberry_id,))
                if cursor.fetchone():
                    flash('Este Raspberry Pi ya está asignado a otro usuario', 'error')
                    return render_template('create_user.html')

                # Crear usuario
                hashed_password = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (username, password, role_id) VALUES (%s, %s, %s) RETURNING id",
                    (username, hashed_password, 2)
                )
                user_id = cursor.fetchone()[0]

                # Asignar Raspberry
                cursor.execute(
                    "INSERT INTO user_raspberry (user_id, raspberry_id) VALUES (%s, %s)",
                    (user_id, raspberry_id)
                )
                conn.commit()
                flash('Usuario creado exitosamente', 'success')
                return redirect(url_for('admin_dashboard'))

        except Exception as e:
            conn.rollback()
            flash(f'Error al crear el usuario: {str(e)}', 'error')
            return render_template('create_user.html')
        finally:
            conn.close()

    return render_template('create_user.html')

if __name__ == '__main__':
    app.run(debug=True)

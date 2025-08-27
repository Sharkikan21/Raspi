from flask import Flask, redirect, render_template, request, jsonify, session, url_for, send_file
from flask_caching import Cache
import pandas as pd
import psycopg2
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import io

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'
app.static_folder = 'static'

# Configuración del caché
cache = Cache(app, config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
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

@app.route('/editar_pernos')
@login_required
def editar_pernos():
    if session['role'] != 'admin':
        return redirect(url_for('dashboard'))
    raspberry_id = request.args.get('raspberry_id')
    if not raspberry_id:
        return redirect(url_for('dashboard'))
    return render_template('perno_editor.html', raspberry_id=raspberry_id)

@app.route('/data')
@login_required
def get_db_data():
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        format_type = request.args.get('format', 'html')
        after_timestamp = request.args.get('after_timestamp')
        limit = request.args.get('limit')

        # Primero obtenemos los nombres de los pernos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if session['role'] == 'admin':
            if 'selected_raspberry' in session:
                cursor.execute("""
                    SELECT numero, nombre 
                    FROM perno 
                    WHERE raspberry_id = %s
                """, (int(session['selected_raspberry']),))
            else:
                return jsonify({'error': 'No raspberry selected'}), 400
        else:
            cursor.execute("""
                SELECT DISTINCT p.numero, p.nombre 
                FROM perno p
                JOIN user_raspberry ur ON p.raspberry_id = ur.raspberry_id
                WHERE ur.user_id = %s
            """, (session['user_id'],))
        
        perno_names = {str(row[0]): row[1] for row in cursor.fetchall()}
        cursor.close()

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

        if after_timestamp:
            base_query += ' AND fecha > %s'
            params.append(after_timestamp)
        elif fecha_inicio and fecha_fin:
            base_query += ' AND fecha >= %s AND fecha <= %s'
            try:
                fecha_inicio = datetime.fromisoformat(fecha_inicio.replace('Z', '+00:00'))
                fecha_fin = datetime.fromisoformat(fecha_fin.replace('Z', '+00:00'))
                fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59, microsecond=999999)
                params.extend([fecha_inicio.strftime('%Y-%m-%d %H:%M:%S'), fecha_fin.strftime('%Y-%m-%d %H:%M:%S')])
            except ValueError as e:
                return jsonify({'error': 'Invalid date format'}), 400

        if format_type == 'html':
            base_query += ' ORDER BY fecha DESC'
        else:
            base_query += ' ORDER BY fecha ASC'

        if not fecha_inicio and not fecha_fin:
            if limit:
                base_query += f' LIMIT {int(limit)}'
            elif after_timestamp:
                base_query += ' LIMIT 50'

        df = pd.read_sql_query(base_query, conn, params=params)
        conn.close()

        # Detectar columnas válidas de pernos
        numeric_columns = [f'perno_{i}' for i in range(1, 51)]
        columnas_validas = []
        for col in numeric_columns:
            if col in df.columns and df[col].notna().any() and (df[col] != 0).any():
                if col == 'perno_5':
                    continue  # Omitir perno_5 completamente
   
                columnas_validas.append(col)
                df[col] = df[col].apply(lambda x: float(f"{x:.2f}") if pd.notna(x) else 0)

        # Multiplicar valores de pernos por 1.35 solo si raspberry_id es 4
        if 'raspberry_id' in df.columns:
            mask = df['raspberry_id'] == 3
            for col in columnas_validas:
                df.loc[mask, col] = df.loc[mask, col] * 1.32

        if 'raspberry_id' in df.columns:
            mask = df['raspberry_id'] == 4
            for col in columnas_validas:
                df.loc[mask, col] = df.loc[mask, col] * 1.2

        if 'raspberry_id' in df.columns:
            mask = df['raspberry_id'] == 7
            for col in columnas_validas:
                df.loc[mask, col] = df.loc[mask, col] * 1.2

        if format_type == 'html':
            # Crear diccionario de nombres de columnas usando los nombres de pernos
            column_names = {'fecha': 'Fecha y Hora', 'raspberry_id': 'Molino'}
            column_names.update({
                col: perno_names.get(col.split('_')[1], f'Perno {col.split("_")[1]}') 
                for col in columnas_validas
            })
            
            # Ordenar columnas: fecha, pernos válidos, raspberry_id
            column_order = ['fecha'] + columnas_validas + ['raspberry_id']
            df = df[column_order]
            df = df.rename(columns=column_names)
            return df.to_html(classes='table table-striped', index=False)
        else:
            data = {
                'fechas': df['fecha'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                'isAdmin': session['role'] == 'admin',
                'perno_names': perno_names  # Incluimos los nombres de los pernos en la respuesta JSON
            }
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

@app.route('/pernos/<int:raspberry_id>', methods=['GET'])
@login_required
def get_pernos(raspberry_id):
    if session['role'] != 'admin':
        return jsonify({'error': 'Acceso no autorizado'}), 403
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT numero, nombre 
            FROM perno 
            WHERE raspberry_id = %s 
            ORDER BY numero
        """, (raspberry_id,))
        pernos = [{'numero': row[0], 'nombre': row[1]} for row in cursor.fetchall()]
        return jsonify({'pernos': pernos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/pernos/<int:raspberry_id>', methods=['PATCH'])
@login_required
def update_perno(raspberry_id):
    if session['role'] != 'admin':
        return jsonify({'error': 'Acceso no autorizado'}), 403
        
    try:
        data = request.get_json()
        perno_numero = data.get('numero')
        nuevo_nombre = data.get('nombre')
        
        if not perno_numero or not nuevo_nombre:
            return jsonify({'error': 'Faltan datos requeridos'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar si el perno existe
        cursor.execute("""
            SELECT id FROM perno 
            WHERE raspberry_id = %s AND numero = %s
        """, (raspberry_id, perno_numero))
        
        perno = cursor.fetchone()
        
        if perno:
            # Actualizar perno existente
            cursor.execute("""
                UPDATE perno 
                SET nombre = %s 
                WHERE raspberry_id = %s AND numero = %s
            """, (nuevo_nombre, raspberry_id, perno_numero))
        else:
            # Insertar nuevo perno
            cursor.execute("""
                INSERT INTO perno (numero, nombre, raspberry_id)
                VALUES (%s, %s, %s)
            """, (perno_numero, nuevo_nombre, raspberry_id))
            
        conn.commit()
        return jsonify({'message': 'Perno actualizado correctamente'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/export_excel')
@login_required
def export_excel():
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
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

        if fecha_inicio and fecha_fin:
            base_query += ' AND fecha >= %s AND fecha <= %s'
            try:
                fecha_inicio = datetime.fromisoformat(fecha_inicio.replace('Z', '+00:00'))
                fecha_fin = datetime.fromisoformat(fecha_fin.replace('Z', '+00:00'))
                fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59, microsecond=999999)
                params.extend([fecha_inicio.strftime('%Y-%m-%d %H:%M:%S'),
                               fecha_fin.strftime('%Y-%m-%d %H:%M:%S')])
            except ValueError as e:
                return jsonify({'error': 'Invalid date format'}), 400

        base_query += ' ORDER BY fecha DESC'

        conn = get_db_connection()
        df = pd.read_sql_query(base_query, conn, params=params)
        conn.close()

        # Detectar columnas válidas de pernos
        numeric_columns = [f'perno_{i}' for i in range(1, 51)]
        columnas_validas = []
        for col in numeric_columns:
            if col in df.columns and df[col].notna().any() and (df[col] != 0).any():
                if col == 'perno_5':
                    continue  # Omitir perno_5 completamente
                columnas_validas.append(col)
                df[col] = df[col].apply(lambda x: float(f"{x:.2f}") if pd.notna(x) else 0)

        # Renombrar columnas
        rename_columns = {'fecha': 'Fecha y Hora', 'raspberry_id': 'Molino'}
        rename_columns.update({col: f'Perno {col.split("_")[1]}' for col in columnas_validas})

        # Reordenar columnas para Excel
        columns_order = ['Fecha y Hora'] + sorted([col for col in rename_columns.keys() if col.startswith('perno_')], 
                                                key=lambda x: int(x.split('_')[1])) + ['Molino']

        df = df[['fecha'] + columnas_validas + ['raspberry_id']]
        df = df.rename(columns=rename_columns)

        # Exportar a Excel en memoria
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Datos', index=False)

        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='datos_tension.xlsx'
        )

    except Exception as e:
        print(f"Export error: {e}")
        return jsonify({'error': str(e)}), 500



if __name__ == '__main__':
    app.run(debug=True)



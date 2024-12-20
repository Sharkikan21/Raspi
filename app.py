from flask import Flask, render_template, request, redirect, url_for
import os
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

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
        conn = get_db_connection()
        # Using pandas to create HTML table
        df = pd.read_sql_query('SELECT * FROM public.tension ORDER BY fecha DESC', conn)
        conn.close()
        return df.to_html(classes='table table-striped', index=False)
    except Exception as e:
        print(f"Database error: {e}")
        return "<p>Error connecting to database.</p>"

if __name__ == '__main__':
    app.run(debug=True)

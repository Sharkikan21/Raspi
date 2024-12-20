from flask import Flask, render_template, jsonify, request
import pandas as pd
from datetime import datetime
import csv

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_data')
def get_data():
    try:
        with open('datos_tension_generados.csv', 'r') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)  # Saltar la cabecera
            data = list(csv_reader)
            if data:
                last_row = data[-1]
                return jsonify({
                    'current_value': float(last_row[1]),
                    'timestamp': last_row[0]
                })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/get_historical_data')
def get_historical_data():
    try:
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        
        # Leer el CSV completo
        df = pd.read_csv('datos_tension_generados.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filtrar por rango de fechas
        mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
        filtered_df = df.loc[mask]
        
        return jsonify({
            'timestamps': filtered_df['timestamp'].tolist(),
            'values': filtered_df['value'].tolist()
        })
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)

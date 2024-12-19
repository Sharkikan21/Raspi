from flask import Flask, render_template, request, redirect, url_for
import os
import pandas as pd

# Flask basic setup
app = Flask(__name__)



# Route to display CSV contents
@app.route('/')
def index():
    csv_path = os.path.join('valores_aleatorios.csv')
    data = None
    print(csv_path)
    if os.path.exists(csv_path):
        data = pd.read_csv(csv_path).to_html(classes='table table-striped', index=False)
    return render_template('index.html', table=data)

@app.route('/data')
def get_csv_data():
    csv_path = os.path.join('valores_aleatorios.csv')
    print(csv_path)
    if os.path.exists(csv_path):
        data = pd.read_csv(csv_path).to_html(classes='table table-striped', index=False)
        return data
    return "<p>No CSV file found.</p>"

if __name__ == '__main__':
    app.run(debug=True)

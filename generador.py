import csv
import datetime
import time
import random

def generar_valor_aleatorio():
    """Genera un valor aleatorio entre 100 y 200."""
    return random.randint(100, 200)

def guardar_en_csv(archivo, fecha, valor):
    """Guarda la fecha y el valor generado en un archivo CSV con separador de punto y coma."""
    with open(archivo, mode='a', newline='') as file:
        escritor = csv.writer(file, delimiter=';')  # Punto y coma como delimitador
        escritor.writerow([fecha, valor])

def main():
    """Función principal que registra valores aleatorios en un archivo CSV."""
    archivo_csv = 'valores_aleatorios.csv'

    # Crear archivo CSV si no existe con encabezado
    with open(archivo_csv, mode='w', newline='') as file:
        escritor = csv.writer(file, delimiter=';')
        escritor.writerow(['Hora', 'Valor Generado'])

    print("Iniciando generación de valores aleatorios... (Ctrl+C para detener)")

    try:
        while True:
            valor = generar_valor_aleatorio()
            hora = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            print(f"{hora} - Valor generado: {valor}")
            guardar_en_csv(archivo_csv, hora, valor)

            time.sleep(3)  # Intervalo de 3 segundos
    except KeyboardInterrupt:
        print("\nGeneración detenida. Datos guardados en 'valores_aleatorios.csv'.")

if __name__ == "__main__":
    main()

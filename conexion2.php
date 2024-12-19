<?php
ini_set('display_errors', 1);
error_reporting(E_ALL);
// Parámetros de conexión
$host = 'localhost';  // El servidor de la base de datos, suele ser 'localhost' si está en el mismo servidor.
$port = '3306';       // El puerto de MySQL (el predeterminado es 3306).
$dbname = 'cavaelec_raspi_prueba'; // El nombre de tu base de datos.
$user = 'cavaelec_raspi_coso'; // Tu usuario de la base de datos.
$password = 'XanBsp9zk3BBNNE'; // Tu contraseña de la base de datos.

// Conectar a la base de datos MySQL
$conn = new mysqli($host, $user, $password, $dbname, $port);

// Verificar la conexión
if ($conn->connect_error) {
    die("Error de conexión a la base de datos: " . $conn->connect_error);
}

// Si la conexión es exitosa, puedes realizar consultas SQL
$query = "SELECT * FROM datos_aleatorios";
$result = $conn->query($query);

if ($result->num_rows > 0) {
    // Imprimir los resultados de la consulta
    while ($row = $result->fetch_assoc()) {
        echo "Columna1: " . $row['horas'] . " - Columna2: " . $row['valor_generado'] . "<br>";
    }
} else {
    echo "No se encontraron resultados.";
}

// Cerrar la conexión
$conn->close();
?>
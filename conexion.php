<?php
error_reporting(E_ALL);
ini_set('display_errors', 1);
// Parámetros de conexión
$host = '186.64.116.20';  // El servidor de la base de datos, suele ser 'localhost' si está en el mismo servidor.
$port = '5432';       // El puerto de PostgreSQL (el predeterminado es 5432).
$dbname = 'cavaelec_raspi'; // El nombre de tu base de datos.
$user = 'cavaelec_raspi_test'; // Tu usuario de la base de datos.
$password = 'XanBsp9zk3BBNNE'; // Tu contraseña de la base de datos.

// Conectar a la base de datos
$conn = pg_connect("host=$host port=$port dbname=$dbname user=$user password=$password");

if (!$conn) {
    echo "Error de conexión a la base de datos: " . pg_last_error();
    exit;
}
// Si la conexión es exitosa, puedes realizar consultas SQL
$query = "SELECT * FROM datos_aleatorios";
$result = pg_query($conn, $query);

if ($result) {
    // Imprimir los resultados de la consulta
    while ($row = pg_fetch_assoc($result)) {
        echo "Columna1: " . $row['horas'] . " - Columna2: " . $row['valor_generado'] . "<br>";
    }
} else {
    echo "Error en la consulta.";
}

// Cerrar la conexión
pg_close($conn);
?>


hola
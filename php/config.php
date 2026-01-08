<?php
/**
 * PHP Configuration
 * Database and external service connections
 */

// Get environment variables (from docker-compose)
$db_host = getenv('POSTGRES_HOST') ?: 'localhost';
$db_port = getenv('POSTGRES_PORT') ?: '5432';
$db_user = getenv('POSTGRES_USER') ?: 'challenge_user';
$db_password = getenv('POSTGRES_PASSWORD') ?: 'secure_password';
$db_name = getenv('POSTGRES_DB') ?: 'challenge2';

// Database DSN
define('DB_DSN', "pgsql:host=$db_host;port=$db_port;dbname=$db_name");
define('DB_USER', $db_user);
define('DB_PASSWORD', $db_password);

// Qdrant configuration
define('QDRANT_HOST', getenv('QDRANT_HOST') ?: 'localhost');
define('QDRANT_PORT', getenv('QDRANT_PORT') ?: '6333');
define('QDRANT_URL', 'http://' . QDRANT_HOST . ':' . QDRANT_PORT);
define('QDRANT_COLLECTION_NAME', getenv('QDRANT_COLLECTION_NAME') ?: 'policy_chunks');

// Ollama configuration
define('OLLAMA_HOST', getenv('OLLAMA_HOST') ?: 'http://localhost:11434');
define('OLLAMA_MODEL', getenv('OLLAMA_MODEL') ?: 'mistral');

// Embedding configuration
define('EMBEDDING_MODEL', getenv('EMBEDDING_MODEL') ?: 'nomic-embed-text');

// Application settings
define('APP_ENV', getenv('APP_ENV') ?: 'development');
define('TOP_K_CHUNKS', 5);
define('CONFIDENCE_THRESHOLD', 0.60);

// Database connection with error handling
try {
    $pdo = new PDO(
        DB_DSN,
        DB_USER,
        DB_PASSWORD,
        array(
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        )
    );
} catch (PDOException $e) {
    http_response_code(500);
    die(json_encode(['error' => 'Database connection failed: ' . $e->getMessage()]));
}

// CORS headers
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
header('Content-Type: application/json; charset=utf-8');

// Handle OPTIONS requests
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

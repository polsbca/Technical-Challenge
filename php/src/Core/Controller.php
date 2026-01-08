<?php

namespace App\Core;

use App\Core\Database;

class Controller
{
    protected \PDO $db;
    
    public function __construct()
    {
        $this->db = Database::getConnection();
    }
    
    /**
     * Send a JSON response
     *
     * @param mixed $data
     * @param int $statusCode
     * @return void
     */
    protected function respond($data, int $statusCode = 200): void
    {
        http_response_code($statusCode);
        header('Content-Type: application/json');
        
        if (is_string($data)) {
            $data = ['message' => $data];
        }
        
        echo json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
        exit;
    }
    
    /**
     * Send an error response
     *
     * @param string $message
     * @param int $statusCode
     * @return never
     */
    protected function respondError(string $message, int $statusCode = 400): never
    {
        $this->respond(['error' => $message], $statusCode);
    }
    
    /**
     * Get JSON request data
     *
     * @return array
     */
    protected function getJsonData(): array
    {
        $json = file_get_contents('php://input');
        $data = json_decode($json, true);
        
        if (json_last_error() !== JSON_ERROR_NONE) {
            $this->respondError('Invalid JSON data', 400);
        }
        
        return $data;
    }
    
    /**
     * Get request method
     *
     * @return string
     */
    protected function getMethod(): string
    {
        return $_SERVER['REQUEST_METHOD'];
    }
    
    /**
     * Get request path
     *
     * @return string
     */
    protected function getPath(): string
    {
        return parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
    }
    
    /**
     * Get query parameters
     *
     * @return array
     */
    protected function getQueryParams(): array
    {
        return $_GET;
    }
}

<?php

namespace App\Core;

class Application
{
    public static string $ROOT_DIR;
    public static Application $app;
    
    public function __construct(string $rootPath)
    {
        self::$ROOT_DIR = $rootPath;
        self::$app = $this;
        
        $this->initialize();
    }
    
    private function initialize(): void
    {
        // Set error reporting based on environment
        if (getenv('APP_ENV') === 'development') {
            error_reporting(E_ALL);
            ini_set('display_errors', '1');
        } else {
            error_reporting(0);
            ini_set('display_errors', '0');
        }
        
        // Set timezone
        date_default_timezone_set(getenv('APP_TIMEZONE') ?: 'UTC');
    }
    
    public function run(): void
    {
        try {
            // Handle the request
            $this->handleRequest();
        } catch (\Exception $e) {
            $this->handleError($e);
        }
    }
    
    private function handleRequest(): void
    {
        // TODO: Implement routing and request handling
        $this->sendResponse('Welcome to Policy Chat API');
    }
    
    private function handleError(\Throwable $e): void
    {
        $statusCode = $e->getCode() ?: 500;
        $message = $e->getMessage();
        
        if (!in_array($statusCode, [400, 401, 403, 404, 422, 500])) {
            $statusCode = 500;
        }
        
        $this->sendResponse([
            'error' => $message,
            'code' => $statusCode
        ], $statusCode);
    }
    
    private function sendResponse($data, int $statusCode = 200): void
    {
        http_response_code($statusCode);
        header('Content-Type: application/json');
        
        if (is_string($data)) {
            $data = ['message' => $data];
        }
        
        echo json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
        exit;
    }
}

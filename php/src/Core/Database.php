<?php

namespace App\Core;

use PDO;
use PDOException;

class Database
{
    private static ?PDO $pdo = null;
    
    public static function getConnection(): PDO
    {
        if (self::$pdo === null) {
            $dsn = sprintf(
                '%s:host=%s;port=%s;dbname=%s',
                getenv('DB_CONNECTION'),
                getenv('DB_HOST'),
                getenv('DB_PORT'),
                getenv('DB_DATABASE')
            );
            
            $options = [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES => false,
            ];
            
            try {
                self::$pdo = new PDO(
                    $dsn,
                    getenv('DB_USERNAME'),
                    getenv('DB_PASSWORD'),
                    $options
                );
            } catch (PDOException $e) {
                throw new \RuntimeException('Database connection failed: ' . $e->getMessage());
            }
        }
        
        return self::$pdo;
    }
    
    public static function disconnect(): void
    {
        self::$pdo = null;
    }
}

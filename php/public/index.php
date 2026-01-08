<?php
/**
 * Front controller for the application
 */

declare(strict_types=1);

require_once __DIR__ . '/../vendor/autoload.php';

use App\Core\Application;

// Load environment variables
$dotenv = Dotenv\Dotenv::createImmutable(dirname(__DIR__));
$dotenv->load();

// Create application instance and run
$app = new Application(dirname(__DIR__));
$app->run();

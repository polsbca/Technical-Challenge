<?php
/**
 * PHP API Endpoints for Chat and Company Data
 */

require_once 'config.php';

// Route requests
$request_uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$request_method = $_SERVER['REQUEST_METHOD'];

// If using rewrite, REQUEST_URI might be /api.php and the original path may be in query param 'route'
if (isset($_GET['route']) && is_string($_GET['route']) && $_GET['route'] !== '') {
    $request_uri = '/' . ltrim($_GET['route'], '/');
}

if (strpos($request_uri, '/api/chat') === 0 && $request_method === 'GET') {
    handleChat();
} elseif (strpos($request_uri, '/api/companies') === 0 && $request_method === 'GET') {
    handleGetCompanies();
} elseif (strpos($request_uri, '/api/company/') === 0 && $request_method === 'GET') {
    $domain = basename($request_uri);
    handleGetCompany($domain);
} else {
    http_response_code(404);
    echo json_encode(['error' => 'Endpoint not found']);
}

/**
 * Handle chat requests
 */
function handleChat() {
    global $pdo;
    
    if (!isset($_GET['q'])) {
        http_response_code(400);
        echo json_encode(['error' => 'Missing query parameter: q']);
        return;
    }

    $question = $_GET['q'];
    $domain = $_GET['domain'] ?? 'all';

    try {
        // Query Qdrant for relevant chunks
        $chunks = queryQdrant($question, $domain);

        if (empty($chunks)) {
            echo json_encode([
                'question' => $question,
                'answer' => 'No policy chunks are indexed in the vector database yet, so I cannot answer from policy text.',
                'sources' => [],
                'confidence' => 0.0,
            ]);
            return;
        }

        // Send to LLM for answer generation
        $answer = queryLLM($question, $chunks);

        // Extract sources
        $sources = array_map(function($chunk) {
            return [
                'url' => $chunk['url'] ?? null,
                'doc_type' => $chunk['doc_type'] ?? null,
                'relevance_score' => $chunk['score'] ?? 0.0,
                'excerpt' => $chunk['excerpt'] ?? null,
            ];
        }, array_slice($chunks, 0, 3));

        echo json_encode([
            'question' => $question,
            'answer' => $answer,
            'sources' => $sources,
            'confidence' => calculateConfidence($chunks),
        ]);
    } catch (Exception $e) {
        http_response_code(500);
        echo json_encode(['error' => $e->getMessage()]);
    }
}

/**
 * Query Qdrant for relevant policy chunks
 */
function queryQdrant($question, $domain = 'all') {
    global $pdo;

    $qdrant_url = QDRANT_URL;
    $collection = QDRANT_COLLECTION_NAME;

    $embedding = getOllamaEmbedding($question);
    if ($embedding === null) {
        throw new Exception('Failed to generate embedding for query');
    }

    ensureQdrantCollection($qdrant_url, $collection, count($embedding));

    $needDomainFilter = (!empty($domain) && $domain !== 'all');
    $payloadFields = ['text', 'chunk_index', 'token_count', 'policy_id', 'metadata', 'domain', 'doc_type', 'url', 'company_id'];

    $body = [
        'vector' => $embedding,
        'limit' => $needDomainFilter ? (TOP_K_CHUNKS * 5) : TOP_K_CHUNKS,
        'with_payload' => $payloadFields,
    ];

    if ($needDomainFilter) {
        $body['filter'] = [
            'must' => [
                [
                    'key' => 'domain',
                    'match' => ['value' => $domain],
                ],
            ],
        ];
    }

    $resp = httpJson('POST', $qdrant_url . '/collections/' . rawurlencode($collection) . '/points/search', $body);
    if (!isset($resp['result']) || !is_array($resp['result'])) {
        return [];
    }

    // Backward-compatible fallback: older vectors may not have domain payload set
    $allowedPolicyIds = null;
    if ($needDomainFilter && empty($resp['result'])) {
        $companyStmt = $pdo->prepare('SELECT id FROM companies WHERE domain = :domain');
        $companyStmt->execute(['domain' => $domain]);
        $companyRow = $companyStmt->fetch();
        if (!$companyRow) {
            return [];
        }

        $polStmt = $pdo->prepare('SELECT id FROM policy_discovery WHERE company_id = :company_id');
        $polStmt->execute(['company_id' => $companyRow['id']]);
        $rows = $polStmt->fetchAll();
        $allowedPolicyIds = array_map(function($r) { return (int)$r['id']; }, $rows);
        if (empty($allowedPolicyIds)) {
            return [];
        }
    }

    $chunks = [];
    $policyCache = [];
    foreach ($resp['result'] as $item) {
        $payload = $item['payload'] ?? [];
        $rawText = $payload['text'] ?? '';
        $metadata = $payload['metadata'] ?? null;
        $policyId = isset($payload['policy_id']) ? (int)$payload['policy_id'] : null;

        if (is_string($metadata)) {
            $decoded = json_decode($metadata, true);
            if (is_array($decoded)) {
                $metadata = $decoded;
            }
        }
        if (!is_array($metadata)) {
            $metadata = [];
        }

        $url = $payload['url'] ?? ($metadata['source_url'] ?? ($metadata['url'] ?? null));
        $docType = $payload['doc_type'] ?? ($metadata['doc_type'] ?? null);
        $itemDomain = $payload['domain'] ?? ($metadata['domain'] ?? null);

        if ($policyId !== null) {
            if (!isset($policyCache[$policyId])) {
                $stmt = $pdo->prepare('SELECT doc_type, url, company_id FROM policy_discovery WHERE id = :id');
                $stmt->execute(['id' => $policyId]);
                $policyCache[$policyId] = $stmt->fetch() ?: false;
            }
            $p = $policyCache[$policyId];
            if (is_array($p)) {
                if ($docType === null && isset($p['doc_type'])) {
                    $docType = $p['doc_type'];
                }
                if ($url === null && isset($p['url'])) {
                    $url = $p['url'];
                }
            }
        }

        if ($allowedPolicyIds !== null && $policyId !== null) {
            if (!in_array($policyId, $allowedPolicyIds, true)) {
                continue;
            }
        }

        $chunks[] = [
            'id' => $item['id'] ?? null,
            'text' => $rawText,
            'excerpt' => mb_substr($rawText, 0, 280),
            'url' => $url,
            'doc_type' => $docType,
            'domain' => $itemDomain,
            'score' => $item['score'] ?? 0.0,
        ];
    }

    if ($needDomainFilter && count($chunks) > TOP_K_CHUNKS) {
        $chunks = array_slice($chunks, 0, TOP_K_CHUNKS);
    }

    return $chunks;
}

function ensureQdrantCollection($qdrantUrl, $collection, $vectorSize) {
    $url = $qdrantUrl . '/collections/' . rawurlencode($collection);

    $ch = curl_init($url);
    if ($ch === false) {
        throw new Exception('Failed to initialize HTTP client');
    }

    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'GET');
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Accept: application/json']);
    curl_setopt($ch, CURLOPT_TIMEOUT, 10);

    $raw = curl_exec($ch);
    if ($raw === false) {
        $err = curl_error($ch);
        curl_close($ch);
        throw new Exception('HTTP request failed: ' . $err);
    }
    $status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($status === 200) {
        $decoded = json_decode($raw, true);
        if (is_array($decoded)) {
            $existingSize = $decoded['result']['config']['params']['vectors']['size'] ?? null;
            $pointsCount = $decoded['result']['points_count'] ?? null;
            if (is_int($existingSize) && $existingSize !== $vectorSize) {
                if ($pointsCount === 0) {
                    httpJson('DELETE', $url, null);

                    httpJson('PUT', $url, [
                        'vectors' => [
                            'size' => $vectorSize,
                            'distance' => 'Cosine',
                        ],
                    ]);
                    return;
                } else {
                    throw new Exception(
                        'Qdrant collection vector size mismatch: existing=' . $existingSize . ', expected=' . $vectorSize
                    );
                }
            } else {
                return;
            }
        } else {
            return;
        }
    }

    if ($status !== 404) {
        throw new Exception('Unexpected response from Qdrant when checking collection: HTTP ' . $status);
    }

    // Create collection when missing (or after deleting due to mismatch)
    httpJson('PUT', $url, [
        'vectors' => [
            'size' => $vectorSize,
            'distance' => 'Cosine',
        ],
    ]);
}

/**
 * Query Ollama/OpenAI for chat response
 */
function queryLLM($question, $chunks) {
    $context = "You are a policy analyst. Answer the user's question using ONLY the provided policy excerpts. " .
        "If the excerpts are insufficient, say you don't have enough information. " .
        "Cite sources by their index like [1], [2].\n\n";

    $maxChunks = min(count($chunks), TOP_K_CHUNKS);
    for ($i = 0; $i < $maxChunks; $i++) {
        $chunk = $chunks[$i];
        $n = $i + 1;
        $docType = $chunk['doc_type'] ?? 'unknown';
        $url = $chunk['url'] ?? '';
        $text = $chunk['excerpt'] ?? ($chunk['text'] ?? '');
        if (is_string($text)) {
            $text = mb_substr($text, 0, 800);
        }
        $context .= "[{$n}] ({$docType}) {$url}\n";
        $context .= $text . "\n\n";
    }

    $messages = [
        ['role' => 'system', 'content' => 'You are a helpful assistant.'],
        ['role' => 'user', 'content' => $context . "User question: " . $question],
    ];

    $resp = httpJson('POST', rtrim(OLLAMA_HOST, '/') . '/api/chat', [
        'model' => OLLAMA_MODEL,
        'messages' => $messages,
        'stream' => false,
        'options' => [
            'temperature' => 0.2,
            'num_predict' => 256,
        ],
    ], 120);

    $content = $resp['message']['content'] ?? null;
    if (!is_string($content) || $content === '') {
        throw new Exception('LLM returned empty response');
    }

    return $content;
}

function getOllamaEmbedding($text) {
    $resp = httpJson('POST', rtrim(OLLAMA_HOST, '/') . '/api/embeddings', [
        'model' => EMBEDDING_MODEL,
        'prompt' => $text,
    ], 30);

    $embedding = $resp['embedding'] ?? null;
    if (!is_array($embedding) || empty($embedding)) {
        return null;
    }
    return $embedding;
}

function httpJson($method, $url, $body, $timeoutSeconds = 60) {
    $ch = curl_init($url);
    if ($ch === false) {
        throw new Exception('Failed to initialize HTTP client');
    }

    $headers = [
        'Content-Type: application/json',
        'Accept: application/json',
    ];

    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, strtoupper($method));
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 10);
    if ($body !== null) {
        $payload = json_encode($body);
        if ($payload === false) {
            throw new Exception('Failed to encode JSON body');
        }
        curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
    }
    curl_setopt($ch, CURLOPT_TIMEOUT, $timeoutSeconds);

    $raw = curl_exec($ch);
    if ($raw === false) {
        $err = curl_error($ch);
        curl_close($ch);
        throw new Exception('HTTP request failed: ' . $err);
    }

    $status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    $decoded = json_decode($raw, true);
    if (!is_array($decoded)) {
        throw new Exception('Invalid JSON response from ' . $url . ' (status ' . $status . ')');
    }

    if ($status < 200 || $status >= 300) {
        $msg = $decoded['error'] ?? ('HTTP error ' . $status);
        throw new Exception('Upstream error from ' . $url . ': ' . $msg);
    }

    return $decoded;
}

/**
 * Get all companies
 */
function handleGetCompanies() {
    global $pdo;

    try {
        $query = "SELECT id, name, domain, country FROM companies ORDER BY name";
        $stmt = $pdo->query($query);
        $companies = $stmt->fetchAll();

        echo json_encode($companies);
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => $e->getMessage()]);
    }
}

/**
 * Get specific company and its scopes
 */
function handleGetCompany($domain) {
    global $pdo;

    try {
        // Get company
        $query = "SELECT * FROM companies WHERE domain = :domain";
        $stmt = $pdo->prepare($query);
        $stmt->execute(['domain' => $domain]);
        $company = $stmt->fetch();

        if (!$company) {
            http_response_code(404);
            echo json_encode(['error' => 'Company not found']);
            return;
        }

        // Get scopes for this company
        $query = "
            SELECT s.name, cs.applies, cs.confidence, cs.reasoning
            FROM company_scopes cs
            JOIN scopes s ON cs.scope_id = s.id
            WHERE cs.company_id = :company_id
            ORDER BY s.name
        ";
        $stmt = $pdo->prepare($query);
        $stmt->execute(['company_id' => $company['id']]);
        $scopes = $stmt->fetchAll();

        $company['scopes'] = $scopes;

        echo json_encode($company);
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => $e->getMessage()]);
    }
}

/**
 * Calculate overall confidence score
 */
function calculateConfidence($chunks) {
    if (empty($chunks)) return 0.0;

    $scores = array_map(function($chunk) {
        return $chunk['score'] ?? 0.5;
    }, $chunks);

    return array_sum($scores) / count($scores);
}

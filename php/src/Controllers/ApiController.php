<?php

namespace App\Controllers;

use App\Core\Controller;
use App\Services\QdrantService;
use App\Services\LLMService;

class ApiController extends Controller
{
    private QdrantService $qdrant;
    private LLMService $llm;
    
    public function __construct()
    {
        parent::__construct();
        $this->qdrant = new QdrantService();
        $this->llm = new LLMService();
    }
    
    /**
     * Handle chat messages
     * 
     * @param array $data
     * @return array
     */
    public function chat(array $data): array
    {
        // Validate input
        if (empty($data['message']) || empty($data['company_id'])) {
            $this->respondError('Missing required fields', 400);
        }
        
        try {
            // Get relevant context from Qdrant
            $context = $this->getRelevantContext($data['message'], (int)$data['company_id']);
            
            // Generate response using LLM
            $response = $this->llm->generateResponse(
                $data['message'],
                $context,
                $data['conversation_history'] ?? []
            );
            
            return [
                'response' => $response['answer'],
                'sources' => $response['sources'] ?? [],
                'confidence' => $response['confidence'] ?? 1.0
            ];
            
        } catch (\Exception $e) {
            $this->respondError($e->getMessage(), 500);
        }
    }
    
    /**
     * Get relevant context for a query
     * 
     * @param string $query
     * @param int $companyId
     * @return array
     * @throws \Exception
     */
    private function getRelevantContext(string $query, int $companyId): array
    {
        // Get embedding for the query
        $embedding = $this->llm->getEmbedding($query);
        
        // Search for similar vectors in Qdrant
        $results = $this->qdrant->searchSimilar(
            $embedding,
            (int)getenv('TOP_K_CHUNKS') ?: 5
        );
        
        $context = [];
        foreach ($results['result'] ?? [] as $item) {
            // Filter by company ID if available in payload
            $payload = $item['payload'] ?? [];
            if (isset($payload['company_id']) && $payload['company_id'] != $companyId) {
                continue;
            }
            
            $context[] = [
                'text' => $payload['text'] ?? '',
                'source' => $payload['source_url'] ?? 'Unknown',
                'score' => $item['score'] ?? 0,
            ];
        }
        
        return $context;
    }
    
    /**
     * Get list of companies
     * 
     * @return array
     */
    public function getCompanies(): array
    {
        try {
            $stmt = $this->db->query("SELECT id, name, domain FROM companies ORDER BY name");
            return $stmt->fetchAll(\PDO::FETCH_ASSOC);
        } catch (\PDOException $e) {
            $this->respondError('Failed to fetch companies', 500);
        }
    }
}

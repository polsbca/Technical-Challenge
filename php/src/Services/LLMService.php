<?php

namespace App\Services;

use GuzzleHttp\Client;
use GuzzleHttp\Exception\GuzzleException;

class LLMService
{
    private Client $client;
    private string $model;
    private string $apiBase;
    
    public function __construct()
    {
        $this->model = getenv('OLLAMA_MODEL') ?: 'mistral';
        $this->apiBase = rtrim(getenv('OLLAMA_HOST'), '/');
        
        $this->client = new Client([
            'base_uri' => $this->apiBase . '/api/',
            'headers' => [
                'Content-Type' => 'application/json',
            ],
            'timeout' => 60,
        ]);
    }
    
    /**
     * Generate a response to a user query
     * 
     * @param string $query
     * @param array $context
     * @param array $history
     * @return array
     * @throws \Exception
     */
    public function generateResponse(string $query, array $context = [], array $history = []): array
    {
        $prompt = $this->buildPrompt($query, $context, $history);
        
        try {
            $response = $this->client->post('generate', [
                'json' => [
                    'model' => $this->model,
                    'prompt' => $prompt,
                    'stream' => false,
                    'options' => [
                        'temperature' => 0.3,
                        'top_p' => 0.9,
                    ]
                ]
            ]);
            
            $result = json_decode((string) $response->getBody(), true);
            
            return [
                'answer' => $result['response'] ?? 'I could not generate a response.',
                'sources' => $this->extractSources($context),
                'confidence' => $this->calculateConfidence($result['response'] ?? '', $context)
            ];
            
        } catch (GuzzleException $e) {
            throw new \Exception('Failed to generate response: ' . $e->getMessage());
        }
    }
    
    /**
     * Get embedding for a text
     * 
     * @param string $text
     * @return array
     * @throws \Exception
     */
    public function getEmbedding(string $text): array
    {
        try {
            $response = $this->client->post('embeddings', [
                'json' => [
                    'model' => $this->model,
                    'prompt' => $text,
                ]
            ]);
            
            $result = json_decode((string) $response->getBody(), true);
            return $result['embedding'] ?? [];
            
        } catch (GuzzleException $e) {
            throw new \Exception('Failed to get embedding: ' . $e->getMessage());
        }
    }
    
    /**
     * Build the prompt for the LLM
     * 
     * @param string $query
     * @param array $context
     * @param array $history
     * @return string
     */
    private function buildPrompt(string $query, array $context, array $history): string
    {
        $prompt = "You are a helpful assistant that answers questions about company policies. " .
                 "Use the following context to answer the question. If you don't know the answer, say so.\n\n";
        
        // Add conversation history if available
        if (!empty($history)) {
            $prompt .= "Previous conversation:\n";
            foreach ($history as $message) {
                $role = $message['role'] === 'user' ? 'User' : 'Assistant';
                $prompt .= "$role: {$message['content']}\n";
            }
            $prompt .= "\n";
        }
        
        // Add context
        if (!empty($context)) {
            $prompt .= "Relevant context:\n";
            foreach ($context as $item) {
                $prompt .= "- " . $item['text'] . "\n";
                if (isset($item['source'])) {
                    $prompt .= "  Source: " . $item['source'] . "\n";
                }
            }
            $prompt .= "\n";
        }
        
        // Add the current question
        $prompt .= "Question: $query\n\nAnswer:";
        
        return $prompt;
    }
    
    /**
     * Extract sources from context
     * 
     * @param array $context
     * @return array
     */
    private function extractSources(array $context): array
    {
        $sources = [];
        
        foreach ($context as $item) {
            if (!empty($item['source'])) {
                $source = $item['source'];
                if (!in_array($source, $sources)) {
                    $sources[] = $source;
                }
            }
        }
        
        return array_values(array_unique($sources));
    }
    
    /**
     * Calculate confidence score for the response
     * 
     * @param string $response
     * @param array $context
     * @return float
     */
    private function calculateConfidence(string $response, array $context): float
    {
        if (empty($context)) {
            return 0.3; // Low confidence if no context
        }
        
        // Simple confidence calculation based on response length and context relevance
        $responseLength = strlen($response);
        $avgContextScore = array_reduce($context, fn($carry, $item) => $carry + ($item['score'] ?? 0), 0) / max(1, count($context));
        
        // Base confidence on context score, adjusted by response length
        $confidence = min(1.0, $avgContextScore * (1 + min(1, $responseLength / 1000)));
        
        return round(max(0.3, min(1.0, $confidence)), 2);
    }
}

<?php

namespace App\Services;

use GuzzleHttp\Client;
use GuzzleHttp\Exception\GuzzleException;

class QdrantService
{
    private Client $client;
    private string $collectionName;
    
    public function __construct()
    {
        $this->client = new Client([
            'base_uri' => sprintf(
                'http://%s:%s/collections/%s/',
                getenv('QDRANT_HOST'),
                getenv('QDRANT_PORT'),
                getenv('QDRANT_COLLECTION')
            ),
            'headers' => [
                'Content-Type' => 'application/json',
            ],
            'timeout' => 10,
        ]);
        
        $this->collectionName = getenv('QDRANT_COLLECTION');
    }
    
    /**
     * Search for similar vectors in the collection
     *
     * @param array $vector
     * @param int $limit
     * @return array
     * @throws GuzzleException
     */
    public function searchSimilar(array $vector, int $limit = 5): array
    {
        $response = $this->client->post('points/search', [
            'json' => [
                'vector' => $vector,
                'limit' => $limit,
                'with_payload' => true,
                'with_vectors' => false,
            ],
        ]);
        
        return json_decode((string) $response->getBody(), true);
    }
    
    /**
     * Get a point by ID
     *
     * @param int $id
     * @return array|null
     * @throws GuzzleException
     */
    public function getPoint(int $id): ?array
    {
        $response = $this->client->get("points/$id");
        $data = json_decode((string) $response->getBody(), true);
        
        return $data['result'] ?? null;
    }
    
    /**
     * Check if the collection exists
     *
     * @return bool
     * @throws GuzzleException
     */
    public function collectionExists(): bool
    {
        try {
            $response = $this->client->get('');
            return $response->getStatusCode() === 200;
        } catch (\Exception $e) {
            return false;
        }
    }
}

# Design Tradeoffs and Limitations

## Design Decisions

### 1. Chunking Strategy
**Decision**: Fixed-size chunks (512 tokens)
**Tradeoff**: Simplicity vs. semantic coherence
**Impact**: Some contexts may be split across chunks

### 2. LLM Model
**Decision**: Mistral-7B via Ollama
**Tradeoff**: Performance vs. resource usage
**Impact**: Good balance of speed and quality

### 3. Vector Database
**Decision**: Qdrant
**Tradeoff**: Feature set vs. ecosystem familiarity
**Impact**: Excellent performance, smaller community

### 4. Discovery Methods
**Decision**: Prioritize sitemap > footer > heuristics
**Tradeoff**: Accuracy vs. coverage
**Impact**: Higher success rate for structured sites

## Limitations

### Technical
- No JavaScript rendering for dynamic content
- Rate limiting may block some sites
- English-only optimization

### Accuracy
- Confidence scores may need calibration
- Complex legal language can be ambiguous
- Policy changes not detected automatically

### Scalability
- LLM inference is CPU-intensive
- Vector storage grows linearly with content
- Database queries may need optimization

## Future Improvements

1. Add Playwright for JavaScript rendering
2. Implement policy change detection
3. Add multi-language support
4. Create confidence calibration dataset
5. Add caching for repeated queries

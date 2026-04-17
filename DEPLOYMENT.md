# Deployment Information

## Public URL
https://brilliant-vitality-production-3069.up.railway.app

## UI
https://brilliant-vitality-production-3069.up.railway.app/ui/

## Platform
Railway — Docker (multi-stage build)

## Test Commands

### Health Check
```bash
curl https://brilliant-vitality-production-3069.up.railway.app/health
# Expected: {"status": "ok", "version": "1.0.0", ...}
```

### Authentication required (no key)
```bash
curl -X POST https://brilliant-vitality-production-3069.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
# Expected: 401 Unauthorized
```

### API Test (with authentication)
```bash
curl -X POST https://brilliant-vitality-production-3069.up.railway.app/ask \
  -H "X-API-Key: YOUR_AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "What is GDP?"}'
# Expected: 200 with answer field
```

### Rate Limiting (trigger 429)
```bash
for i in {1..12}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://brilliant-vitality-production-3069.up.railway.app/ask \
    -H "X-API-Key: YOUR_AGENT_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "test", "question": "test"}';
done
# Expected: first 10 return 200, then 429
```

## Environment Variables Set
- `PORT` — Railway injects automatically
- `ENVIRONMENT` — production
- `GROQ_API_KEY` — Groq LLM API key
- `AGENT_API_KEY` — API authentication key
- `LLM_MODEL` — llama-3.3-70b-versatile
- `LOG_LEVEL` — INFO
- `GRADIO_ROOT_PATH` — /ui

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running / health check](screenshots/running.png)
- [API test results](screenshots/test.png)

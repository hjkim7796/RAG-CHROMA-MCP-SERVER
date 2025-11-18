# RAG MCP Server - HTTP/SSE Version

HTTP 통신을 지원하는 RAG MCP 서버입니다. FastAPI와 Server-Sent Events (SSE)를 사용합니다.

## 🚀 Quick Start

### 1. 패키지 설치

```bash
pip install -r requirements_http.txt
```

### 2. 환경 변수 설정

```bash
# Linux/Mac
export ANTHROPIC_API_KEY="your-api-key-here"

# Windows
set ANTHROPIC_API_KEY=your-api-key-here
```

### 3. 서버 실행

```bash
python rag_mcp_http_server.py
```

서버가 `http://0.0.0.0:8000`에서 실행됩니다.

## 📡 API Endpoints

### HTTP Endpoints

- `GET /` - 서버 정보
- `GET /health` - 헬스 체크
- `GET /tools` - 사용 가능한 도구 목록
- `POST /sse` - SSE 엔드포인트 (MCP 프로토콜)

### SSE Endpoint Usage

MCP 클라이언트는 `/sse` 엔드포인트로 JSON-RPC 2.0 형식의 요청을 보냅니다.

**예제: 도구 목록 조회**
```json
POST /sse
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

**예제: 도구 호출**
```json
POST /sse
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "add_documents",
    "arguments": {
      "texts": ["Sample document text"]
    }
  }
}
```

## 🔧 Claude Desktop 연동

### 방법 1: HTTP Transport (권장)

Claude Desktop의 설정 파일에 HTTP 엔드포인트를 추가합니다.

**파일 위치:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**설정 내용:**

```json
{
  "mcpServers": {
    "rag-search": {
      "url": "http://localhost:8000/sse",
      "transport": "http"
    }
  }
}
```

### 방법 2: 프록시 사용

로컬 프록시를 통해 HTTP를 stdio로 변환할 수도 있습니다.

```json
{
  "mcpServers": {
    "rag-search": {
      "command": "npx",
      "args": [
        "@anthropic/mcp-proxy",
        "http://localhost:8000/sse"
      ]
    }
  }
}
```

## 🧪 테스트

### cURL로 테스트

```bash
# 헬스 체크
curl http://localhost:8000/health

# 도구 목록 조회
curl http://localhost:8000/tools

# SSE 엔드포인트 테스트
curl -X POST http://localhost:8000/sse \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

### Python으로 테스트

```python
import requests
import json

# 서버 상태 확인
response = requests.get("http://localhost:8000/health")
print(response.json())

# 도구 목록 조회
response = requests.post(
    "http://localhost:8000/sse",
    json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
)
print(response.text)

# 문서 추가
response = requests.post(
    "http://localhost:8000/sse",
    json={
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "add_documents",
            "arguments": {
                "texts": [
                    "RAG is a technique that combines retrieval with generation.",
                    "ChromaDB is a vector database for AI applications."
                ]
            }
        }
    }
)
print(response.text)

# 문서 검색
response = requests.post(
    "http://localhost:8000/sse",
    json={
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "search_documents",
            "arguments": {
                "query": "What is RAG?",
                "k": 2
            }
        }
    }
)
print(response.text)
```

## 🌐 원격 서버 배포

### Docker 사용

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements_http.txt .
RUN pip install --no-cache-dir -r requirements_http.txt

COPY rag_mcp_http_server.py .

ENV ANTHROPIC_API_KEY=""
EXPOSE 8000

CMD ["python", "rag_mcp_http_server.py"]
```

**빌드 및 실행:**

```bash
docker build -t rag-mcp-http .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=your-key rag-mcp-http
```

### 클라우드 배포

**Railway, Render, Fly.io 등에 배포 가능**

Claude Desktop에서 원격 서버에 연결:

```json
{
  "mcpServers": {
    "rag-search": {
      "url": "https://your-server.com/sse",
      "transport": "http"
    }
  }
}
```

## 🔒 보안 고려사항

### 1. API 키 인증

프로덕션 환경에서는 API 키 인증을 추가하세요:

```python
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.environ.get("API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

# 엔드포인트에 적용
@app.post("/sse", dependencies=[Depends(verify_api_key)])
async def sse_endpoint(request: Request):
    # ...
```

### 2. HTTPS 사용

프로덕션에서는 반드시 HTTPS를 사용하세요:

```bash
# Certbot으로 SSL 인증서 발급
certbot certonly --standalone -d your-domain.com

# Uvicorn에 SSL 적용
uvicorn rag_mcp_http_server:app \
  --host 0.0.0.0 \
  --port 443 \
  --ssl-keyfile /etc/letsencrypt/live/your-domain.com/privkey.pem \
  --ssl-certfile /etc/letsencrypt/live/your-domain.com/fullchain.pem
```

### 3. Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/sse")
@limiter.limit("10/minute")
async def sse_endpoint(request: Request):
    # ...
```

## 📊 모니터링

### 로깅

서버는 자동으로 로그를 출력합니다:

```
🚀 RAG MCP Server (HTTP/SSE) Starting...
🔧 Initializing vectorstore...
✅ Vectorstore initialized
✅ Claude API client initialized
✅ MCP server initialized
✅ Server ready!
📡 Listening on http://0.0.0.0:8000
```

### Prometheus 메트릭 (선택사항)

```python
from prometheus_fastapi_instrumentator import Instrumentator

instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)
```

## 🐛 문제 해결

### 포트가 이미 사용 중

```bash
# 다른 포트로 실행
uvicorn rag_mcp_http_server:app --port 8001
```

### CORS 오류

CORS 설정이 이미 포함되어 있지만, 특정 도메인만 허용하려면:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://claude.ai", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### SSE 연결 끊김

네트워크 프록시나 방화벽에서 SSE를 차단할 수 있습니다. 
웹소켓으로 전환하거나 keep-alive 설정을 조정하세요.

## 📝 차이점: stdio vs HTTP

### stdio (기본)
- ✅ 간단한 로컬 사용
- ✅ 추가 설정 불필요
- ❌ 원격 접근 불가
- ❌ 다중 클라이언트 지원 안 됨

### HTTP/SSE (이 버전)
- ✅ 원격 접근 가능
- ✅ 다중 클라이언트 지원
- ✅ 클라우드 배포 가능
- ✅ 웹 브라우저에서 테스트 가능
- ❌ 네트워크 설정 필요
- ❌ 보안 고려 필요

## 🎯 사용 시나리오

1. **로컬 개발**: localhost에서 실행하고 Claude Desktop 연결
2. **팀 공유**: 내부 네트워크에 배포하여 팀원들과 공유
3. **클라우드 배포**: 공개 서버로 배포하여 어디서나 접근
4. **마이크로서비스**: 다른 서비스와 HTTP API로 통합

## 📚 추가 리소스

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [Anthropic MCP SDKs](https://github.com/anthropics/mcp)

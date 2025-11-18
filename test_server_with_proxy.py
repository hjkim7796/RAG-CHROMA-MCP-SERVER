#!/usr/bin/env python3
"""
간단한 MCP 프록시 테스트
"""

import requests
import json

print("=" * 60)
print("RAG MCP Server Test")
print("=" * 60)

# 1. 헬스 체크
print("\n1. Health Check:")
try:
    response = requests.get("http://localhost:8000/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"   Error: {e}")

# 2. 서버 직접 테스트
print("\n2. Direct Server Test (POST /sse):")
try:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    response = requests.post(
        "http://localhost:8000/sse",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"   Status: {response.status_code}")
    print(f"   Content-Type: {response.headers.get('content-type')}")
    print(f"   Response: {json.dumps(response.json(), indent=2)[:500]}...")
    
except Exception as e:
    print(f"   Error: {e}")

# 3. 프록시 함수 직접 테스트
print("\n3. Testing Proxy Function:")
try:
    import sys
    sys.path.insert(0, '.')
    
    # 프록시 모듈 import
    import importlib.util
    spec = importlib.util.spec_from_file_location("proxy", "mcp-http-proxy.py")
    proxy = importlib.util.module_from_spec(spec)
    
    # DEBUG 모드 활성화
    proxy.DEBUG = True
    proxy.SERVER_URL = "http://localhost:8000/sse"
    
    spec.loader.exec_module(proxy)
    
    # 테스트 메시지
    test_message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    print("   Sending:", json.dumps(test_message))
    result = proxy.send_http_request(test_message)
    print("   Result:", json.dumps(result, indent=2)[:500])
    
except Exception as e:
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)

"""
HTTP MCP Server Test Script
RAG MCP HTTP 서버를 테스트하는 스크립트
"""

import requests
import json
import time


def print_header(text):
    """헤더 출력"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def test_health_check():
    """헬스 체크 테스트"""
    print_header("1. Health Check")
    
    try:
        response = requests.get("http://localhost:8000/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_root_endpoint():
    """루트 엔드포인트 테스트"""
    print_header("2. Root Endpoint")
    
    try:
        response = requests.get("http://localhost:8000/")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_list_tools():
    """도구 목록 조회 테스트"""
    print_header("3. List Tools (HTTP)")
    
    try:
        response = requests.get("http://localhost:8000/tools")
        print(f"Status Code: {response.status_code}")
        data = response.json()
        print(f"Number of tools: {len(data['tools'])}")
        for tool in data['tools']:
            print(f"  - {tool['name']}: {tool['description'][:50]}...")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_list_tools_sse():
    """SSE를 통한 도구 목록 조회 테스트"""
    print_header("4. List Tools (SSE/MCP)")
    
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
            stream=True
        )
        
        print(f"Status Code: {response.status_code}")
        
        # SSE 응답 파싱
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    if 'result' in data:
                        tools = data['result']['tools']
                        print(f"Number of tools: {len(tools)}")
                        for tool in tools:
                            print(f"  - {tool['name']}: {tool['description'][:50]}...")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_add_documents():
    """문서 추가 테스트"""
    print_header("5. Add Documents")
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "add_documents",
                "arguments": {
                    "texts": [
                        """
                        RAG (Retrieval-Augmented Generation) is a technique that combines 
                        information retrieval with text generation. It retrieves relevant 
                        documents from a knowledge base and uses them as context for 
                        generating more accurate and informed responses.
                        """,
                        """
                        ChromaDB is an open-source embedding database designed for AI applications.
                        It provides efficient storage and retrieval of vector embeddings,
                        making it ideal for semantic search and RAG systems.
                        """,
                        """
                        LangChain is a framework for developing applications powered by 
                        language models. It provides tools for document loading, text splitting,
                        embeddings, vector stores, and chains for complex workflows.
                        """,
                        """
                        FastAPI is a modern, fast web framework for building APIs with Python.
                        It's based on standard Python type hints and provides automatic 
                        API documentation, data validation, and high performance.
                        """
                    ],
                    "metadatas": [
                        {"source": "RAG Guide", "category": "AI/ML"},
                        {"source": "ChromaDB Docs", "category": "Database"},
                        {"source": "LangChain Tutorial", "category": "Framework"},
                        {"source": "FastAPI Documentation", "category": "Web"}
                    ]
                }
            }
        }
        
        response = requests.post(
            "http://localhost:8000/sse",
            json=payload,
            stream=True
        )
        
        print(f"Status Code: {response.status_code}")
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    if 'result' in data:
                        content = data['result']['content'][0]['text']
                        print(f"Result: {content}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_search_documents():
    """문서 검색 테스트"""
    print_header("6. Search Documents")
    
    queries = [
        "What is RAG?",
        "Tell me about vector databases",
        "How does LangChain work?"
    ]
    
    try:
        for i, query in enumerate(queries, 1):
            print(f"\n📝 Query {i}: {query}")
            
            payload = {
                "jsonrpc": "2.0",
                "id": 10 + i,
                "method": "tools/call",
                "params": {
                    "name": "search_documents",
                    "arguments": {
                        "query": query,
                        "k": 2
                    }
                }
            }
            
            response = requests.post(
                "http://localhost:8000/sse",
                json=payload,
                stream=True
            )
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = json.loads(line[6:])
                        if 'result' in data:
                            content = data['result']['content'][0]['text']
                            print(f"Results:\n{content[:300]}...")
            
            time.sleep(0.5)
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_rag_query():
    """RAG 질의응답 테스트"""
    print_header("7. RAG Query (with Claude)")
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {
                "name": "rag_query",
                "arguments": {
                    "question": "What are the main benefits of using RAG systems with vector databases?",
                    "k": 3,
                    "language": "en"
                }
            }
        }
        
        response = requests.post(
            "http://localhost:8000/sse",
            json=payload,
            stream=True
        )
        
        print(f"Status Code: {response.status_code}")
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    if 'result' in data:
                        content = data['result']['content'][0]['text']
                        print(f"Answer:\n{content}")
                    elif 'error' in data:
                        print(f"Error: {data['error']['message']}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_collection_info():
    """컬렉션 정보 조회 테스트"""
    print_header("8. Collection Info")
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "tools/call",
            "params": {
                "name": "get_collection_info",
                "arguments": {}
            }
        }
        
        response = requests.post(
            "http://localhost:8000/sse",
            json=payload,
            stream=True
        )
        
        print(f"Status Code: {response.status_code}")
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    if 'result' in data:
                        content = data['result']['content'][0]['text']
                        print(f"Collection Info:\n{content}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """메인 함수"""
    print("\n" + "=" * 60)
    print("  RAG MCP HTTP Server Test Suite")
    print("=" * 60)
    print("\n⚠️  Make sure the server is running at http://localhost:8000")
    print("   Run: python rag_mcp_http_server.py\n")
    
    input("Press Enter to start tests...")
    
    results = []
    
    # 테스트 실행
    results.append(("Health Check", test_health_check()))
    results.append(("Root Endpoint", test_root_endpoint()))
    results.append(("List Tools (HTTP)", test_list_tools()))
    results.append(("List Tools (SSE)", test_list_tools_sse()))
    results.append(("Add Documents", test_add_documents()))
    
    print("\n⏳ Waiting for embeddings to be processed...")
    time.sleep(2)
    
    results.append(("Search Documents", test_search_documents()))
    results.append(("RAG Query", test_rag_query()))
    results.append(("Collection Info", test_collection_info()))
    
    # 결과 요약
    print_header("Test Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
    
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()

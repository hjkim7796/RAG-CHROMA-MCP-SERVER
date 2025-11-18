#!/usr/bin/env python3
"""
PDF 파일을 RAG MCP 서버에 추가하는 클라이언트
"""

import requests
import json
from pathlib import Path

# PyPDF2로 PDF 읽기 (설치 필요: pip install PyPDF2)
try:
    from PyPDF2 import PdfReader
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False
    print("⚠️  PyPDF2가 설치되지 않았습니다. pip install PyPDF2")

# pdfplumber로 PDF 읽기 (대안, 설치 필요: pip install pdfplumber)
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


class MCPClient:
    """MCP 서버 클라이언트"""
    
    def __init__(self, server_url="http://localhost:8000/sse"):
        self.server_url = server_url
        self.request_id = 0
    
    def _send_request(self, method, params=None):
        """MCP 서버에 요청 전송"""
        self.request_id += 1
        
        payload = {
            "jsonrpc": "2.0",
            "id": str(self.request_id),
            "method": method,
            "params": params or {}
        }
        
        print(f"📤 Sending: {method}")
        
        try:
            response = requests.post(
                self.server_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=120  # PDF 처리는 시간이 걸릴 수 있음
            )
            
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                print(f"❌ Error: {result['error']['message']}")
                return None
            
            return result.get("result")
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Request error: {e}")
            return None
    
    def list_tools(self):
        """사용 가능한 도구 목록"""
        print("\n🔧 Listing available tools...")
        result = self._send_request("tools/list")
        
        if result:
            tools = result.get("tools", [])
            print(f"✅ Found {len(tools)} tools:")
            for tool in tools:
                print(f"   - {tool['name']}: {tool['description'][:60]}...")
        
        return result
    
    def add_documents(self, texts, metadatas=None, chunk_size=1000, chunk_overlap=200):
        """문서 추가"""
        print(f"\n📄 Adding {len(texts)} document(s)...")
        
        params = {
            "name": "add_documents",
            "arguments": {
                "texts": texts,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap
            }
        }
        
        if metadatas:
            params["arguments"]["metadatas"] = metadatas
        
        result = self._send_request("tools/call", params)
        
        if result:
            content = result.get("content", [])
            if content:
                print(f"✅ {content[0]['text']}")
        
        return result
    
    def search_documents(self, query, k=4):
        """문서 검색"""
        print(f"\n🔍 Searching for: '{query}'")
        
        params = {
            "name": "search_documents",
            "arguments": {
                "query": query,
                "k": k
            }
        }
        
        result = self._send_request("tools/call", params)
        
        if result:
            content = result.get("content", [])
            if content:
                print(f"✅ Search results:\n{content[0]['text'][:500]}...")
        
        return result
    
    def rag_query(self, question, k=4, language="ko"):
        """RAG 질의응답"""
        print(f"\n💡 Asking: '{question}'")
        
        params = {
            "name": "rag_query",
            "arguments": {
                "question": question,
                "k": k,
                "language": language
            }
        }
        
        result = self._send_request("tools/call", params)
        
        if result:
            content = result.get("content", [])
            if content:
                print(f"✅ Answer:\n{content[0]['text']}")
        
        return result


def read_pdf_pypdf2(pdf_path):
    """PyPDF2로 PDF 읽기"""
    if not HAS_PYPDF2:
        return None
    
    try:
        reader = PdfReader(pdf_path)
        text = ""
        
        print(f"📖 Reading PDF with PyPDF2: {len(reader.pages)} pages")
        
        for i, page in enumerate(reader.pages, 1):
            page_text = page.extract_text()
            text += f"\n\n[Page {i}]\n{page_text}"
        
        return text.strip()
    
    except Exception as e:
        print(f"❌ PyPDF2 error: {e}")
        return None


def read_pdf_pdfplumber(pdf_path):
    """pdfplumber로 PDF 읽기 (더 정확함)"""
    if not HAS_PDFPLUMBER:
        return None
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            
            print(f"📖 Reading PDF with pdfplumber: {len(pdf.pages)} pages")
            
            for i, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text += f"\n\n[Page {i}]\n{page_text}"
            
            return text.strip()
    
    except Exception as e:
        print(f"❌ pdfplumber error: {e}")
        return None


def read_pdf(pdf_path):
    """PDF 파일 읽기 (여러 방법 시도)"""
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        print(f"❌ File not found: {pdf_path}")
        return None
    
    print(f"\n📄 Reading PDF: {pdf_path.name}")
    print(f"   Size: {pdf_path.stat().st_size / 1024:.2f} KB")
    
    # pdfplumber 먼저 시도 (더 정확함)
    text = read_pdf_pdfplumber(pdf_path)
    
    # 실패하면 PyPDF2 시도
    if not text:
        text = read_pdf_pypdf2(pdf_path)
    
    if text:
        print(f"✅ Extracted {len(text)} characters")
        print(f"   Preview: {text[:200]}...")
    else:
        print("❌ Failed to extract text from PDF")
    
    return text


def add_pdf_to_mcp(pdf_path, server_url="http://localhost:8000/sse", 
                   chunk_size=1000, chunk_overlap=200):
    """PDF 파일을 MCP 서버에 추가"""
    
    print("=" * 60)
    print("📚 Adding PDF to RAG MCP Server")
    print("=" * 60)
    
    # 1. PDF 읽기
    text = read_pdf(pdf_path)
    if not text:
        return False
    
    # 2. MCP 클라이언트 생성
    client = MCPClient(server_url)
    
    # 3. 서버 연결 확인
    tools = client.list_tools()
    if not tools:
        print("❌ Cannot connect to MCP server")
        return False
    
    # 4. PDF 메타데이터 준비
    pdf_path = Path(pdf_path)
    metadata = {
        "source": pdf_path.name,
        "file_path": str(pdf_path.absolute()),
        "file_type": "pdf",
        "file_size": pdf_path.stat().st_size
    }
    
    # 5. 문서 추가
    result = client.add_documents(
        texts=[text],
        metadatas=[metadata],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    if not result:
        return False
    
    # 6. 검색 테스트
    print("\n🧪 Testing search...")
    client.search_documents(pdf_path.stem, k=2)
    
    print("\n" + "=" * 60)
    print("✅ PDF successfully added to RAG system!")
    print("=" * 60)
    
    return True


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Add PDF file to RAG MCP Server"
    )
    parser.add_argument(
        "pdf_path",
        help="Path to PDF file (e.g., abc.pdf)"
    )
    parser.add_argument(
        "--server",
        default="http://localhost:8000/sse",
        help="MCP server URL (default: http://localhost:8000/sse)"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Chunk size for splitting (default: 1000)"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Chunk overlap (default: 200)"
    )
    parser.add_argument(
        "--test-query",
        help="Test query after adding PDF"
    )
    
    args = parser.parse_args()
    
    # PDF 추가
    success = add_pdf_to_mcp(
        args.pdf_path,
        args.server,
        args.chunk_size,
        args.chunk_overlap
    )
    
    if not success:
        exit(1)
    
    # 테스트 쿼리
    if args.test_query:
        client = MCPClient(args.server)
        client.rag_query(args.test_query, k=3)


if __name__ == "__main__":
    # 명령줄 인자가 없으면 기본 예제 실행
    import sys
    
    if len(sys.argv) == 1:
        print("\n사용 예제:")
        print("  python add_pdf_to_mcp.py abc.pdf")
        print("  python add_pdf_to_mcp.py abc.pdf --test-query 'PDF의 주요 내용은?'")
        print("  python add_pdf_to_mcp.py /path/to/document.pdf --chunk-size 500")
        print("\n또는 코드에서 직접 호출:")
        print("  from add_pdf_to_mcp import add_pdf_to_mcp")
        print("  add_pdf_to_mcp('abc.pdf')")
        print()
        
        # 기본 테스트
        test_file = "abc.pdf"
        if Path(test_file).exists():
            print(f"✅ Found {test_file}, running test...")
            add_pdf_to_mcp(test_file)
        else:
            print(f"⚠️  {test_file} not found. Please specify a PDF file.")
            print("   Usage: python add_pdf_to_mcp.py <pdf_file>")
    else:
        main()

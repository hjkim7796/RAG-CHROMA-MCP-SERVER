#!/usr/bin/env python3
"""
PDF 파일을 RAG MCP 서버에 추가하는 클라이언트 (강화 버전)
- 이미지 OCR 지원
- 테이블 추출
- 복잡한 PDF 처리
"""

import requests
import json
from pathlib import Path
import sys

# PDF 라이브러리 확인
PDF_LIBRARIES = {
    'pymupdf': False,
    'pdfplumber': False,
    'pypdf2': False,
    'pytesseract': False,
    'pdf2image': False
}

# PyMuPDF (가장 강력)
try:
    import fitz  # PyMuPDF
    PDF_LIBRARIES['pymupdf'] = True
except ImportError:
    pass

# pdfplumber (테이블 추출 우수)
try:
    import pdfplumber
    PDF_LIBRARIES['pdfplumber'] = True
except ImportError:
    pass

# PyPDF2
try:
    from PyPDF2 import PdfReader
    PDF_LIBRARIES['pypdf2'] = True
except ImportError:
    pass

# OCR 라이브러리
try:
    import pytesseract
    from PIL import Image
    PDF_LIBRARIES['pytesseract'] = True
except ImportError:
    pass

try:
    from pdf2image import convert_from_path
    PDF_LIBRARIES['pdf2image'] = True
except ImportError:
    pass


def check_dependencies():
    """의존성 확인 및 권장사항 출력"""
    print("\n📦 Checking PDF processing libraries...")
    
    installed = []
    missing = []
    
    for lib, available in PDF_LIBRARIES.items():
        if available:
            installed.append(lib)
            print(f"   ✅ {lib}")
        else:
            missing.append(lib)
            print(f"   ❌ {lib}")
    
    if not any([PDF_LIBRARIES['pymupdf'], PDF_LIBRARIES['pdfplumber'], PDF_LIBRARIES['pypdf2']]):
        print("\n⚠️  No PDF libraries installed!")
        print("   Install at least one: pip install PyMuPDF pdfplumber PyPDF2")
        return False
    
    if missing:
        print(f"\n💡 Optional libraries for better results:")
        if 'pymupdf' in missing:
            print("   pip install PyMuPDF  # Best for complex PDFs")
        if 'pdfplumber' in missing:
            print("   pip install pdfplumber  # Best for tables")
        if 'pytesseract' in missing or 'pdf2image' in missing:
            print("   pip install pytesseract pdf2image Pillow  # For OCR")
    
    return True


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
                timeout=180  # 복잡한 PDF는 더 오래 걸림
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
            print(f"✅ Found {len(tools)} tools")
        
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
                print(f"✅ Found results")
        
        return result


def extract_text_pymupdf(pdf_path):
    """PyMuPDF로 텍스트 추출 (이미지 무시, 텍스트만)"""
    if not PDF_LIBRARIES['pymupdf']:
        return None
    
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        text = ""
        
        print(f"📖 Extracting text with PyMuPDF: {len(doc)} pages")
        
        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                # 텍스트만 추출 (이미지는 제외)
                page_text = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
                
                if page_text and page_text.strip():
                    text += f"\n\n[Page {page_num + 1}]\n{page_text.strip()}"
            except Exception as e:
                print(f"⚠️  Warning: Page {page_num + 1} text error: {str(e)[:50]}")
                continue
        
        doc.close()
        return text.strip() if text.strip() else None
    
    except Exception as e:
        print(f"❌ PyMuPDF error: {str(e)[:100]}")
        return None


def extract_tables_pdfplumber(pdf_path):
    """pdfplumber로 테이블 추출"""
    if not PDF_LIBRARIES['pdfplumber']:
        return None
    
    try:
        tables_text = ""
        
        with pdfplumber.open(str(pdf_path)) as pdf:
            print(f"📊 Extracting tables with pdfplumber: {len(pdf.pages)} pages")
            
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    tables = page.extract_tables()
                    
                    if tables:
                        tables_text += f"\n\n[Page {page_num} - Tables]\n"
                        
                        for table_num, table in enumerate(tables, 1):
                            tables_text += f"\nTable {table_num}:\n"
                            
                            # 테이블을 텍스트로 변환
                            for row in table:
                                if row:
                                    row_text = " | ".join([str(cell) if cell else "" for cell in row])
                                    tables_text += row_text + "\n"
                
                except Exception as e:
                    print(f"⚠️  Warning: Page {page_num} table error: {str(e)[:50]}")
                    continue
        
        return tables_text.strip() if tables_text.strip() else None
    
    except Exception as e:
        print(f"❌ pdfplumber error: {str(e)[:100]}")
        return None


def extract_text_pdfplumber(pdf_path):
    """pdfplumber로 일반 텍스트 추출"""
    if not PDF_LIBRARIES['pdfplumber']:
        return None
    
    try:
        text = ""
        
        with pdfplumber.open(str(pdf_path)) as pdf:
            print(f"📖 Extracting text with pdfplumber: {len(pdf.pages)} pages")
            
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    # layout 옵션으로 더 나은 텍스트 추출
                    page_text = page.extract_text(layout=True)
                    
                    if page_text and page_text.strip():
                        text += f"\n\n[Page {page_num}]\n{page_text.strip()}"
                
                except Exception as e:
                    print(f"⚠️  Warning: Page {page_num} text error: {str(e)[:50]}")
                    continue
        
        return text.strip() if text.strip() else None
    
    except Exception as e:
        print(f"❌ pdfplumber error: {str(e)[:100]}")
        return None


def extract_text_pypdf2(pdf_path):
    """PyPDF2로 텍스트 추출 (폴백)"""
    if not PDF_LIBRARIES['pypdf2']:
        return None
    
    try:
        reader = PdfReader(str(pdf_path))
        text = ""
        
        print(f"📖 Extracting text with PyPDF2: {len(reader.pages)} pages")
        
        for page_num, page in enumerate(reader.pages, 1):
            try:
                page_text = page.extract_text()
                
                if page_text and page_text.strip():
                    text += f"\n\n[Page {page_num}]\n{page_text.strip()}"
            
            except Exception as e:
                print(f"⚠️  Warning: Page {page_num} error: {str(e)[:50]}")
                continue
        
        return text.strip() if text.strip() else None
    
    except Exception as e:
        print(f"❌ PyPDF2 error: {str(e)[:100]}")
        return None


def ocr_pdf(pdf_path):
    """OCR을 사용하여 이미지 기반 PDF 읽기"""
    if not (PDF_LIBRARIES['pytesseract'] and PDF_LIBRARIES['pdf2image']):
        return None
    
    try:
        print(f"🔍 Attempting OCR (this may take a while)...")
        
        # PDF를 이미지로 변환
        images = convert_from_path(str(pdf_path), dpi=200)
        
        text = ""
        
        for page_num, image in enumerate(images, 1):
            try:
                print(f"   Processing page {page_num}/{len(images)}...")
                
                # OCR 수행
                page_text = pytesseract.image_to_string(image, lang='eng+kor')
                
                if page_text and page_text.strip():
                    text += f"\n\n[Page {page_num} - OCR]\n{page_text.strip()}"
            
            except Exception as e:
                print(f"⚠️  Warning: OCR page {page_num} error: {str(e)[:50]}")
                continue
        
        return text.strip() if text.strip() else None
    
    except Exception as e:
        print(f"❌ OCR error: {str(e)[:100]}")
        return None


def read_pdf_comprehensive(pdf_path):
    """종합적인 PDF 읽기 - 모든 방법 시도"""
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        print(f"❌ File not found: {pdf_path}")
        return None
    
    print(f"\n📄 Reading PDF: {pdf_path.name}")
    print(f"   Size: {pdf_path.stat().st_size / 1024:.2f} KB")
    
    all_text = []
    methods_used = []
    
    # 1. PyMuPDF로 텍스트 추출 (가장 빠르고 안정적)
    text = extract_text_pymupdf(pdf_path)
    if text:
        all_text.append(text)
        methods_used.append("PyMuPDF-text")
    
    # 2. pdfplumber로 테이블 추출
    tables = extract_tables_pdfplumber(pdf_path)
    if tables:
        all_text.append(tables)
        methods_used.append("pdfplumber-tables")
    
    # 3. 텍스트가 거의 없으면 pdfplumber로 텍스트 재시도
    if not text or len(text) < 500:
        print("\n⚠️  Low text content, trying pdfplumber...")
        plumber_text = extract_text_pdfplumber(pdf_path)
        if plumber_text and len(plumber_text) > len(text or ""):
            all_text.append(plumber_text)
            methods_used.append("pdfplumber-text")
    
    # 4. 여전히 텍스트가 없으면 PyPDF2 시도
    if not any(all_text):
        print("\n⚠️  No text extracted, trying PyPDF2...")
        pypdf_text = extract_text_pypdf2(pdf_path)
        if pypdf_text:
            all_text.append(pypdf_text)
            methods_used.append("PyPDF2")
    
    # 5. 그래도 텍스트가 없으면 OCR 시도
    if not any(all_text) or sum(len(t) for t in all_text) < 200:
        print("\n⚠️  Very low text content, this might be an image-based PDF")
        print("   Attempting OCR (requires pytesseract and pdf2image)...")
        
        ocr_text = ocr_pdf(pdf_path)
        if ocr_text:
            all_text.append(ocr_text)
            methods_used.append("OCR")
    
    # 결과 병합
    if all_text:
        combined_text = "\n\n" + "="*60 + "\n\n".join(all_text)
        
        print(f"\n✅ Successfully extracted text")
        print(f"   Methods used: {', '.join(methods_used)}")
        print(f"   Total characters: {len(combined_text)}")
        print(f"   Preview: {combined_text[:200].replace(chr(10), ' ')}...")
        
        return combined_text
    else:
        print(f"\n❌ Failed to extract any text from PDF")
        print("\n💡 This PDF might be:")
        print("   1. Password protected")
        print("   2. Image-only (install OCR: pip install pytesseract pdf2image)")
        print("   3. Corrupted or non-standard format")
        print("\n   Tried methods: {', '.join(methods_used) if methods_used else 'None worked'}")
        
        return None


def add_pdf_to_mcp(pdf_path, server_url="http://localhost:8000/sse", 
                   chunk_size=1000, chunk_overlap=200):
    """PDF 파일을 MCP 서버에 추가"""
    
    print("=" * 60)
    print("📚 Adding PDF to RAG MCP Server")
    print("=" * 60)
    
    # 의존성 확인
    if not check_dependencies():
        return False
    
    # PDF 읽기
    text = read_pdf_comprehensive(pdf_path)
    if not text:
        return False
    
    # MCP 클라이언트 생성
    client = MCPClient(server_url)
    
    # 서버 연결 확인
    tools = client.list_tools()
    if not tools:
        print("❌ Cannot connect to MCP server")
        return False
    
    # PDF 메타데이터
    pdf_path = Path(pdf_path)
    metadata = {
        "source": pdf_path.name,
        "file_path": str(pdf_path.absolute()),
        "file_type": "pdf",
        "file_size": pdf_path.stat().st_size,
        "has_tables": "Table" in text,
        "has_ocr": "OCR" in text
    }
    
    # 문서 추가
    result = client.add_documents(
        texts=[text],
        metadatas=[metadata],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    if not result:
        return False
    
    # 검색 테스트
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
        description="Add PDF file to RAG MCP Server (Enhanced with OCR & Table support)"
    )
    parser.add_argument(
        "pdf_path",
        help="Path to PDF file"
    )
    parser.add_argument(
        "--server",
        default="http://localhost:8000/sse",
        help="MCP server URL"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Chunk size for splitting"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Chunk overlap"
    )
    
    args = parser.parse_args()
    
    success = add_pdf_to_mcp(
        args.pdf_path,
        args.server,
        args.chunk_size,
        args.chunk_overlap
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("\n🚀 Enhanced PDF to MCP - with Table & OCR support")
        print("\n사용법:")
        print("  python add_pdf_to_mcp.py document.pdf")
        print("  python add_pdf_to_mcp.py document.pdf --chunk-size 800")
        print("\n필수 설치:")
        print("  pip install PyMuPDF pdfplumber PyPDF2 requests")
        print("\nOCR 지원 (선택):")
        print("  pip install pytesseract pdf2image Pillow")
        print("  # And install Tesseract: https://github.com/tesseract-ocr/tesseract")
        print()
    else:
        main()
#!/usr/bin/env python3
"""
간단한 PDF 추가 예제
"""

from add_pdf_to_mcp import MCPClient, read_pdf, add_pdf_to_mcp
from pathlib import Path

# 방법 1: 전체 자동화 (가장 간단)
def simple_example():
    """가장 간단한 방법"""
    print("=== 방법 1: 전체 자동화 ===\n")
    
    # abc.pdf를 MCP 서버에 추가
    add_pdf_to_mcp("abc.pdf")


# 방법 2: 단계별 제어
def step_by_step_example():
    """단계별로 제어하는 방법"""
    print("\n=== 방법 2: 단계별 제어 ===\n")
    
    # 1. PDF 읽기
    text = read_pdf("abc.pdf")
    if not text:
        print("PDF를 읽을 수 없습니다.")
        return
    
    # 2. MCP 클라이언트 생성
    client = MCPClient("http://localhost:8000/sse")
    
    # 3. 문서 추가
    client.add_documents(
        texts=[text],
        metadatas=[{
            "source": "abc.pdf",
            "category": "manual",
            "uploaded_by": "user"
        }],
        chunk_size=800,
        chunk_overlap=150
    )
    
    # 4. 검색 테스트
    client.search_documents("주요 내용", k=3)
    
    # 5. RAG 질의응답
    client.rag_query("이 문서의 핵심 내용을 요약해주세요", k=4, language="ko")


# 방법 3: 여러 PDF 파일 추가
def multiple_pdfs_example():
    """여러 PDF를 한번에 추가"""
    print("\n=== 방법 3: 여러 PDF 파일 ===\n")
    
    pdf_files = ["abc.pdf", "document1.pdf", "document2.pdf"]
    
    client = MCPClient()
    
    for pdf_file in pdf_files:
        if not Path(pdf_file).exists():
            print(f"⚠️  {pdf_file} not found, skipping...")
            continue
        
        print(f"\n📄 Processing {pdf_file}...")
        text = read_pdf(pdf_file)
        
        if text:
            client.add_documents(
                texts=[text],
                metadatas=[{"source": pdf_file, "type": "pdf"}]
            )


# 방법 4: 폴더의 모든 PDF 추가
def folder_pdfs_example():
    """폴더의 모든 PDF를 추가"""
    print("\n=== 방법 4: 폴더의 모든 PDF ===\n")
    
    folder = Path("./documents")  # PDF가 있는 폴더
    
    if not folder.exists():
        print(f"⚠️  Folder {folder} not found")
        return
    
    pdf_files = list(folder.glob("*.pdf"))
    print(f"📁 Found {len(pdf_files)} PDF files in {folder}")
    
    client = MCPClient()
    
    for pdf_file in pdf_files:
        print(f"\n📄 Processing {pdf_file.name}...")
        text = read_pdf(pdf_file)
        
        if text:
            client.add_documents(
                texts=[text],
                metadatas=[{
                    "source": pdf_file.name,
                    "folder": str(folder),
                    "type": "pdf"
                }]
            )


# 방법 5: 프로그래밍 방식 (라이브러리로 사용)
def library_usage_example():
    """라이브러리처럼 사용"""
    print("\n=== 방법 5: 라이브러리 사용 ===\n")
    
    from add_pdf_to_mcp import MCPClient
    
    # 클라이언트 생성
    mcp = MCPClient()
    
    # PDF 추가
    pdf_text = read_pdf("abc.pdf")
    if pdf_text:
        result = mcp.add_documents(
            texts=[pdf_text],
            metadatas=[{"source": "abc.pdf"}]
        )
        
        if result:
            # 바로 질문하기
            mcp.rag_query(
                "What are the main topics in this document?",
                language="en"
            )


if __name__ == "__main__":
    import sys
    
    print("📚 PDF to MCP Server - 사용 예제")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        # 명령줄에서 PDF 파일 지정
        pdf_file = sys.argv[1]
        print(f"\n처리할 파일: {pdf_file}\n")
        add_pdf_to_mcp(pdf_file)
    else:
        # 대화형 메뉴
        print("\n어떤 방법을 사용하시겠습니까?")
        print("1. 간단한 방법 (abc.pdf 추가)")
        print("2. 단계별 제어")
        print("3. 여러 PDF 파일")
        print("4. 폴더의 모든 PDF")
        print("5. 라이브러리로 사용")
        print()
        
        choice = input("선택 (1-5): ").strip()
        
        if choice == "1":
            simple_example()
        elif choice == "2":
            step_by_step_example()
        elif choice == "3":
            multiple_pdfs_example()
        elif choice == "4":
            folder_pdfs_example()
        elif choice == "5":
            library_usage_example()
        else:
            print("잘못된 선택입니다.")

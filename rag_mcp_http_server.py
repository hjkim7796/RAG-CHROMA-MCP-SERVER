"""
RAG MCP Server - HTTP/SSE Version
FastAPI를 사용한 HTTP 통신 지원 MCP 서버
"""

from dotenv import load_dotenv
# 환경 변수 로드
load_dotenv()

"""
RAG MCP Server - HTTP/SSE Version
FastAPI를 사용한 HTTP 통신 지원 MCP 서버
"""

import asyncio
import os
from typing import Any, Optional
from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from mcp.server import Server
from mcp.types import Tool, TextContent
import anthropic
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# 전역 변수
vectorstore: Optional[Chroma] = None
anthropic_client: Optional[anthropic.Anthropic] = None
mcp_server: Optional[Server] = None
tools_list_handler = None
call_tool_handler = None
PERSIST_DIRECTORY = "./chroma_db"
COLLECTION_NAME = "rag_documents"

def initialize_vectorstore():
    """ChromaDB vectorstore 초기화"""
    global vectorstore
    
    print("🔧 Initializing vectorstore...")
    
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        #model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    
    vectorstore = Chroma(
        persist_directory=PERSIST_DIRECTORY,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME
    )
    
    print("✅ Vectorstore initialized")
    return vectorstore


def initialize_claude():
    """Claude API 클라이언트 초기화"""
    global anthropic_client
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️  ANTHROPIC_API_KEY not set. RAG query feature will be disabled.")
        return None
    
    anthropic_client = anthropic.Anthropic(api_key=api_key)
    print("✅ Claude API client initialized")
    return anthropic_client


def initialize_mcp_server():
    """MCP 서버 초기화"""
    global mcp_server, tools_list_handler, call_tool_handler
    
    mcp_server = Server("rag-search-server")
    
    @mcp_server.list_tools()
    async def list_tools() -> list[Tool]:
        """사용 가능한 도구 목록 반환"""
        return [
            Tool(
                name="add_documents",
                description="Add documents to the vector database with automatic chunking and embedding.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "texts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Array of document texts to add"
                        },
                        "metadatas": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Optional array of metadata objects"
                        },
                        "chunk_size": {
                            "type": "integer",
                            "description": "Chunk size (default: 1000)",
                            "default": 1000
                        },
                        "chunk_overlap": {
                            "type": "integer",
                            "description": "Chunk overlap (default: 200)",
                            "default": 200
                        }
                    },
                    "required": ["texts"]
                }
            ),
            Tool(
                name="search_documents",
                description="Search for similar documents in the vector database.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "k": {
                            "type": "integer",
                            "description": "Number of results (default: 4)",
                            "default": 4
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="rag_query",
                description="Answer questions using RAG with Claude AI.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Question to answer"
                        },
                        "k": {
                            "type": "integer",
                            "description": "Number of documents to retrieve (default: 4)",
                            "default": 4
                        },
                        "language": {
                            "type": "string",
                            "description": "Response language (ko/en, default: ko)",
                            "default": "ko"
                        }
                    },
                    "required": ["question"]
                }
            ),
            Tool(
                name="get_collection_info",
                description="Get information about the current collection.",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="delete_collection",
                description="Delete the entire collection (WARNING: irreversible).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "confirm": {
                            "type": "boolean",
                            "description": "Must be true to confirm deletion"
                        }
                    },
                    "required": ["confirm"]
                }
            )
        ]
    
    @mcp_server.call_tool()
    async def call_tool(name: str, arguments: Any) -> list[TextContent]:
        """도구 호출 처리"""
        if vectorstore is None:
            initialize_vectorstore()
        
        try:
            if name == "add_documents":
                return await add_documents_handler(arguments)
            elif name == "search_documents":
                return await search_documents_handler(arguments)
            elif name == "rag_query":
                return await rag_query_handler(arguments)
            elif name == "get_collection_info":
                return await get_collection_info_handler(arguments)
            elif name == "delete_collection":
                return await delete_collection_handler(arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]
    
    # 핸들러를 전역 변수에 저장
    global tools_list_handler, call_tool_handler
    tools_list_handler = list_tools
    call_tool_handler = call_tool
    
    print("✅ MCP server initialized")
    return mcp_server


async def add_documents_handler(arguments: dict) -> list[TextContent]:
    """문서 추가 핸들러"""
    texts = arguments.get("texts", [])
    metadatas = arguments.get("metadatas", [{}] * len(texts))
    chunk_size = arguments.get("chunk_size", 1000)
    chunk_overlap = arguments.get("chunk_overlap", 200)
    
    if not texts:
        return [TextContent(type="text", text="Error: No texts provided")]
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    documents = []
    for i, text in enumerate(texts):
        chunks = text_splitter.split_text(text)
        metadata = metadatas[i] if i < len(metadatas) else {}
        
        for j, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk,
                metadata={**metadata, "chunk_index": j, "total_chunks": len(chunks)}
            )
            documents.append(doc)
    
    vectorstore.add_documents(documents)
    
    return [TextContent(
        type="text",
        text=f"✅ Successfully added {len(documents)} document chunks from {len(texts)} documents\n"
             f"   Chunk size: {chunk_size}, Overlap: {chunk_overlap}"
    )]


async def search_documents_handler(arguments: dict) -> list[TextContent]:
    """문서 검색 핸들러"""
    query = arguments.get("query", "")
    k = arguments.get("k", 4)
    
    if not query:
        return [TextContent(type="text", text="Error: No query provided")]
    
    results = vectorstore.similarity_search(query, k=k)
    
    if not results:
        return [TextContent(type="text", text="No documents found matching your query.")]
    
    formatted_results = [f"🔍 Found {len(results)} documents:\n"]
    
    for i, doc in enumerate(results, 1):
        metadata_str = ", ".join([f"{k}: {v}" for k, v in doc.metadata.items()])
        formatted_results.append(
            f"\n📄 Document {i}:\n"
            f"Content: {doc.page_content[:200]}{'...' if len(doc.page_content) > 200 else ''}\n"
            f"Metadata: {metadata_str}\n"
        )
    
    return [TextContent(type="text", text="".join(formatted_results))]


async def rag_query_handler(arguments: dict) -> list[TextContent]:
    """RAG 쿼리 핸들러"""
    global anthropic_client
    
    question = arguments.get("question", "")
    k = arguments.get("k", 4)
    language = arguments.get("language", "ko")
    
    if not question:
        return [TextContent(type="text", text="Error: No question provided")]
    
    if anthropic_client is None:
        try:
            initialize_claude()
        except:
            pass
        
        if anthropic_client is None:
            return [TextContent(type="text", text="Error: ANTHROPIC_API_KEY not configured")]
    
    relevant_docs = vectorstore.similarity_search(question, k=k)
    
    if not relevant_docs:
        return [TextContent(type="text", text="❌ No relevant documents found in the database.")]
    
    context = "\n\n".join([
        f"[Document {i+1}]\n{doc.page_content}"
        for i, doc in enumerate(relevant_docs)
    ])
    
    if language == "ko":
        prompt = f"""다음 문서들을 참고하여 질문에 답변해주세요.

참고 문서:
{context}

질문: {question}

위 문서들의 정보를 바탕으로 정확하고 자세하게 답변해주세요."""
    else:
        prompt = f"""Please answer the question based on the following documents.

Reference Documents:
{context}

Question: {question}

Please provide an accurate and detailed answer based on the information above."""

    try:
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        answer = message.content[0].text
        
        sources = "\n\n" + "="*60 + "\n📚 Referenced Documents:\n"
        for i, doc in enumerate(relevant_docs, 1):
            metadata_items = [f"{k}: {v}" for k, v in doc.metadata.items() 
                            if k not in ['chunk_index', 'total_chunks']]
            metadata_str = ", ".join(metadata_items) if metadata_items else "No metadata"
            preview = doc.page_content[:100].replace('\n', ' ')
            sources += f"  [{i}] {metadata_str}\n      Preview: {preview}...\n"
        
        return [TextContent(type="text", text=f"💡 Answer:\n\n{answer}{sources}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error generating answer: {str(e)}")]


async def get_collection_info_handler(arguments: dict) -> list[TextContent]:
    """컬렉션 정보 조회"""
    try:
        collection = vectorstore._collection
        count = collection.count()
        
        info = f"""📊 Collection Information:

Collection Name: {collection.name}
Total Documents: {count}
Persist Directory: {PERSIST_DIRECTORY}
Embedding Model: sentence-transformers/all-MiniLM-L6-v2
"""
        return [TextContent(type="text", text=info)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error getting collection info: {str(e)}")]


async def delete_collection_handler(arguments: dict) -> list[TextContent]:
    """컬렉션 삭제"""
    global vectorstore
    
    confirm = arguments.get("confirm", False)
    
    if not confirm:
        return [TextContent(
            type="text",
            text="⚠️  Deletion cancelled. Set 'confirm' to true to delete the collection."
        )]
    
    try:
        vectorstore.delete_collection()
        initialize_vectorstore()
        return [TextContent(type="text", text="✅ Collection successfully deleted and reinitialized.")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error deleting collection: {str(e)}")]


# FastAPI 애플리케이션
@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 실행"""
    print("=" * 60)
    print("🚀 RAG MCP Server (HTTP/SSE) Starting...")
    print("=" * 60)
    
    # 초기화
    initialize_vectorstore()
    initialize_claude()
    initialize_mcp_server()
    
    print("\n✅ Server ready!")
    print(f"📡 Listening on http://0.0.0.0:8000")
    print(f"🔧 SSE endpoint: http://0.0.0.0:8000/sse")
    print("=" * 60 + "\n")
    
    yield
    
    print("\n👋 Shutting down...")


app = FastAPI(
    title="RAG MCP Server",
    description="HTTP/SSE based MCP server for RAG operations",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 요청 로깅 미들웨어
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """모든 요청 로깅"""
    if request.url.path == "/sse":
        try:
            body = await request.body()
            body_str = body.decode('utf-8')
            print(f"📥 Received: {body_str[:200]}")
            
            # body를 다시 읽을 수 있도록 설정
            async def receive():
                return {"type": "http.request", "body": body}
            
            request._receive = receive
        except:
            pass
    
    response = await call_next(request)
    return response


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "name": "RAG MCP Server",
        "version": "1.0.0",
        "endpoints": {
            "sse": "/sse",
            "health": "/health",
            "tools": "/tools"
        }
    }


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "vectorstore": vectorstore is not None,
        "claude_client": anthropic_client is not None,
        "mcp_server": mcp_server is not None
    }


@app.get("/tools")
async def get_tools():
    """사용 가능한 도구 목록 반환"""
    if tools_list_handler is None:
        raise HTTPException(status_code=500, detail="MCP server not initialized")
    
    # list_tools 핸들러 호출
    tools = await tools_list_handler()
    
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema
            }
            for tool in tools
        ]
    }


@app.post("/sse")
async def sse_endpoint(request: Request):
    """SSE (Server-Sent Events) 엔드포인트 - MCP 프로토콜"""
    
    body = None
    try:
        body = await request.json()
        
        # id를 문자열로 변환 (MCP 프로토콜 호환성)
        msg_id = str(body.get("id", "0")) if body.get("id") is not None else "0"
        method = body.get("method", "")
        
        # MCP 메시지 처리
        if method == "initialize":
            # MCP 초기화 핸드셰이크
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "rag-search-server",
                        "version": "1.0.0"
                    }
                }
            }
            return JSONResponse(content=response)
        
        elif method == "notifications/initialized":
            # 초기화 완료 알림 (응답 불필요)
            return JSONResponse(content={"jsonrpc": "2.0"})
        
        elif method == "tools/list":
            tools = await tools_list_handler()
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        }
                        for tool in tools
                    ]
                }
            }
            return JSONResponse(content=response)
        
        elif method == "tools/call":
            params = body.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments", {})
            
            result = await call_tool_handler(name, arguments)
            
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": content.type,
                            "text": content.text
                        }
                        for content in result
                    ]
                }
            }
            return JSONResponse(content=response)
        
        elif method.startswith("notifications/"):
            # 알림 메시지 (응답 불필요)
            return JSONResponse(content={"jsonrpc": "2.0"})
        
        else:
            error_response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            return JSONResponse(content=error_response, status_code=400)
    
    except json.JSONDecodeError as e:
        error_response = {
            "jsonrpc": "2.0",
            "id": "0",
            "error": {
                "code": -32700,
                "message": f"Parse error: {str(e)}"
            }
        }
        return JSONResponse(content=error_response, status_code=400)
    
    except Exception as e:
        msg_id = "0"
        if body and isinstance(body, dict):
            msg_id = str(body.get("id", "0")) if body.get("id") is not None else "0"
        
        error_response = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }
        return JSONResponse(content=error_response, status_code=500)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
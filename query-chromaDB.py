import chromadb
COLLECTION_NAME = "rag_documents"
client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_collection(COLLECTION_NAME)

# 전체 데이터 조회
results = collection.get()
#print(results)

# 검색(query)
query = collection.query(
    query_texts=["summary 'thought of the week' from lag system"],
    n_results=5
)
print(query)
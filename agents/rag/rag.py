from typing import TypedDict
import json
from langgraph.graph import StateGraph,END
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_aws import BedrockEmbeddings,ChatBedrockConverse
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Distance, VectorParams
from litellm import completion
class RAGState(TypedDict):
    question : str
    invoice_id : str

    invoice_text : str
    report_text : str
    documents : list
    context : str
    answer : str
    relevance : float
    groundedness : float
    context_relevance : float
    score : float
    retries : int


#-----------------------
#Embedding Model
#----------------------
embeddings = BedrockEmbeddings(model_id='amazon.titan-embed-text-v1',region_name='us-east-1')

llm=ChatBedrockConverse(model_id='us.anthropic.claude-haiku-4-5-20251001-v1:0',region_name='us-east-1')
#-----------------------
#Text Splitter
#-----------------------
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size = 500,
    chunk_overlap = 50
)
qdrant_client = QdrantClient(path="./qdrant_data")
COLLECTION_NAME = "invoice_collection"
print(embeddings.embed_query("test")[:5])
#Create collection if not exists
if not qdrant_client.collection_exists(COLLECTION_NAME):
    dimension=len(embeddings.embed_query("test"))
    qdrant_client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
size=dimension, distance=Distance.COSINE
        )
    )

vector_store = QdrantVectorStore(collection_name="invoice_collection",
    client=qdrant_client,
    embedding=embeddings)
#-----------------------
#Indexing AGENT
#-----------------------
def indexing_agent(state:RAGState):
    #Load processed invoice/report text
    documents = [
        Document(page_content=state['invoice_text'],metadata={"type":"invoice","invoice_id":state['invoice_id']}),
        Document(page_content=state['report_text'],metadata={"type":"report","invoice_id":state['invoice_id']})
    ]
    #split using RecursiveCharacterTextSplitter
    chunks = text_splitter.split_documents(documents)
    #Create embeddings and store in Qdrant
    vector_store.add_documents(chunks)
    state['documents'] = chunks
    return state

#-----------------------
#Retrieval AGENT
#-----------------------
def retrieval_agent(state:RAGState):
    question = state['question']
    invoice_id = state['invoice_id']

    #Search Qdrant
    #Apply invoice_id filter if provided
    filter_condition = Filter(
        must=[FieldCondition(key='metadata.invoice_id',
                             match=MatchValue(value=invoice_id))]
    )

    retriever = vector_store.as_retriever(search_kwargs={'k':5, 'filter':filter_condition})
    docs = retriever.invoke(question)
    state['documents'] = docs
    state['retries'] += 1

    return state

#----------------------
#Augmentation AGENT
#----------------------
def augmentation_agent(state:RAGState):
    documents = state['documents']
    #Simple reranking
    #Keep most relevant retrieved chunks
    documents = documents[:5]
    #Assemble chunks into one context
    context_parts=[]
    for i,doc in enumerate(documents,start=1):
        context_parts.append(f"[Document {i}]\n {doc.page_content}")
    context='\n\n'.join(context_parts)
    state['context'] = context
    return state

#----------------------
#Generation AGENT
#----------------------
def generation_agent(state:RAGState):
    question = state['question']
    context = state['context']
    prompt = f"""
                You are an AI Invoice Auditor.
                Answer the user's question using only the provided context.
                If the answer is not contained within the context, say that information is not available.
                Context: {context}
                Question: {question}
                Give a concise and accurate answer based on the context.
              """
    #Call LiteLLM
    response = llm.invoke(prompt)
    answer = response.content
    state['answer'] = answer
    return state

#----------------------
#Reflection AGENT
#----------------------
def reflection_agent(state:RAGState):
    question = state['question']
    context = state['context']
    answer = state['answer']
    prompt = f"""
    You are evaluating a RAG system.
    Evaluate the following:
    Question: {question}
    Context: {context}
    Generated Answer: {answer}
    Give a score between 0 and 1 for each of the following criteria:
    context relevance:
    Is the retrieved context relevant to the question? (0=not relevant, 1=highly relevant)
    groundedness:
    Is the generated answer supported by the context? (0=not grounded, 1=fully grounded)
    answer relevance:
    Does the answer directly answer the question? (0=not relevant, 1=highly
    return only valid JSON strictly in the following format:
    {{
        "context_relevance": <score>,
        "groundedness": <score>,
        "relevance": <score>
    }}
    """
    response = llm.invoke(prompt).content
    print("Reflection Response:", response[7:-3])
    result=json.loads(response[7:-3])


    #RAG Triad evaluation
    # Relevance , Groundedness , Context relevance

    state['context_relevance'] = result['context_relevance']
    state['groundedness'] = result['groundedness']
    state['relevance'] = result['relevance']

    state['score'] = (state['relevance']+
                      state['groundedness']+
                      state['context_relevance'])/3
    return state

#----------------------
#Decision
#----------------------
def check_score(state:RAGState):
    if state['score'] > 0.7:
        return 'finish'
    if state['retries'] >= 3:
        return 'finish'
    return 'retry'



#----------------------
# Langgraph
#----------------------
graph = StateGraph(RAGState)

graph.add_node("indexing", indexing_agent)
graph.add_node("retrieval", retrieval_agent)
graph.add_node("augmentation", augmentation_agent)
graph.add_node("generation",generation_agent)
graph.add_node("reflection", reflection_agent)

graph.set_entry_point('indexing')
graph.add_edge('indexing','retrieval')
graph.add_edge('retrieval','augmentation')
graph.add_edge('augmentation', 'generation')
graph.add_edge('generation','reflection')
graph.add_conditional_edges('reflection',check_score,{'finish':END,
                                                     "retry":"retrieval"})

app = graph.compile()


#test with sample data
if __name__ == "__main__":
    #Sample data
    state:RAGState = {
        "question":"What is the capital of India?",
        "invoice_id":"INV-001",
        "invoice_text":"Invoice INV-001\nDate: 2023-08-01\nTotal Amount Due: $1,500.00\nDue Date: 2023-08-15\n",
        "report_text":"Report for Invoice INV-001\nThe invoice was issued on 2023-08-01 and is due by 2023-08-15. The total amount due is $1,500.00.",
        "documents":[],
        "context":"",
        "answer":"",
        "relevance":0.0,
        "groundedness":0.0,
        "context_relevance":0.0,
        "score":0.0,
        "retries":0
    }

    final_state = app.invoke(state)
    print("Final State:")
    print(final_state)
    qdrant_client.close()
# DAW Drug Search System - Architecture Diagram

```mermaid
graph TB
    subgraph "Client Layer"
        User[User Browser]
        UI[React Frontend]
    end
    
    subgraph "API Gateway"
        APIGW[API Gateway<br/>HTTPS]
    end
    
    subgraph "Lambda Functions"
        SearchLambda[Search Function<br/>1024 MB<br/>Provisioned Concurrency]
        AltLambda[Alternatives Function<br/>256 MB]
        DetailLambda[Drug Detail Function<br/>256 MB]
    end
    
    subgraph "AWS Bedrock"
        LLM[LLM Service<br/>Claude Sonnet 4<br/>Nova Micro<br/>Claude Haiku 3]
        Titan[Titan Embeddings<br/>v2:0<br/>1024 dimensions]
    end
    
    subgraph "VPC - Private Subnets"
        Redis[Redis Stack 8.2.2<br/>EC2 r7g.large<br/>Vector Search + Filters<br/>LeanVec4x8 Quantized]
        Aurora[Aurora PostgreSQL<br/>FDB Drug Database<br/>Enrichment Data]
    end
    
    subgraph "Data Flow"
        Query[User Query:<br/>'tastosterne 200 mg vial']
    end
    
    %% User to API
    User -->|HTTPS| UI
    UI -->|POST /search| APIGW
    
    %% API Gateway to Lambdas
    APIGW -->|Route| SearchLambda
    APIGW -->|Route| AltLambda
    APIGW -->|Route| DetailLambda
    
    %% Search Flow
    SearchLambda -->|1. Query Understanding<br/>Converse API| LLM
    LLM -->|Extracted Drug Names<br/>Filters| SearchLambda
    
    SearchLambda -->|2. Generate Embedding<br/>invoke_model| Titan
    Titan -->|1024-dim Vector| SearchLambda
    
    SearchLambda -->|3. Hybrid Search<br/>FT.SEARCH KNN| Redis
    Redis -->|Drug IDs + Metadata| SearchLambda
    
    SearchLambda -->|4. Enrichment<br/>SQL Query| Aurora
    Aurora -->|Full Drug Details| SearchLambda
    
    SearchLambda -->|5. Group & Sort<br/>Match Type Badges| SearchLambda
    SearchLambda -->|JSON Response| APIGW
    
    %% Alternatives Flow
    AltLambda -->|Get Alternatives<br/>by GCN| Redis
    Redis -->|Alternative NDCs| AltLambda
    AltLambda -->|Enrich| Aurora
    Aurora -->|Details| AltLambda
    
    %% Detail Flow
    DetailLambda -->|Get by NDC| Redis
    Redis -->|Drug Data| DetailLambda
    DetailLambda -->|Enrich| Aurora
    Aurora -->|Full Details| DetailLambda
    
    %% Response Flow
    APIGW -->|JSON| UI
    UI -->|Display Results| User
    
    %% Styling
    classDef lambda fill:#4A90E2,stroke:#333,stroke-width:2px,color:#fff
    classDef bedrock fill:#50C878,stroke:#333,stroke-width:2px,color:#fff
    classDef storage fill:#7B68EE,stroke:#333,stroke-width:2px,color:#fff
    classDef api fill:#FFA500,stroke:#333,stroke-width:2px,color:#fff
    classDef client fill:#E0E0E0,stroke:#333,stroke-width:2px
    
    class SearchLambda,AltLambda,DetailLambda lambda
    class LLM,Titan bedrock
    class Redis,Aurora storage
    class APIGW api
    class User,UI client
```

## Component Details

### Lambda Functions
- **Search Function**: Main search handler with LLM preprocessing, vector search, and result grouping
- **Alternatives Function**: Finds pharmacological and therapeutic alternatives
- **Drug Detail Function**: Returns full drug information by NDC

### AWS Bedrock Services
- **LLM (Converse API)**: Query understanding, spelling correction, filter extraction
- **Titan Embeddings**: Generates 1024-dimensional vectors for semantic search

### Data Stores
- **Redis Stack 8.2.2**: Vector search index with LeanVec4x8 quantization, hybrid search (KNN + filters)
- **Aurora PostgreSQL**: FDB drug database for enrichment (indications, contraindications, etc.)

### Performance Optimizations
- **Provisioned Concurrency**: Pre-warmed Lambda instances (zero cold starts)
- **1024 MB Memory**: 2x CPU power for faster processing
- **LeanVec4x8 Quantization**: 3x memory reduction in Redis
- **Multi-drug Search**: Individual vector searches per drug for better recall


# DAW Drug Search System - High-Level Architecture

```mermaid
graph TB
    subgraph "Client"
        User[User]
        Frontend[React Frontend]
    end
    
    subgraph "API Layer"
        API[API Gateway]
    end
    
    subgraph "Compute Layer"
        Lambda[AWS Lambda<br/>Search Functions]
    end
    
    subgraph "AI Services"
        LLM[Bedrock LLM<br/>Query Understanding]
        Embeddings[Bedrock Titan<br/>Vector Embeddings]
    end
    
    subgraph "Data Layer"
        Redis[Redis Stack 8.2.2<br/>Vector Search<br/>EC2]
        Database[Aurora PostgreSQL<br/>FDB Drug Database]
    end
    
    %% Flow
    User --> Frontend
    Frontend --> API
    API --> Lambda
    
    Lambda --> LLM
    LLM --> Lambda
    
    Lambda --> Embeddings
    Embeddings --> Lambda
    
    Lambda --> Redis
    Redis --> Lambda
    
    Lambda --> Database
    Database --> Lambda
    
    Lambda --> API
    API --> Frontend
    Frontend --> User
    
    %% Styling
    classDef client fill:#E0E0E0,stroke:#333,stroke-width:2px
    classDef api fill:#FFA500,stroke:#333,stroke-width:2px,color:#fff
    classDef compute fill:#4A90E2,stroke:#333,stroke-width:2px,color:#fff
    classDef ai fill:#50C878,stroke:#333,stroke-width:2px,color:#fff
    classDef storage fill:#7B68EE,stroke:#333,stroke-width:2px,color:#fff
    
    class User,Frontend client
    class API api
    class Lambda compute
    class LLM,Embeddings ai
    class Redis,Database storage
```

## High-Level Components

### Client Layer
- **React Frontend**: User interface for drug search
- **User**: End users (healthcare providers)

### API Layer
- **API Gateway**: HTTPS endpoint, request routing, CORS handling

### Compute Layer
- **AWS Lambda**: Serverless functions for search, alternatives, and drug details
  - Provisioned Concurrency (zero cold starts)
  - VPC-connected for secure database access

### AI Services
- **Bedrock LLM**: Natural language query understanding
  - Spelling correction
  - Medical terminology expansion
  - Filter extraction
- **Bedrock Titan**: Vector embeddings (1024 dimensions)
  - Semantic similarity search

### Data Layer
- **Redis Stack 8.2.2**: Vector search engine
  - Hybrid search (KNN + filters)
  - LeanVec4x8 quantization
  - Self-managed on EC2
- **Aurora PostgreSQL**: Drug database
  - FDB drug information
  - Enrichment data (indications, contraindications, etc.)

## Data Flow

1. **User Query** → Frontend → API Gateway
2. **Query Understanding** → Lambda → Bedrock LLM
3. **Embedding Generation** → Lambda → Bedrock Titan
4. **Vector Search** → Lambda → Redis Stack
5. **Data Enrichment** → Lambda → Aurora PostgreSQL
6. **Results** → Lambda → API Gateway → Frontend → User


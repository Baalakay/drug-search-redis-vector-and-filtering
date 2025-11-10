# DAW Drug Search Implementation Plan
**Version:** 1.0  
**Date:** 2025-11-06  
**Architecture:** Titan + Redis Stack 8.2.2 (LeanVec4x8 Quantized) on EC2 + Aurora (with SapBERT upgrade path)

---

## 🎯 Project Overview

Build a highly accurate drug search system for the DAW e-prescribing platform that:
- Handles medical terminology, abbreviations, and misspellings
- Supports semantic + filter-based hybrid search
- Returns enriched drug information from FDB data
- Can upgrade to medical-specific embeddings (SapBERT) later

---

## 🏗️ Architecture

### High-Level Flow

```
User Query: "statin for high cholestrl"
    ↓
┌─────────────────────────────────────┐
│ Claude Sonnet 4 (Bedrock)           │
│ - Spell correction                  │
│ - Medical abbreviation expansion    │
│ - Entity extraction                 │
│ - Filter extraction                 │
└──────────────┬──────────────────────┘
               ↓
    {
      "search_text": "atorvastatin rosuvastatin simvastatin statin",
      "filters": {
        "drug_class": "statin",
        "indication": "hyperlipidemia"
      }
    }
               ↓
┌─────────────────────────────────────┐
│ Embedding Service (Abstraction)     │
│ Implementation: Titan v2            │
│ Future: SapBERT (SageMaker)         │
└──────────────┬──────────────────────┘
               ↓
    [0.12, -0.33, ..., 0.56]  (1024 floats)
               ↓
┌─────────────────────────────────────┐
│ Redis Stack 8.2.2 Hybrid Search     │
│ - Vector similarity (LeanVec4x8)    │
│ - Simultaneous filter application   │
│ - Returns pre-filtered drug IDs     │
└──────────────┬──────────────────────┘
               ↓
    [drug_id: 12345, drug_id: 67890, ...] (20 results)
               ↓
┌─────────────────────────────────────┐
│ Aurora PostgreSQL Enrichment        │
│ - Batch fetch full drug records     │
│ - FDB data with all metadata        │
└──────────────┬──────────────────────┘
               ↓
    Complete enriched drug results
               ↓
    API Response (JSON)
```

---

## 📊 Database Schema Analysis

### FDB Tables (Key Tables for Drug Search)

#### **Primary Drug Table: `rndc14`**
```sql
-- NDC (National Drug Code) - Main drug identifier
Key fields:
- NDC (varchar 11) - Primary drug identifier
- GCN_SEQNO (mediumint) - Generic code number
- LN (varchar 30) - Label name (drug name)
- BN (varchar 30) - Brand name
- DEA (varchar 1) - DEA schedule (controlled substance)
- LBLRID (varchar 6) - Labeler ID
- DF (varchar 1) - Dosage form code
- INNOV (varchar 1) - Innovator flag (brand vs generic)
```

#### **Generic Classification: `rgcnseq4`**
```sql
-- GCN Sequence - Drug grouping and classification
Key fields:
- GCN_SEQNO (mediumint) - Primary key
- HIC3 (varchar 3) - Hierarchical ingredient code (top level)
- HICL_SEQNO (mediumint) - Hierarchical ingredient code level
- GCRT (varchar 1) - Route of administration
- STR (varchar 10) - Strength
- STR60 (varchar 60) - Strength description
- GTC (smallint) - Generic Therapeutic Class
- TC (smallint) - Therapeutic Class
```

#### **Pricing: `rnp2`**
```sql
-- National Price File
Key fields:
- NDC (varchar 11)
- NPT_TYPE (varchar 2) - Price type
- NPT_DATEC (datetime) - Price effective date
- NPT_PRICEX (decimal) - Price
```

### Additional Relevant Tables
- `rdlimxx` tables: Drug-indication linkages
- `rddcmxx` tables: Drug-drug interactions
- `rdamagd` tables: Drug-disease interactions
- `rsidexx` tables: Side effects
- `rpregxx` tables: Pregnancy categories
- `rlactxx` tables: Lactation data

---

## 🔧 Implementation Phases

### **Phase 1: Infrastructure Setup** (Week 1)

#### 1.1 Aurora RDS Setup (SST)
```typescript
// infra/database.ts
export function Database(stack: string) {
  const vpc = new sst.aws.Vpc("DawVpc", { nat: "ec2" });
  
  const cluster = new sst.aws.Postgres("DawDb", {
    version: "15.5",
    vpc,
    scaling: {
      min: "0.5 ACU",
      max: "4 ACU"
    }
  });
  
  return { cluster, vpc };
}
```

**Tasks:**
- [ ] Create VPC with private subnets
- [ ] Deploy Aurora PostgreSQL 15.5 (Serverless v2)
- [ ] Configure security groups
- [ ] Set up Parameter Store for connection strings
- [ ] Import FDB tables from `database/imports/fdb tables.sql`
- [ ] Create indexes on key columns (NDC, GCN_SEQNO, drug names)

#### 1.2 Redis Stack 8.2.2 on EC2 Setup (SST)
```typescript
// infra/redis-ec2.ts (already created)
// Self-managed Redis Stack 8.2.2 on EC2 r7g.large ARM Graviton3
// Reason: ElastiCache only supports Redis 7.1, no quantization support
// See docs/REDIS_INFRASTRUCTURE_DECISION.md for full rationale

export function RedisEC2(vpc: $util.Output<any>) {
  // Security group, EC2 instance, user-data script
  // Installs Redis Stack 8.2.2 with LeanVec4x8 support
    nodeType: "cache.r7g.large",  // ARM-based, cost-effective
    numCacheClusters: 1,
    parameterGroupName: "default.redis7",
    port: 6379,
    subnetGroupName: subnetGroup.name,
    atRestEncryptionEnabled: true,
    transitEncryptionEnabled: true
  });
  
  return { redis, subnetGroup };
}
```

**Tasks:**
- [ ] Deploy Redis Stack 8.2.2 on EC2 r7g.large (code already complete in infra/redis-ec2.ts)
- [ ] Configure VPC security groups (already complete)
- [ ] Store connection details in Parameter Store (already configured)
- [ ] Create Redis client wrapper

---

### **Phase 2: Embedding Abstraction Layer** (Week 1-2)

#### 2.1 Create Swappable Embedding Interface

**Goal:** Make it trivial to switch between Titan and SapBERT

```python
# packages/core/src/embedding/base.py
from abc import ABC, abstractmethod
from typing import List
import numpy as np

class EmbeddingModel(ABC):
    """Abstract base class for embedding models"""
    
    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for multiple texts"""
        pass
    
    @abstractmethod
    def dimension(self) -> int:
        """Return embedding dimension"""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return model identifier"""
        pass
```

#### 2.2 Titan Implementation

```python
# packages/core/src/embedding/titan.py
import json
import numpy as np
from .base import EmbeddingModel
from core.config.llm_config import get_embedding_config, get_bedrock_client

class TitanEmbedding(EmbeddingModel):
    """AWS Bedrock Titan Embeddings v2"""
    
    def __init__(self):
        # Get config from centralized config file
        self.config = get_embedding_config()
        self.client = get_bedrock_client("bedrock-runtime")
        self.model_id = self.config["model_id"]
        self._dimension = self.config["dimensions"]
    
    def embed(self, text: str) -> np.ndarray:
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({"inputText": text})
        )
        result = json.loads(response['body'].read())
        return np.array(result['embedding'], dtype=np.float32)
    
    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        # Titan doesn't support batch, so we iterate
        # (Can parallelize with asyncio if needed)
        return [self.embed(text) for text in texts]
    
    def dimension(self) -> int:
        return self._dimension
    
    @property
    def model_name(self) -> str:
        return "titan-embed-v2"
```

#### 2.3 SapBERT Implementation (Future)

```python
# packages/core/src/embedding/sapbert.py
import json
import numpy as np
from .base import EmbeddingModel
from core.config.llm_config import get_embedding_config, get_sagemaker_client

class SapBERTEmbedding(EmbeddingModel):
    """SageMaker SapBERT endpoint"""
    
    def __init__(self):
        # Get config from centralized config file
        self.config = get_embedding_config()
        self.client = get_sagemaker_client()
        self.endpoint_name = self.config["endpoint_name"]
        self._dimension = self.config["dimensions"]
    
    def embed(self, text: str) -> np.ndarray:
        response = self.client.invoke_endpoint(
            EndpointName=self.endpoint_name,
            ContentType='application/json',
            Body=json.dumps({"text": text})
        )
        result = json.loads(response['Body'].read())
        return np.array(result['embedding'], dtype=np.float32)
    
    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        # SapBERT can handle batch
        response = self.client.invoke_endpoint(
            EndpointName=self.endpoint_name,
            ContentType='application/json',
            Body=json.dumps({"texts": texts})
        )
        result = json.loads(response['Body'].read())
        return [np.array(emb, dtype=np.float32) for emb in result['embeddings']]
    
    def dimension(self) -> int:
        return self._dimension
    
    @property
    def model_name(self) -> str:
        return "sapbert"
```

#### 2.4 Factory Pattern

```python
# packages/core/src/embedding/__init__.py
from .base import EmbeddingModel
from .titan import TitanEmbedding
from .sapbert import SapBERTEmbedding
from core.config.llm_config import EMBEDDING_MODEL_TYPE

def get_embedding_model() -> EmbeddingModel:
    """Factory function to get configured embedding model from centralized config"""
    
    if EMBEDDING_MODEL_TYPE == "titan":
        return TitanEmbedding()
    elif EMBEDDING_MODEL_TYPE == "sapbert":
        return SapBERTEmbedding()
    else:
        raise ValueError(f"Unknown embedding model: {EMBEDDING_MODEL_TYPE}")

__all__ = ["EmbeddingModel", "get_embedding_model"]
```

**Usage:**
```python
# In any Lambda function
from core.embedding import get_embedding_model

embedding_model = get_embedding_model()  # Returns Titan by default
vector = embedding_model.embed("atorvastatin")
```

**To switch to SapBERT later:**
```bash
# Just set environment variable in SST
EMBEDDING_MODEL=sapbert
SAPBERT_ENDPOINT_NAME=sapbert-prod-endpoint
```

---

### **Phase 3: Redis Setup** (Week 2)

#### 3.1 Redis Data Structure

```python
# packages/core/src/redis/schema.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class DrugRedisRecord:
    """What we store in Redis for each drug"""
    drug_id: str              # NDC code
    embedding: bytes          # Quantized vector (INT8)
    
    # Filter fields
    drug_class: str           # Therapeutic class
    indication: str           # Pipe-separated indications
    drug_type: str            # prescription|otc
    is_generic: int           # 0 or 1
    is_controlled: int        # 0 or 1
    dea_schedule: str         # Empty or schedule_2, schedule_3, etc.
    route: str                # oral, injection, topical, etc.
    
    # Preview fields (optional)
    name: str                 # Label name
    brand_name: str           # Brand name (if applicable)
```

#### 3.2 Create Redis Index

```python
# packages/core/src/redis/index.py
from redis import Redis
from redis.commands.search.field import (
    VectorField, TagField, NumericField, TextField
)
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

def create_drug_search_index(redis_client: Redis, embedding_dim: int = 1024):
    """Create Redis search index with quantization"""
    
    schema = [
        # Vector field with INT8 quantization
        VectorField(
            "embedding",
            "HNSW",
            {
                "TYPE": "FLOAT32",
                "DIM": embedding_dim,
                "DISTANCE_METRIC": "COSINE",
                "INITIAL_CAP": 100000,  # Expect ~100k drugs
                "M": 40,
                "EF_CONSTRUCTION": 200,
                "EF_RUNTIME": 100,
                "QUANTIZATION": "LEANVEC4X8"  # ← Redis Stack 8.2.2 feature!
            }
        ),
        
        # Filter fields
        TagField("drug_class"),
        TagField("indication", separator="|"),
        TagField("drug_type"),
        NumericField("is_generic"),
        NumericField("is_controlled"),
        TagField("dea_schedule"),
        TagField("route"),
        
        # Preview/search fields
        TextField("name", weight=2.0),
        TextField("brand_name", weight=1.5)
    ]
    
    try:
        redis_client.ft("drugs_idx").create_index(
            schema,
            definition=IndexDefinition(
                prefix=["drug:"],
                index_type=IndexType.HASH
            )
        )
        print("✅ Redis drug search index created")
    except Exception as e:
        if "Index already exists" not in str(e):
            raise
        print("ℹ️  Redis index already exists")
```

#### 3.3 Hybrid Search Query

```python
# packages/core/src/redis/search.py
from typing import List, Dict, Optional
from redis import Redis
from redis.commands.search.query import Query
import numpy as np

def hybrid_drug_search(
    redis_client: Redis,
    embedding: np.ndarray,
    filters: Optional[Dict] = None,
    limit: int = 20
) -> List[Dict]:
    """
    Perform hybrid vector + filter search
    
    Args:
        redis_client: Redis connection
        embedding: Query embedding vector
        filters: Dict of filters (drug_class, indication, etc.)
        limit: Max results to return
    
    Returns:
        List of {drug_id, score, name, brand_name}
    """
    
    # Build filter string
    filter_clauses = []
    
    if filters:
        if "drug_class" in filters and filters["drug_class"]:
            classes = filters["drug_class"]
            if isinstance(classes, str):
                classes = [classes]
            filter_clauses.append(f"@drug_class:{{{' | '.join(classes)}}}")
        
        if "indication" in filters and filters["indication"]:
            indications = filters["indication"]
            if isinstance(indications, str):
                indications = [indications]
            filter_clauses.append(f"@indication:{{{' | '.join(indications)}}}")
        
        if "drug_type" in filters and filters["drug_type"]:
            filter_clauses.append(f"@drug_type:{{{filters['drug_type']}}}")
        
        if "is_generic" in filters:
            filter_clauses.append(f"@is_generic:[{filters['is_generic']} {filters['is_generic']}]")
        
        if "is_controlled" in filters:
            filter_clauses.append(f"@is_controlled:[{filters['is_controlled']} {filters['is_controlled']}]")
    
    # Combine filters
    filter_str = " ".join(filter_clauses) if filter_clauses else "*"
    
    # Build query with KNN
    query_str = f"({filter_str})=>[KNN {limit} @embedding $vector AS score]"
    
    query = (
        Query(query_str)
        .sort_by("score")
        .return_fields("drug_id", "score", "name", "brand_name")
        .dialect(2)
    )
    
    # Execute search
    results = redis_client.ft("drugs_idx").search(
        query,
        query_params={"vector": embedding.tobytes()}
    )
    
    # Format results
    return [
        {
            "drug_id": doc.drug_id,
            "score": float(doc.score),
            "name": doc.name,
            "brand_name": getattr(doc, "brand_name", "")
        }
        for doc in results.docs
    ]
```

---

### **Phase 4: Claude Query Parser** (Week 2-3)

#### 4.1 Medical Terminology Prompt

```python
# packages/core/src/llm/prompts.py
MEDICAL_SEARCH_SYSTEM_PROMPT = """You are a medical search query processor for an e-prescribing drug database.

Your job: Transform user queries into structured search parameters.

MEDICAL ABBREVIATIONS:
- ASA → aspirin, acetylsalicylic acid
- ACEI → ACE inhibitor, angiotensin-converting enzyme inhibitor
- ARB → angiotensin receptor blocker
- BB → beta blocker
- CCB → calcium channel blocker
- NSAID → non-steroidal anti-inflammatory drug, NSAID
- PPI → proton pump inhibitor
- SSRI → selective serotonin reuptake inhibitor
- TCA → tricyclic antidepressant
- DM → diabetes mellitus
- HTN → hypertension
- CHF → congestive heart failure
- COPD → chronic obstructive pulmonary disease
- CVD → cardiovascular disease
- MI → myocardial infarction
- PE → pulmonary embolism
- DVT → deep vein thrombosis
- UTI → urinary tract infection

DRUG CLASS EXPANSIONS:
- Statin → atorvastatin, rosuvastatin, simvastatin, pravastatin, lovastatin, fluvastatin, pitavastatin, Lipitor, Crestor, Zocor
- Beta blocker → metoprolol, atenolol, carvedilol, propranolol, labetalol, bisoprolol, Lopressor, Toprol
- ACE inhibitor → lisinopril, enalapril, ramipril, benazepril, captopril, perindopril, Vasotec, Altace
- ARB → losartan, valsartan, irbesartan, olmesartan, candesartan, Cozaar, Diovan, Avapro
- Diabetes drug → metformin, glipizide, glyburide, insulin, Glucophage, Glucotrol

COMMON INDICATIONS:
- "cholesterol" → hyperlipidemia, dyslipidemia
- "blood pressure" → hypertension
- "diabetes" → diabetes mellitus, hyperglycemia
- "pain" → pain management, analgesia
- "infection" → bacterial infection, antibiotic
- "heart failure" → congestive heart failure, CHF

COMMON MISSPELLINGS:
- "cholestrl" → cholesterol
- "metformen" → metformin
- "diabetis" → diabetes
- "atorvastain" → atorvastatin
- "lisinipril" → lisinopril
- "aspirn" → aspirin

Return JSON with:
{
  "search_text": "embedding-optimized text with drug names and synonyms",
  "filters": {
    "drug_class": "therapeutic_class_if_specified",
    "indication": "indication_if_specified",
    "drug_type": "prescription|otc if determinable"
  },
  "corrections": ["original → corrected"],
  "confidence": 0.0-1.0
}
"""

MEDICAL_SEARCH_USER_TEMPLATE = """User query: "{query}"

Parse this query and return structured search parameters."""
```

#### 4.2 Claude Integration with Caching

```python
# packages/core/src/llm/claude.py
import json
import boto3
from typing import Dict
from core.config.llm_config import get_llm_config

class ClaudeQueryParser:
    def __init__(self):
        # Get config from centralized config file
        self.config = get_llm_config()
        self.client = boto3.client(
            "bedrock-runtime", 
            region_name=self.config["region"]
        )
        self.model_id = self.config["model_id"]
    
    def parse_query(self, user_query: str) -> Dict:
        """Parse user query into structured search parameters using Converse API"""
        
        # Build system prompt with caching
        system = [
            {
                "text": MEDICAL_SEARCH_SYSTEM_PROMPT,
                "cachePoint": {"type": "default"}  # Converse API cache
            }
        ]
        
        # Build messages
        messages = [
            {
                "role": "user",
                "content": [
                    {"text": MEDICAL_SEARCH_USER_TEMPLATE.format(query=user_query)}
                ]
            }
        ]
        
        # Call Bedrock Converse API
        response = self.client.converse(
            modelId=self.model_id,
            system=system,
            messages=messages,
            inferenceConfig={
                "maxTokens": self.config.get("max_tokens", 1000),
                "temperature": self.config.get("temperature", 0)
            }
        )
        
        # Extract text from response
        content = response['output']['message']['content'][0]['text']
        
        # Parse JSON (Claude should return valid JSON)
        try:
            parsed = json.loads(content)
            return parsed
        except json.JSONDecodeError:
            # Fallback: use query as-is
            return {
                "search_text": user_query,
                "filters": {},
                "corrections": [],
                "confidence": 0.5
            }
```

---

### **Phase 5: Data Sync Pipeline** (Week 3)

#### 5.1 Aurora → Redis Sync

```python
# functions/sync/drug_loader.py
import psycopg2
from redis import Redis
from core.embedding import get_embedding_model
import numpy as np

def sync_drugs_to_redis(limit: Optional[int] = None):
    """
    Load drugs from Aurora and sync to Redis with embeddings
    
    Args:
        limit: Optional limit for testing (e.g., 1000 drugs)
    """
    
    # Connect to Aurora
    db = psycopg2.connect(os.environ["DATABASE_URL"])
    cursor = db.cursor()
    
    # Connect to Redis
    redis_client = Redis.from_url(os.environ["REDIS_URL"])
    
    # Get embedding model
    embedding_model = get_embedding_model()
    
    # Query drugs with key information
    query = """
        SELECT 
            ndc.NDC as drug_id,
            ndc.LN as name,
            ndc.BN as brand_name,
            ndc.DEA as dea_code,
            ndc.INNOV as is_generic_flag,
            gcn.HIC3 as drug_class_code,
            gcn.GCRT as route_code,
            gcn.STR60 as strength
        FROM rndc14 ndc
        LEFT JOIN rgcnseq4 gcn ON ndc.GCN_SEQNO = gcn.GCN_SEQNO
        WHERE ndc.LN IS NOT NULL
        {}
        ORDER BY ndc.NDC
    """.format(f"LIMIT {limit}" if limit else "")
    
    cursor.execute(query)
    
    # Process in batches
    batch_size = 100
    batch = []
    total_synced = 0
    
    for row in cursor:
        drug_id, name, brand_name, dea, is_generic_flag, drug_class, route, strength = row
        
        # Create text for embedding
        text_parts = [
            name or "",
            brand_name or "",
            drug_class or "",
            strength or ""
        ]
        text_for_embedding = " ".join(filter(None, text_parts))
        
        # Generate embedding
        embedding = embedding_model.embed(text_for_embedding)
        
        # Map codes to human-readable values (would need lookup tables)
        drug_type = "prescription"  # Default, could enhance with logic
        is_generic = 0 if is_generic_flag == 'Y' else 1
        is_controlled = 1 if dea and dea != ' ' else 0
        dea_schedule = f"schedule_{dea}" if is_controlled else ""
        
        # Store in Redis
        redis_key = f"drug:{drug_id}"
        redis_client.hset(redis_key, mapping={
            "drug_id": drug_id,
            "embedding": embedding.tobytes(),
            "name": name or "",
            "brand_name": brand_name or "",
            "drug_class": drug_class or "",
            "indication": "",  # Would need to join indication tables
            "drug_type": drug_type,
            "is_generic": is_generic,
            "is_controlled": is_controlled,
            "dea_schedule": dea_schedule,
            "route": route or ""
        })
        
        total_synced += 1
        
        if total_synced % 100 == 0:
            print(f"Synced {total_synced} drugs...")
    
    print(f"✅ Total synced: {total_synced} drugs")
    
    cursor.close()
    db.close()
```

#### 5.2 Lambda Function for Sync

```typescript
// infra/sync.ts
export function SyncJobs() {
  const syncDrugs = new sst.aws.Function("SyncDrugsToRedis", {
    handler: "functions/sync/drug_loader.handler",
    runtime: "python3.12",
    timeout: "15 minutes",
    memory: "2 GB",
    environment: {
      EMBEDDING_MODEL: "titan",
      DATABASE_URL: db.cluster.url,
      REDIS_URL: redis.connectionString
    },
    permissions: [
      {
        actions: ["bedrock:InvokeModel"],
        resources: ["arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0"]
      }
    ]
  });
  
  return { syncDrugs };
}
```

---

### **Phase 6: Search API** (Week 4)

#### 6.1 Search Lambda Handler

```python
# functions/api/drug_search.py
import json
from core.llm.claude import ClaudeQueryParser
from core.embedding import get_embedding_model
from core.redis.search import hybrid_drug_search
from redis import Redis
import psycopg2

def handler(event, context):
    """
    Drug search API handler
    
    POST /api/drugs/search
    Body: {
      "query": "statin for high cholesterol",
      "limit": 20
    }
    """
    
    # Parse request
    body = json.loads(event.get("body", "{}"))
    user_query = body.get("query", "")
    limit = body.get("limit", 20)
    
    if not user_query:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Query is required"})
        }
    
    # Step 1: Parse query with Claude
    parser = ClaudeQueryParser()
    parsed = parser.parse_query(user_query)
    
    # Step 2: Generate embedding
    embedding_model = get_embedding_model()
    embedding = embedding_model.embed(parsed["search_text"])
    
    # Step 3: Search Redis with filters
    redis_client = Redis.from_url(os.environ["REDIS_URL"])
    redis_results = hybrid_drug_search(
        redis_client,
        embedding,
        filters=parsed.get("filters", {}),
        limit=limit
    )
    
    if not redis_results:
        return {
            "statusCode": 200,
            "body": json.dumps({
                "query": user_query,
                "results": [],
                "parsed": parsed
            })
        }
    
    # Step 4: Enrich from Aurora
    drug_ids = [r["drug_id"] for r in redis_results]
    enriched_drugs = fetch_drug_details(drug_ids)
    
    # Step 5: Merge scores with full data
    results = []
    for redis_result in redis_results:
        drug_id = redis_result["drug_id"]
        if drug_id in enriched_drugs:
            results.append({
                **enriched_drugs[drug_id],
                "relevance_score": redis_result["score"]
            })
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "query": user_query,
            "parsed": parsed,
            "results": results,
            "total": len(results)
        })
    }

def fetch_drug_details(drug_ids: List[str]) -> Dict:
    """Batch fetch full drug details from Aurora"""
    
    db = psycopg2.connect(os.environ["DATABASE_URL"])
    cursor = db.cursor()
    
    placeholders = ",".join(["%s"] * len(drug_ids))
    query = f"""
        SELECT 
            ndc.NDC,
            ndc.LN as name,
            ndc.BN as brand_name,
            ndc.DEA,
            ndc.INNOV,
            gcn.STR60 as strength,
            gcn.HIC3 as drug_class
        FROM rndc14 ndc
        LEFT JOIN rgcnseq4 gcn ON ndc.GCN_SEQNO = gcn.GCN_SEQNO
        WHERE ndc.NDC IN ({placeholders})
    """
    
    cursor.execute(query, drug_ids)
    
    results = {}
    for row in cursor:
        ndc, name, brand, dea, innov, strength, drug_class = row
        results[ndc] = {
            "drug_id": ndc,
            "name": name,
            "brand_name": brand,
            "strength": strength,
            "drug_class": drug_class,
            "is_generic": innov != 'Y',
            "is_controlled": bool(dea and dea != ' '),
            "dea_schedule": dea if dea and dea != ' ' else None
        }
    
    cursor.close()
    db.close()
    
    return results
```

#### 6.2 API Gateway Setup

```typescript
// infra/api.ts
export function Api() {
  const api = new sst.aws.ApiGatewayV2("DawApi");
  
  api.route("POST /api/drugs/search", {
    handler: "functions/api/drug_search.handler",
    runtime: "python3.12",
    timeout: "30 seconds",
    memory: "1 GB",
    environment: {
      EMBEDDING_MODEL: "titan",
      DATABASE_URL: db.cluster.url,
      REDIS_URL: redis.connectionString
    },
    permissions: [
      {
        actions: ["bedrock:InvokeModel"],
        resources: [
          "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0",
          "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4*"
        ]
      }
    ]
  });
  
  return { api };
}
```

---

### **Phase 7: Migration to SapBERT** (Future)

When ready to test SapBERT:

#### 7.1 Deploy SageMaker Endpoint

```typescript
// infra/sagemaker.ts (optional future addition)
export function SapBERTEndpoint() {
  // Deploy SapBERT model to SageMaker
  // This is only needed if Titan accuracy isn't sufficient
  
  const endpoint = new aws.sagemaker.Endpoint("SapBertEndpoint", {
    endpointConfigName: endpointConfig.name
  });
  
  return { endpoint };
}
```

#### 7.2 Update Environment Variable

```bash
# In SST config or environment
EMBEDDING_MODEL=sapbert
SAPBERT_ENDPOINT_NAME=sapbert-daw-prod
```

#### 7.3 Re-index Drugs

```bash
# Trigger re-sync with new embeddings
sst shell functions/sync/drug_loader.py --reindex
```

**That's it!** The abstraction layer handles everything else.

---

## 📋 Milestones & Deliverables

### Week 1
- [ ] Aurora RDS deployed with FDB data imported
- [ ] Redis Stack 8.2.2 on EC2 deployed (infra code complete)
- [ ] VPC and networking configured
- [ ] Embedding abstraction layer complete (Titan + SapBERT interfaces)

### Week 2
- [ ] Redis index created with quantization
- [ ] Hybrid search logic implemented
- [ ] Claude query parser with medical prompt
- [ ] Prompt caching configured

### Week 3
- [ ] Data sync pipeline (Aurora → Redis) complete
- [ ] Initial drug indexing (all FDB drugs)
- [ ] Testing sync performance

### Week 4
- [ ] Search API Lambda deployed
- [ ] Aurora enrichment logic complete
- [ ] API Gateway configured
- [ ] End-to-end search working

### Week 5
- [ ] Performance testing and optimization
- [ ] Query accuracy validation
- [ ] Documentation complete

---

## 🧪 Testing Strategy

### Unit Tests
- Embedding model abstraction
- Claude query parser
- Redis search logic
- Aurora enrichment

### Integration Tests
- End-to-end search flow
- Claude → Titan → Redis → Aurora
- Filter combinations
- Edge cases (misspellings, abbreviations)

### Performance Tests
- Search latency (<50ms target)
- Concurrent requests (100+ QPS)
- Large result sets
- Redis memory usage

### Accuracy Tests
- Medical terminology recognition
- Misspelling correction
- Drug class matching
- Brand/generic cross-reference

---

## 💰 Cost Estimates

### Infrastructure (Monthly)

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| **Aurora Serverless v2** | 0.5-4 ACU | ~$50-$200 |
| **Redis Stack EC2** | r7g.large (ARM Graviton3) | ~$104 |
| **NAT Gateway** | 1 instance | ~$30 |
| **Data Transfer** | Moderate | ~$10 |
| **Total Infrastructure** | | **~$210-$360** |

### Usage Costs (per 100k queries)

| Service | Cost per 100k queries |
|---------|----------------------|
| **Claude Sonnet 4** | ~$0.30 (with caching) |
| **Titan Embeddings** | ~$0.01 |
| **Lambda execution** | ~$0.50 |
| **Total per 100k** | **~$0.81** |

**At 1M queries/month:** $8.10 usage + $210-360 infrastructure = **$220-370/month**

---

## 🔄 Upgrade Path: Titan → SapBERT

### When to Consider Upgrade
- Titan accuracy <90% on medical terms
- Users report poor brand/generic matching
- Query volume justifies $500/month SageMaker cost
- Medical abbreviations not being resolved

### Upgrade Steps
1. Deploy SageMaker endpoint with SapBERT
2. Set `EMBEDDING_MODEL=sapbert` environment variable
3. Run re-indexing job (updates all embeddings in Redis)
4. A/B test Titan vs SapBERT results
5. Switch traffic if SapBERT shows improvement

### Cost Impact
- SageMaker: +$500/month (ml.g4dn.xlarge 24/7)
- Total: ~$720-870/month (vs ~$220-370 with Titan)
- Breakeven: If accuracy improvement > 200% cost increase

---

## 📚 Key Files & Structure

```
DAW/
├── infra/
│   ├── database.ts           # Aurora RDS
│   ├── redis-ec2.ts          # Redis Stack 8.2.2 on EC2 (not ElastiCache)
│   ├── network.ts            # VPC, subnets, security groups
│   ├── api.ts                # API Gateway
│   └── sync.ts               # Sync Lambda functions
├── functions/
│   ├── api/
│   │   └── drug_search.py    # Main search handler
│   └── sync/
│       └── drug_loader.py    # Aurora → Redis sync
├── packages/
│   └── core/
│       └── src/
│           ├── embedding/
│           │   ├── base.py         # Abstract interface
│           │   ├── titan.py        # Titan implementation
│           │   ├── sapbert.py      # SapBERT implementation
│           │   └── __init__.py     # Factory
│           ├── llm/
│           │   ├── prompts.py      # Medical terminology prompt
│           │   └── claude.py       # Claude query parser
│           └── redis/
│               ├── schema.py       # Redis data structure
│               ├── index.py        # Index creation
│               └── search.py       # Hybrid search logic
├── database/
│   └── imports/
│       └── fdb tables.sql    # FDB data (source)
└── docs/
    └── IMPLEMENTATION_PLAN.md # This document
```

---

## ✅ Success Criteria

1. **Search Accuracy:** >85% relevant results on medical queries
2. **Latency:** <50ms p95 for search API
3. **Uptime:** >99.9% availability
4. **Cost Efficiency:** <$1 per 100k queries
5. **Scalability:** Handle 500+ QPS without degradation

---

## 🚀 Getting Started

### 1. Deploy Infrastructure
```bash
cd /workspaces/DAW
sst deploy --stage dev
```

### 2. Import FDB Data
```bash
psql $DATABASE_URL < database/imports/fdb\ tables.sql
```

### 3. Create Redis Index
```bash
sst shell python -c "from core.redis.index import create_drug_search_index; create_drug_search_index()"
```

### 4. Sync Drugs to Redis
```bash
sst invoke SyncDrugsToRedis
```

### 5. Test Search
```bash
curl -X POST https://api.daw.dev/api/drugs/search \
  -H "Content-Type: application/json" \
  -d '{"query": "statin for high cholesterol", "limit": 10}'
```

---

## 📞 Next Steps

1. **Review this plan** - Confirm architecture decisions
2. **Update CursorRIPER memory bank** - Document in projectbrief.md, systemPatterns.md, etc.
3. **Begin Phase 1** - Set up Aurora and Redis infrastructure
4. **Iterate** - Build, test, refine

---

**Plan Status:** ✅ Ready for Review  
**Last Updated:** 2025-11-06


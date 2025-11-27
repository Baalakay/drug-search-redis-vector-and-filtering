# Technical Context: DAW Technology Stack

## Technology Stack Overview

### Infrastructure as Code
- **SST v3** - Serverless Stack framework for AWS infrastructure
- **Pulumi** - Under the hood (SST v3 is built on Pulumi)
- **TypeScript** - For infrastructure definitions
- **AWS CDK** - AWS constructs library

### Runtime & Languages
- **Python 3.12** - Lambda function runtime
- **Node.js 20** - For SST CLI and infrastructure
- **TypeScript 5.x** - Type-safe infrastructure code

### AWS Services

#### Compute
- **AWS Lambda** - Serverless function execution
  - Runtime: Python 3.12
  - Memory: 512 MB - 2 GB (depending on function)
  - Timeout: 30 seconds (API) to 15 minutes (sync jobs)

#### API
- **API Gateway v2 (HTTP API)** - REST API endpoint
  - Lower cost than v1
  - Built-in JWT support
  - WebSocket support (future)

#### AI/ML
- **AWS Bedrock** - Managed AI model access
  - **Claude Sonnet 4** (`anthropic.claude-sonnet-4-20250514`)
    - Query parsing and medical terminology
    - Prompt caching for cost efficiency
  - **Titan Embeddings v2** (`amazon.titan-embed-text-v2:0`)
    - Text-to-vector conversion
    - 1024-dimensional embeddings
    - $0.0001 per 1000 tokens

#### Databases
- **Aurora MySQL Serverless v2** - Relational database for FDB data
  - Version: 8.0.mysql_aurora.3.04.0
  - **Note:** Using MySQL instead of PostgreSQL because FDB data is in MySQL format
  - Scaling: 0.5 to 4 ACU (adjustable)
  - Features: Point-in-time recovery, automated backups
  - Storage: Auto-scaling from 10 GB
  - Port: 3306

- **Redis 8.2.3 Open Source on EC2** - Vector store with LeanVec4x8 quantization
  - Instance: **r7i.large** (x86, self-managed, 16 GB RAM)
  - **Current Instance:** i-0aad9fc4ba71454fa (10.0.11.153)
  - **Password:** DAW-Redis-SecureAuth-2025
  - **OS:** Debian 12 x86
  - **Data Status:** 493,573 drugs loaded with LeanVec4x8 compression
  - **Note:** Initially tried r7g.large ARM but Redis Stack 7.4 segfaulted. Switched to x86 for stability.
  - **Note:** Using EC2 instead of ElastiCache because ElastiCache only supports Redis 7.1
  - **Installation:** Redis 8.2.3 from official Debian APT repository (packages.redis.io)
  - **Modules included:** RediSearch (FT.*), RedisJSON, vectorset, bloom filters, timeseries
  - **Management:** Manually managed (SST does NOT create this instance)
  - Features: LeanVec4x8 quantization (3x memory reduction), hybrid search, HNSW vector index
  - Encryption: At-rest and in-transit
  - Port: 6379
  - **Why Redis 8.2.3:** Required for LeanVec4x8 quantization support (not available in 7.x)
  - See `docs/REDIS_8.2.3_INSTALLATION_ODYSSEY.md` for detailed installation history
  - See `docs/REDIS_8.2.3_AMI_QUICK_REFERENCE.md` for quick deployment guide

#### Networking
- **VPC** - Virtual Private Cloud
  - Public subnets: API Gateway
  - Private subnets: Lambda, Redis, Aurora
  - NAT Gateway: For Lambda → Bedrock access

#### Security & Secrets
- **AWS Secrets Manager** - Database credentials (Aurora MySQL master password)
- **AWS Parameter Store** - Connection strings
  - `/daw/{stage}/database/connection-string` - MySQL connection string (mysql://...)
  - Future: Redis connection URL
- **IAM** - Role-based access control
- **Security Groups** - Network-level security
  - Lambda → Aurora MySQL
  - Lambda → Redis
  - Redis → Aurora MySQL (for data loading)

#### Storage
- **S3** - Future use (logs, exports)

---

## Development Environment

### Workspace Setup
- **Platform:** AWS Workspace (VDI environment)
- **OS:** Amazon Linux 2 (kernel 4.14.355)
- **Constraint:** No local Docker support (cloud development only)

### Development Tools
- **Cursor IDE** - AI-powered code editor
- **CursorRIPER Framework** - Project management and memory
- **Git** - Version control
- **SST CLI** - Infrastructure deployment

### Package Managers
- **npm** - Node.js packages (SST, TypeScript)
- **uv** - Python package manager (fast, modern replacement for pip)
  - Used for Lambda dependencies
  - Creates isolated environments
  - Much faster than pip

---

## Project Structure

```
DAW/
├── .cursor/
│   └── rules/
│       ├── core.mdc                    # CursorRIPER framework core
│       ├── state.mdc                   # Project state tracking
│       ├── customization.mdc           # User customizations
│       ├── riper-workflow.mdc          # RIPER workflow rules
│       └── start-phase.mdc             # START phase rules
├── .devcontainer/
│   ├── devcontainer.json               # Dev container config
│   └── README.md                       # Setup instructions
├── database/
│   └── imports/
│       ├── fdb tables.sql              # FDB drug database (200+ MB)
│       └── patient tables.sql          # Patient/pharmacy tables
├── docs/
│   ├── IMPLEMENTATION_PLAN.md          # Detailed implementation guide
│   ├── CURSOR_RIPPER_PROJECT_TEMPLATE_INFO.md  # Template docs
│   └── SST_LAMBDA_MIGRATION_COMPLETE_GUIDE.md  # SST migration guide
├── functions/
│   ├── api/
│   │   └── drug_search.py              # Main search API handler
│   └── sync/
│       └── drug_loader.py              # Aurora → Redis sync job
├── infra/
│   ├── database.ts                     # Aurora RDS infrastructure
│   ├── redis-ec2.ts                    # Redis Stack 8.2.2 on EC2 (not ElastiCache)
│   ├── network.ts                      # VPC, subnets, security groups
│   ├── api.ts                          # API Gateway setup
│   └── sync.ts                         # Sync Lambda functions
├── packages/
│   ├── core/
│   │   ├── package.json
│   │   ├── pyproject.toml              # Python dependencies (uv)
│   │   └── src/
│   │       ├── embedding/
│   │       │   ├── __init__.py         # Factory pattern
│   │       │   ├── base.py             # Abstract interface
│   │       │   ├── titan.py            # Titan implementation
│   │       │   └── sapbert.py          # SapBERT implementation (future)
│   │       ├── llm/
│   │       │   ├── prompts.py          # Claude prompts
│   │       │   └── claude.py           # Claude integration
│   │       └── redis/
│   │           ├── schema.py           # Data structures
│   │           ├── index.py            # Index management
│   │           └── search.py           # Search logic
│   └── scripts/
│       └── package.json                # Utility scripts
├── memory-bank/
│   ├── projectbrief.md                 # Project goals and requirements
│   ├── systemPatterns.md               # Architecture patterns
│   ├── techContext.md                  # This file
│   ├── activeContext.md                # Current work focus
│   └── progress.md                     # Implementation status
├── tests/
│   ├── unit/                           # Unit tests
│   ├── integration/                    # Integration tests
│   └── load/                           # Load tests
├── .gitignore
├── package.json                        # Root workspace config
├── project.config.ts                   # Project configuration
├── sst.config.ts                       # SST main config
├── sst-env.d.ts                        # SST type definitions
├── tsconfig.json                       # TypeScript config
└── README.md                           # Project overview
```

---

## Key Dependencies

### Infrastructure (Node.js)
```json
{
  "dependencies": {
    "sst": "^3.0.0",                    // SST framework
    "@pulumi/aws": "^7.8.0",            // AWS Pulumi provider
    "aws-cdk-lib": "^2.100.0",          // AWS CDK constructs
    "constructs": "^10.3.0"             // CDK construct library
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "typescript": "^5.0.0"
  }
}
```

### Python Lambda Functions
```toml
# pyproject.toml (managed by uv)
[project]
name = "daw-core"
version = "1.0.0"
requires-python = ">=3.12"

dependencies = [
    "boto3 >= 1.34.0",              # AWS SDK
    "psycopg2-binary >= 2.9.9",     # PostgreSQL client
    "redis >= 5.0.0",               # Redis client with search support
    "numpy >= 1.26.0",              # Array operations
    "pydantic >= 2.5.0",            # Data validation
]

[project.optional-dependencies]
dev = [
    "pytest >= 7.4.0",
    "black >= 23.12.0",
    "mypy >= 1.7.0",
    "isort >= 5.13.0"
]
```

---

## AWS Region & Account Strategy

### Regions
- **Primary:** `us-east-1` (customer requirement)
- **Backup:** `us-west-2` (disaster recovery, future)

### Stage-to-Account Mapping
```typescript
// project.config.ts
export const projectConfig = {
  stages: {
    dev: {
      account: process.env.AWS_ACCOUNT_ID_DEV || "123456789012",
      region: "us-east-1",
      protect: false,
      removal: "remove"  // Delete resources on sst remove
    },
    staging: {
      account: process.env.AWS_ACCOUNT_ID_STAGING || "234567890123",
      region: "us-east-1",
      protect: false,
      removal: "remove"
    },
    prod: {
      account: process.env.AWS_ACCOUNT_ID_PROD || "345678901234",
      region: "us-east-1",
      protect: true,       // Prevent accidental deletion
      removal: "retain"    // Keep resources on sst remove
    }
  }
};
```

---

## External APIs & Services

### First Databank (FDB)
- **Purpose:** Drug database provider
- **License:** Customer-owned
- **Data Format:** SQL dumps (MySQL format)
- **Update Frequency:** Weekly
- **Tables Used:**
  - `rndc14` - NDC (National Drug Code) main table
  - `rgcnseq4` - GCN (Generic Code Number) and classification
  - `rnp2` - National pricing data
  - `rdlimxx` - Drug-indication linkages
  - `rdamagd` - Drug-disease interactions
  - `rddcmxx` - Drug-drug interactions

### AWS Bedrock Models
**Claude Sonnet 4**
- Model ID: `anthropic.claude-sonnet-4-20250514`
- Input pricing: $3.00/MTok
- Output pricing: $15.00/MTok
- Cache write: $3.75/MTok
- Cache read: $0.30/MTok (10x cheaper!)
- Context window: 200K tokens
- Max output: 4096 tokens

**Titan Embeddings v2**
- Model ID: `amazon.titan-embed-text-v2:0`
- Pricing: $0.0001/1K tokens
- Dimensions: 1024
- Max input: 8192 tokens
- Output format: Float32 array

### Future: SageMaker SapBERT (Optional)
- **When to use:** If Titan accuracy < 85%
- **Model:** SapBERT (pre-trained on UMLS)
- **Deployment:** SageMaker real-time endpoint
- **Instance:** ml.g4dn.xlarge ($0.736/hour = ~$530/month)
- **Dimensions:** 768
- **Advantage:** Better medical terminology understanding

---

## Configuration Management

### Environment Variables
```bash
# Embedding model selection
EMBEDDING_MODEL=titan                    # or "sapbert"
SAPBERT_ENDPOINT_NAME=sapbert-prod       # If using SapBERT

# Claude model selection
CLAUDE_MODEL_ID=anthropic.claude-sonnet-4-20250514

# Database
DATABASE_URL=postgresql://user:pass@host:5432/daw

# Redis Stack 8.2.2 on EC2
REDIS_URL=redis://daw-redis-server.internal:6379  # Internal VPC address
REDIS_PASSWORD=<from-secrets-manager>

# AWS
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=<from-project-config>

# Stage
SST_STAGE=dev                            # or staging, prod
```

### SST Secrets (Encrypted)
```typescript
// Defined in sst.config.ts, injected at runtime
const dbPassword = new sst.Secret("DatabasePassword");
// Redis connection stored in Parameter Store (not Secrets Manager)
```

### Stage-Specific Config
```typescript
// project.config.ts
export function getStageConfig(stage: string) {
  return projectConfig.stages[stage];
}

// In Lambda
const config = getStageConfig(process.env.SST_STAGE);
```

---

## Development Workflow

### Local Development
```bash
# Start SST dev mode (live Lambda testing)
npm run dev

# This deploys to AWS but with hot-reload
# Lambda logs stream to local terminal
# Changes sync automatically
```

### Testing
```bash
# Unit tests
npm run test:unit

# Integration tests (requires deployed infrastructure)
npm run test:integration

# Load tests
npm run test:load

# Type checking
npm run type-check

# Linting
npm run lint
```

### Deployment
```bash
# Deploy to dev
sst deploy --stage dev

# Deploy to staging
sst deploy --stage staging

# Deploy to production
sst deploy --stage prod

# Remove/destroy infrastructure
sst remove --stage dev
```

### Database Management
```bash
# Import FDB data to Aurora
psql $DATABASE_URL < database/imports/fdb\ tables.sql

# Create Redis indexes
sst shell python -c "from core.redis.index import create_drug_search_index; create_drug_search_index()"

# Sync drugs to Redis
sst invoke SyncDrugsToRedis
```

---

## Performance Characteristics

### Lambda Cold Start
- **Python 3.12:** ~150-200ms (with dependencies)
- **Mitigation:** Provisioned concurrency (if needed)
- **Trade-off:** Cost vs latency (not needed initially)

### Lambda Warm Performance
- **Search handler:** ~200-300ms total
  - Claude: 150-200ms
  - Titan: 50-100ms
  - Redis: 10-15ms
  - Aurora: 15-20ms
  - Overhead: 5-10ms

### Database Performance
- **Aurora:** 0.5 ACU handles ~50 QPS
- **Redis:** Single node handles 50k+ RPS (way more than needed)

### Scaling Limits
- **Lambda concurrency:** 1000 default (can request increase)
- **API Gateway:** 10,000 RPS (soft limit, can increase)
- **Bedrock:** 200 requests/minute Claude, 2000/min Titan (can increase)
- **Aurora:** Scales to 128 ACU (handles thousands of QPS)

---

## Cost Breakdown (Detailed)

### Infrastructure (Monthly, Dev Environment)
```
Aurora Serverless v2:
  - 0.5 ACU average × $0.12/ACU-hour × 730 hours = $43.80
  - Storage: 10 GB × $0.10/GB = $1.00
  - Subtotal: $44.80

Redis ElastiCache:
  - cache.r7g.large: $0.163/hour × 730 hours = $119.00
  - Subtotal: $119.00

NAT Gateway:
  - $0.045/hour × 730 hours = $32.85
  - Data transfer: ~$10
  - Subtotal: $42.85

VPC:
  - Free

Lambda:
  - 1M requests × $0.20/1M = $0.20
  - Duration: 1M × 300ms × $0.0000166667/GB-sec = $8.33
  - Subtotal: $8.53

API Gateway:
  - 1M requests × $1.00/1M = $1.00
  - Subtotal: $1.00

Total Infrastructure: ~$216/month
```

### Usage Costs (Per 100k Queries)
```
Claude Sonnet 4:
  - Input: 5000 tokens × 100k / 1M × $3.00 = $1.50
  - Cache hits (90%): 90k × 5000 / 1M × $0.30 = $0.135
  - Output: 200 tokens × 100k / 1M × $15.00 = $0.30
  - Subtotal: ~$0.30 (with caching)

Titan Embeddings:
  - 100 tokens × 100k / 1k × $0.0001 = $0.01
  - Subtotal: $0.01

Lambda execution:
  - Included in infrastructure (covered by free tier for low volume)

Total Usage: ~$0.31 per 100k queries
```

**At 1M queries/month:** $216 (infra) + $3.10 (usage) = **~$220/month**

---

## Security Considerations

### Network Security
- Lambda in private subnets (no direct internet access)
- NAT Gateway for outbound (Bedrock API calls)
- Security groups restrict port access
- VPC endpoints for AWS services (future optimization)

### Data Security
- Aurora: Encryption at rest (AES-256)
- Redis: TLS in transit, encryption at rest
- Secrets Manager: Automatic rotation (future)
- IAM: Least-privilege access

### API Security
- API Gateway: JWT authentication (future)
- Rate limiting: AWS WAF (future)
- CORS: Restricted origins (future)

### Compliance
- **HIPAA:** Not required (drug search, not patient data)
- **PCI:** Not applicable
- **Data residency:** US-East-1 only

---

## Monitoring & Observability

### CloudWatch Logs
- Lambda function logs (all invocations)
- API Gateway access logs
- VPC Flow Logs (security audit)

### CloudWatch Metrics
- Lambda: Duration, errors, throttles, concurrent executions
- API Gateway: Latency, 4XX/5XX errors, request count
- Aurora: CPU, connections, IOPS
- Redis: CPU, memory, commands/sec

### X-Ray (Future)
- Distributed tracing
- Service map visualization
- Performance bottleneck identification

### Custom Metrics
```python
# In Lambda
cloudwatch = boto3.client('cloudwatch')

cloudwatch.put_metric_data(
    Namespace='DAW/DrugSearch',
    MetricData=[
        {
            'MetricName': 'SearchLatency',
            'Value': latency_ms,
            'Unit': 'Milliseconds'
        }
    ]
)
```

---

## Known Limitations

### Technical Constraints
1. **Lambda timeout:** 30 seconds (API) - sufficient for search
2. **Lambda memory:** 10 GB max - more than enough
3. **Bedrock rate limits:** 200/min Claude (can request increase)
4. **Redis single-node:** No automatic failover (can upgrade to cluster)

### Development Constraints
1. **No local Docker:** Must develop against AWS (SST dev mode helps)
2. **Cold starts:** 150-200ms (acceptable for API)
3. **VPC networking:** Adds complexity and NAT cost

### Business Constraints
1. **FDB license:** Customer-owned, can't share data
2. **AWS-only:** No multi-cloud support
3. **US-East-1:** Single region (no HA across regions initially)

---

## Future Enhancements

### Phase 2 (Possible Additions)
- [ ] Pharmacy search (deferred from Phase 1)
- [ ] Drug interaction checking
- [ ] Dosing calculator
- [ ] Autocomplete/typeahead
- [ ] Search analytics dashboard

### Technical Improvements
- [ ] Upgrade to SapBERT if Titan accuracy < 85%
- [ ] Add Redis Cluster for HA
- [ ] Implement CloudFront caching
- [ ] Add VPC endpoints (reduce NAT costs)
- [ ] Implement automated testing pipeline
- [ ] Add X-Ray distributed tracing

---

**Status:** ✅ Technical context documented
**Last Updated:** 2025-11-06
**Next Review:** After technology changes or version upgrades


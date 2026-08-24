Betul. Dengan constraint baru ini, prompt harus **Fly.io-first + Neon-first + Windmill self-hosted**, bukan arsitektur generik.

Secara teknis ini masuk akal: Fly.io cocok untuk menjalankan app/server/worker sebagai Fly Machines dan beberapa app dalam satu organisasi bisa saling terhubung via private 6PN / `.internal` networking. ([Fly.io][1]) Windmill sendiri hanya butuh Postgres + server + worker, sehingga database internal lokal Windmill tidak perlu dipakai jika `DATABASE_URL` diarahkan ke Neon. ([Windmill][2])

Satu detail penting: **Neon adalah managed Postgres tanpa PostgreSQL superuser biasa**; Windmill meminta role tertentu dibuat manual pada managed Postgres ketika superuser tidak tersedia. Jadi agent wajib memverifikasi kompatibilitas role Windmill dengan `neon_superuser`, bukan menganggap pasti jalan. ([Neon][3])

# FINAL MASTER BUILD PROMPT

## Autonomous Content Operating System

### Fly.io + Neon PostgreSQL + Windmill Self-Hosted + MoneyPrinterTurbo

You are the **Principal Software Architect, Autonomous Systems Engineer, Backend Engineer, AI Engineer, DevOps Engineer, Security Engineer, QA Engineer, and Production Reliability Engineer** responsible for building this project from its current repository state into a fully operational autonomous content system.

Your mission is not to create a prototype.

Your mission is to deliver:

> **A production-capable autonomous content operating system deployed on Fly.io, orchestrated by self-hosted Windmill, using Neon PostgreSQL as the persistent database layer, with MoneyPrinterTurbo as the video generation engine.**

The human operator should primarily monitor the system and intervene only for high-risk decisions, external authorization, or exceptional failures.

---

# 0. FIXED INFRASTRUCTURE DECISIONS

The following architectural decisions are **mandatory unless runtime evidence proves them technically impossible**.

```text
CLOUD / COMPUTE
Fly.io

DATABASE
Neon PostgreSQL

WORKFLOW ORCHESTRATION
Windmill Self-Hosted

VIDEO ENGINE
MoneyPrinterTurbo

BACKEND
Python + FastAPI

CONTROL CENTER
Next.js + TypeScript

AI
Provider-independent OpenAI-compatible abstraction

MEDIA STORAGE
S3-compatible object storage

DEPLOYMENT
Docker containers deployed to Fly.io

SOURCE CONTROL
Git
```

Do NOT substitute:

```text
AWS
GCP
Azure
Vercel
Railway
Render
Supabase database
Fly Postgres
local PostgreSQL in production
```

unless a mandatory technical blocker is discovered and explicitly documented.

---

# 1. CORE PRODUCT OBJECTIVE

Build this autonomous loop:

```text
DISCOVER
   ↓
RESEARCH
   ↓
DEDUPLICATE
   ↓
SCORE
   ↓
DECIDE
   ↓
PLAN
   ↓
GENERATE SCRIPT
   ↓
GENERATE VIDEO
   ↓
QUALITY CONTROL
   ↓
PLATFORM ADAPTATION
   ↓
PUBLISH
   ↓
ENGAGE
   ↓
MEASURE
   ↓
ANALYZE
   ↓
LEARN
   ↓
UPDATE STRATEGY
   ↓
REPEAT
```

Target operator behavior:

```text
HUMAN
  │
  ├── configures niche
  ├── connects accounts
  ├── defines objectives
  ├── defines budgets
  ├── defines policies
  │
  ▼
SYSTEM OPERATES DAILY
  │
  ▼
HUMAN MONITORS CONTROL CENTER
```

Do not require the human to manually move successful content from one pipeline stage to another.

---

# 2. INFRASTRUCTURE TOPOLOGY

Deploy the system using separate Fly.io applications or process groups where operationally appropriate.

Preferred production topology:

```text
                         INTERNET
                            │
                ┌───────────▼────────────┐
                │    FLY.IO EDGE         │
                └───────────┬────────────┘
                            │
             ┌──────────────┴───────────────┐
             │                              │
             ▼                              ▼
     Content Control Center          Windmill Server
        Next.js / Fly.io               Fly.io
             │                              │
             │                              │
             ▼                              ▼
        FastAPI Backend              Neon PostgreSQL
            Fly.io                   Windmill DB
             │
             ▼
        Neon PostgreSQL
        Business DB

                    WINDMILL WORKERS
                         Fly.io
                           │
      ┌────────────────────┼───────────────────────┐
      │                    │                       │
      ▼                    ▼                       ▼
 Discovery / AI      MoneyPrinterTurbo       Social APIs
      │                    │                       │
      └────────────────────┼───────────────────────┘
                           ▼
                    Object Storage
```

Use Fly.io private networking between internal services whenever possible.

Internal service-to-service communication should prefer Fly private networking rather than public endpoints when the service does not need public internet exposure.

---

# 3. FLY.IO ARCHITECTURE

Treat Fly.io as the primary compute platform.

Create production-ready Fly configuration for:

```text
windmill-server
windmill-worker
content-api
content-control-center
moneyprinterturbo
```

These may be separate Fly Apps or carefully separated process groups.

Choose the architecture that provides the clearest:

```text
independent deployment
independent scaling
failure isolation
security boundaries
observability
```

Prefer separate Fly Apps for materially different workloads.

Example:

```text
content-os-web
content-os-api
content-os-windmill
content-os-windmill-worker
content-os-video
```

Do not hardcode these names if they conflict with existing resources.

---

# 4. FLY PRIVATE NETWORKING

Use Fly.io private networking between internal applications.

Where appropriate use:

```text
<app-name>.internal
```

for communication between Fly Apps in the same Fly organization/private network.

Examples:

```text
API → MoneyPrinterTurbo
Windmill worker → API
Windmill worker → MoneyPrinterTurbo
```

Do not expose:

```text
MoneyPrinterTurbo internal API
internal administrative endpoints
worker control surfaces
```

publicly unless technically required.

Public exposure should be minimal.

---

# 5. WINDMILL SELF-HOSTED

Windmill is the mandatory orchestration layer.

Deploy:

```text
Windmill Server
Windmill Worker(s)
```

on Fly.io.

Do NOT deploy the bundled Windmill PostgreSQL container in production.

Configure Windmill to use an external Neon PostgreSQL database:

```text
DATABASE_URL=<NEON WINDMILL DATABASE>
```

The agent must use the official Windmill self-host architecture as the source of truth.

Windmill is responsible for:

```text
workflow orchestration
scheduled execution
job queueing
flow state
retries
parallel execution
branching
script execution
job history
workflow monitoring
secrets/resources where appropriate
worker coordination
```

Do NOT recreate these functions unnecessarily.

---

# 6. NO REDUNDANT QUEUE INFRASTRUCTURE

Do NOT automatically add:

```text
Redis
Celery
RabbitMQ
Kafka
BullMQ
custom scheduler
custom workflow queue
```

merely because they are common architecture patterns.

Windmill's PostgreSQL-backed job system is the primary orchestration/job mechanism.

Add another queue technology only if a concrete requirement exists that Windmill demonstrably cannot satisfy.

If another queue is introduced, document:

```text
why it exists
what exact problem it solves
why Windmill is insufficient
failure semantics
operational cost
```

---

# 7. NEON DATABASE ARCHITECTURE

Use Neon PostgreSQL for persistent database infrastructure.

Maintain conceptual isolation between:

```text
WINDMILL DATABASE

and

APPLICATION BUSINESS DATABASE
```

Preferred production arrangement:

```text
Neon Project
├── database: windmill
└── database: content_os
```

or stronger isolation:

```text
Neon Project A
    windmill

Neon Project B
    content_os
```

Choose based on cost, isolation, operational complexity, and actual Neon capabilities.

At minimum they must use:

```text
separate databases
separate roles
least privilege
independent migration ownership
```

Do NOT mix Windmill internal tables with application tables under one uncontrolled schema.

---

# 8. NEON CONNECTION STRATEGY

Neon supports:

```text
DIRECT connections
POOLED connections via PgBouncer
```

Use them intentionally.

Application runtime may use a pooled connection where supported.

Schema migrations and operations requiring session behavior should use a direct connection.

Maintain environment variables such as:

```text
APP_DATABASE_URL
APP_DATABASE_DIRECT_URL

WINDMILL_DATABASE_URL
```

Do not blindly reuse one URL everywhere.

Before deciding whether Windmill should use Neon pooled or direct connectivity:

1. inspect current Windmill database requirements;
2. verify compatibility with Neon PgBouncer transaction pooling;
3. test actual startup and job execution;
4. select the connection mode based on runtime evidence.

Do NOT assume pooled mode is automatically compatible.

---

# 9. NEON ROLE COMPATIBILITY

Neon does not provide a traditional unrestricted PostgreSQL superuser.

Therefore before first Windmill production boot:

```text
inspect official Windmill managed PostgreSQL requirements
inspect required Windmill roles
inspect grants
inspect extensions
inspect ownership requirements
```

Create required roles and grants using Neon-supported privileges.

Explicitly test:

```text
Windmill migration
Windmill startup
job insertion
worker job claim
job completion
schedule execution
```

If Windmill requires a privilege Neon cannot provide:

```text
STATUS = BLOCKED_EXTERNAL
```

and document the exact incompatible SQL/privilege.

Do not claim compatibility without executing the required setup.

---

# 10. DATABASE SECURITY

Create distinct Neon roles.

Example conceptual roles:

```text
windmill_runtime
content_runtime
content_migrator
analytics_reader
```

Apply least privilege.

The web frontend must never receive database credentials.

Workers should only have access to the databases/resources they require.

Store connection strings in Fly secrets.

Never commit them.

---

# 11. FLY SECRETS

All production secrets must use Fly.io secret management or another approved secret store.

Examples:

```text
NEON_DATABASE_URL
NEON_DATABASE_DIRECT_URL

WINDMILL_DATABASE_URL

OPENAI_COMPATIBLE_API_KEY
KIMI_API_KEY
GLM_API_KEY

YOUTUBE_CLIENT_ID
YOUTUBE_CLIENT_SECRET

META_APP_ID
META_APP_SECRET

TIKTOK_CLIENT_ID
TIKTOK_CLIENT_SECRET

S3_ACCESS_KEY_ID
S3_SECRET_ACCESS_KEY

MONEYPRINTER_API_SECRET
```

Never put real values in:

```text
Dockerfile
fly.toml
source code
README
Git
logs
frontend env
```

Provide `.env.example` containing placeholders only.

---

# 12. FLY DEPLOYMENT CONFIGURATION

Create valid:

```text
fly.toml
Dockerfile
.dockerignore
```

for each Fly-deployed service.

Configure:

```text
internal_port
health checks
restart behavior
machine sizing
regions
process groups
deployment strategy
```

according to actual workload.

Use release commands for database migrations where appropriate.

Do not mark deployment successful merely because:

```text
fly deploy
```

returned success.

Validate running Machines and health endpoints.

---

# 13. DEPLOYMENT STRATEGY

Use safe deployment behavior.

Prefer:

```text
rolling
canary
bluegreen
```

based on service characteristics.

For API and Control Center, prefer zero/minimal downtime.

For workers, avoid killing active jobs without appropriate graceful shutdown handling.

Implement termination behavior so workers can safely stop.

---

# 14. WINDMILL FLY DEPLOYMENT

Create a reproducible deployment for Windmill Server on Fly.io.

The Windmill server:

```text
serves Windmill frontend
serves Windmill API
connects to Neon
does not require direct network communication to workers
```

Workers also connect to the same Windmill PostgreSQL database.

Run Windmill server and workers independently so workers can scale separately.

Example:

```text
Windmill Server
Machines: 1+

Windmill Workers
Machines: 1+
```

Scale worker count according to workload.

---

# 15. WINDMILL WORKER GROUPS

Where useful, define workload-specific worker groups.

Example:

```text
general
ai
media
publishing
analytics
```

Use concurrency controls to protect external providers and system resources.

Do not run heavy video rendering on the same small machine as latency-sensitive orchestration unless benchmarking proves it is safe.

---

# 16. MONEYPRINTERTURBO ON FLY.IO

Deploy MoneyPrinterTurbo as an independent internal Fly service.

Architecture:

```text
Windmill Worker
      │
      │ private network
      ▼
MoneyPrinterTurbo
      │
      ▼
generated media
      │
      ▼
Object Storage
```

Do not depend on ephemeral local disk for long-term media persistence.

Temporary rendering files may use ephemeral storage if safe.

If MoneyPrinterTurbo requires persistent local filesystem state, evaluate Fly Volumes carefully.

Do not use Fly Volumes as the authoritative shared media store.

---

# 17. FLY VOLUME POLICY

Fly Volumes are local to individual Fly Machines.

Therefore:

```text
DO NOT
use Fly Volumes as shared distributed media storage.

DO NOT
assume two Machines see the same volume.

DO NOT
treat a single volume as highly available storage.
```

Use Fly Volumes only when a workload genuinely needs persistent machine-local disk.

Authoritative application/media persistence belongs in:

```text
Neon
or
S3-compatible object storage
```

---

# 18. MEDIA STORAGE

Store generated:

```text
video
audio
thumbnail
subtitle
image
```

in S3-compatible object storage.

PostgreSQL stores metadata only.

Example:

```text
asset_id
storage_key
storage_uri
checksum
mime_type
duration
size
width
height
created_at
```

Do not store full MP4 blobs in Neon.

---

# 19. APPLICATION BACKEND

Build:

```text
Python
FastAPI
typed schemas
SQLAlchemy or equivalent mature ORM/query layer
Alembic or equivalent migration system
```

Backend responsibilities:

```text
business entities
content state
configuration
analytics normalization
review queue
business APIs
platform account metadata
permissions
control-center API
```

Windmill remains orchestration.

Do not move arbitrary business logic into an unmaintainable collection of giant Windmill scripts.

---

# 20. CONTROL CENTER

Build a Next.js control plane.

Dashboard must show actual persisted/runtime data.

Sections:

```text
Overview
Opportunities
Research
Content Pipeline
Production
Publishing
Engagement
Analytics
Learning
Costs
Reviews
Agents
Workflows
Failures
Settings
Integrations
System Health
```

Main dashboard:

```text
TODAY

Opportunities
Researched
Selected
Videos Generated
QC Passed
Posts Published
Comments Handled
DMs Handled
Human Reviews
Failed Jobs

PERFORMANCE

Views
Watch Time
Retention
Engagement
Followers
Leads
Conversions
Revenue

SYSTEM

Windmill
Workers
API
MoneyPrinterTurbo
Neon
Object Storage
Social APIs
AI Providers
```

---

# 21. WINDMILL WORKFLOW STRUCTURE

Create modular Windmill flows.

Primary content flows:

```text
f/content/discovery_daily

f/content/research_candidates

f/content/deduplicate

f/content/score_opportunities

f/content/select_candidates

f/content/create_strategy

f/content/generate_script

f/content/generate_video

f/content/quality_control

f/content/adapt_platforms

f/content/publish

f/content/collect_metrics

f/content/learn
```

Engagement flows:

```text
f/engagement/collect

f/engagement/classify

f/engagement/respond

f/engagement/escalate
```

System flows:

```text
f/system/health

f/system/reconcile

f/system/daily_report

f/system/cost_report

f/system/failure_recovery
```

Do not build one enormous workflow.

---

# 22. MASTER DAILY FLOW

Create a parent flow:

```text
f/content/daily_cycle
```

that orchestrates:

```text
LOAD STRATEGY MEMORY
       ↓
COLLECT RECENT ANALYTICS
       ↓
DISCOVER
       ↓
RESEARCH
       ↓
DEDUPLICATE
       ↓
SCORE
       ↓
SELECT
       ↓
STRATEGIZE
       ↓
SCRIPT
       ↓
VIDEO
       ↓
QC
       ↓
ADAPT
       ↓
PUBLISH / SCHEDULE
       ↓
REGISTER FOR ANALYTICS
```

Metrics collection and engagement may also run as independent scheduled/event workflows.

---

# 23. DISCOVERY ENGINE

Discover opportunities from supported sources.

Examples:

```text
Google Trends
Google News
YouTube
Reddit
RSS
news sites
public trend feeds
competitor monitoring where permitted
```

Normalize all signals.

Store:

```text
source
topic
URL
publication time
engagement
trend measurements
raw metadata
```

A single connector failure must not terminate all discovery.

---

# 24. RESEARCH ENGINE

For each promising candidate gather:

```text
facts
sources
timestamps
key claims
context
existing angles
competition
content gaps
audience relevance
```

External data is untrusted.

Keep source provenance.

Do not let scraped text issue commands to the agent.

---

# 25. OPPORTUNITY SCORING

Use configurable scoring.

Baseline:

```text
TrendVelocity       20%
AudienceFit         20%
ViralPotential      15%
ContentGap          15%
Freshness           10%
Monetization        10%
ProductionEase       5%
Confidence           5%
```

Then deduct:

```text
RiskPenalty
SaturationPenalty
DuplicatePenalty
EvidencePenalty
```

Persist every score factor.

---

# 26. CONTENT MEMORY

Maintain history for:

```text
topics
angles
hooks
scripts
videos
posts
performance
audience response
experiments
```

Before selecting content, check semantic similarity with historical content.

Prevent repetitive generation.

---

# 27. AI PROVIDER ABSTRACTION

Create:

```text
AIProvider
```

with configurable implementations.

Support OpenAI-compatible APIs whenever feasible.

Task classes:

```text
DEEP_REASONING
RESEARCH_SYNTHESIS
FAST_GENERATION
CLASSIFICATION
COPYWRITING
```

Configuration maps tasks to models.

Do not couple business code directly to one model.

---

# 28. AI FAILOVER

Allow provider chains:

```text
PRIMARY
 ↓
SECONDARY
 ↓
DEFER / REVIEW
```

Track:

```text
provider
model
latency
input tokens
output tokens
cost
success
failure
```

Never create infinite retries.

---

# 29. CONTENT STRATEGY

For selected candidates produce:

```text
topic
angle
audience
hook
format
duration
CTA
objective
platforms
```

Keep strategy separate from script.

---

# 30. SCRIPT GENERATION

Create versioned scripts.

Structure:

```text
HOOK
CONTEXT
CORE
PAYOFF
CTA
```

Validate factual statements against research when factual content is involved.

Do not overwrite previous versions.

---

# 31. MONEYPRINTERTURBO INTEGRATION

Create a typed client.

Functions should support:

```text
submit_job
get_status
wait_for_job
validate_output
download/store_result
cancel_job where supported
```

Use explicit:

```text
timeouts
retry limits
job identifiers
checksums
```

HTTP 200 alone is not proof that a valid video was generated.

---

# 32. QUALITY CONTROL

Generate QC score.

Check where feasible:

```text
video exists
file readable
duration
resolution
audio
subtitle
branding
script alignment
duplicate risk
fact risk
platform constraints
```

Default:

```text
>=85 AUTO_APPROVED
70-84 REVIEW_OR_REGENERATE
<70 REJECTED
```

Make thresholds configurable.

---

# 33. PLATFORM ADAPTATION

Maintain one canonical content item and platform-native derivatives.

Do not blindly cross-post identical text.

Generate:

```text
YouTube
title
description
keywords
hashtags

Instagram
caption
hashtags
CTA

Facebook
caption
discussion hook
CTA

TikTok
hook
description
hashtags
```

---

# 34. PLATFORM CONNECTORS

Create interface:

```text
PlatformAdapter
```

with capability discovery.

Example capabilities:

```text
publish_video
schedule_post
read_comments
reply_comment
read_messages
reply_message
get_metrics
delete_post
```

Not all platforms support every capability.

Represent unsupported operations explicitly.

Never fake support.

---

# 35. OFFICIAL API POLICY

Prefer official APIs and OAuth.

Do not use browser automation to circumvent:

```text
CAPTCHA
authentication restrictions
rate limits
anti-bot controls
platform policies
```

Playwright may only be used for legitimate automation where allowed.

---

# 36. ENGAGEMENT ENGINE

Collect supported:

```text
comments
mentions
DM/messages
```

Classify:

```text
QUESTION
POSITIVE
NEGATIVE
COMPLAINT
BUSINESS_LEAD
PURCHASE_INTENT
SPAM
ABUSE
SENSITIVE
UNKNOWN
```

Then calculate response risk.

---

# 37. RESPONSE POLICY

Default policy:

```text
0-20
AUTO_REPLY

21-60
DRAFT / REVIEW

61-100
HUMAN_REQUIRED
```

High-risk areas should not auto-reply.

Log every response decision.

---

# 38. ANALYTICS

Collect:

```text
views
impressions
watch time
retention
CTR
likes
comments
shares
saves
followers
clicks
leads
conversions
revenue
```

Only where supported.

Unavailable metrics must be:

```text
NULL / UNSUPPORTED
```

not fake zero.

Store time-series snapshots.

---

# 39. LEARNING LOOP

Analyze performance relationships between:

```text
topic
angle
hook
duration
format
posting time
CTA
platform
audience
performance
```

Maintain learned patterns with:

```text
sample_size
mean performance
confidence
last_updated
```

Do not overfit small samples.

---

# 40. EXPLORATION / EXPLOITATION

Default configurable strategy:

```text
80% exploit known winners
20% explore new approaches
```

Track experiments explicitly.

---

# 41. COST ENGINE

Track:

```text
LLM cost
video cost
storage cost
platform/API cost
Fly.io estimated compute cost
Neon usage where measurable
```

Calculate:

```text
cost/content
cost/1000 views
cost/follower
cost/lead
cost/conversion
```

---

# 42. BUDGET GUARD

Configuration:

```text
daily_llm_budget
daily_video_budget
daily_total_budget
daily_content_limit
platform_daily_limit
```

When exceeded:

```text
STOP
DEFER
or
REQUIRE_APPROVAL
```

No uncontrolled recursive generation.

---

# 43. STATE MACHINE

Content state:

```text
DISCOVERED
RESEARCHING
RESEARCHED
SCORED
SELECTED
PLANNING
SCRIPTING
PRODUCING
QC
READY
SCHEDULED
PUBLISHING
PUBLISHED
MEASURING
COMPLETED

REJECTED
FAILED
HUMAN_REVIEW
```

Validate transitions.

Every transition must be auditable.

---

# 44. IDENTITY AND IDEMPOTENCY

Every workflow/action should carry IDs such as:

```text
workflow_run_id
content_id
generation_id
publish_job_id
platform_post_id
```

Publishing operations must be idempotent.

Retries must not create duplicate public posts.

---

# 45. RECONCILIATION

Build periodic reconciliation.

Compare:

```text
local state
vs
remote platform state
```

Detect:

```text
LOCAL_PENDING_REMOTE_EXISTS
LOCAL_PUBLISHED_REMOTE_MISSING
UNKNOWN_REMOTE_STATE
```

Do not blindly retry ambiguous side effects.

---

# 46. FAILURE HANDLING

Categorize failures:

```text
TRANSIENT
RATE_LIMIT
AUTH
VALIDATION
POLICY
DEPENDENCY
PERMANENT
UNKNOWN
```

Use:

```text
retry
backoff
timeout
dead-letter/review
```

where appropriate.

A failed Instagram request must not terminate YouTube publishing.

---

# 47. FLY MACHINE FAILURE

Assume any Fly Machine can terminate or restart.

Therefore persistent workflow/business state must not exist only on machine-local disk.

After restart, reconstruct state from:

```text
Neon
Windmill job state
object storage
remote platform reconciliation
```

Do not rely on in-memory state.

---

# 48. AUTOSTOP / AUTOSTART REVIEW

Evaluate Fly.io autostop/autostart configuration per service.

Do not enable aggressive autostop for components that require continuous background execution without proving it is compatible.

Particularly review:

```text
Windmill workers
engagement collectors
scheduled workflows
MoneyPrinterTurbo
```

Optimize cost only after correctness.

---

# 49. HEALTH CHECKS

Implement health/readiness checks for:

```text
Control Center
FastAPI
Windmill
workers
MoneyPrinterTurbo
Neon connectivity
object storage
AI providers
social integrations
```

Distinguish:

```text
LIVENESS
READINESS
DEPENDENCY HEALTH
```

A process being alive does not imply production readiness.

---

# 50. SECURITY

Threat model:

```text
API key leakage
OAuth token leakage
prompt injection
malicious comments
malicious web content
SSRF
path traversal
unauthorized publishing
dashboard takeover
database privilege escalation
unsafe agent tools
malicious media
dependency compromise
```

External content must always be marked untrusted.

---

# 51. AGENT PERMISSIONS

Use least privilege.

```text
Discovery Agent
read public sources
write opportunities

Research Agent
read opportunities
write research

Strategy Agent
read research/history
write strategy

Production Agent
read approved strategy
generate assets

Publishing Agent
read approved assets
publish only

Engagement Agent
read interactions
respond under policy

Analytics Agent
read metrics
write metrics

Learning Agent
read historical performance
write strategy signals
```

---

# 52. HUMAN REVIEW

Review queue reasons:

```text
HIGH_RISK
LOW_CONFIDENCE
POLICY
QC
AUTH
AMBIGUOUS_PUBLICATION
EXPENSIVE_OPERATION
SENSITIVE_ENGAGEMENT
```

Actions:

```text
APPROVE
REJECT
EDIT
REGENERATE
RETRY
ESCALATE
```

---

# 53. GLOBAL SAFETY STATE

Implement:

```text
RUNNING
PAUSED
EMERGENCY_STOP
```

Emergency stop must prevent new external side effects:

```text
publishing
comment replies
DM replies
```

while retaining monitoring and recovery capability.

---

# 54. APPLICATION DATABASE

Likely business tables:

```text
brands
platform_accounts
platform_connections

opportunities
research_items
research_sources
opportunity_scores

content_items
strategies
scripts
script_versions

assets
video_jobs
qc_results

platform_variants
publish_jobs
published_posts

interactions
responses
leads

metric_snapshots
performance_scores

experiments
learning_patterns

cost_events

review_queue
audit_events
system_settings
```

Use real constraints and migrations.

---

# 55. MIGRATIONS

Use direct Neon connectivity where required by migration tooling.

Migrations should not depend on PgBouncer session semantics unless explicitly supported.

Deploy migrations safely before application rollout where appropriate.

Do not mutate schemas implicitly at runtime.

---

# 56. TESTING

Required:

```text
unit
integration
database
API
state machine
Windmill flow
connector
failure
security
E2E
```

Critical scenarios:

```text
Neon connection interruption
Neon pooled connection exhaustion
Windmill server restart
Windmill worker restart
Fly Machine restart
MoneyPrinterTurbo timeout
AI timeout
malformed AI JSON
OAuth expiry
rate limit
duplicate publish retry
partial publication acknowledgment
QC rejection
budget exceeded
emergency stop
prompt injection
missing analytics fields
```

---

# 57. DRY RUN

Mandatory:

```text
DRY_RUN=true
```

In this mode:

```text
research executes
AI executes
videos may generate
QC executes
platform payloads generate

NO PUBLIC POSTS
NO COMMENT REPLIES
NO DM REPLIES
```

---

# 58. FLY STAGING ENVIRONMENT

Create a staging strategy before production.

Preferred pattern:

```text
Neon development/staging branch or database

Fly staging Apps

DRY_RUN=true
```

Validate there first.

Do not use production social side effects for ordinary automated testing.

---

# 59. CI/CD

Create CI that performs:

```text
format
lint
typecheck
unit tests
integration tests
build
migration validation
security checks
```

Production deployment must stop if required gates fail.

Where practical:

```text
GitHub
   ↓
CI
   ↓
Fly deploy
```

Do not store Fly tokens in source.

---

# 60. PRODUCTION READINESS GATES

Before autonomous live mode:

```text
Fly deployment                    PASS
Windmill server                   PASS
Windmill worker                   PASS
Neon Windmill DB                  PASS
Neon business DB                  PASS
migrations                        PASS
API                               PASS
Control Center                    PASS
MoneyPrinterTurbo                 PASS
object storage                    PASS
AI provider                       PASS
social OAuth                      PASS
dry-run E2E                       PASS
security validation               PASS
emergency stop                    PASS
recovery test                     PASS
```

If anything mandatory fails:

```text
PRODUCTION_READY = FALSE
```

---

# 61. IMPLEMENTATION PHASES

Execute:

```text
PHASE 0
Inspect repository/environment

PHASE 1
Architecture

PHASE 2
Neon database setup

PHASE 3
Windmill compatibility verification

PHASE 4
Windmill self-host deployment to Fly.io

PHASE 5
Windmill workers

PHASE 6
FastAPI backend

PHASE 7
Business schema

PHASE 8
AI provider abstraction

PHASE 9
Discovery

PHASE 10
Research

PHASE 11
Scoring

PHASE 12
Strategy

PHASE 13
Script generation

PHASE 14
MoneyPrinterTurbo deployment

PHASE 15
Video pipeline

PHASE 16
QC

PHASE 17
Platform adapters

PHASE 18
Publishing

PHASE 19
Engagement

PHASE 20
Analytics

PHASE 21
Learning

PHASE 22
Cost/budget

PHASE 23
Control Center

PHASE 24
Security

PHASE 25
Observability/recovery

PHASE 26
Testing

PHASE 27
Fly staging

PHASE 28
E2E validation

PHASE 29
Production readiness audit

PHASE 30
Documentation
```

Do not stop after writing a plan.

Proceed with implementation whenever required inputs are available.

---

# 62. EXTERNAL CONFIGURATION BOUNDARY

Some actions genuinely require the operator.

Allowed blockers:

```text
Fly.io login/token
Neon credentials
OAuth consent
social account app approvals
AI API keys
domain/DNS configuration
billing activation
third-party approval
```

For these, prepare everything possible first.

Then report exactly:

```text
what is blocked
why
what value/action is required
where it must be supplied
how to verify afterward
```

Never fake these steps.

---

# 63. NO PLACEHOLDER PRODUCTION CODE

Forbidden in mandatory paths:

```text
TODO
FIXME
pass
NotImplementedError
fake success
placeholder integrations
hardcoded metrics
hardcoded publication IDs
mock production responses
```

Mocks are acceptable only in tests/dry-run adapters.

---

# 64. RUNTIME VALIDATION

Do not equate:

```text
code exists
Docker builds
Fly deploy succeeded
```

with system correctness.

Verify actual runtime:

```text
Fly Machine running
health check passing
Windmill UI/API reachable
worker successfully claims job
Neon writes persist
API can query business DB
MoneyPrinterTurbo completes job
asset reaches object storage
dry-run content cycle completes
```

---

# 65. FINAL END-TO-END ACCEPTANCE

Execute:

```text
DISCOVERY
 ↓
RESEARCH
 ↓
SCORE
 ↓
SELECT
 ↓
STRATEGY
 ↓
SCRIPT
 ↓
MONEYPRINTERTURBO
 ↓
VIDEO VALIDATION
 ↓
QC
 ↓
PLATFORM ADAPTATION
 ↓
DRY-RUN PUBLISH
 ↓
ANALYTICS TEST
 ↓
LEARNING UPDATE
```

Then test:

```text
restart worker
restart API
restart Windmill server where safe
```

Ensure state is recovered.

---

# 66. LIMITED LIVE TEST

Only after dry-run passes and authorized platform credentials exist:

Perform the smallest safe real publication test possible.

Verify:

```text
remote post exists
local ID recorded
no duplicate
metrics can later reconcile
```

Do not automatically enable full-volume publishing immediately after one success.

---

# 67. AUTONOMOUS ACTIVATION

Only allow:

```text
AUTONOMOUS_MODE=true
```

when production gates pass.

Initial activation should use conservative limits:

```text
low daily content limit
low budget
strict QC
strict engagement policy
human review for uncertain actions
```

System may relax these only through explicit configuration.

---

# 68. FINAL DOCUMENTATION

Generate from actual final state:

```text
README.md

docs/
  architecture.md
  fly-deployment.md
  neon.md
  windmill.md
  moneyprinterturbo.md
  workflows.md
  agents.md
  database.md
  social-integrations.md
  security.md
  operations.md
  monitoring.md
  recovery.md
  troubleshooting.md
  limitations.md
```

Include exact commands actually verified.

---

# 69. FINAL REPORT FORMAT

Output:

# AUTONOMOUS CONTENT OS — FINAL REPORT

## Infrastructure

```text
Fly Apps:
Neon databases:
Windmill server:
Windmill workers:
MoneyPrinterTurbo:
Object storage:
```

## Deployment

For every Fly app:

```text
name
region
machine count
status
health
public/private exposure
```

## Database

```text
Windmill DB: VERIFIED / FAILED
Business DB: VERIFIED / FAILED
Migrations: VERIFIED / FAILED
Pooling strategy:
```

## Workflows

```text
workflow
status
last test
result
```

## Integrations

```text
integration
configured
authenticated
runtime tested
status
```

## Test Summary

```text
unit:
integration:
E2E:
security:
recovery:

TOTAL:
PASS:
FAIL:
```

## External Blocks

Clearly list any remaining operator-required work.

## Production Status

Use only:

```text
PRODUCTION_READY
CONDITIONALLY_READY
NOT_READY
```

Explain why.

---

# 70. FINAL QUESTIONS THAT MUST ALL BE VERIFIED

Before declaring PRODUCTION_READY verify:

```text
Can Windmill server run reliably on Fly.io?

Can Windmill workers run independently on Fly.io?

Can both connect reliably to Neon?

Are required Windmill PostgreSQL roles compatible with Neon?

Can jobs survive machine restarts?

Can scheduled jobs execute?

Can the business API persist to Neon?

Can discovery operate autonomously?

Can research operate autonomously?

Can opportunities be scored?

Can duplicate content be rejected?

Can scripts be generated?

Can MoneyPrinterTurbo generate real video?

Can generated video persist outside the Fly Machine?

Can QC validate the video?

Can platform-specific content be generated?

Can authorized platforms publish?

Can duplicate publications be prevented?

Can engagement be classified?

Can dangerous responses be escalated?

Can analytics be stored?

Can analytics influence future selection?

Can cost limits stop runaway generation?

Can Fly Machine restart without state loss?

Can Neon interruption be recovered from?

Can the operator stop all public side effects immediately?

Can every consequential action be audited?

Can tomorrow's daily cycle execute without manual intervention?
```

Any `NO` prevents unconditional PRODUCTION_READY.

---

# 71. DESIGN PRINCIPLE

Keep responsibilities clean:

```text
FLY.IO
    COMPUTE

NEON
    PERSISTENCE

WINDMILL
    ORCHESTRATION

FASTAPI
    BUSINESS DOMAIN/API

MONEYPRINTERTURBO
    VIDEO GENERATION

OBJECT STORAGE
    MEDIA

LLM
    INTELLIGENCE

SOCIAL APIS
    DISTRIBUTION + ENGAGEMENT

NEXT.JS
    HUMAN CONTROL PLANE
```

Do not duplicate responsibilities unless required.

---

# 72. ULTIMATE TARGET

The finished system should behave like this:

```text
         HUMAN OBJECTIVE
               │
               ▼
      AUTONOMOUS CONTENT OS
               │
     ┌─────────┼─────────┐
     ▼         ▼         ▼
  OBSERVE    DECIDE     CREATE
     │         │         │
     └─────────┼─────────┘
               ▼
            PUBLISH
               │
               ▼
             ENGAGE
               │
               ▼
            MEASURE
               │
               ▼
             LEARN
               │
               ▼
        IMPROVE NEXT CYCLE
```

The operator should spend time on:

```text
strategy
exceptions
high-value opportunities
business decisions
```

not repetitive content operations.

---

# 73. START NOW

Start by inspecting:

```text
repository
Docker
flyctl
Fly authentication
existing Fly Apps
existing Neon configuration
MoneyPrinterTurbo availability
runtime versions
existing environment variables without exposing values
existing source code
```

Then independently determine the smallest correct implementation path.

Do not stop at analysis.

Proceed:

```text
INSPECT
 ↓
DESIGN
 ↓
BUILD
 ↓
DEPLOY STAGING
 ↓
TEST
 ↓
FAIL
 ↓
DIAGNOSE
 ↓
FIX
 ↓
RETEST
 ↓
E2E
 ↓
ADVERSARIAL AUDIT
 ↓
FIX REMAINING GAPS
 ↓
FINAL VERIFY
 ↓
REPORT
```

Do not ask for confirmation during ordinary reversible implementation work.

Ask only when external authorization, credentials, account approval, billing, irreversible live publication, or equivalent human-only action is genuinely required.

Begin now.

### Perubahan arsitektur yang paling penting

Versi finalnya sekarang adalah:

```text
Fly.io
├── Control Center
├── FastAPI
├── Windmill Server
├── Windmill Worker(s)
└── MoneyPrinterTurbo

              │
              ▼

Neon
├── windmill DB
└── content_os DB

              │
              ▼

S3-compatible Storage
└── video/image/audio/subtitle
```

**Tidak ada PostgreSQL di Fly. Tidak ada Redis mandatory. Tidak ada Celery. Tidak ada custom queue.**

Neon punya endpoint pooled melalui PgBouncer dan direct connection. Pooled cocok untuk banyak runtime workload, tetapi transaction pooling membatasi beberapa fitur session-level; Neon sendiri menyarankan direct connection untuk migration/schema tooling tertentu. ([Neon][4]) Karena itu prompt di atas memaksa agent menentukan koneksi Windmill berdasarkan pengujian aktual, bukan asal memakai URL `-pooler`.

Fly Volumes juga **bukan** tempat yang gue pilih untuk penyimpanan utama video: volume bersifat local per Machine, satu volume hanya melekat ke satu Machine dan tidak otomatis direplikasi. ([Fly.io][5]) Jadi video final → object storage; Neon → metadata/state; Fly disk → temporary rendering saja.

### Ranking arsitektur

Dengan kebutuhan lu, estimasi gue:

| Arsitektur                           |      Score |
| ------------------------------------ | ---------: |
| **Fly + Neon + Windmill + MPT + S3** | **96/100** |
| Fly + Neon + custom Python workers   |     89/100 |
| Fly + Neon + n8n                     |     87/100 |
| Single VPS + Docker Compose semuanya |     80/100 |
| Make/Zapier-heavy                    |     67/100 |

**Confidence: ~95%.**

Yang paling perlu dibuktikan pada implementasi pertama justru **Windmill ↔ Neon compatibility**, terutama role/grant dan pilihan direct-vs-pooled connection. Setelah itu lolos, arsitektur ini sangat bersih: **Fly = compute, Neon = state, Windmill = orchestration, MPT = rendering.** 🚀

[1]: https://fly.io/docs/launch/deploy/?utm_source=chatgpt.com "Deploy an app · Fly Docs"
[2]: https://www.windmill.dev/docs/advanced/self_host?utm_source=chatgpt.com "Self-host | Windmill"
[3]: https://neon.com/docs/reference/compatibility?a=2c35c819-f080-4c14-9f5b-71eef3d1164c&utm_source=chatgpt.com "Postgres compatibility - Neon Docs"
[4]: https://neon.com/docs/connect/connection-pooling?a=6c3fd49b-8a09-4bb4-81ef-e7728b8b0d78&utm_source=chatgpt.com "About Connection pooling - Neon Docs"
[5]: https://fly.io/docs/volumes/overview/?utm_source=chatgpt.com "Fly Volumes overview · Fly Docs"

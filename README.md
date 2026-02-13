# ML Pipeline — Real-Time Inference with Kafka, FastAPI & Observability

A production-style, event-driven ML inference pipeline demonstrating backend engineering, cloud-native microservices, and MLOps best practices.

## Architecture

```
┌─────────────┐       ┌───────────────────┐       ┌─────────────────┐
│   Client     │──────▶│  Gateway (FastAPI) │──────▶│  Kafka Broker   │
│  POST /predict│      │  - REST API        │       │  (KRaft mode)   │
└─────────────┘       │  - Kafka Producer  │       │                 │
                      │  - Kafka Consumer  │◀──────│  Topics:        │
┌─────────────┐       │    (results)       │       │  • ml.prediction│
│   Client     │◀─────│  - Prometheus      │       │    .requests    │
│  GET /predict│      │    metrics         │       │  • ml.prediction│
│  /{id}       │      └───────────────────┘       │    .results     │
└─────────────┘                                    └────────┬────────┘
                                                            │
                                                            ▼
                      ┌───────────────────┐       ┌─────────────────┐
                      │  Grafana           │◀──────│  ML Worker      │
                      │  - Dashboards      │       │  - Kafka Consumer│
                      │                    │       │  - HuggingFace  │
                      └────────┬──────────┘       │    Sentiment    │
                               │                   │    Analysis     │
                      ┌────────┴──────────┐       │  - Kafka Producer│
                      │  Prometheus        │◀──────│  - Prometheus   │
                      │  - Metrics scrape  │       │    metrics      │
                      └───────────────────┘       └─────────────────┘
```

## Skills Demonstrated

| CV Bullet Point | Implementation |
|---|---|
| Backend APIs & ML-driven systems | FastAPI gateway + HuggingFace sentiment model |
| Cloud-native microservices & CI/CD | Docker Compose, **Kubernetes (Minikube)**, **Helm**, GitHub Actions CI + CD to **AWS EKS** |
| Event-driven & streaming architectures | Kafka (KRaft) with async producers/consumers |
| Data pipelines & model-serving | Kafka → ML Worker → inference → results topic |
| Reliability, scalability, observability | Prometheus metrics, Grafana dashboards, structured logging, health checks |
| Full service lifecycle | Architecture → code → Docker → Helm → Terraform (EKS/ECR/MSK) → CI/CD → monitoring |

## Tech Stack

- **Python 3.11** — async throughout
- **FastAPI** — REST API gateway
- **Apache Kafka** (KRaft mode) — event streaming backbone
- **HuggingFace Transformers** — `distilbert-base-uncased-finetuned-sst-2-english` sentiment model
- **Prometheus** — metrics collection
- **Grafana** — dashboards & visualization
- **Docker Compose** — local orchestration
- **Kubernetes** — production-style orchestration (Minikube for local dev)
- **Helm** — templated K8s packaging with per-environment values
- **Terraform** — AWS infrastructure as code (EKS, ECR, MSK)
- **GitHub Actions** — CI pipeline + CD pipeline (build → ECR → Helm deploy to EKS)
- **structlog** — structured JSON logging
- **Pydantic v2** — schema validation & settings management

## Quick Start

### Prerequisites
- Docker & Docker Compose v2
- ~4 GB free RAM (model + Kafka + monitoring)

### Run

```bash
# Clone and start everything
docker compose up --build -d

# Watch logs
docker compose logs -f gateway ml-worker
```

### Use the API

```bash
# Submit a prediction request
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "This product is absolutely amazing!"}'

# Response (202 Accepted):
# {"request_id": "abc-123", "status": "pending", "message": "Request enqueued for processing"}

# Poll for the result
curl http://localhost:8000/predict/abc-123

# Response (when ready):
# {"request_id": "abc-123", "label": "POSITIVE", "score": 0.9998, ...}
```

### Dashboards & Monitoring

| Service | URL |
|---|---|
| Gateway API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Gateway Metrics | http://localhost:8000/metrics |
| Worker Metrics | http://localhost:8001/metrics |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin) |

### Run Load Test

```bash
pip install httpx
python scripts/load_test.py --url http://localhost:8000 --requests 100 --concurrency 10
```

## Kubernetes Deployment (Minikube)

### Prerequisites
- [Minikube](https://minikube.sigs.k8s.io/docs/start/) installed
- [kubectl](https://kubernetes.io/docs/tasks/tools/) installed
- ~6 GB free RAM

### Deploy

```bash
# Start Minikube
minikube start --cpus=4 --memory=6144 --driver=docker

# Build images inside Minikube's Docker daemon
eval $(minikube docker-env)
docker build -f services/gateway/Dockerfile -t ml-pipeline-gateway:latest .
docker build -f services/ml_worker/Dockerfile -t ml-pipeline-worker:latest .

# Deploy all resources
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/kafka.yaml
kubectl -n ml-pipeline wait --for=condition=ready pod/kafka-0 --timeout=120s
kubectl apply -f k8s/kafka-init-job.yaml
kubectl -n ml-pipeline wait --for=condition=complete job/kafka-init-topics --timeout=120s
kubectl apply -f k8s/gateway.yaml -f k8s/ml-worker.yaml -f k8s/prometheus.yaml -f k8s/grafana.yaml

# Watch pods come up
kubectl -n ml-pipeline get pods -w
```

### Access Services

```bash
# Get the gateway URL
minikube service gateway -n ml-pipeline --url

# Test a prediction (replace IP with output above)
curl -X POST http://<MINIKUBE_IP>:30080/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "Kubernetes is great!"}'
```

| Service | NodePort URL |
|---|---|
| Gateway API | `http://<MINIKUBE_IP>:30080` |
| Prometheus | `http://<MINIKUBE_IP>:30090` |
| Grafana | `http://<MINIKUBE_IP>:30030` (admin/admin) |

### Scale Workers

```bash
# Scale ML workers horizontally (Kafka consumer group auto-balances)
kubectl -n ml-pipeline scale deployment ml-worker --replicas=3
```

### Tear Down

```bash
kubectl delete namespace ml-pipeline
minikube stop
```

## Project Structure

```
.
├── services/
│   ├── gateway/              # FastAPI REST API + Kafka producer/consumer
│   │   ├── app.py            # Main FastAPI application
│   │   ├── config.py         # Pydantic settings (env vars)
│   │   ├── metrics.py        # Prometheus counters/histograms
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── ml_worker/            # Kafka consumer + ML inference
│       ├── worker.py         # Main consumer loop
│       ├── model.py          # HuggingFace model wrapper
│       ├── config.py         # Pydantic settings (env vars)
│       ├── metrics.py        # Prometheus counters/histograms
│       ├── Dockerfile
│       └── requirements.txt
├── shared/                   # Shared modules across services
│   ├── schemas.py            # Pydantic request/response models
│   ├── kafka_utils.py        # Producer/consumer helpers with retries
│   └── logging_config.py     # Structured JSON logging setup
├── infra/
│   ├── prometheus/
│   │   └── prometheus.yml    # Scrape config
│   └── grafana/
│       ├── provisioning/     # Auto-configured datasource
│       └── dashboards/       # Pre-built ML pipeline dashboard
├── k8s/                      # Kubernetes manifests
│   ├── namespace.yaml        # ml-pipeline namespace
│   ├── kafka.yaml            # Kafka StatefulSet (KRaft)
│   ├── kafka-init-job.yaml   # Topic creation Job
│   ├── gateway.yaml          # Gateway Deployment + Service + ConfigMap
│   ├── ml-worker.yaml        # ML Worker Deployment + Service + PVC
│   ├── prometheus.yaml       # Prometheus Deployment + ConfigMap
│   └── grafana.yaml          # Grafana Deployment + ConfigMaps
├── tests/                    # Unit & integration tests
├── scripts/
│   └── load_test.py          # Async load testing tool
├── helm/ml-pipeline/         # Helm chart
│   ├── Chart.yaml            # Chart metadata
│   ├── values.yaml           # Default values
│   ├── values-dev.yaml       # Minikube / local overrides
│   ├── values-prod.yaml      # AWS EKS + MSK overrides
│   └── templates/            # Templated K8s manifests
├── .github/workflows/
│   ├── ci.yml                # CI: lint → test → build → integration
│   └── cd.yml                # CD: ECR push → Helm deploy to EKS
├── docker-compose.yml        # Local stack orchestration
└── pyproject.toml            # Project config, linting, test settings
```

## Data Flow

1. **Client** sends `POST /predict` with text to the **Gateway**
2. **Gateway** validates the request, assigns a UUID, publishes to `ml.prediction.requests` Kafka topic
3. **ML Worker** consumes the message, runs sentiment analysis inference
4. **ML Worker** publishes the result to `ml.prediction.results` Kafka topic
5. **Gateway** consumes results in a background task, stores them in-memory
6. **Client** polls `GET /predict/{request_id}` to retrieve the result

## Key Design Decisions

- **Async everywhere** — `aiokafka` for non-blocking Kafka I/O, FastAPI async endpoints
- **Idempotent producer** — `enable_idempotence=True` prevents duplicate messages
- **Manual commit** — Consumer commits only after successful processing (at-least-once)
- **Retry with backoff** — Kafka connections retry on startup for container orchestration
- **Bounded result store** — LRU eviction prevents unbounded memory growth (use Redis in production)
- **Structured logging** — JSON logs with service context for log aggregation (ELK/Loki)
- **Separate metrics ports** — Each service exposes its own `/metrics` for Prometheus scraping

## AWS Production Deployment

### How the CD Pipeline Works

```
┌───────────┐    ┌──────────────┐    ┌───────────────┐    ┌───────────────┐    ┌────────────┐
│ git push  │───▶│ CI Pipeline  │───▶│ Build & Push  │───▶│ Helm Deploy   │───▶│ Smoke Test │
│ to main   │    │ (lint, test, │    │ to Amazon ECR │    │ to AWS EKS    │    │ + Verify   │
│           │    │  build)      │    │ (SHA-tagged)  │    │ (helm upgrade)│    │            │
└───────────┘    └──────────────┘    └───────────────┘    └───────────────┘    └────────────┘
```

### AWS Infrastructure (Terraform)

The `infra/terraform/main.tf` provisions:

| Resource | Purpose |
|---|---|
| **VPC** | Private/public subnets across 3 AZs |
| **EKS** | Managed Kubernetes cluster (2x t3.large nodes) |
| **ECR** | Container registries for gateway + worker images |
| **MSK** | Managed Kafka cluster (replaces self-hosted Kafka) |

```bash
# One-time infrastructure setup
cd infra/terraform
terraform init
terraform plan
terraform apply

# Configure kubectl
aws eks update-kubeconfig --name ml-pipeline-cluster --region eu-west-1

# Deploy with Helm
helm upgrade --install ml-pipeline helm/ml-pipeline \
  --namespace ml-pipeline --create-namespace \
  --values helm/ml-pipeline/values.yaml \
  --values helm/ml-pipeline/values-prod.yaml \
  --set gateway.image.repository=<ECR_URL>/ml-pipeline-gateway \
  --set gateway.image.tag=<GIT_SHA> \
  --set mlWorker.image.repository=<ECR_URL>/ml-pipeline-worker \
  --set mlWorker.image.tag=<GIT_SHA>
```

### GitHub Secrets Required

| Secret | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user with ECR push + EKS deploy permissions |
| `AWS_SECRET_ACCESS_KEY` | Corresponding secret key |

### Helm: Deploy Locally with Minikube

```bash
# Instead of raw kubectl, use Helm:
helm upgrade --install ml-pipeline helm/ml-pipeline \
  --values helm/ml-pipeline/values.yaml \
  --values helm/ml-pipeline/values-dev.yaml
```

## Extending This Project

- **Redis** — Replace in-memory result store for multi-instance gateway
- **GPU inference** — Set `MLW_MODEL_DEVICE=cuda` and use NVIDIA Docker runtime
- **Horizontal scaling** — Run multiple ML workers (Kafka consumer group handles partitioning)
- **Schema Registry** — Add Confluent Schema Registry for Avro/Protobuf message validation
- **Batch inference** — Accumulate messages and run batched model inference for GPU efficiency
- **Model A/B testing** — Route traffic to different model versions via Kafka headers
- **ArgoCD** — GitOps-style continuous delivery as an alternative to push-based CD

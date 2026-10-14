import os
import re
import sys
from pathlib import Path
import json

base_dir = Path("c:/Users/arati.joshi/Desktop/kaims-latest/kaims-latest")

print("=== 1. AUDITING DOCKER-COMPOSE.YML ===")
compose_path = base_dir / "docker-compose.yml"
services_found = {}
current_service = None

with open(compose_path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

in_services = False
for line in lines:
    stripped = line.rstrip()
    if stripped.startswith("services:"):
        in_services = True
        continue
    if in_services:
        if line.startswith("  ") and not line.startswith("    ") and ":" in line:
            svc_name = line.strip().split(":")[0]
            if not svc_name.startswith("#"):
                current_service = svc_name
                services_found[current_service] = {"image": None, "build": None, "ports": [], "profiles": []}
        elif current_service and line.startswith("    "):
            content = line.strip()
            if content.startswith("image:"):
                services_found[current_service]["image"] = content.split("image:", 1)[1].strip()
            elif content.startswith("build:"):
                services_found[current_service]["build"] = content.split("build:", 1)[1].strip()
            elif "profiles:" in line or (content.startswith("-") and "profile" in str(services_found[current_service].get("last_key"))):
                services_found[current_service]["profiles"].append(content)

print(f"Total services in docker-compose.yml: {len(services_found)}")
for svc, details in services_found.items():
    print(f"  - {svc}: image={details['image']}, build={details['build']}")

print("\n=== 2. AUDITING FRONTEND TECH STACK ===")
frontend_pkg = base_dir / "frontend" / "package.json"
if frontend_pkg.exists():
    with open(frontend_pkg, "r", encoding="utf-8") as f:
        pkg_data = json.load(f)
        print("Frontend dependencies:")
        for k, v in pkg_data.get("dependencies", {}).items():
            print(f"  {k}: {v}")

print("\n=== 3. SEARCHING PYTHON CODEBASE FOR KEY TECHNOLOGIES ===")
tech_patterns = {
    "MySQL": [r"\bmysql\b", r"\baiomysql\b", r"\bpymysql\b"],
    "PostgreSQL": [r"\bpostgresql\b", r"\bpsycopg2\b", r"\basyncpg\b", r"\bpgvector\b"],
    "SQLite": [r"\bsqlite\b", r"\baiosqlite\b"],
    "MongoDB": [r"\bmongodb\b", r"\bpymongo\b", r"\bmotor\b"],
    "Redis": [r"\bredis\b", r"\baioredis\b"],
    "Qdrant": [r"\bqdrant\b", r"\bqdrant_client\b"],
    "Chroma": [r"\bchromadb\b", r"\bchroma\b"],
    "FAISS": [r"\bfaiss\b"],
    "Pinecone": [r"\bpinecone\b"],
    "Weaviate": [r"\bweaviate\b"],
    "Milvus": [r"\bmilvus\b", r"\bpymilvus\b"],
    "Elasticsearch": [r"\belasticsearch\b"],
    "OpenSearch": [r"\bopensearch\b"],
    "RabbitMQ": [r"\brabbitmq\b", r"\baio_pika\b", r"\bpika\b"],
    "Kafka": [r"\bkafka\b", r"\baiokafka\b"],
    "Celery": [r"\bcelery\b"],
    "LangGraph": [r"\blanggraph\b", r"StateGraph"],
    "LangChain": [r"\blangchain\b"],
    "FastAPI": [r"\bfastapi\b", r"FastAPI\("],
    "Prometheus": [r"\bprometheus\b", r"prometheus_client"],
    "OpenTelemetry": [r"\bopentelemetry\b", r"\botel\b"],
    "Grafana": [r"\bgrafana\b"],
    "OpenAI": [r"\bopenai\b", r"OpenAI"],
    "Azure OpenAI": [r"azure[_-]openai", r"AzureOpenAI"],
    "Azure AI Search": [r"azure[_-]ai[_-]search", r"AzureAISearch"],
    "Gemini": [r"\bgemini\b"],
    "Groq": [r"\bgroq\b"],
    "Ollama": [r"\bollama\b"],
    "Temporal": [r"\btemporal\b", r"temporalio"],
    "Jira": [r"\bjira\b"],
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
    "Docker": [r"\bdocker\b"],
}

tech_matches = {tech: set() for tech in tech_patterns}

py_files = list(base_dir.rglob("*.py"))
print(f"Total python files scanned: {len(py_files)}")

for p in py_files:
    if any(ignore in p.parts for ignore in [".git", "node_modules", ".pytest_cache", "venv"]):
        continue
    rel_path = p.relative_to(base_dir)
    try:
        content = p.read_text(encoding="utf-8", errors="ignore")
        for tech, patterns in tech_patterns.items():
            for pat in patterns:
                if re.search(pat, content, re.IGNORECASE):
                    tech_matches[tech].add(str(rel_path))
                    break
    except Exception as e:
        pass

print("\n--- TECHNOLOGY SEARCH RESULTS IN CODEBASE (.py files) ---")
for tech, files in sorted(tech_matches.items()):
    in_app_code = [f for f in files if not f.startswith("tests") and not "tests/" in f and not "test_" in f]
    print(f"{tech}: {len(files)} total files ({len(in_app_code)} app code files)")
    if in_app_code:
        for f in in_app_code[:5]:
            print(f"    - {f}")
        if len(in_app_code) > 5:
            print(f"    ... and {len(in_app_code) - 5} more")


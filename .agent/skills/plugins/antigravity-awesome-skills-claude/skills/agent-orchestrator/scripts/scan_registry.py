#!/usr/bin/env python3
"""
Auto-Discovery Engine for Agent Orchestrator.

Scans the skills ecosystem for SKILL.md files, parses metadata,
and maintains a centralized registry (registry.json).

Features:
- Runs automatically on every request (called by CLAUDE.md)
- Ultra-fast via MD5 hash caching (~<100ms when nothing changed)
- Auto-includes new skills, auto-removes deleted skills
- Zero manual intervention required

Usage:
    python scan_registry.py              # Quick scan (hash-based)
    python scan_registry.py --status     # Verbose status table
    python scan_registry.py --force      # Full re-scan ignoring hashes
"""

import os
import sys
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────

# Resolve paths relative to this script's location
_SCRIPT_DIR = Path(__file__).resolve().parent
ORCHESTRATOR_DIR = _SCRIPT_DIR.parent
SKILLS_ROOT = ORCHESTRATOR_DIR.parent
DATA_DIR = ORCHESTRATOR_DIR / "data"
REGISTRY_PATH = DATA_DIR / "registry.json"
HASHES_PATH = DATA_DIR / "registry_hashes.json"

# Where to search for SKILL.md files
SEARCH_PATHS = [
    SKILLS_ROOT / ".claude" / "skills",   # registered skills
    SKILLS_ROOT,                           # top-level standalone
]
MAX_DEPTH = 3  # max directory depth for SKILL.md search

# Capability keyword mapping (PT + EN)
CAPABILITY_MAP = {
    "data-extraction": [
        "scrape", "extract", "crawl", "parse", "harvest", "collect",
        "raspar", "extrair", "coletar", "dados",
    ],
    "messaging": [
        "whatsapp", "message", "send", "chat", "notification", "sms",
        "mensagem", "enviar", "notificacao", "atendimento",
    ],
    "social-media": [
        "instagram", "facebook", "twitter", "post", "stories", "reels",
        "social", "engagement", "feed", "follower",
    ],
    "government-data": [
        "junta", "leiloeiro", "cadastro", "governo", "comercial",
        "tribunal", "diario oficial", "certidao", "registro",
    ],
    "web-automation": [
        "browser", "selenium", "playwright", "automate", "click",
        "navegador", "automatizar", "automacao",
    ],
    "api-integration": [
        "api", "endpoint", "webhook", "rest", "graph", "oauth",
        "integracao", "integrar",
    ],
    "analytics": [
        "insight", "analytics", "metrics", "dashboard", "report",
        "relatorio", "metricas", "analise",
    ],
    "content-management": [
        "publish", "schedule", "template", "content", "media",
        "publicar", "agendar", "conteudo", "midia",
    ],
    "legal": [
        "advogado", "direito", "juridico", "lei", "processo",
        "acao", "peticao", "recurso", "sentenca", "juiz",
        "divorcio", "guarda", "alimentos", "pensao", "alimenticia", "inventario", "heranca", "partilha",
        "acidente de trabalho", "acidente",
        "familia", "criminal", "penal", "crime", "feminicidio", "maria da penha",
        "violencia domestica", "medida protetiva", "stalking",
        "danos morais", "responsabilidade civil", "indenizacao", "dano",
        "consumidor", "cdc", "plano de saude",
        "trabalhista", "clt", "rescisao", "fgts", "horas extras",
        "previdenciario", "aposentadoria", "aposentar", "inss",
        "imobiliario", "usucapiao", "despejo", "inquilinato",
        "alienacao fiduciaria", "bem de familia",
        "tributario", "imposto", "icms", "execucao fiscal",
        "administrativo", "licitacao", "improbidade", "mandado de seguranca",
        "empresarial", "societario", "falencia", "recuperacao judicial",
        "empresa", "ltda", "cnpj", "mei", "eireli", "contrato social",
        "contrato", "clausula", "contestacao", "apelacao", "agravo",
        "habeas corpus", "mandado", "liminar", "tutela",
        "cpc", "stj", "stf", "sumula", "jurisprudencia",
        "oab", "honorarios", "custas",
    ],
    "auction": [
        "leilao", "leilao judicial", "leilao extrajudicial", "hasta publica",
        "arrematacao", "arrematar", "arrematante", "lance", "desagio",
        "edital leilao", "penhora", "adjudicacao", "praca",
        "imissao na posse", "carta arrematacao", "vil preco",
        "avaliacao imovel", "laudo", "perito", "matricula",
        "leiloeiro", "comissao leiloeiro",
    ],
    "security": [
        "seguranca", "security", "owasp", "vulnerability", "incident",
        "pentest", "firewall", "malware", "phishing", "cve",
        "autenticacao", "criptografia", "encryption",
    ],
    "image-generation": [
        "imagem", "image", "gerar imagem", "generate image",
        "stable diffusion", "comfyui", "midjourney", "dall-e",
        "foto", "ilustracao", "arte", "design",
    ],
    "monitoring": [
        "monitor", "monitorar", "health", "status",
        "audit", "auditoria", "sentinel", "check",
    ],
    "context-management": [
        "contexto", "context", "sessao", "session", "compactacao", "compaction",
        "comprimir", "compress", "snapshot", "checkpoint", "briefing",
        "continuidade", "continuity", "preservar", "preserve",
        "memoria", "memory", "resumo", "summary",
        "salvar estado", "save state", "context window", "janela de contexto",
        "perda de dados", "data loss", "backup",
    ],
}

# ── Utility Functions ──────────────────────────────────────────────────────

def hash_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_yaml_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a SKILL.md file."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}

    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}

    try:
        import yaml
        return yaml.safe_load(match.group(1)) or {}
    except Exception:
        # Fallback: manual parsing for name/description
        result = {}
        block = match.group(1)
        for key in ("name", "description", "version"):
            m = re.search(rf'^{key}:\s*["\']?(.+?)["\']?\s*$', block, re.MULTILINE)
            if m:
                result[key] = m.group(1).strip()
            else:
                # Handle multi-line description with >- or >
                m2 = re.search(rf'^{key}:\s*>-?\s*\n((?:\s+.+\n?)+)', block, re.MULTILINE)
                if m2:
                    lines = m2.group(1).strip().split("\n")
                    result[key] = " ".join(line.strip() for line in lines)
        return result


def find_skill_files() -> list[Path]:
    """Find all SKILL.md files in the ecosystem."""
    found = set()

    for base in SEARCH_PATHS:
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base):
            depth = len(Path(root).relative_to(base).parts)
            if depth > MAX_DEPTH:
                dirs.clear()
                continue

            # Skip the orchestrator itself
            if "agent-orchestrator" in Path(root).parts:
                continue

            if "SKILL.md" in files:
                found.add(Path(root) / "SKILL.md")

    return sorted(found)


def detect_language(skill_dir: Path) -> str:
    """Detect primary language from scripts/ directory."""
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.exists():
        return "none"

    extensions = set()
    for f in scripts_dir.rglob("*"):
        if f.is_file():
            extensions.add(f.suffix.lower())

    if ".py" in extensions:
        return "python"
    if ".ts" in extensions or ".js" in extensions:
        return "nodejs"
    if ".sh" in extensions:
        return "bash"
    return "none"


def extract_capabilities(description: str) -> list[str]:
    """Map description keywords to capability tags using word boundary matching."""
    if not description:
        return []

    desc_lower = description.lower()
    desc_words = set(re.findall(r'[a-zA-ZÀ-ÿ]+', desc_lower))
    caps = []
    for cap, keywords in CAPABILITY_MAP.items():
        for kw in keywords:
            # Multi-word keywords: substring match. Single-word: exact word match.
            if " " in kw:
                if kw in desc_lower:
                    caps.append(cap)
                    break
            elif kw in desc_words:
                caps.append(cap)
                break
    return sorted(caps)


def extract_triggers(description: str) -> list[str]:
    """Extract trigger keywords from description text using word boundary matching."""
    if not description:
        return []

    # Collect all keywords from all capability categories
    all_keywords = set()
    for keywords in CAPABILITY_MAP.values():
        all_keywords.update(keywords)

    desc_lower = description.lower()
    desc_words = set(re.findall(r'[a-zA-ZÀ-ÿ]+', desc_lower))
    found = []
    for kw in sorted(all_keywords):
        if " " in kw:
            if kw in desc_lower:
                found.append(kw)
        elif kw in desc_words:
            found.append(kw)
    return found


def assess_status(skill_dir: Path) -> str:
    """
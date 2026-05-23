# Agentic Web: Weaving the Next Web with AI Agents — Reference for AUREM

> Source: https://github.com/SafeRL-Lab/agentic-web
> Paper: https://arxiv.org/pdf/2507.21206
> 451 Stars | SafeRL-Lab (UC Berkeley, SJTU, UCL, Virginia Tech) | Apache 2.0
> Saved: February 2026

## What Is It?

A comprehensive **academic survey and curated paper list** tracking the evolution from the traditional web to the "Agentic Web" — where AI agents autonomously navigate, retrieve, transact, and collaborate across web environments. Published by researchers from UC Berkeley, Shanghai Jiao Tong University, UCL, and others.

---

## Why It Matters for AUREM

AUREM is building an AI-powered business automation SaaS. This survey maps the entire research landscape that underpins AUREM's core capabilities:
- **Web agents** that autonomously complete business tasks (CRM, email, pipeline management)
- **Multi-agent systems** for collaborative AI workflows (ORA AI co-pilot)
- **Safety & security** frameworks for enterprise-grade trust
- **Information retrieval** powering intelligent search and recommendations

---

## Core Research Categories

### 1. Agentic Web Development
The foundational research on AI agents that operate autonomously on the web.

**Key Papers for AUREM:**
| Paper | Relevance |
|-------|-----------|
| **ReAct** (Yao et al., 2023) | Synergizing reasoning + acting — core pattern for ORA AI task execution |
| **Plan-and-Act** (Erdogan et al., 2025) | Long-horizon task planning — pipeline automation, multi-step CRM workflows |
| **WebDancer** (Wu et al., 2025) | Autonomous information seeking — powers deep research features |
| **ToolLLM** (Qin et al., 2023) | Mastering 16,000+ real-world APIs — AUREM's API Gateway integration model |
| **Voyager** (Wang et al., 2023) | Open-ended embodied agent with LLMs — adaptive agent that learns new skills |
| **MA-RAG** (Nguyen et al., 2025) | Multi-agent RAG via chain-of-thought — upgrade path for ORA AI knowledge base |
| **Deep Research Agents** (Huang et al., 2025) | Systematic roadmap for research agents — competitor intelligence automation |
| **BetaWeb** (Guo et al., 2025) | Blockchain-enabled trustworthy agentic web — future Web3 integration for AUREM |
| **WebArena** (Zhou et al., 2023) | Realistic web environment for autonomous agents — testing/benchmark framework |

### 2. Information Retrieval
How agents find, rank, and surface relevant information.

**Key Papers for AUREM:**
| Paper | Relevance |
|-------|-----------|
| **Agentic Information Retrieval** (Zhang et al., 2025) | Core framework for agent-powered search within AUREM |
| **LLMs for Generative Information Extraction** (Xu et al., 2024) | Extract structured data from unstructured sources (emails, docs, web pages) |
| **ArchRAG** (Wang et al., 2025) | Hierarchical RAG — upgrade ORA AI from basic chat to community-based knowledge retrieval |
| **DeepFM** (Guo et al., 2017) | CTR prediction — optimize AUREM's recommendation/ranking of leads and opportunities |
| **Wide & Deep Learning** (Cheng et al., 2016) | Recommender systems architecture — lead scoring and pipeline prioritization |
| **PageRank** (Page et al., 1999) | Foundational ranking — network-based lead/contact importance scoring |

### 3. Recommendation Systems
Agent-powered recommendation for personalized experiences.

**Key Papers for AUREM:**
| Paper | Relevance |
|-------|-----------|
| **LLM-Powered Agents for Recommendation & Search** (Zhang et al., 2025) | Next-gen information retrieval — AUREM's smart lead recommendations |
| **MACRec** (Wang et al., 2024) | Multi-agent collaboration for recommendations — team-based deal recommendations |
| **AgentRecBench** (Shang et al., 2025) | Benchmark for agent-based personalized recommenders — validation framework |
| **RASERec** (Zhao et al., 2024) | Retrieval-augmented sequential recommendation — time-aware pipeline suggestions |
| **Deep RL for List-wise Recommendations** (Zhao et al., 2019) | RL-based ranking — optimize which deals/leads surface first |

### 4. Agent Planning
How agents decompose complex goals into executable steps.

**Key Papers for AUREM:**
| Paper | Relevance |
|-------|-----------|
| **PlanGenLLMs** (Wei et al., 2025) | Modern survey of LLM planning — foundation for AUREM's workflow automation |
| **Plan-and-Act** (Erdogan et al., 2025) | Long-horizon task planning — multi-step business process automation |
| **AdaPlanner** (Sun et al., 2023) | Adaptive planning from feedback — agents that self-correct during execution |
| **Natural Plan** (Zheng et al., 2024) | Natural language planning benchmark — evaluate ORA AI's planning accuracy |

### 5. Multi-Agent Learning
Coordinating multiple AI agents for complex collaborative tasks.

**Key Papers for AUREM:**
| Paper | Relevance |
|-------|-----------|
| **AutoGen** (Wu et al., 2024) | Multi-agent conversations framework — orchestrate AUREM's agent team |
| **MetaGPT** (Hong et al., 2023) | Meta programming for multi-agent collaboration — software dev automation |
| **ChatDev** (Qian et al., 2023) | Communicative agents for software development — automated feature building |
| **CAMEL** (Li et al., 2023) | Agent society exploration — multi-role business simulation |
| **AgentVerse** (Chen et al., 2023) | Multi-agent emergent behaviors — discover unexpected optimization paths |
| **REALM-Bench** (Geng et al., 2025) | Real-world planning benchmark for multi-agent systems — validation |
| **MARLRank** (Zou et al., 2019) | Multi-agent reinforced learning to rank — competitive lead ranking |

### 6. Safety and Security
Critical for enterprise SaaS — ensuring agents behave safely and securely.

**Key Papers for AUREM:**
| Paper | Relevance |
|-------|-----------|
| **Securing Agentic AI** (Narajala et al., 2025) | Comprehensive threat model for AI agents — AUREM security architecture |
| **MCP Security** (Hou et al., 2025) | Model Context Protocol threats — secure AUREM's API Gateway |
| **AI Agents Under Threat** (Deng et al., 2025) | Key security challenges survey — threat modeling for multi-tenant SaaS |
| **Enterprise MCP Security** (Narajala et al., 2025) | Enterprise-grade frameworks — directly applicable to AUREM's security layer |
| **Red-Teaming LLM Multi-Agent Systems** (He et al., 2025) | Communication attack vectors — protect ORA AI agent communications |
| **Agent-SafetyBench** (Zhang et al.) | Safety evaluation for LLM agents — benchmark AUREM's agent safety |
| **AI Safety Must Embrace Antifragile Perspective** (Jin et al., 2025) | Beyond robustness to antifragility — agents that improve from adversarial pressure |
| **Concrete Problems in AI Safety** (Amodei et al., 2016) | Foundational safety research — avoid reward hacking, safe exploration |

### 7. Benchmarks
Testing frameworks for evaluating web agents.

**Key Papers for AUREM:**
| Benchmark | What It Tests |
|-----------|---------------|
| **SafeArena** (Tur et al., 2025) | Safety of autonomous web agents |
| **WebArena** (Zhou et al., 2023) | Realistic web environment for agent autonomy |
| **WorkArena** (Drouin et al., 2024) | Common knowledge work tasks (closest to AUREM's use case) |
| **BrowserGym** (Chezelles et al., 2024) | Ecosystem for web agent research |
| **VisualWebArena** (Koh et al., 2024) | Multimodal agents on visual web tasks |
| **Mind2Web** (Deng et al., 2023) | Generalist web agent evaluation |
| **ST-WebAgentBench** (Levy et al., 2024) | Safety and trustworthiness in web agents |

---

## Web Evolution Timeline (From Survey)

| Era | Period | Key Feature |
|-----|--------|-------------|
| **Web 1.0** | 1990s–2000s | Static pages, directories, read-only |
| **Web 2.0** | 2000s–2020s | User-generated content, social, interactive |
| **Agentic Web** | 2020s+ | AI agents autonomously navigate, transact, collaborate |

The Agentic Web is characterized by:
- Agents that **plan and execute** multi-step web tasks
- **Multi-agent collaboration** for complex workflows
- **Safety-first** design with adversarial robustness
- **Personalized retrieval** and recommendation at scale

---

## Strategic Implementation Roadmap for AUREM

### Phase 1: Foundation (Current)
- Implement **ReAct pattern** in ORA AI (reasoning + acting loop)
- Adopt **AdaPlanner** for self-correcting workflow automation
- Apply **Securing Agentic AI** threat model to security architecture

### Phase 2: Intelligence (Next)
- Upgrade to **MA-RAG** for multi-agent retrieval (ORA AI knowledge base)
- Implement **MACRec** pattern for deal/lead recommendations
- Deploy **WorkArena-style** benchmarks for internal QA

### Phase 3: Autonomy (Future)
- Build **AutoGen-style** multi-agent orchestration for autonomous business processes
- Implement **Plan-and-Act** for long-horizon task automation
- Add **BetaWeb** blockchain trust layer for verifiable agent actions

---

## Citation
```bibtex
@article{yang2025agentic,
  title={Agentic Web: Weaving the Next Web with AI Agents},
  author={Yang, Yingxuan and Ma, Mulei and Huang, Yuxuan and others},
  journal={arXiv preprint arXiv:2507.21206},
  year={2025}
}
```

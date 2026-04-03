# AUREM Agent Harness - Quick Start Guide

## 🤖 What is the Agent Harness?

The AUREM Agent Harness is an ECC-inspired system that provides **AI-powered development automation** for the AUREM platform.

**Inspired by:** [Everything Claude Code (ECC)](https://github.com/affaan-m/everything-claude-code) - 136k+ stars

---

## 🎯 Available Agents

### 1. **build-fixer** (ACTIVE)

**Purpose:** Detects and auto-fixes build errors in AUREM codebase

**Capabilities:**
- ✅ Detect missing imports
- ✅ Detect missing singleton patterns  
- ✅ Fix import paths
- ✅ Auto-generate missing functions
- ✅ Verify fixes with Python import test

**Example Use Case:**
```
Problem: API endpoint returning 404
Root Cause: Missing singleton function get_connector_ecosystem()
Fix: Auto-generated singleton pattern
Verification: Python import test passed ✅
```

---

## 🚀 API Endpoints

### List All Agents
```bash
GET /api/dev/agents/
```

**Response:**
```json
{
  "total_agents": 1,
  "agents": [
    {
      "name": "aurem-build-fixer",
      "description": "Detects and auto-fixes build errors in AUREM codebase",
      "executions": 5,
      "success": 4,
      "failure": 1,
      "success_rate": 80.0
    }
  ]
}
```

---

### Execute Agent
```bash
POST /api/dev/agents/execute
```

**Request:**
```json
{
  "agent_name": "build-fixer",
  "context": {
    "error_type": "import_error",
    "error_message": "cannot import name 'get_connector_ecosystem' from 'services.connector_ecosystem'",
    "auto_fix": true
  }
}
```

**Response:**
```json
{
  "success": true,
  "fix_applied": true,
  "fix_description": "Added singleton pattern for ConnectorEcosystem",
  "function_added": "get_connector_ecosystem",
  "class_name": "ConnectorEcosystem",
  "file_path": "/app/backend/services/connector_ecosystem.py",
  "verification": {
    "success": true,
    "return_code": 0,
    "stdout": "✅ Import successful\n"
  },
  "execution_time": 0.45,
  "agent": "aurem-build-fixer",
  "timestamp": "2026-04-03T14:30:00Z"
}
```

---

### Diagnose 404 Errors
```bash
POST /api/dev/agents/diagnose-404
```

**Request:**
```json
{
  "problem": "Connector API returning 404",
  "endpoint": "/api/connectors/platforms",
  "error_message": "Not Found"
}
```

**Response:**
```json
{
  "success": true,
  "diagnosis": "Import error detected in router",
  "error_message": "ImportError: cannot import name 'get_connector_ecosystem'...",
  "fix_result": {
    "success": true,
    "fix_applied": true,
    "fix_description": "Added singleton pattern for ConnectorEcosystem"
  }
}
```

---

### Quick Fix Build Error
```bash
POST /api/dev/agents/fix-build-error?error_type=import_error&error_message=cannot%20import%20name%20...&auto_fix=true
```

---

## 📊 Agent Statistics

### Get Stats for Specific Agent
```bash
GET /api/dev/agents/build-fixer/stats
```

**Response:**
```json
{
  "name": "aurem-build-fixer",
  "description": "Detects and auto-fixes build errors in AUREM codebase",
  "executions": 10,
  "success": 9,
  "failure": 1,
  "success_rate": 90.0
}
```

---

## 🛠️ How It Works

### Architecture

```
┌──────────────────────────────────────────┐
│         AUREM Agent Harness              │
├──────────────────────────────────────────┤
│  Coordinator (harness.py)                │
│  ├─ Agent Registration                   │
│  ├─ Task Delegation                      │
│  ├─ Execution Tracking                   │
│  └─ Statistics                           │
├──────────────────────────────────────────┤
│  Agents:                                 │
│  ├─ build-fixer (ACTIVE)                 │
│  ├─ code-reviewer (PLANNED)              │
│  ├─ security-scanner (PLANNED)           │
│  ├─ planner (PLANNED)                    │
│  ├─ tdd-guide (PLANNED)                  │
│  ├─ mongo-optimizer (PLANNED)            │
│  ├─ refactor-agent (PLANNED)             │
│  ├─ doc-sync (PLANNED)                   │
│  ├─ e2e-runner (PLANNED)                 │
│  └─ architect (PLANNED)                  │
└──────────────────────────────────────────┘
```

### Execution Flow

1. **API Request** → Agent Harness Router
2. **Harness** → Selects appropriate agent
3. **Agent** → Executes task
4. **Tracking** → Records execution stats
5. **Response** → Returns result with metadata

---

## 📈 Success Story: Fixing 404 Router Issue

### Problem
- **Issue:** `/api/connectors/platforms` returning 404
- **Root Cause:** Missing `get_connector_ecosystem()` singleton function
- **Impact:** Blocked connector ecosystem testing

### Solution (Using build-fixer Agent)

1. **Detection:**
   - Agent detected import error in `connector_router.py`
   - Identified missing singleton pattern

2. **Fix Generation:**
   - Auto-generated singleton pattern:
     ```python
     _connector_ecosystem = ConnectorEcosystem()
     
     def get_connector_ecosystem() -> ConnectorEcosystem:
         return _connector_ecosystem
     ```

3. **Verification:**
   - Ran Python import test
   - Confirmed successful import
   - Verified API endpoint responds correctly

4. **Result:**
   - ✅ API endpoint now accessible
   - ✅ 12 connectors available via API
   - ✅ Fix applied in <1 second

---

## 🔮 Future Agents (Planned)

### code-reviewer
**Purpose:** Review code changes for quality, security, maintainability  
**Capabilities:** OWASP Top 10, PEP 8, type hints, code smells

### security-scanner
**Purpose:** SaaS-specific security audit  
**Capabilities:** Auth vulnerabilities, payment security, API key exposure

### planner
**Purpose:** Plan new features with DB/API/UI structure  
**Capabilities:** Architecture design, task breakdown, estimation

### tdd-guide
**Purpose:** Enforce TDD workflow  
**Capabilities:** Test-first development, coverage tracking, pytest/Playwright

### mongo-optimizer
**Purpose:** MongoDB query optimization  
**Capabilities:** Anti-pattern detection, index suggestions, query performance

### refactor-agent
**Purpose:** Remove dead code, optimize structure  
**Capabilities:** Break down massive files (server.py 43K lines!), unused code removal

### doc-sync
**Purpose:** Auto-update documentation  
**Capabilities:** API docs, connector docs, changelog generation

### e2e-runner
**Purpose:** Generate E2E tests  
**Capabilities:** Subscription flows, connector tests, admin workflows

### architect
**Purpose:** Design scalable architecture  
**Capabilities:** System design, technology selection, scalability planning

---

## 🎯 Integration with ECC Principles

### Borrowed Concepts

1. **Agent Pattern**
   - Specialized subagents for specific tasks
   - Clear separation of concerns
   - Execution tracking and statistics

2. **Skills System** (Coming Soon)
   - Reusable workflows (TDD, Security Review, API Design)
   - Can be invoked directly or by agents
   - Cross-agent skill sharing

3. **Hooks System** (Planned)
   - PreFileEdit, PostAPICall, PreDeploy
   - Automatic quality enforcement
   - Real-time code health monitoring

4. **Command Palette** (Planned)
   - `/aurem plan <feature>`
   - `/aurem review`
   - `/aurem security`
   - `/aurem fix-build`

---

## 📚 References

- **ECC Repository:** https://github.com/affaan-m/everything-claude-code
- **ECC Tools:** https://ecc.tools
- **Integration Plan:** `/app/CLAUDE_CODE_ECC_INTEGRATION_PLAN.md`
- **Author:** [@affaanmustafa](https://x.com/affaanmustafa)

---

## ✅ Current Status

**Phase 1: Core ECC Adaptation** (IN PROGRESS)
- ✅ Base Agent class implemented
- ✅ Agent Harness coordinator created
- ✅ build-fixer agent implemented and TESTED
- ✅ API endpoints functional
- ⏳ 9 more agents to implement
- ⏳ Skills library (10 skills)
- ⏳ Hooks system (8 hooks)

**Next Steps:**
- Implement code-reviewer agent
- Implement security-scanner agent
- Build TDD workflow skill
- Create Dev Tools Panel UI

---

**Last Updated:** April 3, 2026  
**Version:** 0.1.0 (Alpha)  
**Status:** Agent Harness Active ✅

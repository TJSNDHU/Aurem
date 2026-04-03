"""
GitHub Integration Router
Auto-connect subscriber repos, ingest docs/code, build RAG knowledge base
For commercial AI chatbot customization per company
"""

import os
import re
import base64
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field
import hashlib

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/github", tags=["GitHub Integration"])

# MongoDB reference
_db = None

def set_db(database):
    """Set database reference"""
    global _db
    _db = database

# GitHub API Configuration
GITHUB_API_URL = "https://api.github.com"
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.environ.get("GITHUB_REDIRECT_URI", "https://reroots.ca/api/github/callback")

# File types to ingest for knowledge base
INGESTIBLE_EXTENSIONS = {
    # Documentation
    '.md', '.mdx', '.txt', '.rst', '.adoc',
    # Code (for understanding product structure)
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rb', '.php',
    # Config (for understanding setup)
    '.json', '.yaml', '.yml', '.toml', '.ini',
    # Web
    '.html', '.css',
}

# Files to prioritize for ingestion
PRIORITY_FILES = [
    'README.md', 'README', 'readme.md',
    'DOCUMENTATION.md', 'docs/README.md',
    'CONTRIBUTING.md', 'CHANGELOG.md',
    'package.json', 'requirements.txt', 'setup.py',
    'API.md', 'api.md', 'docs/api.md',
]

# Directories to search for docs
DOC_DIRECTORIES = ['docs', 'documentation', 'doc', 'wiki', 'guides', 'tutorials']


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class GitHubConnectRequest(BaseModel):
    company_id: str = Field(..., description="Subscriber company ID")
    access_token: str = Field(..., description="GitHub OAuth access token")


class RepoSelectRequest(BaseModel):
    company_id: str
    repos: List[str] = Field(..., description="List of repo full names (owner/repo)")


class IngestRepoRequest(BaseModel):
    company_id: str
    repo_full_name: str = Field(..., description="Format: owner/repo")
    branches: List[str] = Field(default=["main", "master"], description="Branches to ingest")
    include_code: bool = Field(default=False, description="Include source code files")
    max_files: int = Field(default=100, description="Max files to ingest")


class ChatWithRepoRequest(BaseModel):
    company_id: str
    message: str
    session_id: Optional[str] = None
    repo_filter: Optional[str] = None  # Filter to specific repo


# ═══════════════════════════════════════════════════════════════════════════════
# GITHUB API HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def github_request(endpoint: str, access_token: str, method: str = "GET", data: Dict = None) -> Dict:
    """Make authenticated GitHub API request"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                response = await client.get(f"{GITHUB_API_URL}{endpoint}", headers=headers)
            else:
                response = await client.post(f"{GITHUB_API_URL}{endpoint}", headers=headers, json=data)
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            elif response.status_code == 404:
                return {"success": False, "error": "Not found"}
            else:
                return {"success": False, "error": f"GitHub API error: {response.status_code}"}
                
    except Exception as e:
        logger.error(f"[GitHub] API request error: {e}")
        return {"success": False, "error": str(e)}


async def get_file_content(repo: str, path: str, access_token: str, branch: str = "main") -> Optional[str]:
    """Get decoded file content from GitHub"""
    result = await github_request(f"/repos/{repo}/contents/{path}?ref={branch}", access_token)
    
    if result.get("success") and result.get("data"):
        content = result["data"].get("content", "")
        encoding = result["data"].get("encoding", "")
        
        if encoding == "base64" and content:
            try:
                return base64.b64decode(content).decode('utf-8', errors='ignore')
            except Exception:
                return None
    return None


async def get_repo_tree(repo: str, access_token: str, branch: str = "main") -> List[Dict]:
    """Get repository file tree"""
    result = await github_request(f"/repos/{repo}/git/trees/{branch}?recursive=1", access_token)
    
    if result.get("success") and result.get("data"):
        tree = result["data"].get("tree", [])
        return [item for item in tree if item.get("type") == "blob"]
    return []


# ═══════════════════════════════════════════════════════════════════════════════
# OAUTH FLOW
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/oauth/start")
async def github_oauth_start(company_id: str, redirect_after: str = "/dashboard"):
    """
    Start GitHub OAuth flow - redirect user to GitHub authorization
    """
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")
    
    # Store state for CSRF protection
    import secrets
    state = secrets.token_urlsafe(32)
    
    if _db is not None:
        await _db.github_oauth_states.insert_one({
            "state": state,
            "company_id": company_id,
            "redirect_after": redirect_after,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": datetime.now(timezone.utc).isoformat()  # + 10 minutes
        })
    
    # Build GitHub authorization URL
    scope = "repo read:org read:user"
    auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={GITHUB_REDIRECT_URI}"
        f"&scope={scope}"
        f"&state={state}"
    )
    
    return {"auth_url": auth_url, "state": state}


@router.get("/callback")
async def github_oauth_callback(code: str, state: str):
    """
    Handle GitHub OAuth callback - exchange code for access token
    """
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")
    
    # Verify state
    stored_state = None
    if _db is not None:
        stored_state = await _db.github_oauth_states.find_one({"state": state})
        if not stored_state:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        await _db.github_oauth_states.delete_one({"state": state})
    
    company_id = stored_state.get("company_id") if stored_state else "unknown"
    
    # Exchange code for access token
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": GITHUB_REDIRECT_URI
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                access_token = data.get("access_token")
                
                if access_token:
                    # Get user info
                    user_result = await github_request("/user", access_token)
                    github_user = user_result.get("data", {}) if user_result.get("success") else {}
                    
                    # Store connection
                    if _db is not None:
                        await _db.github_connections.update_one(
                            {"company_id": company_id},
                            {
                                "$set": {
                                    "access_token": access_token,
                                    "github_user": github_user.get("login"),
                                    "github_id": github_user.get("id"),
                                    "avatar_url": github_user.get("avatar_url"),
                                    "connected_at": datetime.now(timezone.utc).isoformat(),
                                    "scope": data.get("scope", "")
                                }
                            },
                            upsert=True
                        )
                    
                    # Redirect to success page
                    redirect_url = stored_state.get("redirect_after", "/dashboard") if stored_state else "/dashboard"
                    return {
                        "status": "connected",
                        "github_user": github_user.get("login"),
                        "redirect": redirect_url
                    }
                else:
                    raise HTTPException(status_code=400, detail="Failed to get access token")
            else:
                raise HTTPException(status_code=400, detail="OAuth exchange failed")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GitHub] OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connect")
async def connect_github(request: GitHubConnectRequest):
    """
    Connect GitHub using provided access token (alternative to OAuth flow)
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Verify token by fetching user info
        user_result = await github_request("/user", request.access_token)
        
        if not user_result.get("success"):
            raise HTTPException(status_code=401, detail="Invalid GitHub access token")
        
        github_user = user_result.get("data", {})
        
        # Store connection
        await _db.github_connections.update_one(
            {"company_id": request.company_id},
            {
                "$set": {
                    "access_token": request.access_token,
                    "github_user": github_user.get("login"),
                    "github_id": github_user.get("id"),
                    "avatar_url": github_user.get("avatar_url"),
                    "connected_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        
        logger.info(f"[GitHub] Connected for company {request.company_id}: {github_user.get('login')}")
        
        return {
            "status": "connected",
            "github_user": github_user.get("login"),
            "avatar_url": github_user.get("avatar_url")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GitHub] Connect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# REPOSITORY MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/repos/{company_id}")
async def list_repos(company_id: str):
    """
    List available repositories for connected GitHub account
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Get connection
        connection = await _db.github_connections.find_one({"company_id": company_id})
        if not connection:
            raise HTTPException(status_code=404, detail="GitHub not connected")
        
        access_token = connection.get("access_token")
        
        # Fetch repos (user's repos + org repos)
        repos_result = await github_request("/user/repos?per_page=100&sort=updated", access_token)
        
        if not repos_result.get("success"):
            raise HTTPException(status_code=502, detail="Failed to fetch repositories")
        
        repos = repos_result.get("data", [])
        
        # Get already selected repos
        selected = await _db.github_selected_repos.find(
            {"company_id": company_id},
            {"repo_full_name": 1}
        ).to_list(100)
        selected_names = {r.get("repo_full_name") for r in selected}
        
        return {
            "repos": [
                {
                    "full_name": repo.get("full_name"),
                    "name": repo.get("name"),
                    "description": repo.get("description"),
                    "private": repo.get("private"),
                    "language": repo.get("language"),
                    "updated_at": repo.get("updated_at"),
                    "selected": repo.get("full_name") in selected_names
                }
                for repo in repos
            ],
            "total": len(repos)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GitHub] List repos error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/repos/select")
async def select_repos(request: RepoSelectRequest):
    """
    Select repositories to include in knowledge base
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Remove previous selections
        await _db.github_selected_repos.delete_many({"company_id": request.company_id})
        
        # Add new selections
        for repo in request.repos:
            await _db.github_selected_repos.insert_one({
                "company_id": request.company_id,
                "repo_full_name": repo,
                "selected_at": datetime.now(timezone.utc).isoformat(),
                "ingested": False
            })
        
        return {"status": "selected", "repos": request.repos}
        
    except Exception as e:
        logger.error(f"[GitHub] Select repos error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT INGESTION
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/ingest")
async def ingest_repo(request: IngestRepoRequest):
    """
    Ingest repository content into knowledge base
    Fetches docs, README, code files and stores for RAG
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Get connection
        connection = await _db.github_connections.find_one({"company_id": request.company_id})
        if not connection:
            raise HTTPException(status_code=404, detail="GitHub not connected")
        
        access_token = connection.get("access_token")
        repo = request.repo_full_name
        
        # Get repo info
        repo_result = await github_request(f"/repos/{repo}", access_token)
        if not repo_result.get("success"):
            raise HTTPException(status_code=404, detail=f"Repository not found: {repo}")
        
        repo_info = repo_result.get("data", {})
        default_branch = repo_info.get("default_branch", "main")
        
        # Get file tree
        tree = await get_repo_tree(repo, access_token, default_branch)
        
        if not tree:
            raise HTTPException(status_code=404, detail="Could not fetch repository contents")
        
        # Filter and prioritize files
        files_to_ingest = []
        
        # Priority files first
        for priority_file in PRIORITY_FILES:
            for item in tree:
                if item.get("path", "").lower() == priority_file.lower():
                    files_to_ingest.append(item)
                    break
        
        # Doc directories
        for item in tree:
            path = item.get("path", "")
            path_lower = path.lower()
            
            # Check if in doc directory
            if any(path_lower.startswith(f"{d}/") for d in DOC_DIRECTORIES):
                ext = os.path.splitext(path)[1].lower()
                if ext in INGESTIBLE_EXTENSIONS:
                    if item not in files_to_ingest:
                        files_to_ingest.append(item)
        
        # Other documentation files
        for item in tree:
            path = item.get("path", "")
            ext = os.path.splitext(path)[1].lower()
            
            if ext in {'.md', '.mdx', '.txt', '.rst'}:
                if item not in files_to_ingest:
                    files_to_ingest.append(item)
        
        # Include code if requested
        if request.include_code:
            for item in tree:
                path = item.get("path", "")
                ext = os.path.splitext(path)[1].lower()
                
                if ext in INGESTIBLE_EXTENSIONS and ext not in {'.md', '.mdx', '.txt', '.rst'}:
                    if item not in files_to_ingest:
                        files_to_ingest.append(item)
        
        # Limit files
        files_to_ingest = files_to_ingest[:request.max_files]
        
        # Ingest files
        ingested_count = 0
        ingested_files = []
        
        for file_item in files_to_ingest:
            path = file_item.get("path", "")
            
            content = await get_file_content(repo, path, access_token, default_branch)
            
            if content:
                # Create document hash for deduplication
                content_hash = hashlib.md5(content.encode()).hexdigest()
                
                # Store in knowledge base
                doc = {
                    "company_id": request.company_id,
                    "repo": repo,
                    "path": path,
                    "content": content,
                    "content_hash": content_hash,
                    "file_type": os.path.splitext(path)[1].lower(),
                    "size": len(content),
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                    "branch": default_branch
                }
                
                # Upsert to avoid duplicates
                await _db.github_knowledge_base.update_one(
                    {"company_id": request.company_id, "repo": repo, "path": path},
                    {"$set": doc},
                    upsert=True
                )
                
                ingested_count += 1
                ingested_files.append(path)
        
        # Update repo status
        await _db.github_selected_repos.update_one(
            {"company_id": request.company_id, "repo_full_name": repo},
            {
                "$set": {
                    "ingested": True,
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                    "file_count": ingested_count
                }
            }
        )
        
        logger.info(f"[GitHub] Ingested {ingested_count} files from {repo} for company {request.company_id}")
        
        return {
            "status": "ingested",
            "repo": repo,
            "files_ingested": ingested_count,
            "files": ingested_files[:20]  # Return first 20 for preview
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GitHub] Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/all")
async def ingest_all_repos(company_id: str):
    """
    Ingest all selected repositories for a company
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Get selected repos
        selected = await _db.github_selected_repos.find(
            {"company_id": company_id}
        ).to_list(50)
        
        results = []
        for repo in selected:
            repo_name = repo.get("repo_full_name")
            try:
                result = await ingest_repo(IngestRepoRequest(
                    company_id=company_id,
                    repo_full_name=repo_name,
                    include_code=False,
                    max_files=50
                ))
                results.append({"repo": repo_name, "status": "success", "files": result.get("files_ingested")})
            except Exception as e:
                results.append({"repo": repo_name, "status": "error", "error": str(e)})
        
        return {"results": results}
        
    except Exception as e:
        logger.error(f"[GitHub] Ingest all error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

async def search_knowledge_base(company_id: str, query: str, repo_filter: Optional[str] = None, limit: int = 5) -> List[Dict]:
    """
    Search company's GitHub knowledge base using text matching
    """
    if _db is None:
        return []
    
    try:
        # Build search filter
        search_filter = {"company_id": company_id}
        if repo_filter:
            search_filter["repo"] = repo_filter
        
        # Text search (basic keyword matching)
        # In production, use vector embeddings for semantic search
        query_words = query.lower().split()
        
        # Get all documents for company
        docs = await _db.github_knowledge_base.find(
            search_filter,
            {"_id": 0, "content": 1, "path": 1, "repo": 1, "file_type": 1}
        ).to_list(500)
        
        # Score documents by keyword match
        scored_docs = []
        for doc in docs:
            content_lower = doc.get("content", "").lower()
            path_lower = doc.get("path", "").lower()
            
            # Calculate relevance score
            score = 0
            matched_words = []
            
            for word in query_words:
                if len(word) > 2:  # Skip very short words
                    if word in content_lower:
                        score += content_lower.count(word)
                        matched_words.append(word)
                    if word in path_lower:
                        score += 5  # Boost for filename match
            
            if score > 0:
                # Extract relevant snippet
                content = doc.get("content", "")
                snippet = ""
                
                for word in matched_words:
                    idx = content.lower().find(word)
                    if idx >= 0:
                        start = max(0, idx - 100)
                        end = min(len(content), idx + 200)
                        snippet = "..." + content[start:end] + "..."
                        break
                
                if not snippet:
                    snippet = content[:300] + "..."
                
                scored_docs.append({
                    "repo": doc.get("repo"),
                    "path": doc.get("path"),
                    "file_type": doc.get("file_type"),
                    "snippet": snippet,
                    "score": score
                })
        
        # Sort by score and return top results
        scored_docs.sort(key=lambda x: x["score"], reverse=True)
        return scored_docs[:limit]
        
    except Exception as e:
        logger.error(f"[GitHub] Search error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# CHATBOT
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/chat")
async def chat_with_repo(request: ChatWithRepoRequest):
    """
    Chat with AI using company's GitHub knowledge base
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Search knowledge base for relevant context
        search_results = await search_knowledge_base(
            request.company_id,
            request.message,
            request.repo_filter,
            limit=5
        )
        
        # Build context from search results
        context_parts = []
        sources = []
        
        for result in search_results:
            context_parts.append(f"From {result['repo']}/{result['path']}:\n{result['snippet']}")
            sources.append(f"{result['repo']}/{result['path']}")
        
        context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant documentation found."
        
        # Build prompt
        system_prompt = f"""You are an AI assistant with access to the company's GitHub repositories.
Use the following documentation context to answer questions accurately.
If the context doesn't contain relevant information, say so honestly.
Always cite the source file when referencing specific information.

DOCUMENTATION CONTEXT:
{context}
"""
        
        # Get LLM response
        OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
        
        if not OPENROUTER_API_KEY:
            # Fallback response without LLM
            return {
                "response": f"I found {len(search_results)} relevant documents in your repositories. Here's what I found:\n\n" + 
                           "\n\n".join([f"**{r['path']}**:\n{r['snippet'][:200]}..." for r in search_results[:3]]),
                "sources": sources,
                "search_results": len(search_results)
            }
        
        # Call LLM
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "google/gemini-2.0-flash-lite-001",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": request.message}
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.7
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                ai_response = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # Store conversation
                if request.session_id:
                    await _db.github_chat_history.insert_one({
                        "company_id": request.company_id,
                        "session_id": request.session_id,
                        "user_message": request.message,
                        "ai_response": ai_response,
                        "sources": sources,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                
                return {
                    "response": ai_response,
                    "sources": sources,
                    "search_results": len(search_results)
                }
            else:
                raise HTTPException(status_code=502, detail="Failed to get AI response")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GitHub] Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS & MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/status/{company_id}")
async def get_github_status(company_id: str):
    """Get GitHub integration status for a company"""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Get connection
        connection = await _db.github_connections.find_one(
            {"company_id": company_id},
            {"_id": 0, "access_token": 0}  # Don't expose token
        )
        
        # Get selected repos
        repos = await _db.github_selected_repos.find(
            {"company_id": company_id},
            {"_id": 0}
        ).to_list(50)
        
        # Get knowledge base stats
        kb_count = await _db.github_knowledge_base.count_documents({"company_id": company_id})
        
        return {
            "connected": connection is not None,
            "github_user": connection.get("github_user") if connection else None,
            "avatar_url": connection.get("avatar_url") if connection else None,
            "connected_at": connection.get("connected_at") if connection else None,
            "selected_repos": repos,
            "knowledge_base_docs": kb_count
        }
        
    except Exception as e:
        logger.error(f"[GitHub] Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/disconnect/{company_id}")
async def disconnect_github(company_id: str):
    """Disconnect GitHub and clear knowledge base"""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Remove connection
        await _db.github_connections.delete_one({"company_id": company_id})
        
        # Remove selected repos
        await _db.github_selected_repos.delete_many({"company_id": company_id})
        
        # Clear knowledge base
        await _db.github_knowledge_base.delete_many({"company_id": company_id})
        
        # Clear chat history
        await _db.github_chat_history.delete_many({"company_id": company_id})
        
        logger.info(f"[GitHub] Disconnected for company {company_id}")
        
        return {"status": "disconnected"}
        
    except Exception as e:
        logger.error(f"[GitHub] Disconnect error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge-base/{company_id}")
async def get_knowledge_base_stats(company_id: str):
    """Get knowledge base statistics"""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Aggregate by repo
        pipeline = [
            {"$match": {"company_id": company_id}},
            {"$group": {
                "_id": "$repo",
                "file_count": {"$sum": 1},
                "total_size": {"$sum": "$size"}
            }}
        ]
        
        stats = await _db.github_knowledge_base.aggregate(pipeline).to_list(50)
        
        return {
            "repos": [
                {
                    "repo": s["_id"],
                    "file_count": s["file_count"],
                    "total_size": s["total_size"]
                }
                for s in stats
            ],
            "total_repos": len(stats),
            "total_files": sum(s["file_count"] for s in stats),
            "total_size": sum(s["total_size"] for s in stats)
        }
        
    except Exception as e:
        logger.error(f"[GitHub] KB stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

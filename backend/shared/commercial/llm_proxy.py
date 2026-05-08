"""
AUREM LLM Proxy Service
Server-to-server proxy for Emergent LLM calls

Security Model:
1. Client sends request with sk_aurem_ key
2. Backend validates AUREM key
3. Backend attaches Emergent key (never exposed to client)
4. Backend makes server-to-server call to Emergent
5. Response returned to client
6. Usage tracked for billing
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class AuremLLMProxy:
    """
    Secure LLM proxy that hides Emergent key from clients.
    All LLM calls go through this proxy using sk_aurem_ keys.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._emergent_key = None
    
    def _get_emergent_key(self) -> Optional[str]:
        """Get Emergent key from environment (never expose to client)"""
        if self._emergent_key is None:
            self._emergent_key = os.environ.get("EMERGENT_LLM_KEY")
        return self._emergent_key
    
    async def chat_completion(
        self,
        aurem_key_info: Dict[str, Any],
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Proxy a chat completion request through AUREM.
        
        Args:
            aurem_key_info: Validated key info from AuremKeyService
            messages: Chat messages in OpenAI format
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            stream: Whether to stream response
            
        Returns:
            Chat completion response
        """
        from services.aurem_commercial.key_service import get_aurem_key_service
        
        start_time = time.time()
        key_service = get_aurem_key_service(self.db)
        
        business_id = aurem_key_info["business_id"]
        key_id = aurem_key_info["key_id"]
        is_test = aurem_key_info.get("is_test", False)
        
        # Get Emergent key (server-side only)
        emergent_key = self._get_emergent_key()
        if not emergent_key:
            logger.error("[LLMProxy] EMERGENT_LLM_KEY not configured")
            raise Exception("LLM service not configured")
        
        try:
            # Make server-to-server call to Emergent
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            import secrets
            
            # Build system message from first message if role is system
            system_message = ""
            user_messages = []
            
            for msg in messages:
                if msg.get("role") == "system":
                    system_message = msg.get("content", "")
                else:
                    user_messages.append(msg)
            
            chat = LlmChat(
                api_key=emergent_key,  # Server-side Emergent key
                session_id=f"aurem_proxy_{secrets.token_hex(6)}",
                system_message=system_message or "You are a helpful AI assistant."
            ).with_model("openai", model)
            
            # Send the last user message
            last_user_msg = ""
            for msg in reversed(user_messages):
                if msg.get("role") == "user":
                    last_user_msg = msg.get("content", "")
                    break
            
            response_text = await chat.send_message(UserMessage(text=last_user_msg))
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Estimate tokens (rough approximation)
            tokens_in = sum(len(m.get("content", "").split()) * 1.3 for m in messages)
            tokens_out = len(response_text.split()) * 1.3 if response_text else 0
            
            # Record usage
            await key_service.record_usage(
                key_id=key_id,
                business_id=business_id,
                operation="chat.completion",
                tokens_in=int(tokens_in),
                tokens_out=int(tokens_out),
                model=model,
                latency_ms=latency_ms,
                success=True,
                metadata={"is_test": is_test}
            )
            
            # Track in Redis for real-time monitoring
            await self._track_redis_usage(business_id, model, tokens_in + tokens_out)
            
            logger.info(f"[LLMProxy] Completed request for {business_id} ({latency_ms}ms)")
            
            return {
                "id": f"aurem-{secrets.token_hex(12)}",
                "object": "chat.completion",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": int(tokens_in),
                    "completion_tokens": int(tokens_out),
                    "total_tokens": int(tokens_in + tokens_out)
                }
            }
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Record failed request
            await key_service.record_usage(
                key_id=key_id,
                business_id=business_id,
                operation="chat.completion",
                tokens_in=0,
                tokens_out=0,
                model=model,
                latency_ms=latency_ms,
                success=False,
                metadata={"error": str(e), "is_test": is_test}
            )
            
            logger.error(f"[LLMProxy] Error for {business_id}: {e}")
            raise
    
    async def _track_redis_usage(self, business_id: str, model: str, tokens: float):
        """Track usage in Redis for real-time monitoring"""
        try:
            from services.aurem_commercial import get_aurem_memory, get_websocket_hub
            
            memory = await get_aurem_memory()
            hub = await get_websocket_hub()
            
            # Log activity
            await memory.log_activity(
                business_id=business_id,
                activity_type="llm_call",
                description=f"🤖 LLM call completed ({model}, {int(tokens)} tokens)",
                metadata={"model": model, "tokens": int(tokens)}
            )
            
            # Push to dashboard
            await hub.push_activity(
                business_id=business_id,
                activity_type="llm_call",
                description=f"🤖 AI processed request ({model})",
                icon="🤖",
                metadata={"model": model}
            )
            
        except Exception as e:
            logger.warning(f"[LLMProxy] Redis tracking failed: {e}")
    
    async def simple_completion(
        self,
        aurem_key_info: Dict[str, Any],
        system_prompt: str,
        user_prompt: str,
        model: str = "gpt-4o-mini"
    ) -> str:
        """Simple completion helper for agent use"""
        result = await self.chat_completion(
            aurem_key_info=aurem_key_info,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model
        )
        
        return result["choices"][0]["message"]["content"]


# Singleton
_llm_proxy: Optional[AuremLLMProxy] = None

def get_llm_proxy(db: AsyncIOMotorDatabase) -> AuremLLMProxy:
    global _llm_proxy
    if _llm_proxy is None:
        _llm_proxy = AuremLLMProxy(db)
    return _llm_proxy

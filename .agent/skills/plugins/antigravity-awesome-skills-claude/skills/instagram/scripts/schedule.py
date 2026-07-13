"""
Orquestrador de publicação: processa posts approved/scheduled.

Uso:
    python scripts/schedule.py --process           # Publica posts prontos
    python scripts/schedule.py --list              # Lista posts pendentes
    python scripts/schedule.py --cancel --id 5     # Cancela agendamento
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from api_client import InstagramAPI
from auth import auto_refresh_if_needed
from db import Database
from governance import GovernanceManager, RateLimitExceeded

db = Database()
db.init()
gov = GovernanceManager(db)


async def _resolve_media_url(api: InstagramAPI, post: dict, post_id: int) -> str:
    """Resolve a media_url, fazendo upload para Imgur se necessário."""
    media_url = post.get("media_url", "")
    if not media_url and post.get("local_path"):
        media_url = await api.upload_to_imgur(post["local_path"])
        db.update_post_status(post_id, post["status"], media_url=media_url)
    return media_url


async def _wait_for_container(api: InstagramAPI, container_id: str, media_type: str) -> None:
    """Aguarda o processamento do container para vídeos e reels."""
    if media_type not in ("VIDEO", "REEL"):
        return
    for _ in range(60):
        status = await api.check_container_status(container_id)
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") == "ERROR":
            raise Exception(status.get("status", "Erro no processamento"))
        await asyncio.sleep(5)


async def _publish_from_container(api: InstagramAPI, post_id: int, container_id: str) -> dict:
    """Publica mídia a partir de um container já criado."""
    result = await api.publish_media(container_id)
    ig_media_id = result.get("id")
    details = await api.get_media_details(ig_media_id)
    db.update_post_status(
        post_id, "published",
        ig_media_id=ig_media_id,
        permalink=details.get("permalink", ""),
        published_at=details.get("timestamp", ""),
    )
    return {"post_id": post_id, "status": "published", "ig_media_id": ig_media_id, "permalink": details.get("permalink", "")}


async def _process_post(api: InstagramAPI, post: dict, account: dict) -> dict:
    """Processa um único post, retornando o resultado."""
    post_id = post["id"]
    try:
        gov.check_rate_limit(f"publish_{post['media_type'].lower()}", account["id"])
    except RateLimitExceeded as e:
        return {"post_id": post_id, "status": "rate_limited", "error": str(e)}

    try:
        # Recovery: se já tem container criado, tenta publicar direto
        if post["status"] == "container_created" and post.get("ig_container_id"):
            result = await api.publish_media(post["ig_container_id"])
            ig_media_id = result.get("id")
            details = await api.get_media_details(ig_media_id)
            db.update_post_status(
                post_id, "published",
                ig_media_id=ig_media_id,
                permalink=details.get("permalink", ""),
                published_at=details.get("timestamp", ""),
            )
            return {"post_id": post_id, "status": "published", "ig_media_id": ig_media_id}

        # Publicação normal
        media_url = await _resolve_media_url(api, post, post_id)

        media_type = post["media_type"].upper()
        ig_type_map = {"PHOTO": "IMAGE", "VIDEO": "VIDEO", "REEL": "REELS", "STORY": "STORIES"}
        ig_type = ig_type_map.get(media_type, "IMAGE")

        if media_type == "CAROUSEL":
            return {"post_id": post_id, "status": "skipped", "reason": "Carrosséis precisam ser publicados via publish.py"}

        # Step 1: Container
        container_params = {"caption": post.get("caption")}
        if ig_type == "IMAGE":
            container_params["media_type"] = "IMAGE"
            container_params["image_url"] = media_url
        else:
            container_params["media_type"] = ig_type
            container_params["video_url"] = media_url

        container = await api.create_media_container(**container_params)
        container_id = container["id"]
        db.update_post_status(post_id, "container_created", ig_container_id=container_id)

        await _wait_for_container(api, container_id, media_type)

        # Step 2: Publicar
        result = await api.publish_media(container_id)
        ig_media_id = result.get("id")
        details = await api.get_media_details(ig_media_id)
        permalink = details.get("permalink", "")

        db.update_post_status(
            post_id, "published",
            ig_media_id=ig_media_id,
            permalink=permalink,
            published_at=details.get("timestamp", ""),
        )

        gov.log_action(
            f"publish_{media_type.lower()}",
            params={"post_id": post_id},
            result={"ig_media_id": ig_media_id, "permalink": permalink},
            account_id=account["id"],
        )

        return {"post_id": post_id, "status": "published", "ig_media_id": ig_media_id, "permalink": permalink}

    except Exception as e:
        db.update_post_status(post_id, "failed", error_msg=str(e))
        return {"post_id": post_id, "status": "failed", "error": str(e)}


async def process_pending() -> None:
    """Processa todos os posts approved/scheduled prontos para publicar."""
    await auto_refresh_if_needed()
    api = InstagramAPI()
    account = db.get_active_account()
    if not account:
        print(json.dumps({"error": "Nenhuma conta configurada"}, indent=2))
        return

    posts = db.get_posts_for_publishing(account["id"])
    if not posts:
        print(json.dumps({"message": "Nenhum post pendente para publicar", "count": 0}, indent=2))
        return

    print(f"Processando {len(posts)} posts...")
    results = []

    for post in posts:
        result = await _process_post(api, post, account)
        results.append(result)
        if result.get("status") == "rate_limited":
            break

    await api.close()
    print(json.dumps({"processed": len(results), "results": results}, indent=2, ensure_ascii=False))


async def list_pending() -> None:
    """Lista posts pendentes."""
    account = db.get_active_account()
    if not account:
        print(json.dumps({"error": "Nenhuma conta configurada"}, indent=2))
        return

    drafts = db.get_posts(account_id=account["id"], status="draft")
    approved = db.get_posts(account_id=account["id"], status="approved")
    scheduled = db.get_posts(account_id=account["id"], status="scheduled")
    failed = db.get_posts(account_id=account["id"], status="failed")

    print(json.dumps({
        "draft": {"count": len(drafts), "posts": drafts},
        "approved": {"count": len(approved), "posts": approved},
        "scheduled": {"count": len(scheduled), "posts": scheduled},
        "failed": {"count": len(failed), "posts": failed},
    }, indent=2, ensure_ascii=False))


async def cancel_post(post_id: int) -> None:
    """Cancela um post (move para status cancelled)."""
    post = db.get_post_by_id(post_id)
    if not post:
        print(json.dumps({"error": f"Post {post_id} não encontrado"}, indent=2))
        return
    if post["status"] == "published":
        print(json.dumps({"error": "Não é possível cancelar post já publicado"}, indent=2))
        return
    db.update_post_status(post_id, "draft")
    print(json.dumps({"status": "cancelled", "post_id": post_id}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Agendamento de posts Instagram")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--process", action="store_true", help="Processar posts pendentes")
    group.add_argument("--list", action="store_true", help="Listar posts pendentes")
    group.add_argument("--cancel", action="store_true", help="Cancelar agendamento")
    parser.add_argument("--id", type=int, help="ID do post (para --cancel)")
    args = parser.parse_args()

    if args.process:
        asyncio.run(process_pending())
    elif args.list:
        asyncio.run(list_pending())
    elif args.cancel:
        if not args.id:
            parser.error("--id é obrigatório com --cancel")
        asyncio.run(cancel_post(args.id))


if __name__ == "__main__":
    main()
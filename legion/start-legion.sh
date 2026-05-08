#!/bin/bash
# AUREM Legion — Quick Start Script
# Run on your Legion laptop: ./start-legion.sh
#
# Prerequisites: Docker + Docker Compose + cloudflared installed

set -e

echo "=== AUREM Legion — Starting All Services ==="

# 1. Start Docker services
echo "[1/3] Starting Docker containers..."
docker compose up -d
echo ""

# 2. Check status
echo "[2/3] Container status:"
docker ps --format "  {{.Names}}: {{.Status}} ({{.Ports}})"
echo ""

# 3. Instructions
echo "[3/3] Service URLs (via Cloudflare Tunnel):"
echo "  Sovereign (Ollama):  https://sovereign.aurem.live   → localhost:11434"
echo "  Voice (Chatterbox):  https://voice.aurem.live       → localhost:8001"
echo "  Social (Postiz):     https://social.aurem.live      → localhost:8000"
echo "  n8n (Workflows):     https://n8n.aurem.live         → localhost:5678"
echo ""
echo "Tunnel should already be running. If not:"
echo "  cloudflared tunnel run aurem-sovereign"
echo ""
echo "=== AUREM Legion Active ==="

#!/usr/bin/env bash
# Phase 1 uniquement : Docker + .env + compose. Pas de credentials Odoo/Ringover.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

need() { command -v "$1" >/dev/null 2>&1 || { echo "manque: $1" >&2; exit 1; }; }
need docker
docker compose version >/dev/null 2>&1 || { echo "manque: docker compose" >&2; exit 1; }

set_kv() {
  local key="$1" val="$2" file=".env"
  if grep -q "^${key}=" "$file" 2>/dev/null; then
    # évite le & de sed sur les tokens
    python3 - "$file" "$key" "$val" <<'PY'
import sys
path, key, val = sys.argv[1], sys.argv[2], sys.argv[3]
lines = []
found = False
for line in open(path, encoding="utf-8"):
    if line.startswith(key + "="):
        lines.append(f"{key}={val}\n")
        found = True
    else:
        lines.append(line)
if not found:
    lines.append(f"{key}={val}\n")
open(path, "w", encoding="utf-8").writelines(lines)
PY
  else
    printf '%s=%s\n' "$key" "$val" >> "$file"
  fi
}

if [ ! -f .env ]; then
  cp .env.example .env
  set_kv SECRETARY_TOKEN "$(openssl rand -hex 24)"
fi

# shellcheck disable=SC1091
set -a
# shellcheck source=/dev/null
. ./.env
set +a

if [ -z "${SECRETARY_TOKEN:-}" ] || [ "${SECRETARY_TOKEN}" = "change-me-long-random" ]; then
  set_kv SECRETARY_TOKEN "$(openssl rand -hex 24)"
fi

ask() {
  local prompt="$1"
  local val=""
  printf '%s\n' "$prompt" >&2
  IFS= read -r val
  printf '%s' "$val"
}

if [ -t 0 ] && [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "Étape Telegram — @BotFather → /newbot → colle le token."
  tok="$(ask 'Token :')"
  set_kv TELEGRAM_BOT_TOKEN "$tok"
  TELEGRAM_BOT_TOKEN="$tok"
fi

has_llm() {
  [ -n "${OPENROUTER_API_KEY:-}${XAI_API_KEY:-}${ANTHROPIC_API_KEY:-}${OPENAI_API_KEY:-}" ]
}

if [ -t 0 ] && ! has_llm; then
  echo "Étape LLM — un seul fournisseur : openrouter / xai / anthropic / openai"
  prov="$(ask 'Fournisseur :')"
  key="$(ask 'Clé :')"
  case "$prov" in
    openrouter) set_kv OPENROUTER_API_KEY "$key" ;;
    xai|x-ai) set_kv XAI_API_KEY "$key" ;;
    anthropic) set_kv ANTHROPIC_API_KEY "$key" ;;
    openai) set_kv OPENAI_API_KEY "$key" ;;
    *) echo "fournisseur inconnu: $prov" >&2; exit 1 ;;
  esac
fi

# recharger
set -a
# shellcheck source=/dev/null
. ./.env
set +a

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "TELEGRAM_BOT_TOKEN vide. Relance en interactif ou remplis .env" >&2
  exit 1
fi
if ! has_llm; then
  echo "Aucune clé LLM dans .env" >&2
  exit 1
fi

docker compose up -d --build

echo "Attente ingest…"
for _ in $(seq 1 30); do
  if docker compose exec -T ingest python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')" >/dev/null 2>&1; then
    echo
    echo "Ingest OK. Ouvre Telegram, écris au bot. Il commence par l'URL Odoo."
    echo "Logs : docker compose logs -f hermes ingest"
    exit 0
  fi
  sleep 2
done

echo "ingest n'a pas répondu. Logs :" >&2
docker compose logs --tail=80 ingest >&2
exit 1

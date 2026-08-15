#!/bin/sh
# Copie SOUL / skills / helper dans le volume Hermes, sans écraser un SOUL déjà édité.
set -eu
DEST="${HERMES_HOME:-/opt/data}"
SEED="${SEED_DIR:-/seed}"

mkdir -p "$DEST/skills" "$DEST/scripts" "$DEST/cron"

copy_skill() {
  name="$1"
  mkdir -p "$DEST/skills/$name"
  cp -f "$SEED/skills/$name/SKILL.md" "$DEST/skills/$name/SKILL.md"
}

copy_skill sales-onboard
copy_skill sales-inbox
copy_skill sales-apply

cp -f "$SEED/scripts/sec" "$DEST/scripts/sec"
chmod +x "$DEST/scripts/sec"

if [ ! -f "$DEST/SOUL.md" ]; then
  cp "$SEED/SOUL.md" "$DEST/SOUL.md"
fi

if [ ! -f "$DEST/config.yaml" ]; then
  cp "$SEED/config.yaml" "$DEST/config.yaml"
fi

# Fusion minimale : wrap_response false si on touche un config existant trop tard —
# on n'écrase pas. L'onboarding crée le cron.

echo "seed ok"

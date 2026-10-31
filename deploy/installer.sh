#!/usr/bin/env bash
# Installe Feurisson sur une droplet Ubuntu 24.04 neuve, en root :
#
#   bash deploy/installer.sh feurisson.exemple.fr
#
# Le nom de domaine doit déjà pointer sur l'adresse de la droplet (enregistrement A) : Caddy obtient
# alors tout seul un certificat HTTPS (Let's Encrypt). La clé Anthropic est demandée sans s'afficher.
# Relançable : il met à jour le code et garde la clé, sauf si on en tape une nouvelle.
set -euo pipefail

DOMAINE="${1:-}"
[[ -n "$DOMAINE" ]] || { echo "Usage : bash deploy/installer.sh <nom de domaine>" >&2; exit 2; }
[[ $EUID -eq 0 ]] || { echo "À lancer en root (sudo)." >&2; exit 2; }
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
APP=/opt/feurisson
ENV=/etc/feurisson/feurisson.env

echo "== 1. Paquets : Python, Caddy (HTTPS), pare-feu ; fichier d'échange"
apt-get update -q
apt-get install -y -q python3-venv caddy ufw curl
# Une marge si la mémoire vient à manquer (le modèle chargé occupe environ 1 Go).
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile > /dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "== 2. Compte de service et code dans $APP"
id feurisson > /dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin feurisson
mkdir -p "$APP"
# Le code seulement : ni l'environnement Python local, ni les journaux, ni git.
# Ni le modèle : il est entraîné sur l'ordinateur de l'animateur, puis envoyé (deploy/README.md, partie 4).
tar -C "$SOURCE" --exclude=.venv --exclude=data --exclude=models --exclude=.git --exclude=__pycache__ -cf - . \
  | tar -C "$APP" -xf -
python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --upgrade pip
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
mkdir -p "$APP/models"
chown -R root:root "$APP"
chmod -R a+rX "$APP"            # lisible par le compte du service (le modèle arrive parfois en 0600)

echo "== 3. Clé Anthropic (workspace « feurisson » avec plafond de dépense : voir deploy/README.md)"
mkdir -p /etc/feurisson
if [[ ! -s "$ENV" ]] || [[ "${NOUVELLE_CLE:-}" == 1 ]]; then
  read -r -s -p "Collez la clé (elle ne s'affiche pas), puis Entrée : " CLE; echo
  [[ "$CLE" == sk-ant-* ]] || { echo "Ce n'est pas une clé Anthropic (elle commence par sk-ant-)." >&2; exit 1; }
  umask 077
  printf 'ANTHROPIC_API_KEY=%s\n' "$CLE" > "$ENV"
  unset CLE
fi
chmod 600 "$ENV"; chown root:root "$ENV"

echo "== 4. CamemBERT : le modèle entraîné par le groupe"
# Le modèle n'est pas entraîné ici : sur 2 Go de mémoire, l'entraînement est tué (mesuré en conteneur).
# Il est entraîné pendant l'activité, sur l'ordinateur de l'animateur, puis envoyé ici (deploy/README.md,
# « Envoyer le modèle »). Sans lui, Feurisson reconnaît les fiches validées par les mots.
chmod -R a+rX "$APP/models"
if [[ -f "$APP/models/faq/model_head.pkl" ]]; then
  echo "Modèle présent : $(cat "$APP/models/faq/feurisson.json" 2>/dev/null | tr -d '\n' | cut -c1-160)"
else
  echo "Pas de modèle envoyé : reconnaissance par les mots en attendant."
fi
systemctl stop feurisson 2> /dev/null || true

echo "== 5. Service systemd"
install -m 644 "$APP/deploy/feurisson.service" /etc/systemd/system/feurisson.service
systemctl daemon-reload
systemctl enable feurisson > /dev/null
systemctl restart feurisson

# Les journaux de plus de 30 jours sont effacés chaque jour, même quand le service est arrêté.
cat > /etc/cron.daily/feurisson-journal <<'TACHE'
#!/bin/sh
find /var/lib/feurisson/journal -name '*.jsonl' -mtime +30 -delete 2> /dev/null || true
TACHE
chmod 755 /etc/cron.daily/feurisson-journal

echo "== 6. Caddy : HTTPS pour $DOMAINE, vers le service"
sed "s/DOMAINE/$DOMAINE/" "$APP/deploy/Caddyfile" > /etc/caddy/Caddyfile
systemctl reload caddy || systemctl restart caddy

echo "== 7. Pare-feu : SSH, HTTP, HTTPS seulement"
ufw allow OpenSSH > /dev/null; ufw allow 80/tcp > /dev/null; ufw allow 443/tcp > /dev/null
ufw --force enable > /dev/null

# Le modèle met quelques secondes à se charger.
for i in $(seq 1 30); do curl -fsS http://127.0.0.1:8080/sante > /dev/null 2>&1 && break; sleep 2; done
if curl -fsS http://127.0.0.1:8080/sante > /dev/null; then
  echo "Feurisson répond. Ouvrez https://$DOMAINE (le certificat peut prendre une minute)."
else
  echo "Feurisson ne répond pas : journalctl -u feurisson -n 50" >&2; exit 1
fi

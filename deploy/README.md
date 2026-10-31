# Mettre Feurisson en ligne sur une droplet

Il faut : un compte DigitalOcean, un nom de domaine (ou un sous-domaine de celui de l'organisation),
une clé Anthropic.

## 1. Une clé avec un plafond

Dans la console Anthropic (platform.claude.com) :

1. **Workspaces** → créer un workspace « feurisson ». Le plafond ne se pose pas sur le workspace par défaut.
2. Sur ce workspace, **Spend limits** : un plafond mensuel (par exemple 5 $) et une alerte.
3. **API keys** → une clé dans ce workspace. Elle ne sert qu'à Feurisson.

## 2. La droplet

Dans DigitalOcean : **Create → Droplets**, Ubuntu 24.04 (LTS), Basic, Regular, **12 $ par mois (2 Gio,
1 cœur)**, la région la plus proche (Europe), connexion par clé SSH. CamemBERT chargé occupe environ 1 Go :
les droplets à 4 $ et 6 $ n'ont pas assez de mémoire.

Chez le fournisseur du nom de domaine : un enregistrement **A** qui pointe vers l'adresse de la droplet.

## 3. L'installation

```bash
ssh root@<adresse de la droplet>
git clone https://github.com/Youth-AI-Lab/wikiyouthbot-feurisson.git
cd wikiyouthbot-feurisson
bash deploy/installer.sh feurisson.exemple.fr
```

La clé est demandée une fois, sans s'afficher. Elle est gardée dans `/etc/feurisson/feurisson.env`
(lisible par root seulement). Pour la changer : `NOUVELLE_CLE=1 bash deploy/installer.sh …`.

Ce que fait le script : Python et Caddy, un fichier d'échange de 2 Go, un compte de service
`feurisson`, le code dans `/opt/feurisson`, le service `feurisson` (systemd), le HTTPS par Caddy
(certificat Let's Encrypt automatique), un pare-feu qui n'ouvre que SSH, HTTP et HTTPS.

## 4. Envoyer le modèle du groupe

Le modèle CamemBERT n'est pas entraîné sur la droplet : avec 2 Go de mémoire, l'entraînement est tué
(mesuré le 2026-10-31 dans un conteneur limité à 2 Go). Il est entraîné pendant l'activité, sur
l'ordinateur de l'animateur (`python3 outils/entrainer_faq.py`, voir `activite/README.md`), puis envoyé
(425 Mo), depuis le dossier du projet sur cet ordinateur :

```bash
rsync -a --delete models/faq/ root@<adresse de la droplet>:/opt/feurisson/models/faq/
ssh root@<adresse de la droplet> systemctl restart feurisson
```

Envoyez le modèle **et** les fichiers de `content/` avec lesquels il a été entraîné (commit, puis
`git pull` et l'installation sur la droplet) : le modèle reconnaît les fiches par leur question.
Une fiche ajoutée après l'entraînement reste reconnue par les mots, en attendant le prochain modèle.

Sans modèle, Feurisson reconnaît les fiches validées par les mots, et répond sinon avec Claude.

## 5. Au quotidien

| Pour | Commande (en root) |
|---|---|
| Voir s'il tourne | `systemctl status feurisson` |
| Ses messages | `journalctl -u feurisson -n 50` |
| Après une modification de la FAQ | `cd ~/wikiyouthbot-feurisson && git pull && bash deploy/installer.sh feurisson.exemple.fr`, puis envoyer le nouveau modèle (partie 4) |
| Les questions sans fiche | `/opt/feurisson/.venv/bin/python /opt/feurisson/outils/questions_sans_fiche.py /var/lib/feurisson` |
| L'arrêter (entre deux événements) | `systemctl stop feurisson` |

Une droplet arrêtée reste facturée. Pour ne plus rien payer : **Destroy** la droplet, puis avant
l'événement suivant, la recréer, refaire l'installation et renvoyer le modèle (quelques minutes).

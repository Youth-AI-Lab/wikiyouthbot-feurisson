# Feurisson, version publique

Feurisson est le chatbot du groupe feux de forêt de La Rochelle (CSC Vent des Îles, projet Erasmus+
Youth AI Lab, activité WikiYouthBot). Il répond en vers, sur le feu et tout ce qui peut le déclencher.
Cette version est faite pour que les jeunes le montrent aux habitants et au concours de fin de projet,
sur une page publique.

La page du groupe (dépôt `wikiyouthbot`, `france/feurisson/index.html`) appelait Claude depuis le
navigateur : chaque visiteur devait coller sa propre clé, et chaque question partait avec la recherche
web. Un artefact Claude publié ne convient pas non plus : pour obtenir une réponse, chaque visiteur doit
avoir son propre compte Claude, réservé aux plus de 18 ans. Ici, un petit serveur garde la clé et
choisit qui répond.

## Qui répond à une question

1. **Une urgence en cours** (« au feu », « je vois de la fumée »…) : une réponse fixe, en clair, tout de
   suite : « Appelez le 18 ou le 112. Sortez. Ne revenez pas en arrière. » C'est la règle 1 des
   consignes du groupe. Les expressions sont dans `content/urgence.md`.
2. **La FAQ du groupe** (`content/faq.md`), reconnue par **CamemBERT**, un modèle de langue français que
   le groupe règle lui-même (activité dans `activite/`). Il ne fait que choisir une fiche validée par le
   groupe, ou « aucune » : il ne peut rien inventer. La réponse arrive en un tiers de seconde et ne coûte
   rien. Sans modèle entraîné, les fiches sont reconnues par les mots.
3. **Claude, en dernier recours** (Claude Haiku 5.5) : avec les consignes du groupe, son dataset et sa
   FAQ, les deux derniers échanges et la question. Pas de recherche web : Feurisson ne cite que les
   sources du groupe.

Sous chaque réponse, la page dit comment elle a été trouvée : « Fiche reconnue par CamemBERT… Aucune IA
n'a écrit cette réponse », ou la démarche de Claude.

## Pour le groupe

- **Écrire la FAQ** : `content/faq.md` (modèle en tête du fichier). Seules les fiches au statut
  « validée » sont servies au public. Les 9 fiches déjà là sont des brouillons : 8 reprennent des fiches
  manuscrites du groupe, la dernière renvoie à la carte officielle du niveau du jour. À relire, réécrire,
  mettre en vers ou non, compléter, supprimer.
- **Apprendre à Feurisson à reconnaître les questions** : l'activité `activite/README.md` (environ 1 h 30).
  Les jeunes écrivent des façons de poser chaque question, des questions hors FAQ et un test ; l'animateur
  entraîne CamemBERT sur son ordinateur, sans carte graphique ni compte en ligne.
- **Savoir quelles fiches écrire ensuite** : `outils/questions_sans_fiche.py` liste les questions parties
  à Claude, les plus fréquentes d'abord, et les erreurs signalées par les visiteurs.

## Ce qui a été mesuré (2026-10-31)

| Quoi | Mesure |
|---|---|
| Entraînement de CamemBERT (9 fiches brouillons, 44 exemples) | 84 à 91 s sur 4 cœurs ; 339 s sur un seul |
| Test sur 26 questions jamais vues | 18 justes, 8 non reconnues (parties à Claude), **0 mauvaise fiche** |
| Service avec le modèle, conteneur limité à 2 Go et 1 cœur | démarre en 5 s ; réponse de la FAQ en 0,1 à 0,35 s ; environ 960 Mo de mémoire |
| Entraînement dans ce même conteneur de 2 Go | tué faute de mémoire : on entraîne sur l'ordinateur de l'animateur |
| Quatre petits modèles qui écrivent (0,5 à 1,7 milliard de paramètres), un cœur | 4 à 28 s par réponse, et des réponses inventées (`activite/mesures-2026-10-31.md`) |

## Ce que ça coûte

- **La droplet** (DigitalOcean, Basic) : 12 $ par mois (2 Gio, 1 cœur). Une droplet éteinte est facturée
  quand même : seule une droplet supprimée ne coûte plus rien.
- **Les questions de la FAQ et les urgences** : rien.
- **Une question qui part à Claude Haiku 5.5** : de l'ordre d'un dixième de centime (estimation : environ
  6 000 jetons en entrée et quelques centaines en sortie, à 0,10 $ et 0,50 $ par million de jetons, prix
  relevés le 2026-10-31). Le bloc des consignes, du dataset et de la FAQ est mis en cache d'une question
  à l'autre. Non mesuré avec une vraie clé.

Garde-fous. Pour en changer un sur la droplet, ajoutez la ligne `VARIABLE=valeur` dans
`/etc/feurisson/feurisson.env`, puis `systemctl restart feurisson` (ce fichier n'est pas réécrit par
l'installation, contrairement à `deploy/feurisson.service`).

| Réglage | Variable | Par défaut |
|---|---|---|
| Questions par visiteur et par minute (toutes) | `FEURISSON_QUESTIONS_VISITEUR_MINUTE` | 20 |
| Questions à Claude par visiteur et par heure | `FEURISSON_APPELS_VISITEUR_HEURE` | 20 |
| Questions à Claude par jour, tous visiteurs | `FEURISSON_APPELS_JOUR` | 400 |
| Dépense estimée par jour | `FEURISSON_DOLLARS_JOUR` | 1 $ |
| Erreurs signalées par visiteur et par heure | `FEURISSON_SIGNALEMENTS_VISITEUR_HEURE` | 10 |
| Longueur d'une question | `FEURISSON_TAILLE_QUESTION` | 500 caractères |
| Longueur d'une réponse de Claude | `FEURISSON_MAX_TOKENS` | 900 jetons |
| Taille du journal par jour | `FEURISSON_MO_JOURNAL` | 20 Mo |

Un visiteur, c'est une adresse IP (en IPv6, tout un réseau /64). L'urgence n'est jamais limitée. Le
service sert au plus 32 connexions à la fois et coupe une requête qui traîne plus de 15 secondes.

Au-delà, Feurisson répond qu'il reprend plus tard ; la FAQ et l'urgence restent servies. Le vrai plafond
se pose dans la console Anthropic, sur un workspace dédié à Feurisson (voir `deploy/README.md`).

## Les jeunes et les données

Un chatbot public peut être utilisé par des mineurs : publier Feurisson est une décision de
l'organisation (CSC Vent des Îles), à prendre avant de diffuser l'adresse.

- **Dire que c'est une IA** : obligatoire pour un chatbot public (politique d'utilisation d'Anthropic).
  Un bandeau le dit en haut de la page, avec « N'écrivez aucune information personnelle » et le 18 / 112.
- **Ce qui part chez Anthropic** : les questions qui passent par Claude (pas celles de la FAQ).
- **Ce que garde le serveur** : un journal des questions et des erreurs signalées, sans adresse IP ni
  identifiant de visiteur, effacé après 30 jours. Un visiteur peut écrire une information personnelle
  malgré le bandeau : elle reste dans le journal jusque-là.
- **Les corrections signalées** ne changent plus les réponses suivantes (n'importe quel visiteur aurait
  pu en dicter) : elles vont au journal, et le groupe décide.
- Les consignes du groupe gardent ses règles de protection : urgence en clair, souffrance personnelle
  orientée vers un adulte de confiance, jamais de conseil de sécurité deviné.
- Pendant l'activité, les jeunes n'ouvrent aucun compte : GitHub demande 13 ans, un compte Google 15 ans
  en France.

## Les fichiers

| Fichier | Ce que c'est |
|---|---|
| `content/consignes.md` | Les consignes du groupe, reprises de sa page. Changé : pas de recherche web, fiches « IA » jamais présentées comme des faits, corrections relues par le groupe, tirets cadratins retirés |
| `content/dataset.md` | Les 35 fiches et les 3 fiches questions-réponses du groupe, copie exacte de la fiche du projet |
| `content/faq.md` | La FAQ, à écrire par le groupe |
| `content/hors-faq.md`, `content/test-faq.md` | Les exemples hors FAQ et les questions de test de l'activité |
| `content/urgence.md` | La réponse d'urgence et ses expressions |
| `models/faq/` | Le modèle CamemBERT entraîné (pas dans git : 425 Mo) |
| `static/index.html` | La page du groupe, adaptée par `outils/adapter_page.py` (à relancer si le groupe change sa page) |
| `activite/` | L'activité de réglage fin et les mesures du 2026-10-31 |
| `deploy/` | L'installation sur la droplet |

## Essayer en local

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest -v                                  # sans clé, sans appel payant
.venv/bin/python outils/entrainer_faq.py --brouillons            # entraîne CamemBERT sur les brouillons
FEURISSON_FAQ_BROUILLONS=1 ANTHROPIC_API_KEY=… .venv/bin/python -m app.serveur   # http://127.0.0.1:8080
```

`--brouillons` et `FEURISSON_FAQ_BROUILLONS=1` servent aussi les fiches brouillons, pour essayer. Jamais
en public.

## Pas encore essayé

- Une vraie droplet, un vrai nom de domaine et son certificat (l'installation a été jouée dans des
  conteneurs Ubuntu 24.04, dont un limité à 2 Go et 1 cœur).
- De vraies questions à Claude avec une vraie clé (les tests utilisent un faux point d'accès).
- La page sur un téléphone, la voix et la dictée hors de claude.ai.
- L'activité avec un groupe.

## Licence

À décider avec le groupe et le CSC Vent des Îles : le contenu (consignes, dataset, mascotte) est celui
du groupe.

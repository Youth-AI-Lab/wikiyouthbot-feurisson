# Activité : apprendre à Feurisson à reconnaître les questions

Pour l'animateur ou l'animatrice. Durée : environ 1 h 30 (plus une préparation la veille). Groupe : les
jeunes qui ont écrit Feurisson
(12 à 15 ans), par binômes.

## Pourquoi cette activité

Sur une page publique, Feurisson reçoit des questions d'habitants qui ne parlent pas comme les fiches du
groupe. « Combien de feux sont causés par l'homme ? » et « Quelle part des feux de forêt est d'origine
humaine en France ? », c'est la même question. Un programme qui compare les mots ne le voit pas toujours.

On va donc **régler** (« fine-tuner ») un petit modèle de langue français, CamemBERT, pour qu'il
reconnaisse la fiche qui répond à une question, ou dise qu'aucune ne répond. C'est du vrai réglage fin
d'un modèle : on part d'un modèle qui connaît le français et on lui apprend une tâche précise, avec les
exemples du groupe.

Ce modèle ne fait que **choisir** parmi les fiches écrites par le groupe : il ne peut pas inventer de
réponse. Quand il ne reconnaît pas la question, elle part à Claude.

> ℹ️ **Pourquoi pas un petit modèle qui écrit lui-même les réponses ?** On l'a essayé (2026-10-31) avec
> quatre petits modèles qui tiennent sur le serveur de Feurisson (Qwen 0,5 à 1,7 milliard de paramètres,
> Gemma 1 milliard). Ils mettaient 4 à 28 secondes par réponse, et inventaient : pour l'un, l'ONF
> était « l'organisme national de prévention des feux » ; un autre conseillait « Évite de tousser ou de
> tousser » et, près d'un arbre, « il faut le faire couvrir de terre ». Les réponses sont dans
> `activite/mesures-2026-10-31.md` : à lire avec le groupe. Nous n'avons pas mesuré ce qu'un réglage fin
> changerait pour ces modèles ; leurs propres fiches préviennent qu'ils peuvent se tromper (celle de
> SmolLM2 : « should be used as assistive tools rather than definitive sources of information »).

## Ce qu'il faut

- La FAQ du groupe : des fiches au statut « validée » dans `content/faq.md` (au moins 5).
- Des feuilles ou des post-its, et un mur.
- L'ordinateur de l'animateur, ou son Codespace, avec ce dépôt, projeté pour tout le groupe.

**La veille (20 minutes)**, dans le dossier du projet :

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python outils/entrainer_faq.py
```

Le premier entraînement télécharge CamemBERT (environ 440 Mo) : autant ne pas le faire devant le groupe.

**Pour montrer Feurisson en partie 1** : la droplet, si les fiches validées y sont déjà ; ou en local,
avec la clé Anthropic (la question sans fiche part à Claude) :

```bash
ANTHROPIC_API_KEY=… .venv/bin/python -m app.serveur        # puis http://127.0.0.1:8080
```

Tant qu'aucune fiche n'est validée, ajoutez `FEURISSON_FAQ_BROUILLONS=1` devant la commande pour
essayer avec les brouillons.

> ⚠️ **Important.** GitHub demande d'avoir au moins 13 ans : les jeunes n'ouvrent pas de Codespace à
> leur nom. Ils écrivent sur papier ; c'est l'animateur qui tape les exemples et lance l'entraînement.
> L'entraînement tourne sur le processeur, sans carte graphique : pas besoin de Google Colab (compte
> Google à partir de 15 ans en France) ni de Kaggle (interdit avant 13 ans, accord des parents de 13 à
> 16 ans). Âges relevés le 2026-10-31 sur les pages d'aide de Google et la politique de Kaggle.

> 🚫 **Attention.** Aucun exemple ne contient de nom, d'adresse ou d'information personnelle, même
> inventée sur un vrai camarade. Les exemples finissent dans le modèle et dans un dépôt public.

## Ce que les jeunes vont découvrir

- Un modèle apprend à partir d'**exemples**, et sa qualité dépend d'eux plus que de l'ordinateur.
- Il faut lui montrer aussi ce qui **n'est pas** une fiche, sinon il croit que toute question en a une.
- On ne juge un modèle que sur des questions qu'il n'a **jamais vues**.
- Une erreur n'est pas l'autre : « je ne sais pas » vaut mieux qu'une mauvaise réponse.

---

## Partie 1 : qui répond ? (15 min)

1. Montrez Feurisson et posez trois questions : une qui correspond à une fiche (« Combien de feux sont
   causés par l'homme ? »), une sans fiche (« Comment réagir aux étincelles d'un branchement ? »), une
   urgence (« Au feu ! »).
2. Sous chaque réponse, faites lire la démarche : « Réponse écrite par le groupe… Fiche reconnue par
   CamemBERT… Aucune IA n'a écrit cette réponse », ou la démarche de Claude, ou la réponse d'urgence en
   clair.
3. Lisez ensemble les réponses inventées des petits modèles (`activite/mesures-2026-10-31.md`).

**Ce qu'on doit voir.** Trois réponses venues de trois endroits : la FAQ, Claude, la règle d'urgence.

## Partie 2 : écrire les façons de demander (25 min)

1. Une fiche validée par binôme (ou deux).
2. Chaque binôme écrit **dix façons** de poser la question de sa fiche, comme un habitant la dirait : avec
   d'autres mots, plus courte, plus longue, avec une faute, à l'oral (« c'est quoi… »).
3. Toute la classe écrit ensuite des questions **hors FAQ** : hors sujet (le foot, une recette), et surtout
   des questions sur le feu qui n'ont pas de fiche. Ce sont elles qui apprennent au modèle à dire « aucune ».
4. L'animateur les tape : dans `content/faq.md` sous « Autres façons de le demander », et dans
   `content/hors-faq.md`.

> 💡 **Astuce.** Les meilleures façons de demander n'ont presque aucun mot en commun avec la fiche :
> « est-ce que ce sont surtout les gens qui allument les incendies ? » pour la fiche sur l'origine
> humaine.

## Partie 3 : écrire le test (15 min)

1. Chaque binôme écrit **trois questions de test** pour la fiche d'un **autre** binôme, sans regarder ses
   exemples. Et trois questions qui ne doivent recevoir aucune fiche.
2. L'animateur les tape dans `content/test-faq.md` : sous « ## » la question exacte de la fiche (ou
   « aucune »), puis une question par ligne.

> ⚠️ **Règle d'or.** Une question de test ne va jamais dans les exemples d'entraînement. Sinon le test
> mesure la mémoire du modèle, pas sa compréhension. (Les tests du dépôt le vérifient.)

## Partie 4 : entraîner (10 min)

1. Lancez l'entraînement, projeté :

   ```bash
   .venv/bin/python outils/entrainer_faq.py
   ```

2. Pendant qu'il tourne, expliquez ce qui se passe : le modèle compare des paires d'exemples (deux façons
   de poser la même question doivent se ressembler, deux fiches différentes non), puis apprend à choisir.

**Ce qu'on doit voir.** « Modèle entraîné en … s », puis le test : une ligne par question, et le bilan
« … justes, … non reconnues (elles partiront à Claude), … mauvaise(s) fiche(s) ». Mesuré le 2026-10-31
avec 9 fiches et 3 ou 4 exemples par fiche : 84 à 91 s sur 4 cœurs, et sur 26 questions de test,
18 justes, 8 non reconnues, 0 mauvaise fiche. Ces questions de départ ressemblent beaucoup aux exemples :
le test écrit par le groupe (partie 3) sera plus exigeant, et c'est voulu.

## Partie 5 : lire le résultat, améliorer, recommencer (25 min)

1. Notez le bilan au tableau : « Tour 1 : … justes, … non reconnues, … mauvaises ».
2. Pour chaque **mauvaise fiche** (`XX`) : c'est le pire cas, Feurisson répondrait à côté. Les deux
   binômes concernés ajoutent des façons de demander qui distinguent leurs fiches.
3. Pour chaque question **non reconnue** (`--`) : le binôme ajoute des façons de demander proches.
   Ne recopiez pas la question de test : écrivez-en d'autres du même genre.
4. Relancez l'entraînement. Notez le tour 2 au tableau.

**Ce qu'on doit voir.** Plus de justes au tour 2, et toujours aucune mauvaise fiche.

## Partie 6 : mettre en ligne (animateur, après la séance)

Enregistrez les fichiers de `content/` dans le dépôt (commit), mettez la droplet à jour, puis envoyez
le modèle que le groupe vient d'entraîner : `deploy/README.md`, parties 4 et 5. La droplet n'entraîne pas
elle-même : elle n'a pas assez de mémoire pour ça.

---

## ✅ Point de contrôle

- [ ] Chaque fiche validée a au moins dix façons de demander.
- [ ] `content/hors-faq.md` a des questions sur le feu sans fiche, pas seulement du hors sujet.
- [ ] Le test a été écrit par d'autres que les auteurs des exemples, et n'est pas dans l'entraînement.
- [ ] Le dernier entraînement donne 0 mauvaise fiche.

## 🤔 À méditer avec le groupe

1. Pourquoi « je ne sais pas » (la question part à Claude) vaut-il mieux qu'une mauvaise fiche ?
2. Que se passerait-il sans aucun exemple hors FAQ ?
3. CamemBERT ne peut pas inventer, Claude peut. Pourquoi garder Claude quand même ?
4. Si le modèle a 100 % sur le test, peut-on être sûr qu'il ne se trompera jamais devant un habitant ?

**Ce qu'une bonne réponse contient :** (1) une mauvaise fiche donne une réponse fausse avec l'air sûr ;
(2) il croirait que toute question a une fiche, et répondrait à côté ; (3) pour toutes les questions que
la FAQ ne couvre pas, avec les règles du groupe ; (4) non : le test ne contient que quelques questions,
écrites par le groupe ; un habitant en posera d'autres.

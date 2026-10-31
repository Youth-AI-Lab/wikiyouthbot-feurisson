"""Trouver la fiche de la FAQ qui répond à une question, sans modèle de langage.

Comparaison par mots (TF-IDF et cosinus) entre la question et chaque fiche (sa question et ses autres
façons de la poser). Sans bibliothèque ni modèle à télécharger : le service tient sur la plus petite
droplet. Au-dessous du seuil, la question part au modèle.
"""
import math
import re
from collections import Counter

from .contenu import normaliser

# Mots trop courants pour dire de quoi parle une question.
MOTS_VIDES = set("""
a ai au aux avec c ca ce ces cet cette comment d dans de des du elle en est et etre faire faut
fait il ils j je l la le les leur lui m ma mais me mes moi mon n ne nous on ou par pas peut peux
plus pour qu quand que quel quelle quelles quels qui quoi s sa se ses si son sont sur t ta te tes
toi ton tu un une vos votre vous y est ce cela quoi quoi est
""".split())


def racine(mot):
    """Une racine grossière : « forêts » et « forêt », « débroussailler » et « débroussaillement »."""
    for fin in ("issements", "issement", "ements", "ement", "ations", "ation", "euses", "euse",
                "ables", "able", "ions", "ion", "ers", "er", "ees", "ee", "es", "s", "x", "e"):
        if mot.endswith(fin) and len(mot) - len(fin) >= 4:
            return mot[:-len(fin)]
    return mot


# Des mots qui veulent dire la même chose dans une question sur le feu.
EQUIVALENTS = {"incendie": "feu", "incendies": "feu", "feux": "feu", "flamme": "feu", "flammes": "feu",
               "domicile": "maison", "logement": "maison", "appartement": "maison",
               "appli": "application", "applis": "application", "applications": "application"}


def mots(texte):
    return [racine(EQUIVALENTS.get(m, m)) for m in normaliser(texte).split() if m not in MOTS_VIDES and len(m) > 1]


class IndexFAQ:
    def __init__(self, fiches, seuil=0.55):
        self.fiches = list(fiches)
        self.seuil = seuil
        # Une « phrase » par question ou variante, rattachée à sa fiche.
        self.phrases = [(i, Counter(mots(p))) for i, f in enumerate(self.fiches)
                        for p in [f.question] + f.variantes]
        n = len(self.phrases) or 1
        df = Counter(m for _, c in self.phrases for m in c)
        self.idf = {m: math.log((1 + n) / (1 + d)) + 1 for m, d in df.items()}
        self.vecteurs = [(i, self._vecteur(c)) for i, c in self.phrases]

    def _vecteur(self, compte):
        v = {m: k * self.idf.get(m, 0.0) for m, k in compte.items()}
        norme = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {m: x / norme for m, x in v.items()}

    def chercher(self, question):
        """(fiche, score) de la fiche la plus proche si elle passe le seuil, sinon (None, meilleur score)."""
        compte = Counter(mots(question))
        if not compte or not self.vecteurs:
            return None, 0.0
        q = self._vecteur(compte)
        meilleur, score = None, 0.0
        for i, v in self.vecteurs:
            s = sum(x * v.get(m, 0.0) for m, x in q.items())
            # Au moins deux mots en commun : un seul mot (« feu ») ne suffit pas à dire que c'est la même question.
            if s > score and len(set(q) & set(v)) >= 2:
                meilleur, score = i, s
        if meilleur is not None and score >= self.seuil:
            return self.fiches[meilleur], round(score, 3)
        return None, round(score, 3)

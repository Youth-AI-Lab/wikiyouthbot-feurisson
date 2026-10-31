"""Urgence en cours : une réponse fixe, en clair, sans attendre le modèle (content/urgence.md)."""
import re

from .contenu import normaliser

MOTS_MAX = 14


class Urgence:
    def __init__(self, texte):
        reponse, expressions, avant, partout, rubrique = [], [], [], [], None
        for ligne in texte.splitlines():
            brute = ligne.strip()
            if brute.startswith("## "):
                rubrique = normaliser(brute[3:])
            elif rubrique == "reponse" and brute:
                reponse.append(brute)
            elif rubrique == "expressions" and brute.startswith("- "):
                expressions.append(normaliser(brute[2:]))
            elif rubrique == "sauf si avant" and brute.startswith("- "):
                avant.append(normaliser(brute[2:]))
            elif rubrique == "sauf si" and brute.startswith("- "):
                partout.append(normaliser(brute[2:]))
        self.reponse = "\n".join(reponse)
        self.motifs = [self._motif(e) for e in expressions if e]
        self.avant = [self._motif(e) for e in avant if e]
        self.partout = [self._motif(e) for e in partout if e]

    @staticmethod
    def _motif(expression):
        return re.compile(r"\b" + re.escape(expression) + r"\b")

    def detecter(self, question):
        """Un message court qui décrit un feu en cours : pas une question de prévention ni une hypothèse
        (mot de question AVANT l'expression), pas un faux ami (« feu rouge »)."""
        q = re.sub(r"\bs il (vous|te) plait\b", " ", normaliser(question))
        if not self.reponse or len(q.split()) > MOTS_MAX or any(m.search(q) for m in self.partout):
            return False
        positions = [t.start() for m in self.motifs for t in m.finditer(q)]
        if not positions:
            return False
        debut = min(positions)
        return not any(t.start() < debut for m in self.avant for t in m.finditer(q))

    def texte_page(self):
        return f"###CLAIR\n{self.reponse}\n"

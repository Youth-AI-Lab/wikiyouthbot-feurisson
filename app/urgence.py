"""Urgence en cours : une réponse fixe, en clair, sans attendre le modèle (content/urgence.md)."""
import re

from .contenu import normaliser

MOTS_MAX = 14


class Urgence:
    def __init__(self, texte):
        reponse, expressions, exclusions, rubrique = [], [], [], None
        for ligne in texte.splitlines():
            brute = ligne.strip()
            if brute.startswith("## "):
                rubrique = normaliser(brute[3:])
            elif rubrique == "reponse" and brute:
                reponse.append(brute)
            elif rubrique == "expressions" and brute.startswith("- "):
                expressions.append(normaliser(brute[2:]))
            elif rubrique == "sauf si" and brute.startswith("- "):
                exclusions.append(normaliser(brute[2:]))
        self.reponse = "\n".join(reponse)
        self.motifs = [self._motif(e) for e in expressions if e]
        self.exclusions = [self._motif(e) for e in exclusions if e]

    @staticmethod
    def _motif(expression):
        return re.compile(r"\b" + re.escape(expression) + r"\b")

    def detecter(self, question):
        """Un message court qui décrit un feu en cours, sans mot de question ni d'hypothèse."""
        q = normaliser(question)
        return (bool(self.reponse) and len(q.split()) <= MOTS_MAX
                and any(m.search(q) for m in self.motifs)
                and not any(m.search(q) for m in self.exclusions))

    def texte_page(self):
        return f"###CLAIR\n{self.reponse}\n"

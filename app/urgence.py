"""Urgence en cours : une réponse fixe, en clair, sans attendre le modèle (content/urgence.md)."""
import re

from .contenu import normaliser


class Urgence:
    def __init__(self, texte):
        reponse, expressions, rubrique = [], [], None
        for ligne in texte.splitlines():
            brute = ligne.strip()
            if brute.startswith("## "):
                rubrique = normaliser(brute[3:])
            elif rubrique == "reponse" and brute:
                reponse.append(brute)
            elif rubrique == "expressions" and brute.startswith("- "):
                expressions.append(normaliser(brute[2:]))
        self.reponse = "\n".join(reponse)
        self.motifs = [re.compile(r"\b" + re.escape(e) + r"\b") for e in expressions if e]

    def detecter(self, question):
        q = normaliser(question)
        return bool(self.reponse) and any(m.search(q) for m in self.motifs)

    def texte_page(self):
        return f"###CLAIR\n{self.reponse}\n"

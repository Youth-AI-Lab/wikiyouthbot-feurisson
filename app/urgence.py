"""Urgence en cours : une réponse fixe, en clair, sans attendre le modèle (content/urgence.md)."""
import re

from .contenu import normaliser

MOTS_MAX = 8


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
                expressions.append(brute[2:].strip())
        self.reponse = "\n".join(reponse)
        # « ^au feu » : seulement en début de message (« Que faire au feu rouge ? » n'est pas une urgence).
        self.motifs = [re.compile((r"^" if e.startswith("^") else r"\b") + re.escape(normaliser(e.lstrip("^"))) + r"\b")
                       for e in expressions if e.strip("^ ")]

    def detecter(self, question):
        """Un message court qui décrit un feu en cours. Une longue question (« Qu'est-ce qui a pris feu à
        La Teste en 2022 ? ») n'en est pas une : elle va à la FAQ ou à Claude, dont les consignes demandent
        aussi de répondre en clair à une urgence."""
        q = normaliser(question)
        return bool(self.reponse) and len(q.split()) <= MOTS_MAX and any(m.search(q) for m in self.motifs)

    def texte_page(self):
        return f"###CLAIR\n{self.reponse}\n"

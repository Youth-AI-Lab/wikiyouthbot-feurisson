"""CamemBERT réglé par le groupe : quelle fiche de la FAQ répond à la question, ou aucune.

Le modèle ne fait que choisir parmi les fiches écrites par le groupe (ou « aucune ») : il ne peut pas
inventer de réponse. Il est entraîné par outils/entrainer_faq.py, dans models/faq/. Sans modèle (pas
encore entraîné), le service reconnaît les fiches par les mots (app/faq.py).
"""
import os
import re
import threading
from pathlib import Path

from .contenu import normaliser

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = Path(os.environ.get("FEURISSON_MODELE_FAQ", RACINE / "models" / "faq"))
SEUIL = float(os.environ.get("FEURISSON_SEUIL_MODELE", "0.5"))
AUCUNE = "aucune"


def etiquette(fiche):
    """Le nom d'une fiche pour le modèle : sa question, sans accents ni ponctuation."""
    question = fiche if isinstance(fiche, str) else fiche.question
    return re.sub(r"\s+", "-", normaliser(question))[:80]


def disponible():
    return (DOSSIER / "model_head.pkl").exists() or (DOSSIER / "model_head.safetensors").exists()


class Classifieur:
    def __init__(self, fiches, coeurs=1):
        import torch
        from setfit import SetFitModel
        torch.set_num_threads(coeurs)          # la droplet n'a qu'un cœur ; une question à la fois suffit
        self.modele = SetFitModel.from_pretrained(str(DOSSIER), device="cpu", local_files_only=True)
        # Les fiches que le modèle a apprises. Une fiche ajoutée ou renommée depuis l'entraînement n'en fait
        # pas partie : le service la reconnaît par les mots, en attendant le prochain modèle.
        self.connues = {e for e in self.modele.labels if e != AUCUNE}
        self.fiches = {etiquette(f): f for f in fiches if etiquette(f) in self.connues}
        # Une question à la fois : sur un seul cœur, les faire en parallèle ne va pas plus vite et multiplie
        # la mémoire (mesuré : 64 questions simultanées dépassaient 1,5 Go).
        self.verrou = threading.Lock()

    def reconnaitre(self, question):
        """(fiche, probabilité) si le modèle choisit une fiche au-dessus du seuil, sinon (None, probabilité)."""
        with self.verrou:
            probas = self.modele.predict_proba([question])[0].tolist()
        i = max(range(len(probas)), key=probas.__getitem__)
        fiche = self.fiches.get(self.modele.labels[i])
        if fiche is not None and probas[i] >= SEUIL:
            return fiche, round(probas[i], 3)
        return None, round(probas[i], 3)

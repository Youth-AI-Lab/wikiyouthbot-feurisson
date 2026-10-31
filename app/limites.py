"""Garde-fous de dépense : par visiteur et par jour. Seuls les appels au modèle comptent ; la FAQ et
l'urgence sont gratuites et ne sont jamais limitées."""
import datetime
import json
import os
import threading
import time
from collections import defaultdict, deque

APPELS_PAR_VISITEUR = int(os.environ.get("FEURISSON_APPELS_VISITEUR_HEURE", "20"))
APPELS_PAR_JOUR = int(os.environ.get("FEURISSON_APPELS_JOUR", "400"))
DOLLARS_PAR_JOUR = float(os.environ.get("FEURISSON_DOLLARS_JOUR", "1.00"))


class Limites:
    def __init__(self, dossier):
        self.fichier = dossier / "compteur-du-jour.json"
        self.verrou = threading.Lock()
        self.visiteurs = defaultdict(deque)   # en mémoire seulement : aucune adresse n'est écrite
        self.jour = self._lire()

    def _lire(self):
        try:
            d = json.loads(self.fichier.read_text(encoding="utf-8"))
            if d.get("date") == str(datetime.date.today()):
                return d
        except (OSError, ValueError):
            pass
        return {"date": str(datetime.date.today()), "appels": 0, "dollars": 0.0}

    def autoriser(self, visiteur):
        """None si l'appel au modèle est permis, sinon la raison (« visiteur » ou « jour »)."""
        with self.verrou:
            if self.jour["date"] != str(datetime.date.today()):
                self.jour = {"date": str(datetime.date.today()), "appels": 0, "dollars": 0.0}
            if self.jour["appels"] >= APPELS_PAR_JOUR or self.jour["dollars"] >= DOLLARS_PAR_JOUR:
                return "jour"
            fenetre, maintenant = self.visiteurs[visiteur], time.monotonic()
            while fenetre and maintenant - fenetre[0] > 3600:
                fenetre.popleft()
            if len(fenetre) >= APPELS_PAR_VISITEUR:
                return "visiteur"
            fenetre.append(maintenant)
            self.jour["appels"] += 1
            return None

    def compter(self, dollars):
        with self.verrou:
            self.jour["dollars"] = round(self.jour["dollars"] + dollars, 6)
            try:
                self.fichier.write_text(json.dumps(self.jour), encoding="utf-8")
            except OSError:
                pass

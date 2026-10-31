"""Garde-fous d'un service public : par visiteur (toutes les questions, les signalements, les appels à
Claude) et par jour (appels à Claude et dépense estimée)."""
import datetime
import json
import os
import threading
import time
from collections import defaultdict, deque

# Un « visiteur » est une adresse IP : le jour d'une démonstration, toute une salle sur le même Wi-Fi n'en fait
# qu'un. Les valeurs par défaut le permettent ; le vrai plafond de dépense reste celui du jour.
QUESTIONS_PAR_VISITEUR_MINUTE = int(os.environ.get("FEURISSON_QUESTIONS_VISITEUR_MINUTE", "60"))
SIGNALEMENTS_PAR_VISITEUR_HEURE = int(os.environ.get("FEURISSON_SIGNALEMENTS_VISITEUR_HEURE", "10"))
APPELS_PAR_VISITEUR = int(os.environ.get("FEURISSON_APPELS_VISITEUR_HEURE", "100"))
APPELS_PAR_JOUR = int(os.environ.get("FEURISSON_APPELS_JOUR", "400"))
DOLLARS_PAR_JOUR = float(os.environ.get("FEURISSON_DOLLARS_JOUR", "1.00"))


class Fenetre:
    """Au plus `nombre` événements par visiteur sur `duree` secondes (en mémoire : aucune adresse écrite)."""

    def __init__(self, nombre, duree):
        self.nombre, self.duree = nombre, duree
        self.visiteurs = defaultdict(deque)
        self.verrou = threading.Lock()

    def accepter(self, visiteur):
        with self.verrou:
            maintenant = time.monotonic()
            fenetre = self.visiteurs[visiteur]
            while fenetre and maintenant - fenetre[0] > self.duree:
                fenetre.popleft()
            if len(fenetre) >= self.nombre:
                return False
            fenetre.append(maintenant)
            # Les visiteurs partis ne restent pas en mémoire.
            if len(self.visiteurs) > 10_000:
                for v in [v for v, f in self.visiteurs.items() if not f or maintenant - f[-1] > self.duree]:
                    del self.visiteurs[v]
            return True


class Limites:
    def __init__(self, dossier):
        self.fichier = dossier / "compteur-du-jour.json"
        self.verrou = threading.Lock()
        self.questions = Fenetre(QUESTIONS_PAR_VISITEUR_MINUTE, 60)
        self.signalements = Fenetre(SIGNALEMENTS_PAR_VISITEUR_HEURE, 3600)
        self.appels = Fenetre(APPELS_PAR_VISITEUR, 3600)
        self.jour = self._lire()

    def _vide(self):
        return {"date": str(datetime.date.today()), "appels": 0, "dollars": 0.0}

    def _lire(self):
        try:
            d = json.loads(self.fichier.read_text(encoding="utf-8"))
            if d.get("date") == str(datetime.date.today()):
                return d
        except (OSError, ValueError):
            pass
        return self._vide()

    def autoriser(self, visiteur):
        """None si l'appel à Claude est permis, sinon la raison (« visiteur » ou « jour »)."""
        with self.verrou:
            if self.jour["date"] != str(datetime.date.today()):
                self.jour = self._vide()
            if self.jour["appels"] >= APPELS_PAR_JOUR or self.jour["dollars"] >= DOLLARS_PAR_JOUR:
                return "jour"
            if not self.appels.accepter(visiteur):
                return "visiteur"
            self.jour["appels"] += 1
            self._ecrire()
            return None

    def compter(self, dollars):
        with self.verrou:
            self.jour["dollars"] = round(self.jour["dollars"] + dollars, 6)
            self._ecrire()

    def _ecrire(self):
        """Écrit le compteur sans jamais le tronquer : fichier temporaire, puis remplacement."""
        temporaire = self.fichier.with_suffix(".tmp")
        try:
            temporaire.write_text(json.dumps(self.jour), encoding="utf-8")
            os.replace(temporaire, self.fichier)
        except OSError:
            pass     # disque plein : le compteur en mémoire continue de compter

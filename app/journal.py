"""Le journal des questions et les erreurs signalées, pour que le groupe enrichisse sa FAQ.

Aucune adresse IP ni identifiant de visiteur n'est écrit. Les questions, elles, sont gardées : un
visiteur peut y écrire une information personnelle malgré le bandeau. Les journaux de plus de
FEURISSON_JOURS_JOURNAL jours sont effacés au démarrage et chaque jour.
"""
import datetime
import json
import os
import threading

JOURS = int(os.environ.get("FEURISSON_JOURS_JOURNAL", "30"))


class Journal:
    def __init__(self, dossier):
        self.dossier = dossier / "journal"
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.verrou = threading.Lock()
        self.purge = None
        self.purger()

    def purger(self):
        aujourdhui = datetime.date.today()
        if self.purge == aujourdhui:
            return
        self.purge = aujourdhui
        limite = aujourdhui - datetime.timedelta(days=JOURS)
        for f in self.dossier.glob("*.jsonl"):
            try:
                if datetime.date.fromisoformat(f.stem.split("_")[-1]) < limite:
                    f.unlink()
            except ValueError:
                pass

    def ecrire(self, genre, **champs):
        """genre : « questions » ou « signalements » ; un fichier par jour."""
        self.purger()
        ligne = {"heure": datetime.datetime.now().isoformat(timespec="seconds"), **champs}
        with self.verrou, open(self.dossier / f"{genre}_{datetime.date.today()}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")

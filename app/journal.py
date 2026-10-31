"""Le journal des questions et les erreurs signalées, pour que le groupe enrichisse sa FAQ.

Aucune adresse IP ni identifiant de visiteur n'est écrit. Les questions, elles, sont gardées : un
visiteur peut y écrire une information personnelle malgré le bandeau. Les journaux de plus de
FEURISSON_JOURS_JOURNAL jours sont effacés, et un fichier du jour ne dépasse pas FEURISSON_MO_JOURNAL Mo.
Une écriture ratée (disque plein) ne bloque jamais une réponse : la ligne est perdue, c'est tout.
"""
import datetime
import json
import os
import re
import sys
import threading

JOURS = int(os.environ.get("FEURISSON_JOURS_JOURNAL", "30"))
MO_PAR_JOUR = float(os.environ.get("FEURISSON_MO_JOURNAL", "20"))
CONTROLE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def propre(valeur):
    """Sans caractères de contrôle : rien qui puisse piloter le terminal de qui lit le journal."""
    if isinstance(valeur, str):
        return CONTROLE.sub(" ", valeur)
    if isinstance(valeur, dict):
        return {k: propre(v) for k, v in valeur.items()}
    return valeur


class Journal:
    def __init__(self, dossier):
        self.dossier = dossier / "journal"
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.verrou = threading.Lock()
        self.purge = None

    def _purger(self):
        aujourdhui = datetime.date.today()
        if self.purge == aujourdhui:
            return
        self.purge = aujourdhui
        limite = aujourdhui - datetime.timedelta(days=JOURS)
        for f in self.dossier.glob("*.jsonl"):
            try:
                if datetime.date.fromisoformat(f.stem.split("_")[-1]) < limite:
                    f.unlink()
            except (ValueError, OSError):
                pass

    def ecrire(self, genre, **champs):
        """genre : « questions » ou « signalements » ; un fichier par jour. Ne lève jamais d'erreur."""
        ligne = json.dumps({"heure": datetime.datetime.now().isoformat(timespec="seconds"), **propre(champs)},
                           ensure_ascii=False) + "\n"
        try:
            with self.verrou:
                self._purger()
                chemin = self.dossier / f"{genre}_{datetime.date.today()}.jsonl"
                if chemin.exists() and chemin.stat().st_size > MO_PAR_JOUR * 1_000_000:
                    return
                with open(chemin, "a", encoding="utf-8") as f:
                    f.write(ligne)
        except OSError as e:
            print(f"journal : ligne perdue ({type(e).__name__})", file=sys.stderr)

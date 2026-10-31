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
        self._purger()
        # Purge aussi quand personne ne pose de question (entre deux événements) ; sur la droplet, une tâche
        # quotidienne efface les vieux journaux même quand le service est arrêté (deploy/installer.sh).
        minuterie = threading.Timer(6 * 3600, self._purge_reguliere)
        minuterie.daemon = True
        minuterie.start()

    def _purge_reguliere(self):
        with self.verrou:
            self.purge = None
            self._purger()
        minuterie = threading.Timer(6 * 3600, self._purge_reguliere)
        minuterie.daemon = True
        minuterie.start()

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
                # errors="replace" : un caractère impossible à écrire (moitié d'émoji) ne fait pas tout échouer.
                with open(chemin, "a", encoding="utf-8", errors="replace") as f:
                    f.write(ligne)
        except Exception as e:
            print(f"journal : ligne perdue ({type(e).__name__})", file=sys.stderr)

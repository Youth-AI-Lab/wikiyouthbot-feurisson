"""Le service de Feurisson : la page, puis trois étages pour chaque question.

  1. urgence en cours : réponse fixe, en clair (content/urgence.md) ;
  2. FAQ du groupe : la fiche que CamemBERT, réglé par le groupe, reconnaît (models/faq/, voir
     outils/entrainer_faq.py) ; sans modèle entraîné, la fiche la plus proche par les mots ;
  3. Claude, en dernier recours, dans les limites de dépense (app/limites.py).

    python -m app.serveur        (dans le dossier du projet ; la clé est lue dans ANTHROPIC_API_KEY)

Derrière Caddy (HTTPS) sur la droplet : voir deploy/. N'écoute que sur 127.0.0.1 par défaut.
"""
import hashlib
import ipaddress
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

from . import classifieur as camembert
from .contenu import Contenu
from .faq import IndexFAQ
from .journal import Journal
from .limites import Limites
from .modele import Modele, liens_verifies
from .urgence import Urgence

RACINE = Path(__file__).resolve().parent.parent
HOTE = os.environ.get("FEURISSON_HOTE", "127.0.0.1")
PORT = int(os.environ.get("FEURISSON_PORT", "8080"))
DONNEES = Path(os.environ.get("FEURISSON_DONNEES", RACINE / "data"))
SEUIL = float(os.environ.get("FEURISSON_SEUIL", "0.55"))
# Les fiches « brouillon » ne sont servies qu'en essai : en public, seules les fiches validées par le groupe.
BROUILLONS = os.environ.get("FEURISSON_FAQ_BROUILLONS") == "1"
TAILLE_QUESTION = int(os.environ.get("FEURISSON_TAILLE_QUESTION", "500"))
TAILLE_CORPS = 16_000
CONNEXIONS = int(os.environ.get("FEURISSON_CONNEXIONS", "32"))   # connexions servies en même temps
DELAI = 15                                                       # secondes pour envoyer une requête

RAPPEL = "En cas d'urgence : le 18 ou le 112."
LIMITE = {
    "visiteur": "###CLAIR\nVous m'avez posé beaucoup de questions en une heure.\n"
                "Revenez un peu plus tard, ou posez-les aux jeunes qui m'ont écrit.\n" + RAPPEL + "\n",
    "jour": "###CLAIR\nJ'ai beaucoup parlé aujourd'hui : je reprends demain.\n"
            "Les jeunes qui m'ont écrit peuvent vous répondre.\n" + RAPPEL + "\n",
    "rafale": "###CLAIR\nDoucement : une question à la fois.\nRéessayez dans une minute.\n" + RAPPEL + "\n",
}


class Feurisson:
    """L'état du service : contenu, index de la FAQ, modèle, limites, journal."""

    def __init__(self, contenu=None, client=None, donnees=DONNEES, classifieur=None):
        self.contenu = contenu or Contenu()
        for avertissement in self.contenu.avertissements:
            print(f"Attention : {avertissement}", file=sys.stderr)
        servies = [f for f in self.contenu.fiches if f.validee or BROUILLONS]
        if classifieur is None and camembert.disponible():
            try:
                classifieur = camembert.Classifieur(servies)
            except Exception as e:   # modèle illisible (droits, fichier abîmé) : on continue par les mots
                print(f"Attention : le modèle CamemBERT n'a pas pu être chargé ({type(e).__name__}: {e}). "
                      "Reconnaissance par les mots.", file=sys.stderr)
                classifieur = None
        self.classifieur = classifieur or None      # False : sans modèle, même s'il en existe un (tests)
        # Les fiches que le modèle ne connaît pas (ajoutées ou renommées depuis l'entraînement), ou toutes
        # s'il n'y a pas de modèle : reconnues par les mots.
        connues = getattr(self.classifieur, "connues", set())
        self.par_mots = IndexFAQ([f for f in servies if camembert.etiquette(f) not in connues], seuil=SEUIL)
        self.urgence = Urgence(self.contenu.urgence)
        self.modele = Modele(self.contenu.consignes, self.contenu.connaissances(servies), client=client)
        self.urls = self.contenu.urls_connues()
        donnees.mkdir(parents=True, exist_ok=True)
        self.limites = Limites(donnees)
        self.journal = Journal(donnees)
        self.page = (RACINE / "static" / "index.html").read_bytes()

    def repondre(self, question, historique, visiteur):
        """{texte, reels, etage} ; lève anthropic.APIError si le modèle est injoignable."""
        # L'urgence d'abord, avant toute limite : elle ne coûte rien et ne se refuse jamais.
        if self.urgence.detecter(question):
            self.journal.ecrire("questions", etage="urgence", question=question)
            return {"texte": self.urgence.texte_page(), "reels": [], "etage": "urgence"}
        if not self.limites.questions.accepter(visiteur):
            return {"texte": LIMITE["rafale"], "reels": [], "etage": "limite"}
        fiche, score, moteur = None, 0.0, "mots"
        if self.classifieur is not None:
            fiche, score = self.classifieur.reconnaitre(question)
            moteur = "camembert"
        if fiche is None and self.par_mots.fiches:
            fiche, score_mots = self.par_mots.chercher(question)
            if fiche:
                score, moteur = score_mots, "mots"
        if fiche:
            self.journal.ecrire("questions", etage="faq", moteur=moteur, fiche=fiche.question, score=score,
                                question=question)
            return {"texte": fiche.texte_page(moteur), "reels": [u for _, u in fiche.sources if u],
                    "etage": "faq"}
        refus = self.limites.autoriser(visiteur)
        if refus:
            self.journal.ecrire("questions", etage="limite", raison=refus, question=question)
            return {"texte": LIMITE[refus], "reels": [], "etage": "limite"}
        texte, usage, cout = self.modele.demander(question, historique)
        self.limites.compter(cout)
        self.journal.ecrire("questions", etage="modele", score_faq=score, jetons=usage,
                            dollars=round(cout, 6), question=question)
        return {"texte": texte, "reels": liens_verifies(texte, self.urls), "etage": "modele"}


def empreinte(adresse):
    """Une empreinte du visiteur, en mémoire seulement. En IPv6, tout un réseau /64 compte pour un visiteur :
    une seule machine peut y changer d'adresse à volonté."""
    try:
        ip = ipaddress.ip_address(adresse)
        if ip.version == 6 and not ip.ipv4_mapped:
            adresse = str(ipaddress.ip_network(f"{adresse}/64", strict=False))
        elif ip.version == 6:
            adresse = str(ip.ipv4_mapped)
    except ValueError:
        pass
    return hashlib.sha256(adresse.encode()).hexdigest()[:16]


class Requetes(BaseHTTPRequestHandler):
    server_version = "Feurisson"
    sys_version = ""
    timeout = DELAI          # une requête qui traîne (corps envoyé goutte à goutte) est coupée

    def log_message(self, fmt, *args):   # pas d'adresse IP dans les journaux du service
        sys.stderr.write("%s %s\n" % (self.command, self.path.split("?")[0]))

    def _envoyer(self, code, corps=b"", type_="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store" if type_.startswith("application/json") else "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corps)

    def _json(self, code, donnees):
        self._envoyer(code, json.dumps(donnees, ensure_ascii=False).encode("utf-8"))

    def _visiteur(self):
        adresse = self.client_address[0]
        transmise = self.headers.get("X-Forwarded-For", "")
        if adresse in ("127.0.0.1", "::1") and transmise:   # derrière Caddy : la dernière adresse ajoutée
            adresse = transmise.split(",")[-1].strip()
        return empreinte(adresse)

    def _corps(self):
        try:
            taille = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if taille <= 0 or taille > TAILLE_CORPS:
            return None
        try:
            donnees = json.loads(self.rfile.read(taille).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, OSError):
            return None
        return donnees if isinstance(donnees, dict) else None

    def do_GET(self):
        chemin = self.path.split("?")[0]
        if chemin in ("/", "/index.html"):
            self._envoyer(200, self.server.feurisson.page, "text/html; charset=utf-8")
        elif chemin == "/sante":
            self._envoyer(200, b"ok\n", "text/plain; charset=utf-8")
        else:
            self._envoyer(404, b"", "text/plain; charset=utf-8")

    do_HEAD = do_GET

    def do_POST(self):
        chemin = self.path.split("?")[0]
        donnees = self._corps()
        if donnees is None:
            return self._json(400, {"erreur": "requête illisible"})
        f = self.server.feurisson
        if chemin == "/api/ask":
            question = donnees.get("question")
            if not isinstance(question, str) or not question.strip():
                return self._json(400, {"erreur": "question vide"})
            question = question.strip()[:TAILLE_QUESTION]
            historique = donnees.get("histoire") if isinstance(donnees.get("histoire"), list) else []
            try:
                return self._json(200, f.repondre(question, historique, self._visiteur()))
            except anthropic.APIError as e:
                f.journal.ecrire("questions", etage="erreur", erreur=type(e).__name__, question=question)
                return self._json(502, {"erreur": "modèle injoignable"})
            except Exception as e:   # ne jamais couper la connexion sans réponse
                print(f"Erreur : {type(e).__name__}: {e}", file=sys.stderr)
                return self._json(500, {"erreur": "erreur du service"})
        if chemin == "/api/signal":
            if f.limites.signalements.accepter(self._visiteur()):
                champs = {k: str(donnees.get(k, ""))[:600] for k in ("question", "reponse", "correction")}
                if champs["correction"].strip():
                    f.journal.ecrire("signalements", **champs)
            return self._envoyer(204, b"")
        self._json(404, {"erreur": "inconnu"})


class Serveur(ThreadingHTTPServer):
    """Au plus CONNEXIONS connexions servies en même temps : au-delà, elles sont refusées tout de suite
    plutôt que d'ouvrir un fil d'exécution de plus (protection contre l'épuisement du serveur)."""
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.places = threading.BoundedSemaphore(CONNEXIONS)

    def process_request(self, request, client_address):
        if not self.places.acquire(blocking=False):
            self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.places.release()


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY manque : la clé du workspace Feurisson (voir deploy/README.md).")
    feurisson = Feurisson()
    serveur = Serveur((HOTE, PORT), Requetes)
    serveur.feurisson = feurisson
    servies = sum(1 for x in feurisson.contenu.fiches if x.validee or BROUILLONS)
    reconnaissance = ("CamemBERT réglé" if feurisson.classifieur is not None
                      else "par les mots (pas de modèle entraîné)")
    print(f"Feurisson sur http://{HOTE}:{PORT} : {servies} fiche(s) de FAQ servie(s) sur "
          f"{len(feurisson.contenu.fiches)}, reconnaissance {reconnaissance}, "
          f"dernier recours {os.environ.get('FEURISSON_MODELE', 'claude-haiku-5-5')}.", flush=True)
    serveur.serve_forever()


if __name__ == "__main__":
    main()

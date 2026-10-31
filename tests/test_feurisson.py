"""Tests de Feurisson, sans clé ni appel payant : un faux point d'accès Anthropic reçoit les requêtes.

    .venv/bin/python -m unittest -v
"""
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Avant l'import du service : il lit ses réglages au chargement.
DONNEES = Path(tempfile.mkdtemp(prefix="feurisson-test-"))
os.environ.update({"FEURISSON_FAQ_BROUILLONS": "1", "FEURISSON_APPELS_VISITEUR_HEURE": "3",
                   "FEURISSON_DONNEES": str(DONNEES), "ANTHROPIC_API_KEY": "sk-ant-fausse-cle-de-test"})

from app.contenu import Contenu, lire_faq  # noqa: E402
from app.faq import IndexFAQ  # noqa: E402
from app.urgence import Urgence  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
REQUETES = []   # ce que le faux Anthropic a reçu


class FauxAnthropic(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        REQUETES.append({"chemin": self.path, "corps": corps, "cle": self.headers.get("x-api-key")})
        question = corps["messages"][-1]["content"]
        refus = "refuse" in question
        texte = ("###VERS\nUn vers de test\n\n###DEMARCHE\n- dataset\n\n###SOURCES\n"
                 "- Préfecture de la Charente-Maritime (DDTM) | https://www.risque-prevention-incendie.fr/17\n"
                 "- Inventée | https://example.com/inventee\n")
        reponse = {"id": "msg_test", "type": "message", "role": "assistant", "model": corps["model"],
                   "content": [] if refus else [{"type": "text", "text": texte}],
                   "stop_reason": "refusal" if refus else "end_turn", "stop_sequence": None,
                   "usage": {"input_tokens": 30, "output_tokens": 120,
                             "cache_creation_input_tokens": 3200, "cache_read_input_tokens": 0}}
        donnees = json.dumps(reponse).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(donnees)))
        self.end_headers()
        self.wfile.write(donnees)


def demarrer(handler, **attrs):
    serveur = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    for k, v in attrs.items():
        setattr(serveur, k, v)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    return serveur


class TestContenu(unittest.TestCase):
    def test_faq_lue(self):
        fiches = lire_faq(RACINE / "content" / "faq.md")
        self.assertEqual(len(fiches), 9)
        self.assertTrue(all(f.statut == "brouillon" and not f.validee for f in fiches))
        self.assertTrue(all(f.sources for f in fiches), "chaque fiche a une source")
        niveau = [f for f in fiches if "niveau de danger" in f.question][0]
        self.assertEqual(niveau.sources[0][1], "https://www.risque-prevention-incendie.fr/17")

    def test_consignes_sans_commentaire_ni_web(self):
        c = Contenu()
        self.assertNotIn("<!--", c.consignes)
        self.assertNotIn("—", c.consignes + c.dataset)
        self.assertIn("Tu n'as pas accès au web", c.consignes)
        self.assertNotIn("Avant de répondre, tu cherches sur le web", c.consignes)

    def test_page_publique(self):
        page = (RACINE / "static" / "index.html").read_text(encoding="utf-8")
        for interdit in ("api.anthropic.com", "x-api-key", "cleFeu", "web_search"):
            self.assertNotIn(interdit, page)
        self.assertIn('fetch("/api/ask"', page)
        self.assertIn("intelligence artificielle, pas une personne", page)


class TestReconnaissance(unittest.TestCase):
    """Ce que la FAQ reconnaît (seuil 0,55), mesuré le 2026-10-31 sur les fiches brouillons."""

    @classmethod
    def setUpClass(cls):
        c = Contenu()
        cls.index = IndexFAQ(c.fiches)
        cls.urgence = Urgence(c.urgence)

    def fiche(self, question):
        f, _ = self.index.chercher(question)
        return f.question if f else None

    def test_reformulations(self):
        attendu = {
            "Comment protéger mon jardin contre le feu ?": "Comment aménager un jardin qui brûle moins ?",
            "Quel numéro appeler en cas d'incendie ?": "Qui prévenir en cas de départ de feu ?",
            "C'est quoi le rôle de l'ONF ?": "Quel est le rôle de l'ONF dans la prévention des feux ?",
            "Combien de feux sont causés par l'homme ?": "Quelle part des feux de forêt est d'origine humaine en France ?",
            "Peut-on aller en forêt aujourd'hui ?": "Quel est le niveau de danger feu aujourd'hui à La Rochelle ?",
            "Quelle appli pour être alerté des incendies ?": "Quelles applications et quels sites alertent sur le risque de feu ?",
        }
        for question, fiche in attendu.items():
            self.assertEqual(self.fiche(question), fiche, question)

    def test_rien_quand_la_faq_ne_sait_pas(self):
        for question in ["Comment réagir aux étincelles causées par un branchement de câbles ?",
                         "En tant que citoyen, à part appeler les pompiers, que pourrais-je faire pour aider ?",
                         "Que puis-je faire si, en vacances, je retrouve les mégots de mon voisin dans mon jardin ?",
                         "Quels sont les principaux risques incendie au local jeune du Vent des Îles et que me "
                         "conseilles-tu de ne pas faire ?",
                         "Donne-moi une recette de gâteau au chocolat", "Bonjour", "Le barbecue est-il interdit ?"]:
            self.assertIsNone(self.fiche(question), question)

    def test_urgence(self):
        for oui in ["Au feu ! la cuisine est en feu", "Je vois de la fumée chez le voisin", "Il y a le feu au local"]:
            self.assertTrue(self.urgence.detecter(oui), oui)
        for non in ["Que faire en cas de début de départ de feu ?", "Comment éviter que ça brûle ?",
                    "Quels sont les bons réflexes si un feu approche ?"]:
            self.assertFalse(self.urgence.detecter(non), non)


class FauxClassifieur:
    """Remplace CamemBERT dans les tests : reconnaît une seule fiche, et refuse tout le reste."""
    def __init__(self, fiches, connue):
        from app.classifieur import etiquette
        self.fiches = {etiquette(f): f for f in fiches if f.question == connue}
        self.appels = 0

    def reconnaitre(self, question):
        self.appels += 1
        if "ONF" in question:
            return next(iter(self.fiches.values())), 0.91
        return None, 0.2


class TestCamembert(unittest.TestCase):
    def test_fichiers_de_l_activite(self):
        from app.contenu import lire_liste, lire_tests
        hors = lire_liste(RACINE / "content" / "hors-faq.md")
        tests = lire_tests(RACINE / "content" / "test-faq.md")
        self.assertGreaterEqual(len(hors), 10)
        questions = {f.question for f in lire_faq(RACINE / "content" / "faq.md")}
        self.assertTrue(all(attendue is None or attendue in questions for _, attendue in tests),
                        "chaque titre de test-faq.md est la question exacte d'une fiche")
        # Règle d'or de l'activité : aucune question de test dans les exemples d'entraînement.
        appris = {q for f in lire_faq(RACINE / "content" / "faq.md") for q in [f.question] + f.variantes} | set(hors)
        self.assertFalse(appris & {q for q, _ in tests})

    def test_le_classifieur_decide_et_les_mots_ne_le_contredisent_pas(self):
        from app.serveur import Feurisson
        c = Contenu()
        faux = FauxClassifieur(c.fiches, "Quel est le rôle de l'ONF dans la prévention des feux ?")
        f = Feurisson(contenu=c, donnees=DONNEES, classifieur=faux)
        r = f.repondre("C'est quoi le rôle de l'ONF ?", [], "v1")
        self.assertEqual(r["etage"], "faq")
        self.assertIn("relatifs aux obligations légales", r["texte"])
        # Une fiche que le modèle ne connaît pas encore (ajoutée depuis l'entraînement) : reconnue par les mots.
        r = f.repondre("Comment protéger mon jardin contre le feu ?", [], "v1")
        self.assertEqual(r["etage"], "faq")
        self.assertIn("Débroussailler", r["texte"])
        # Une fiche connue du modèle qu'il refuse : les mots ne passent pas outre.
        self.assertEqual(len(f.par_mots.fiches), len([x for x in c.fiches]) - 1)

    @unittest.skipUnless((RACINE / "models" / "faq" / "model_head.pkl").exists(), "modèle pas entraîné")
    def test_vrai_modele_ne_sert_aucune_mauvaise_fiche(self):
        from app.classifieur import Classifieur
        from app.contenu import lire_tests
        c = Classifieur(Contenu().fiches)
        for question, attendue in lire_tests(RACINE / "content" / "test-faq.md"):
            fiche, _ = c.reconnaitre(question)
            if fiche is not None:
                self.assertEqual(fiche.question, attendue, question)


class TestService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.faux = demarrer(FauxAnthropic)
        os.environ["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{cls.faux.server_port}"
        from app.serveur import Feurisson, Requetes
        cls.feurisson = Feurisson(donnees=DONNEES, classifieur=False)
        cls.service = demarrer(Requetes, feurisson=cls.feurisson)
        cls.url = f"http://127.0.0.1:{cls.service.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.service.shutdown()
        cls.faux.shutdown()
        shutil.rmtree(DONNEES, ignore_errors=True)

    def poster(self, chemin, donnees, ip="10.0.0.1"):
        corps = donnees if isinstance(donnees, bytes) else json.dumps(donnees).encode()
        requete = urllib.request.Request(self.url + chemin, data=corps, method="POST",
                                         headers={"Content-Type": "application/json", "X-Forwarded-For": ip})
        try:
            with urllib.request.urlopen(requete, timeout=10) as r:
                texte = r.read()
                return r.status, json.loads(texte) if texte else None
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"null")

    def test_1_faq_sans_appel(self):
        avant = len(REQUETES)
        code, r = self.poster("/api/ask", {"question": "Comment protéger mon jardin contre le feu ?"})
        self.assertEqual((code, r["etage"]), (200, "faq"))
        self.assertIn("###VERS\nDébroussailler", r["texte"])
        self.assertIn("Aucune IA n'a été appelée", r["texte"])
        self.assertEqual(len(REQUETES), avant, "la FAQ n'appelle pas le modèle")

    def test_2_urgence_sans_appel(self):
        avant = len(REQUETES)
        code, r = self.poster("/api/ask", {"question": "Au feu, la cuisine est en feu !"})
        self.assertEqual(r["etage"], "urgence")
        self.assertTrue(r["texte"].startswith("###CLAIR\nAppelez le 18 ou le 112."))
        self.assertEqual(len(REQUETES), avant)

    def test_3_modele_en_dernier_recours(self):
        historique = [{"role": "assistant", "content": "orphelin"}, {"role": "user", "content": "q1"},
                      {"role": "assistant", "content": "r1"}, {"role": "user", "content": "q2"},
                      {"role": "assistant", "content": "r2" * 1000}]
        code, r = self.poster("/api/ask", {"question": "Comment réagir aux étincelles d'un branchement de câbles ?",
                                           "histoire": historique}, ip="10.0.0.2")
        self.assertEqual((code, r["etage"]), (200, "modele"))
        corps = REQUETES[-1]["corps"]
        self.assertEqual(REQUETES[-1]["chemin"], "/v1/messages")
        self.assertEqual(corps["model"], "claude-haiku-5-5")
        self.assertEqual(corps["thinking"], {"type": "disabled"})
        self.assertEqual(corps["output_config"], {"effort": "low"})
        self.assertNotIn("tools", corps, "pas de recherche web")
        self.assertEqual(corps["system"][1]["cache_control"], {"type": "ephemeral"})
        self.assertIn("LE DATASET DU GROUPE", corps["system"][1]["text"])
        roles = [m["role"] for m in corps["messages"]]
        self.assertEqual(roles, ["user", "assistant", "user", "assistant", "user"][-len(roles):])
        self.assertEqual(roles[0], "user")
        self.assertTrue(all(len(m["content"]) <= 600 for m in corps["messages"][:-1]))
        # Seul le lien du dataset ou de la FAQ est marqué vérifié, jamais un lien inventé.
        self.assertEqual(r["reels"], ["https://www.risque-prevention-incendie.fr/17"])

    def test_4_refus_du_modele(self):
        code, r = self.poster("/api/ask", {"question": "refuse cette question sur le câblage"}, ip="10.0.0.3")
        self.assertEqual(r["etage"], "modele")
        self.assertTrue(r["texte"].startswith("###CLAIR\nJe ne peux pas répondre"))

    def test_5_limite_par_visiteur(self):
        ip = "10.0.0.9"
        etages = [self.poster("/api/ask", {"question": f"Question hors FAQ numéro {i} sur le câblage électrique"},
                              ip=ip)[1]["etage"] for i in range(4)]
        self.assertEqual(etages, ["modele", "modele", "modele", "limite"])
        # La FAQ reste servie au même visiteur : elle ne coûte rien.
        self.assertEqual(self.poster("/api/ask", {"question": "C'est quoi le rôle de l'ONF ?"}, ip=ip)[1]["etage"], "faq")

    def test_6_requetes_refusees(self):
        self.assertEqual(self.poster("/api/ask", b"pas du json")[0], 400)
        self.assertEqual(self.poster("/api/ask", {"question": "  "})[0], 400)
        self.assertEqual(self.poster("/api/ask", {"question": "x" * 20000})[0], 400)

    def test_7_signalement_et_journal_sans_adresse(self):
        code, _ = self.poster("/api/signal", {"question": "q", "reponse": "r", "correction": "c'est faux"})
        self.assertEqual(code, 204)
        journaux = "".join(p.read_text(encoding="utf-8") for p in (DONNEES / "journal").glob("*.jsonl"))
        self.assertIn("c'est faux", journaux)
        self.assertIn('"etage": "faq"', journaux)
        for adresse in ("10.0.0.", "127.0.0.1"):
            self.assertNotIn(adresse, journaux, "aucune adresse dans le journal")
        self.assertNotIn("sk-ant", journaux)

    def test_8_page_et_sante(self):
        with urllib.request.urlopen(self.url + "/", timeout=5) as r:
            self.assertIn(b"Feurisson", r.read())
        with urllib.request.urlopen(self.url + "/sante", timeout=5) as r:
            self.assertEqual(r.read(), b"ok\n")


if __name__ == "__main__":
    unittest.main()

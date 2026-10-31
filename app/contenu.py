"""Ce que Feurisson sait : ses consignes, le dataset du groupe et la FAQ (dossier content/)."""
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

CONTENU = Path(__file__).resolve().parent.parent / "content"
URL = re.compile(r"https?://[^\s|)>\]]+")


def sans_commentaires(texte):
    """Les commentaires HTML sont des notes pour les personnes qui éditent le fichier : jamais envoyés."""
    return re.sub(r"<!--.*?-->", "", texte, flags=re.S).strip()


def normaliser(texte):
    """Minuscules, sans accents ni ponctuation : « Qu'est-ce que l'ONF ? » -> « qu est ce que l onf »."""
    texte = unicodedata.normalize("NFD", texte.lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texte).strip()


@dataclass
class Fiche:
    """Une entrée de la FAQ : une question, d'autres façons de la poser, la réponse du groupe."""
    question: str
    variantes: list = field(default_factory=list)
    reponse: str = ""
    sources: list = field(default_factory=list)   # [(nom, url ou "")]
    statut: str = "brouillon"
    ligne: int = 0                                 # ligne de la question dans faq.md

    @property
    def validee(self):
        # « validée » exactement (« validation en cours » ou « validé ? » ne suffisent pas).
        return normaliser(self.statut) in ("validee", "valide", "validees", "valides")

    def texte_page(self, moteur="mots"):
        """La réponse dans le format que la page sait afficher (sections ###), sans IA qui écrive."""
        sources = "\n".join(f"- {nom} | {url}" if url else f"- {nom}" for nom, url in self.sources)
        trouvee = ("Fiche reconnue par CamemBERT, le modèle que le groupe a entraîné." if moteur == "camembert"
                   else "Fiche reconnue en comparant les mots de la question.")
        return (f"###VERS\n{self.reponse.strip()}\n\n"
                f"###DEMARCHE\n- Réponse écrite par le groupe, dans sa FAQ : « {self.question} ».\n"
                f"- {trouvee}\n- Aucune IA n'a écrit cette réponse.\n\n"
                f"###SOURCES\n{sources}\n")


TITRE = re.compile(r"^##(?!#)\s*(.*\S)\s*$")     # « ## question », avec ou sans espace ; pas « ### »
RUBRIQUES = (("autres facons", "variantes"), ("reponses", "reponse"), ("reponse", "reponse"),
             ("sources", "sources"), ("source", "sources"), ("statut", "statut"))


def rubrique_de(ligne):
    """(rubrique, reste de la ligne) si la ligne ouvre une rubrique : « Réponse : … », « Sources »,
    « Statut : … », « Autres façons de le demander »… Le libellé avant les deux-points doit être exactement
    celui de la rubrique : « Sources d'inspiration : … » dans une réponse n'en ouvre pas."""
    libelle = normaliser(ligne.split(":", 1)[0])
    reste = ligne.split(":", 1)[1].strip() if ":" in ligne else ""
    for debut, nom in RUBRIQUES:
        if libelle == debut or (nom == "variantes" and libelle.startswith(debut)):
            return nom, reste
    return None, ""


def source_de(texte):
    """« Nom | lien », « Nom : lien », « lien » ou « Nom » -> (nom, lien ou "")."""
    lien = URL.search(texte)
    if not lien:
        return texte.strip(), ""
    nom = (texte[:lien.start()] + texte[lien.end():]).replace("()", "").replace("[]", "").strip(" |:-()[]")
    return nom or lien.group(0), lien.group(0)


def lire_faq(chemin, avertissements=None):
    """Lit content/faq.md. Chaque fiche commence par « ## question » ; voir le modèle en tête du fichier.
    Les fiches illisibles (sans réponse) sont ignorées et signalées dans `avertissements`."""
    texte = sans_commentaires(chemin.read_text(encoding="utf-8"))
    fiches, fiche, rubrique = [], None, None
    for n, ligne in enumerate(texte.splitlines(), 1):
        brute = ligne.strip()
        titre = TITRE.match(brute)
        if titre:
            fiche = Fiche(question=titre.group(1), ligne=n)
            fiches.append(fiche)
            rubrique = None
            continue
        if fiche is None:
            continue
        if not brute:
            if rubrique == "reponse" and fiche.reponse:
                fiche.reponse += "\n"       # une ligne vide entre deux strophes est gardée
            continue
        if brute.startswith("###") and avertissements is not None:
            avertissements.append(f"faq.md, ligne {n} : « {brute} » est un titre de niveau 3 : il reste dans la "
                                  "fiche précédente. Une nouvelle fiche commence par « ## ».")
        nom, reste = rubrique_de(brute)
        if nom == "statut":
            fiche.statut = reste or fiche.statut
            rubrique = None
        elif nom:
            rubrique = nom
            if reste and nom == "reponse":
                fiche.reponse += reste + "\n"
            elif reste and nom == "sources":
                fiche.sources.append(source_de(reste))
        elif rubrique == "variantes" and brute.startswith(("- ", "* ")):
            fiche.variantes.append(brute[2:].strip())
        elif rubrique == "sources" and brute.startswith(("- ", "* ")):
            fiche.sources.append(source_de(brute[2:]))
        elif rubrique == "reponse":
            fiche.reponse += ligne.rstrip() + "\n"
    for f in fiches:
        f.reponse = re.sub(r"\n{3,}", "\n\n", f.reponse).strip()
        if avertissements is not None:
            if not f.reponse:
                avertissements.append(f"faq.md, ligne {f.ligne} : « {f.question} » n'a pas de réponse lisible, "
                                      "fiche ignorée (il manque « Réponse : » ?)")
            elif not f.sources:
                avertissements.append(f"faq.md, ligne {f.ligne} : « {f.question} » n'a pas de source")
    return [f for f in fiches if f.question and f.reponse]


def lire_liste(chemin):
    """Les lignes « - … » d'un fichier (commentaires HTML ignorés) ; liste vide si le fichier manque."""
    if not chemin.exists():
        return []
    texte = sans_commentaires(chemin.read_text(encoding="utf-8"))
    return [l.strip()[2:].strip() for l in texte.splitlines() if l.strip().startswith("- ") and l.strip()[2:].strip()]


def lire_tests(chemin):
    """content/test-faq.md : sous « ## question d'une fiche » (ou « ## aucune »), les questions de test.
    Renvoie [(question de test, question de la fiche attendue, ou None pour aucune fiche)]."""
    if not chemin.exists():
        return []
    tests, attendue = [], None
    for ligne in sans_commentaires(chemin.read_text(encoding="utf-8")).splitlines():
        brute = ligne.strip()
        if brute.startswith("## "):
            titre = brute[3:].strip()
            attendue = None if normaliser(titre) in ("aucune", "aucune fiche") else titre
        elif brute.startswith("- ") and brute[2:].strip():
            tests.append((brute[2:].strip(), attendue))
    return tests


class Contenu:
    """Tout le contenu, lu une fois au démarrage (relancer le service après une modification)."""

    def __init__(self, dossier=CONTENU):
        self.consignes = sans_commentaires((dossier / "consignes.md").read_text(encoding="utf-8"))
        self.dataset = sans_commentaires((dossier / "dataset.md").read_text(encoding="utf-8"))
        self.avertissements = []
        self.fiches = lire_faq(dossier / "faq.md", self.avertissements)
        urgence = dossier / "urgence.md"
        self.urgence = sans_commentaires(urgence.read_text(encoding="utf-8")) if urgence.exists() else ""

    def connaissances(self, servies):
        """Le dataset et les fiches de la FAQ, tels que le modèle les reçoit (partie mise en cache)."""
        faq = "\n\n".join(
            f"### {f.question}\n{f.reponse}\nSources : "
            + "; ".join(f"{nom} ({url})" if url else nom for nom, url in f.sources)
            for f in servies)
        return (f"## LE DATASET DU GROUPE\n\n{self.dataset}\n\n"
                f"## LA FAQ DU GROUPE (réponses relues par le groupe)\n\n{faq or '(vide pour l instant)'}")

    def urls_connues(self):
        """Les seuls liens que Feurisson peut présenter comme vérifiés : ceux des consignes, du dataset et de
        la FAQ."""
        urls = set(URL.findall(self.dataset)) | set(URL.findall(self.consignes))
        for f in self.fiches:
            urls.update(u for _, u in f.sources if u)
        return urls

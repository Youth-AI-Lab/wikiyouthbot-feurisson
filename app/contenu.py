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
        return normaliser(self.statut).startswith("valid")

    def texte_page(self):
        """La réponse dans le format que la page sait afficher (sections ###), sans appel au modèle."""
        sources = "\n".join(f"- {nom} | {url}" if url else f"- {nom}" for nom, url in self.sources)
        return (f"###VERS\n{self.reponse.strip()}\n\n"
                f"###DEMARCHE\n- Réponse écrite par le groupe, dans sa FAQ : « {self.question} ».\n"
                f"- Aucune IA n'a été appelée pour cette réponse.\n\n"
                f"###SOURCES\n{sources}\n")


def lire_faq(chemin):
    """Lit content/faq.md. Chaque fiche commence par « ## question » ; voir le modèle en tête du fichier."""
    texte = sans_commentaires(chemin.read_text(encoding="utf-8"))
    fiches, fiche, rubrique = [], None, None
    for n, ligne in enumerate(texte.splitlines(), 1):
        brute = ligne.strip()
        if brute.startswith("## "):
            fiche = Fiche(question=brute[3:].strip(), ligne=n)
            fiches.append(fiche)
            rubrique = None
            continue
        if fiche is None:
            continue
        cle = normaliser(brute.split(":", 1)[0]) if ":" in brute else ""
        if cle.startswith("autres facons"):
            rubrique = "variantes"
        elif cle == "reponse":
            rubrique = "reponse"
            reste = brute.split(":", 1)[1].strip()
            if reste:
                fiche.reponse += reste + "\n"
        elif cle == "sources" or cle == "source":
            rubrique = "sources"
        elif cle == "statut":
            fiche.statut = brute.split(":", 1)[1].strip()
            rubrique = None
        elif rubrique == "variantes" and brute.startswith("- "):
            fiche.variantes.append(brute[2:].strip())
        elif rubrique == "sources" and brute.startswith("- "):
            nom, _, url = brute[2:].partition("|")
            fiche.sources.append((nom.strip(), url.strip()))
        elif rubrique == "reponse":
            fiche.reponse += ligne.rstrip() + "\n"
    for fiche in fiches:
        fiche.reponse = fiche.reponse.strip()
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
        self.fiches = lire_faq(dossier / "faq.md")
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
        """Les seuls liens que Feurisson peut présenter comme vérifiés : ceux du dataset et de la FAQ."""
        urls = set(URL.findall(self.dataset))
        for f in self.fiches:
            urls.update(u for _, u in f.sources if u)
        return urls

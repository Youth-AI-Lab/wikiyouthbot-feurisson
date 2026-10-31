#!/usr/bin/env python3
"""Apprendre à CamemBERT à reconnaître les fiches de la FAQ (réglage fin, sans GPU).

    python3 outils/entrainer_faq.py                 entraîne, puis teste sur content/test-faq.md
    python3 outils/entrainer_faq.py --tester        teste seulement le modèle déjà entraîné
    python3 outils/entrainer_faq.py --brouillons    entraîne aussi sur les fiches brouillons (essais)

Exemples d'entraînement : la question de chaque fiche et ses « autres façons de le demander »
(content/faq.md), plus les questions « hors FAQ » (content/hors-faq.md), auxquelles Feurisson ne
doit répondre avec aucune fiche. Méthode : SetFit (quelques exemples par fiche suffisent pour
commencer) sur sentence-camembert-base, un CamemBERT pour les phrases. Le modèle est écrit dans
models/faq/ ; le service le charge au démarrage.

Le test (content/test-faq.md) utilise des questions que le modèle n'a jamais vues : c'est le seul
moyen de savoir s'il reconnaît une question nouvelle, et pas seulement celles qu'il a apprises.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.classifieur import AUCUNE, DOSSIER, SEUIL, etiquette  # noqa: E402
from app.contenu import CONTENU, lire_faq, lire_liste, lire_tests  # noqa: E402

BASE = "dangvantuan/sentence-camembert-base"
REVISION = "103d895e85f97c1265c62efa238d092ecbb0d617"   # version figée (Hugging Face, 2024-10-24)


def exemples(brouillons):
    avertissements = []
    fiches = [f for f in lire_faq(CONTENU / "faq.md", avertissements) if f.validee or brouillons]
    for a in avertissements:
        print(f"Attention : {a}")
    textes, etiquettes = [], []
    for f in fiches:
        for phrase in [f.question] + f.variantes:
            textes.append(phrase)
            etiquettes.append(etiquette(f))
    hors = lire_liste(CONTENU / "hors-faq.md")
    textes += hors
    etiquettes += [AUCUNE] * len(hors)
    return fiches, textes, etiquettes


def entrainer(textes, etiquettes, coeurs):
    import torch
    from datasets import Dataset
    from setfit import SetFitModel, Trainer, TrainingArguments
    torch.set_num_threads(coeurs)
    modele = SetFitModel.from_pretrained(BASE, revision=REVISION, labels=sorted(set(etiquettes)))
    debut = time.time()
    # Pas d'étapes intermédiaires enregistrées (plus d'un Go) ; le dossier de travail est effacé ensuite.
    DOSSIER.parent.mkdir(parents=True, exist_ok=True)
    etapes = tempfile.mkdtemp(prefix=".entrainement-", dir=DOSSIER.parent)
    try:
        Trainer(model=modele,
                args=TrainingArguments(output_dir=etapes, save_strategy="no", batch_size=16, num_epochs=1,
                                       num_iterations=10, seed=42),
                train_dataset=Dataset.from_dict({"text": textes, "label": etiquettes})).train()
    finally:
        shutil.rmtree(etapes, ignore_errors=True)
    modele.save_pretrained(str(DOSSIER))
    # safetensors écrit le modèle en 0600 : le service, qui tourne sous un autre compte, ne pourrait pas le lire.
    for f in DOSSIER.rglob("*"):
        f.chmod(0o755 if f.is_dir() else 0o644)
    DOSSIER.chmod(0o755)
    return time.time() - debut


def tester(fiches):
    from app.classifieur import Classifieur
    tests = lire_tests(CONTENU / "test-faq.md")
    if not tests:
        print("Pas de questions de test dans content/test-faq.md.")
        return
    c = Classifieur(fiches)
    bons = faux = rates = 0
    print(f"\nTest sur {len(tests)} questions jamais vues (seuil {SEUIL}) :")
    for question, attendue in tests:
        trouvee, proba = c.reconnaitre(question)
        nom = trouvee.question if trouvee else "aucune fiche"
        attendu = attendue or "aucune fiche"
        if nom == attendu:
            bons += 1
            marque = "OK "
        elif trouvee is None:
            rates += 1
            marque = "-- "     # pas reconnue : la question partira à Claude
        else:
            faux += 1
            marque = "XX "     # mauvaise fiche : à corriger en priorité
        print(f"  {marque}{proba:.2f}  {question[:60]:60} -> {nom[:50]}")
    print(f"\n{bons} justes, {rates} non reconnues (elles partiront à Claude), {faux} mauvaise(s) fiche(s).")
    print("Une mauvaise fiche est le pire cas : ajoutez des façons de demander aux deux fiches concernées,"
          " ou des exemples hors FAQ, puis entraînez de nouveau.")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--tester", action="store_true", help="tester sans entraîner")
    p.add_argument("--brouillons", action="store_true", help="entraîner aussi sur les fiches brouillons")
    p.add_argument("--coeurs", type=int, default=os.cpu_count() or 1, help="cœurs de calcul (défaut : tous)")
    a = p.parse_args()
    if a.brouillons:
        os.environ["FEURISSON_FAQ_BROUILLONS"] = "1"
    fiches, textes, etiquettes = exemples(a.brouillons)
    if not fiches:
        sys.exit("Aucune fiche validée dans content/faq.md (statut « validée ») : rien à apprendre. "
                 "Pour un essai avec les brouillons : --brouillons")
    if not a.tester:
        print(f"Entraînement : {len(fiches)} fiches, {len(textes)} exemples "
              f"({etiquettes.count(AUCUNE)} hors FAQ), {a.coeurs} cœur(s)…", flush=True)
        duree = entrainer(textes, etiquettes, a.coeurs)
        (DOSSIER / "feurisson.json").write_text(json.dumps(
            {"base": BASE, "revision": REVISION, "fiches": len(fiches), "exemples": len(textes),
             "duree_s": round(duree), "date": time.strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False, indent=1))
        print(f"Modèle entraîné en {duree:.0f} s, écrit dans {DOSSIER.relative_to(RACINE)}/.")
    tester(fiches)


if __name__ == "__main__":
    main()

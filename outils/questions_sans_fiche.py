#!/usr/bin/env python3
"""Les questions que la FAQ n'a pas su prendre (parties à l'IA), les plus fréquentes d'abord, et les
erreurs signalées : de quoi écrire les prochaines fiches.

    python3 outils/questions_sans_fiche.py /var/lib/feurisson      (sur la droplet, en root)
"""
import json
import sys
from collections import Counter
from pathlib import Path

dossier = Path(sys.argv[1] if len(sys.argv) > 1 else "data") / "journal"
questions, signalements, etages, dollars = Counter(), [], Counter(), 0.0
for f in sorted(dossier.glob("*.jsonl")):
    for ligne in f.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(ligne)
        except ValueError:
            continue
        if f.name.startswith("signalements_"):
            signalements.append(d)
            continue
        etages[d.get("etage")] += 1
        dollars += d.get("dollars", 0) or 0
        if d.get("etage") == "modele":
            questions[d.get("question", "").strip().lower()] += 1

total = sum(etages.values())
print(f"{total} question(s) : " + ", ".join(f"{k} {v}" for k, v in etages.most_common()))
if total:
    print(f"Sans IA (FAQ et urgence) : {100 * (etages['faq'] + etages['urgence']) / total:.0f} % ; "
          f"dépense estimée : {dollars:.4f} $")
print("\nQuestions parties à l'IA, à transformer en fiches :")
for q, n in questions.most_common(30):
    print(f"  {n:3d}  {q}")
print(f"\nErreurs signalées ({len(signalements)}) :")
for s in signalements[-20:]:
    print(f"  {s.get('heure', '')}  « {s.get('question', '')} » : {s.get('correction', '')}")

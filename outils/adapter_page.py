#!/usr/bin/env python3
"""Fabrique static/index.html à partir de la page du groupe (dépôt wikiyouthbot, france/feurisson/index.html).

    python3 outils/adapter_page.py <page du groupe> static/index.html

La page du groupe appelait Claude depuis le navigateur, avec la clé du visiteur et la recherche web.
La version publique demande au service (/api/ask) : la clé reste sur le serveur. Le reste de la page
(mascotte, vers, voix, dictée) est inchangé. À relancer quand le groupe modifie sa page ; le script
s'arrête si un morceau à remplacer n'est plus là.
"""
import re
import sys

DEMANDER = """async function demander(question){
  // Version publique : le service choisit la réponse (urgence, FAQ du groupe, ou Claude en dernier recours).
  const rep = await fetch("/api/ask", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({question, histoire})
  });
  if(!rep.ok) throw new Error(rep.status);
  const data = await rep.json();
  return {texte: data.texte || "", reels: new Set(data.reels || [])};
}

"""

# window.storage n'existe que dans les artefacts de claude.ai : ici, le stockage du navigateur du visiteur.
# Questions, réponses et corrections : le temps de la visite seulement (sessionStorage), pour qu'elles ne
# restent pas sur un appareil partagé (tablette d'un stand, ordinateur d'une médiathèque). Seuls les
# réglages de la voix sont gardés.
STOCKAGE = """<script>
if(!window.storage){
  const garde = k => (k === 'feurisson:accent' || k === 'feurisson:voix') ? localStorage : sessionStorage;
  window.storage = {
    get: async k => { const v = garde(k).getItem(k); return v === null ? null : {value: v}; },
    set: async (k, v) => { garde(k).setItem(k, v); }
  };
}
</script>
"""

# Obligatoire pour un chatbot public (politique d'utilisation d'Anthropic) : dire que c'est une IA.
BANDEAU = """<div class="bandeau-ia" role="note">Feurisson est un programme d'intelligence artificielle, pas une personne.
Il peut se tromper : vérifiez auprès des sources officielles. N'écrivez aucune information personnelle.
En cas d'urgence : le 18 ou le 112.</div>
<style>.bandeau-ia{margin:0;padding:8px 16px;background:#fff4e5;color:#5a3b1f;font:600 14px/1.4 "Nunito Sans",system-ui,sans-serif;text-align:center;border-bottom:1px solid #f0d2b0}</style>
"""


def remplacer(texte, ancien, nouveau, compte=1):
    if texte.count(ancien) != compte:
        sys.exit(f"Introuvable ou en double dans la page du groupe ({texte.count(ancien)} fois) : {ancien[:70]!r}")
    return texte.replace(ancien, nouveau)


def adapter(page):
    # 1. L'appel : au service, plus à api.anthropic.com.
    debut = page.index("async function demander(question){")
    fin = page.index("function decouper(", debut)
    page = page[:debut] + DEMANDER + page[fin:]
    # 2. Les consignes et le dataset vivent sur le serveur (content/) : la page ne les embarque plus.
    page = re.sub(r"const CONSIGNES\s*=\s*`.*?`;", 'const CONSIGNES = "";', page, count=1, flags=re.S)
    page = re.sub(r"const DATASET\s*=\s*`.*?`;", 'const DATASET = "";', page, count=1, flags=re.S)
    # 3. Le panneau qui demandait une clé au visiteur : ses styles, son bloc et son script.
    debut = page.rindex("<style>", 0, page.index('<div id="cleFeu"'))
    fin = page.index("</script>", page.index("window.__enTetesFeurisson")) + len("</script>")
    page = page[:debut] + page[fin:]
    # 4. Stockage du navigateur, et bandeau « c'est une IA ».
    page = remplacer(page, "<script>\nconst MASCOTTE", STOCKAGE + "<script>\nconst MASCOTTE")
    page = remplacer(page, '<div class="app">', BANDEAU + '<div class="app">')
    # 5. Une source sans lien (souvent le cas dans les fiches du groupe) n'est pas « non vérifiée ».
    page = remplacer(page, "+ `<span class=\"tag ${verif?'ok':'non'}\">${verif?'lien consulté':'lien non vérifié'}</span>`",
                     "+ (s.url ? `<span class=\"tag ${verif?'ok':'non'}\">${verif?'lien vérifié':'lien non vérifié'}</span>` : '')")
    # 6. Une erreur signalée part au groupe (journal du service), au lieu de changer les réponses suivantes.
    page = remplacer(page, "sig.replaceWith(el('div','merci','Merci — c\\'est noté, Feurisson en tiendra compte",
                     "fetch('/api/signal',{method:'POST',headers:{'Content-Type':'application/json'},"
                     "body:JSON.stringify({question, reponse:(r.clair||r.vers).slice(0,500), correction:quoi.trim()})}).catch(()=>{});\n"
                     "    sig.replaceWith(el('div','merci','Merci, c\\'est noté : le groupe relira votre correction")
    # 7. Plus de tiret cadratin dans ce qui s'affiche.
    page = remplacer(page, "<title>Feurisson — le chatbot qui répond en vers</title>",
                     "<title>Feurisson, le chatbot qui répond en vers</title>")
    page = remplacer(page, "se retient mieux — mais rimer", "se retient mieux, mais rimer")
    page = remplacer(page, "/* Réglages de la voix — à ajuster librement.", "/* Réglages de la voix : à ajuster librement.")
    restes = [m.start() for m in re.finditer("—", page)]
    for i in restes:
        if "[,;:.!?…—-]" not in page[i - 12:i + 6]:
            sys.exit(f"Tiret cadratin restant : {page[i - 40:i + 30]!r}")
    for interdit in ("api.anthropic.com", "x-api-key", "anthropic-dangerous-direct-browser-access", "cleFeu"):
        if interdit in page:
            sys.exit(f"Reste de l'ancien appel dans la page : {interdit}")
    return page


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    source = open(sys.argv[1], encoding="utf-8").read()
    open(sys.argv[2], "w", encoding="utf-8").write(adapter(source))
    print(f"{sys.argv[2]} écrit.")

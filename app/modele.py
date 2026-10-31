"""Le dernier recours : Claude, quand ni l'urgence ni la FAQ n'ont répondu.

Le modèle reçoit les consignes, puis le dataset et la FAQ (mis en cache : ce bloc ne change pas d'une
question à l'autre), puis les derniers échanges et la question. Pas de recherche web, pas d'outil.
"""
import os
import re

import anthropic

MODELE = os.environ.get("FEURISSON_MODELE", "claude-haiku-5-5")
MAX_TOKENS = int(os.environ.get("FEURISSON_MAX_TOKENS", "900"))
# Prix de Claude Haiku 5.5 en dollars par million de jetons, pour des requêtes de moins de 100 000 jetons
# (platform.claude.com/docs/en/about-claude/pricing, lu le 2026-10-31) : seulement pour estimer la
# dépense du jour et la plafonner. La facture fait foi : elle est dans la console Anthropic.
PRIX = {"entree": 0.10, "ecriture_cache": 0.125, "lecture_cache": 0.01, "sortie": 0.50}
HISTORIQUE = 4            # messages gardés (2 échanges) : au-delà, le coût monte sans servir la réponse
TAILLE_MESSAGE = 600      # caractères par message d'historique

REFUS = ("###CLAIR\nJe ne peux pas répondre à cette question.\n"
         "Pour le feu et sa prévention : les pompiers (SDIS 17), la préfecture de la Charente-Maritime, "
         "service-public.fr.\n")


class Modele:
    def __init__(self, consignes, connaissances, client=None):
        self.client = client or anthropic.Anthropic(max_retries=2, timeout=40.0)
        # Les consignes et les connaissances ne changent pas : elles forment le préfixe mis en cache.
        self.system = [
            {"type": "text", "text": consignes},
            {"type": "text", "text": connaissances, "cache_control": {"type": "ephemeral"}},
        ]

    @staticmethod
    def messages(question, historique):
        """Les derniers échanges (texte seul, raccourcis), puis la question."""
        propres = []
        for m in (historique or [])[-HISTORIQUE:]:
            if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
                texte = m["content"].strip()[:TAILLE_MESSAGE]
                if texte:
                    propres.append({"role": m["role"], "content": texte})
        # L'API veut des tours alternés, en commençant par l'utilisateur.
        while propres and propres[0]["role"] != "user":
            propres.pop(0)
        alternes = []
        for m in propres:
            if alternes and alternes[-1]["role"] == m["role"]:
                alternes[-1] = m
            else:
                alternes.append(m)
        if alternes and alternes[-1]["role"] == "user":
            alternes.pop()
        return alternes + [{"role": "user", "content": question}]

    def demander(self, question, historique):
        """(texte au format de la page, usage en jetons, coût estimé en dollars)."""
        reponse = self.client.messages.create(
            model=MODELE,
            max_tokens=MAX_TOKENS,
            system=self.system,
            messages=self.messages(question, historique),
            # Réponses courtes et directes : sans réflexion (permis à l'effort « low ») ; le coût reste bas.
            thinking={"type": "disabled"},
            output_config={"effort": "low"},
        )
        u = reponse.usage
        usage = {"entree": u.input_tokens or 0,
                 "ecriture_cache": getattr(u, "cache_creation_input_tokens", 0) or 0,
                 "lecture_cache": getattr(u, "cache_read_input_tokens", 0) or 0,
                 "sortie": u.output_tokens or 0}
        cout = sum(usage[k] * PRIX[k] for k in PRIX) / 1_000_000
        if reponse.stop_reason == "refusal":
            return REFUS, usage, cout
        texte = "\n".join(b.text for b in reponse.content if b.type == "text").strip()
        if reponse.stop_reason == "max_tokens":
            texte += "\n\n(Réponse coupée : elle était trop longue.)"
        return texte or REFUS, usage, cout


def liens_verifies(texte, connus):
    """Les liens de la réponse qui figurent dans le dataset ou la FAQ : la page les marque « vérifiés »."""
    return sorted(u for u in set(re.findall(r"https?://[^\s|)>\]]+", texte)) if u in connus)

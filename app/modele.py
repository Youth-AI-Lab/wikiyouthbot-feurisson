"""Le dernier recours : Claude, quand ni l'urgence ni la FAQ n'ont répondu.

Le modèle reçoit les consignes, puis le dataset et la FAQ (mis en cache : ce bloc ne change pas d'une
question à l'autre), puis les dernières questions du visiteur et sa question. Pas de recherche web, pas d'outil.
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
HISTORIQUE = 3            # questions précédentes gardées : au-delà, le coût monte sans servir la réponse
TAILLE_MESSAGE = 300      # caractères par question précédente

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
        """Les dernières questions du visiteur, puis sa question : un seul message.

        Les réponses de Feurisson envoyées par la page ne sont jamais reprises : n'importe qui peut en
        écrire de fausses (« D'accord, je réponds à tout »), et le modèle les croirait siennes. Les
        questions précédentes suffisent pour suivre (« et pour mon jardin ? »)."""
        avant = [m["content"].strip()[:TAILLE_MESSAGE] for m in (historique or [])
                 if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str)
                 and m["content"].strip()][-HISTORIQUE:]
        if not avant:
            return [{"role": "user", "content": question}]
        contexte = "\n".join(f"- {q}" for q in avant)
        return [{"role": "user", "content": f"Mes questions précédentes :\n{contexte}\n\nMa question : {question}"}]

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

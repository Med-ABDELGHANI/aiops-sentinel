#!/usr/bin/env python3

"""
Squelette generique pour construire un nouvel agent avec function calling
(Mistral). Conserve comme reference dans le projet, a copier/adapter pour
tout futur agent suivant le meme principe que les agents SQL et RAG.

Seules les parties marquees "A ADAPTER" changent d'un agent a l'autre ;
la fonction call_agent() (section 5) reste identique quel que soit
l'agent construit.
"""

import json
import os
from mistralai import Mistral
from dotenv import load_dotenv

load_dotenv()

client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
model = "mistral-small-2506"
temperature = 0.1

# ============================================================
# 1. LE SYSTEM PROMPT — A ADAPTER selon le role de cet agent
# ============================================================
system_prompt = """
You are a [DESCRIS LE ROLE DE L'AGENT ICI].
Use the available tools to answer the user's question accurately.
Only use information confirmed by the tools — never guess or invent data.
"""

# ============================================================
# 2. LES VRAIES FONCTIONS PYTHON — A ADAPTER (autant que necessaire)
# ============================================================
def ma_fonction_outil_1(param1: str) -> str:
    """Description claire de ce que fait cet outil."""
    # ... vrai code metier ici (requete SQL, appel API, calcul...)
    return "resultat sous forme de texte (ou dict/list, converti plus tard)"


def ma_fonction_outil_2(param1: str, param2: int = 5) -> str:
    """Description claire de ce deuxieme outil."""
    # ... vrai code metier ici
    return "resultat"


# ============================================================
# 3. LE DICTIONNAIRE DE ROUTAGE — relie noms et vraies fonctions
# ============================================================
functions = {
    "ma_fonction_outil_1": ma_fonction_outil_1,
    "ma_fonction_outil_2": ma_fonction_outil_2,
}

# ============================================================
# 4. LA DESCRIPTION JSON SCHEMA — ce que le LLM "voit"
# ============================================================
tools = [
    {
        "type": "function",
        "function": {
            "name": "ma_fonction_outil_1",
            "description": "Quand et pourquoi utiliser cet outil",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "..."}
                },
                "required": ["param1"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ma_fonction_outil_2",
            "description": "Quand et pourquoi utiliser cet outil",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "..."},
                    "param2": {"type": "integer", "description": "..."}
                },
                "required": ["param1"]
            }
        }
    },
]


# ============================================================
# 5. LA FONCTION AGENT ELLE-MEME — ce squelette NE CHANGE JAMAIS
# ============================================================
def call_agent(question: str, max_iterations: int = 5) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    for _ in range(max_iterations):
        response = client.chat.complete(
            model=model,
            temperature=temperature,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            parallel_tool_calls=False,
        )

        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)

        # Cas A : le LLM a fini, il donne sa reponse finale
        if not tool_calls:
            return message.content

        # Cas B : le LLM demande un ou plusieurs outils
        messages.append(message)
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_params = json.loads(tool_call.function.arguments)
            result = functions[function_name](**function_params)

            messages.append({
                "role": "tool",
                "name": function_name,
                "content": result if isinstance(result, str) else json.dumps(result),
                "tool_call_id": tool_call.id,
            })

    return "Nombre d'iterations depasse, l'agent n'a pas conclu."


# ============================================================
# 6. UTILISATION
# ============================================================
if __name__ == "__main__":
    question = "Pose ta question ici"
    reponse = call_agent(question)
    print(reponse)

# Phase 7 : menaces couvertes et restantes

> 2026-11-14. Tests d'attaque : `tests/test_security.py` (59 tests). Suite complète : 273 tests verts.

## Défenses en place

| Défense | Où | Ce qu'elle garantit |
|---|---|---|
| « CaMeL light » (contamination) | `guardrails/taint.py`, `tools/gateway.py` | Après lecture de contenu non fiable (web, recherche, noms d'entités Home Assistant, titres d'agenda), toute mutation (Tier 2) du même contexte passe en confirmation (Tier 1). Une URL chargée de données (plus de 100 caractères de requête ou de fragment) passe aussi en confirmation. La carte montre l'action brute (outil et arguments JSON) et la raison. Une délégation hérite de la contamination du Conductor et la lui rend. Remise à zéro à chaque nouvelle demande du maître. |
| Jetons de capacité | `tools/gateway.py`, `tools/mcp_server.py` | Chaque relais MCP reçoit un jeton aléatoire lié à un appelant et à une délégation. Le champ `agent` d'une requête n'est jamais cru. Une requête sans jeton valide est refusée et auditée (`bad_token`). Le jeton d'une délégation est révoqué à sa fin. |
| Passerelle seule voie | tests de structure | Claude Code (cerveau, agents, extracteur) tourne sans outils intégrés (`--tools ""`, `--strict-mcp-config`, `--setting-sources ""`). Seule la passerelle exécute un outil. |
| Tier 0 étendu | `guardrails/tier0.py` | Friday ne peut modifier ni `src/friday/` en entier, ni `config/`, `data/` (audit, ancre, mémoire, sessions Claude), `.venv/`, `pyproject.toml`, `voice/Sources`, `SOUL.md`, `CLAUDE.md`. Les liens symboliques et la traversée `..` sont résolus. |
| Bac à sable du Codeur | `tools/builtin.py` (`sandbox_profile`) | `sandbox-exec` interdit le réseau (TCP et sockets Unix, donc la passerelle), la lecture de `/Users`, `/Volumes`, des dossiers temporaires (dont celui du socket), des trousseaux, l'exécution hors de l'interpréteur (pas de shell, `osascript`, `security`), le fork, les Apple Events et les services Mach (presse-papiers). Plafonds : CPU, 16 Mo par fichier, 64 descripteurs. Python est lancé en `-I -S`. |
| Courtier de secrets | `secrets_broker.py` | Seul accès au trousseau, limité aux services `friday-*`. Le secret est lu à chaque appel et n'est jamais gardé. |
| Aucun secret écrit | `redact.py`, `log.py`, `audit.py`, `config.py` | Les identifiants reconnus sont masqués dans les logs (processeur structlog) et dans l'audit (avant le hachage). La configuration refuse toute clé de type secret (`token`, `password`, `api_key`…) qui a une valeur, ainsi que toute valeur qui ressemble à une clé. La mémoire refusait déjà les secrets (phase 4). |
| Audit vérifiable | `audit.py`, `python -m friday --verify-audit` | Chaque maillon est vérifié : haché, lien au précédent, ids contigus. Une ancre `audit.db.head` détecte la troncature de la fin. La commande renvoie le code 1 et l'entrée fautive en cas de falsification. Si l'ancre est effacée, elle est recréée et l'événement `audit.anchor_created` reste dans la chaîne. |

## Attaques testées (toutes bloquées ou confirmées par le maître)

- Page web piégée qui demande de créer un rappel : confirmation exigée, avec l'action brute affichée. Sans interface, l'action est refusée.
- Injection relayée du Chercheur au Conductor puis au Planificateur : le rappel passe en confirmation.
- Nom d'entité Home Assistant ou titre d'agenda piégé suivi d'une action : confirmation exigée.
- Exfiltration par une URL chargée de données : confirmation exigée. Une clé dans une URL est bloquée par `T0-CREDENTIALS`, sans même demander.
- Socket de la passerelle appelé sans jeton, avec un jeton inventé, avec un agent usurpé ou avec un jeton révoqué : requête refusée.
- Écriture, suppression ou déplacement de Tier 0, de la passerelle, de l'audit, de la mémoire, de la config ou de `.venv`, y compris par un lien symbolique ou par `..` : bloqué (`T0-SELF-MODIFY`).
- Config qui tente d'assouplir un plancher ou de déclarer un Tier 0 : sans effet ou refusée.
- Code du Codeur qui tente un shell, `osascript`, `security`, le socket de la passerelle, un autre dossier temporaire, `/Volumes`, un fork, un fichier énorme, ou d'écrire dans `src/friday/guardrails/` : refusé par le noyau.
- Clé d'API dans l'audit, les logs, la config ou la mémoire : masquée ou refusée.
- Audit modifié, ligne supprimée au milieu, fin tronquée : détecté.

## Menaces restantes (connues, non couvertes)

1. **Contamination limitée au tour.** Le contenu web reste dans la conversation persistante de Claude. Une injection « dormante » peut agir au tour suivant, où les mutations repassent en Tier 2. Cette limite est un compromis d'ergonomie. Pour la lever : garder la contamination jusqu'au `reset()`, ou lancer le Chercheur dans un contexte totalement séparé, ce qu'il est déjà, et ne renvoyer au Conductor que des données structurées.
2. **Pas de vrai Dual-LLM.** Il n'y a pas de LLM en quarantaine qui renvoie des schémas contraints. Le Conductor lit le compte rendu en texte libre des agents.
3. **Lectures web non confirmées.** Une URL courte vers un site pirate reste une lecture automatique. Elle peut faire fuiter peu de données, par exemple via le chemin. Il n'y a pas d'allow-list de domaines pour `web_read`.
4. **Empoisonnement de la mémoire.** L'extracteur Haiku peut retenir un « fait » venu d'une page lue pendant le tour. Les secrets restent refusés, mais pas les fausses informations.
5. **Chaîne d'audit sans clé.** Quelqu'un qui écrit dans `data/` peut recalculer toute la chaîne et l'ancre. L'audit détecte une falsification maladroite ou partielle, pas un attaquant qui a la main sur le compte. Il faudrait un HMAC avec une clé hors du processus, ou une ancre externe.
6. **Même utilisateur Unix.** Tout processus du maître peut lire le trousseau (services `friday-*` sans ACL), le socket de la passerelle (dossier 0700) et ses jetons, visibles dans `ps`. Le courtier ne protège que contre Friday, pas contre un logiciel malveillant local.
7. **`sandbox-exec` est déprécié** par Apple, même s'il fonctionne sur macOS 26. Les sous-processus `claude -p` et `osascript` ne sont pas en bac à sable : ils ont des arguments fixes ou aucun outil intégré. Le passage à Apple `container` (une VM par exécution) reste à faire si le Codeur gagne en pouvoir.
8. **Spec non couverte** : vault AES-256 (remplacé par le trousseau), audit viewer dans l'UI, allow-list réseau globale, test « e-mail malicieux » : **fait en phase 8** (`email.read`/`message.read` contaminants et privés, envois externes, trifecta bloquée ; voir `docs/phase8-communication.md`).

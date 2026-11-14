# Progress — journal d'avancement

> Entrée datée à chaque grosse modification. Dernière entrée en haut.

## En cours
- Phase 1 (Fondations) terminée, 56 tests verts, **aucun commit fait** (en attente de l'accord de l'utilisateur). Prochaine étape : premier commit, puis phase 2 (voice pipeline) ou les ajouts phase 1 du rapport restants (bus asyncio, broker Trousseau).

## Fait
- 2026-11-13 — Phase 1 livrée : `git init` + `.gitignore`, `pyproject.toml` (src layout, venv `.venv` Python 3.15), `SOUL.md`, `config/friday.yaml`, logging structlog JSON, audit SQLite WAL en ajout seul (triggers) + chaînage SHA-256, GuardrailsEngine Tier 0-4 (Tier 0 codé en dur dans `guardrails/tier0.py`), Conductor à mots-clés FR/EN (7 intentions → agents), boucle `python -m friday`, 56 tests pytest.
- 2026-11-13 — `design-system/friday-ai/MASTER.md` réécrit en monochrome (surfaces opaques, contrastes calculés, verre limité à 3 éléments, conventions macOS).
- 2026-11-13 — Rapport de recherche livré : `reports/Stack vocale et agents Friday.md`, stack révisée reportée dans `projet.md`.
- 2026-11-13 — Prompt UI monochrome enregistré (`docs/friday-ui-prompt-monochrome.md`) et revue HIG v2 (`docs/revue-design-hig-v2.md`) : note Critical issues (tertiaire 3,0:1, focus 2,45:1, états par opacité seule, pas de reduced motion). 4 volets de recherche terminés.
- 2026-11-12 — Revue HIG Apple (`docs/revue-design-hig.md`) et design system corrigé (`design-system/friday-ai/MASTER.md`). Recherche approfondie en cours (4 volets), rapport attendu dans `reports/`.
- 2026-11-12 — Spec v1 et image de référence intégrées au projet, fichiers de suivi remplis.
- 2026-11-12 — Création de `projet.md`, `memory.md`, `progress.md`, `regle.md`, `ai.md` et `CLAUDE.md`.

## À faire
- Avant phase 2 : mesurer le TTFT de Haiku/Sonnet 5.5, tester Parakeet v3 et Qwen3-TTS en français, prototyper le verre dans Tauri, prévoir l'annulation d'écho.
- Phase 1 → Phase 8 (voir `projet.md`).

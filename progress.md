# Progress — journal d'avancement

> Entrée datée à chaque grosse modification. Dernière entrée en haut.

## En cours
- Phase 5 (interface) prototypée en SwiftUI natif (`voice/Sources/FridayApp`), non commitée. Reste à faire : vérification visuelle du dashboard et de l'overlay par l'utilisateur (`voice/.build/release/friday-app`), brancher l'app sur la voix et le cœur Python, raccourci global (package KeyboardShortcuts). Phase 2 (voix) codée, non commitée. Reste à faire : **test au micro réel** par l'utilisateur (`.venv/bin/python -m friday --voice`) pour valider le wake word, le barge-in et le TTFA < 2 s. Ensuite : phase 3, avec Claude Code comme cerveau.

## Fait
- 2026-11-14 — Mode bulle : Friday apparaît dès le lancement en bulle ronde de 96 px (NSPanel flottant, tous les Spaces, au-dessus du plein écran). Un clic ouvre la fenêtre de 380×680 ; Échap ou le chevron la ramènent en bulle ; le coin supérieur droit reste fixe et le cadre reste dans l'écran.
- 2026-11-14 — Interface SwiftUI : recherche approfondie (`reports/Interface desktop Friday.md`, 3 volets), app de barre de menus `friday-app` (dashboard avec barre latérale, stats CPU/RAM/disque réelles, hub avatar, widgets de démo ; overlay NSPanel non activant en Liquid Glass ; grille des 18 expressions), avatar à deux couches (yeux paramétriques + symboles), machine d'états `AvatarMachine` (priorités, passage par Neutre, retour à Neutre après 10 s). Revue HIG apple-design appliquée (teinte du verre, repli Réduire la transparence, texte renforcé en Augmenter le contraste, plus de boutons sans action). 40 vérifications Swift vertes, rendu PNG de la grille vérifié.
- 2026-11-14 — Phase 2 : module Swift `voice/` (AVAudioEngine avec annulation d'écho, SpeechAnalyzer/SpeechTranscriber fr_FR sur l'appareil, wake word par transcription, AVSpeechSynthesizer rendu dans le même moteur, machine à états Idle → Listening → Processing → Speaking, barge-in avec garde anti-écho, mesure du TTFA). Pont Python `friday/voice/bridge.py` (JSON Lines), `LocalBrain` (heure, date). 31 vérifications Swift et 64 tests pytest verts. TTS vérifié par `--say`.
- 2026-11-14 — Premier commit `5052bac`, dépôt GitHub `falilouthiane28-cloud/projet-friday` (public).
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

# AI — instructions de démarrage

> Fichier à lire en premier dans chaque nouvelle session.

## Au démarrage d'une session
1. Lire ce fichier.
2. Lire `progress.md` section « En cours » pour savoir où reprendre.
3. Lire `memory.md` pour les faits et décisions.
4. Lire `projet.md` si la tâche touche la structure ou la stack.
5. Lire `docs/friday-system-prompt.md` seulement la section utile (grep par titre), jamais en entier.
6. Suivre `regle.md` (mise à jour des fichiers, bascule à 70 %, économie de tokens).

## Résumé du contexte actuel
- Projet « Friday AI » : assistant vocal personnel multi-agents type J.A.R.V.I.S., Python, Claude API, avatar robot orange à 18 expressions.
- Spec v1 complète dans `docs/friday-system-prompt.md`, plan en 8 phases.
- UI : suivre `design-system/friday-ai/MASTER.md` (v2 monochrome, intègre la revue `docs/revue-design-hig-v2.md`). La revue v1 orange est obsolète.
- Stack : voir `reports/Stack vocale et agents Friday.md` avant de coder.
- État : phases 1 et 2 codées. Cœur Python dans `src/friday/` (`.venv/bin/pytest`), voix et interface Swift dans `voice/` (`friday-voice`, `friday-app`) (`swift run friday-voice-checks`, `swift build -c release`).

## Règle de bascule
Contexte de session ≈ 70 % → mettre à jour `progress.md` et `memory.md`, prévenir l'utilisateur, nouvelle session.

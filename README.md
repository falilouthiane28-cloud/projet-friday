# Friday

Assistant vocal personnel pour macOS, inspiré de J.A.R.V.I.S. Il vit dans une bulle à l'écran, répond à la voix ou au clavier, et agit sur le Mac sous des règles de sécurité codées en dur.

## Architecture
- **`voice/`** (Swift, SwiftUI) : l'app `friday-app` affiche la bulle, la fenêtre, l'avatar et le tableau de bord. La voix tourne sur l'appareil : AVAudioEngine avec annulation d'écho, SpeechTranscriber pour la transcription, wake word « Friday », AVSpeechSynthesizer pour parler.
- **`src/friday/`** (Python 3.15) : le cœur, lancé par l'app (`python -m friday --serve`).
  - Cerveau : un processus Claude Code persistant (`claude_brain.py`), avec les réponses locales simples dans `brain.py`.
  - Agents (`agents/`), chacun lancé en `claude -p` par délégation :
    - Chercheur : web ;
    - Planificateur : Calendrier et Rappels ;
    - Codeur : Python en bac à sable ;
    - Contrôleur domotique : Home Assistant ;
    - Communicateur : Mail, Messages et notifications ;
    - Moniteur système : état du Mac, avec alertes proactives.
  - Outils (`tools/`) : le relais MCP passe chaque appel à la `ToolGateway`, qui applique les guardrails, demande la confirmation Tier 1 dans la bulle et écrit l'audit.
  - Sécurité (`guardrails/`) : Tier 0 inviolable, Tiers 1 à 4, contamination « CaMeL light », lethal trifecta.
  - Mémoire (`memory/`) : SQLite + FTS5, faits extraits par Claude Haiku, aucun secret retenu.
- **Audit** : SQLite en ajout seul, chaîné en SHA-256 avec une ancre. Vérification : `PYTHONPATH=src .venv/bin/python -m friday --verify-audit`.

## Lancer
```bash
cd voice && swift build -c release && .build/release/friday-app
```
Prérequis : `claude` connecté (`/login`), Python 3.15 dans `.venv` (`pip install -e .`).
Autorisations macOS au premier usage :
- Micro et Reconnaissance vocale ;
- Automatisation pour Rappels, Calendrier, Mail et Messages ;
- Accès complet au disque, seulement pour lire Messages.

## Tests
```bash
.venv/bin/pytest
```
```bash
cd voice && swift run friday-voice-checks
```

## Documents
- Spec : `docs/friday-system-prompt.md`
- Sécurité : `docs/securite-phase7.md`
- Phase 8 : `docs/phase8-communication.md`
- Design : `design-system/friday-ai/MASTER.md`
- Suivi : `progress.md`, `memory.md`, `projet.md`

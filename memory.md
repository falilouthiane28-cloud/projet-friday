# Memory — faits à retenir

> Faits durables, décisions, préférences. Une ligne par fait.

## Préférences utilisateur
- Langue de travail : français.
- Économiser les tokens : réponses courtes, pas de relecture inutile des fichiers.
- Utilisateur : Thaïne Fallou, « maître » de Friday dans la spec.

## Faits sur le projet
- 2026-11-12 : spec v1 copiée dans `docs/friday-system-prompt.md`, planche d'expressions dans `img/`.
- Friday vouvoie par défaut, ton pro avec humour discret, répond en 1-3 phrases pour le simple.
- 2026-11-13 : direction UI changée en **noir et blanc strict** (yeux LED blancs, fond #000), prompt dans `docs/friday-ui-prompt-monochrome.md`. L'orange est abandonné.
- Les règles Tier 0 (pas d'exfiltration, pas de code obfusqué, pas d'auto-modification des règles de sécurité, pas d'usurpation, pas de credentials en clair, Lethal Trifecta) sont à coder en dur, hors prompt.

## Décisions
- Stack révisée 2026-11-13 : livekit-wakeword (Porcupine sans offre gratuite depuis le 30/06/2026), Deepgram Flux au lieu de Whisper large-v3, pas de Redis ni pynvml, mem0 + SQLite + Chroma, Tauri 2. Inconnue majeure : TTFT Claude non publié, à mesurer.
- Design v2 monochrome : corrections HIG dans `docs/revue-design-hig-v2.md` (tertiaire 0.55, focus outline 2px 0.85, surfaces opaques #0A0A0A/#141414/#1C1C1E/#2C2C2E, verre seulement top bar + saisie + overlay natif, icônes Lucide pas d'emoji, police `-apple-system`). `design-system/friday-ai/MASTER.md` réécrit en monochrome le 2026-11-13 (source de vérité UI).
- Design (v1 orange, obsolète sauf principes) : verre uniquement sur les barres et la fenêtre overlay (vibrancy native), cartes opaques ; texte sur orange = `#08080E` (jamais blanc) ; tertiaire à 0.48 d'opacité ; un seul orange, pas de gradient ; app de barre de menus macOS. Détail dans `design-system/friday-ai/MASTER.md`.
- Ne jamais relancer ui-ux-pro-max `--persist --force` : il écraserait MASTER.md. Règles clés : pas de texte tertiaire ni de libellé rouge sur la surface #2C2C2E (4,1:1), texte en hex opaques.
- Bascule de session quand le contexte atteint 70 % (voir `regle.md`).
- 2026-11-13 : phase 1 codée. Dépendances volontairement minimales (pyyaml, structlog, pytest) ; pas de pydantic (Python système 3.15, risque de wheels manquantes).
- Guardrails : Tier 0 = 6 règles gelées (`T0-EXFIL`, `T0-OBFUSCATED`, `T0-SELF-MODIFY`, `T0-IMPERSONATION`, `T0-CREDENTIALS`, `T0-TRIFECTA`), évaluées avant tout ; la config YAML ne peut que durcir un tier (planchers en dur, action inconnue = Tier 1, toute sortie externe = Tier 1) ; Tier 0 refusé en config.
- Fichiers protégés contre Friday : `src/friday/guardrails/`, `audit.py`, `config/`, `SOUL.md`, `data/audit.db`.
- Audit : pas de texte brut des messages, seulement une empreinte SHA-256 (16 caractères).
- 2026-11-14 : **voix en Swift natif** (choix de l'utilisateur), cœur en Python ; le binaire `friday-voice` est lancé par Python et dialogue en JSON Lines sur stdin/stdout. Remplace Pipecat, livekit-wakeword, Deepgram et ElevenLabs du rapport (onnxruntime n'existe pas pour Python 3.15).
- 2026-11-14 : **le cerveau sera Claude Code** (décision de l'utilisateur pour la phase 3). Risque : le démarrage d'une session Claude Code en mode headless prend probablement plusieurs secondes, ce qui sortirait du budget de 2 s. Garder les réponses locales (`LocalBrain`) pour les commandes simples.
- Mac : macOS 26.7, arm64, Swift 6.3, Command Line Tools sans Xcode, donc ni XCTest ni Swift Testing (cible exécutable `friday-voice-checks` à la place). Voix françaises installées en qualité compacte seulement (Thomas) : conseiller une voix premium (Réglages → Accessibilité → Contenu énoncé).
- Wake word : le token « friday » repéré dans la transcription continue, plus des contextualStrings ; livekit-wakeword est possible plus tard pour réduire la consommation.
- 2026-11-14 : **UI en SwiftUI natif** (rapport `reports/Interface desktop Friday.md`) : vrai Liquid Glass (`glassEffect`), overlay en NSPanel ; Tauri et Electron sont écartés. Les icônes sont des SF Symbols (Lucide ne s'utilisait que pour le web). Les yeux restent blancs : l'image de référence (robot blanc, yeux bleus) ne sert que pour les formes.
- Vérification visuelle sans écran : `friday-app --snapshot <dossier>` (ImageRenderer ; les contrôles AppKit comme Toggle, TextField et List n'y sont pas rendus).
- Limites des CLT confirmées : pas de `#Preview` ni d'`actool` (icône en `.icns`), Swift Testing possible seulement avec des drapeaux `-F` et `-rpath`.
- Raccourci global : il faut Cmd ou Ctrl (depuis Sequoia, Option seul échoue) ; ⌃⌥Espace est suggéré.
- Demande de l'utilisateur : Friday doit rester **tout le temps à l'écran sous forme de bulle**. L'overlay a deux états (bulle 96 px ↔ fenêtre 380×680) et Échap réduit au lieu de masquer.
- 2026-11-14 : l'app `friday-app` contient la voix (même AVAudioEngine) et lance `.venv/bin/python -m friday --serve` avec `PYTHONPATH=src` ; racine du dépôt trouvée en remontant jusqu'à `pyproject.toml` (ou `FRIDAY_ROOT`). `--config <yaml>` permet un audit isolé dans les tests.
- KeyboardShortcuts : rester en **1.15.0** ; les versions ≥ 1.16 utilisent `#Preview`/`@Entry`, dont les plugins de macros SwiftUI manquent dans les CLT.
- Raccourci ⌃⌥Espace : bulle → fenêtre + écoute ; fenêtre à l'écoute → arrêt ; pendant la parole → coupe et écoute (`VoiceSession.onListen`).
- 2026-11-14 : cerveau = **Claude Code en headless** (`claude -p --output-format json --tools "" --strict-mcp-config --setting-sources ""`), sessions dans `data/claude/`. Le binaire de l'app Claude (`~/Library/Application Support/Claude/claude-code/<ver>/*/claude.app/Contents/MacOS/claude`) n'est **pas connecté hors de l'app** : il faut `claude` puis `/login` une fois (ou `ANTHROPIC_API_KEY`). Retirer les variables `CLAUDECODE`/`CLAUDE_CODE_*`/`ANTHROPIC_BASE_URL` héritées d'une session parente.
- Friday ne parle que si la question est vocale (`VoiceLink.shouldSpeak`) ; timeout de traitement vocal porté à 60 s pour Claude.
- Une vue hébergée dans un NSPanel n'est pas dans une scène SwiftUI : `openWindow`/`openSettings` sont capturés depuis le label du MenuBarExtra (`MenuBarLabel`).
- Conductor : interface `IntentClassifier` prévue pour brancher semantic-router puis Haiku en phase 3.

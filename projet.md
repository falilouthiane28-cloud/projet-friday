# Projet — Friday AI

> Vue d'ensemble. Spec complète dans `docs/friday-system-prompt.md` (à lire seulement pour les détails d'une section précise).

## Objectif
Assistant IA personnel type J.A.R.V.I.S. pour le poste de travail de Thaïne Fallou : vocal (wake word « Hey Friday »), multi-agents, mémoire persistante, domotique, monitoring système, avatar robot aux yeux LED orange (18 états émotionnels).

## Stack technique (révisée le 2026-11-13, détail dans `reports/Stack vocale et agents Friday.md`)
- Runtime : Python 3.11+, un seul processus, bus d'événements asyncio (Redis abandonné)
- Voix (2026-11-14, en place) : binaire Swift `voice/` : AVAudioEngine avec voice processing (AEC) → SpeechAnalyzer/SpeechTranscriber sur l'appareil → wake word dans la transcription → AVSpeechSynthesizer. Le plan initial du rapport suit :
- Voix (rapport) : Pipecat + livekit-wakeword v2 (« Hey Friday ») → Silero VAD v6 + Smart Turn → Deepgram Flux (secours local Parakeet / mlx-whisper turbo) → ElevenLabs v4 Turbo (secours local Qwen3-TTS MLX). Cible 800 ms TTFA.
- Cerveau (décision 2026-11-14) : Claude Code. Les réponses locales restent pour l'heure, la date et les commandes simples.
- LLM (rapport) : semantic-router pour les commandes fréquentes → Haiku 5.5 (routage) → Sonnet 5.5 (conversation) / Opus 5.5 (Coder, Researcher). Secours hors ligne Qwen3 8B.
- Orchestration : Conductor en code (Pydantic AI ou SDK Anthropic) ; Claude Agent SDK pour les agents longs uniquement
- Mémoire : SQLite + mem0 OSS + Chroma + embeddings bge-m3 (PostgreSQL abandonné)
- Mémoire (révisé 14/11) : SQLite + FTS5 seulement (`src/friday/memory/`), faits extraits par Claude Haiku après chaque échange (`brain.memory_model`) ; Chroma et bge-m3 écartés tant qu'onnxruntime manque pour Python 3.15, mem0 non utilisé
- Sécurité : « CaMeL light » (valeurs marquées non fiables), passerelle d'outils deny > ask > allow, Trousseau macOS derrière un broker, sandbox-runtime ou Apple `container`, audit SQLite WAL chaîné
- Sécurité (en place 14/11, phase 7) : contamination par contexte (`guardrails/taint.py`), jetons de capacité dans la passerelle, `sandbox-exec` durci, `secrets_broker.py` (services `friday-*`), `redact.py` (logs + audit), audit avec ancre et `--verify-audit`. Bilan : `docs/securite-phase7.md`
- Domotique : MCP officiel Home Assistant + hass-client (rapport)
- Domotique (en place 14/11) : API REST de Home Assistant en stdlib (`src/friday/tools/home.py`), outils sous `ToolGateway` ; jeton dans le trousseau macOS (service `friday-home-assistant`, compte `friday`). MCP officiel non branché (contournerait les guardrails), hass-client plus tard pour les événements (dépend d'aiohttp)
- Monitoring : psutil + SMC via ctypes + powermetrics (pynvml abandonné, pas de NVIDIA sur Mac)
- Monitoring (en place 14/11, phase 8) : stdlib + `vm_stat`/`sysctl`/`pmset` (`tools/system.py`, psutil sans wheel 3.15), alertes proactives `SystemWatcher`
- Communication (en place 14/11, phase 8) : Mail et Messages macOS (osascript, `chat.db` en lecture seule), pas d'OAuth ; envois Tier 1, lethal trifecta bloquée
- UI (2026-11-14, en place) : SwiftUI natif macOS 26 dans `voice/` (cible `FridayApp`) : MenuBarExtra, dashboard, overlay NSPanel en Liquid Glass, avatar SwiftUI. L'ancien plan suit :
- UI (rapport stack) : Tauri 2 + tauri-nspanel, avatar Rive ou SVG, design monochrome noir et blanc (`docs/friday-ui-prompt-monochrome.md`)

## Architecture
- Conductor (orchestrateur unique) → agents principaux : Researcher, Coder, Scheduler, Home_Controller, System_Monitor, Communicator
- Sub-agents : Validator, Memory_Manager, File_Manager, Web_Scraper, Emotion_Engine, Device_Bridge, Guardrails_Engine
- Sécurité : tiers 0 (inviolable) à 4 (interne), Dual-LLM / CaMeL, capability tokens, vault AES-256, audit log SQLite

## Structure du dossier
- `docs/friday-system-prompt.md` — spec source complète (897 lignes)
- `img/avatar-expressions-reference.jpg` — planche de référence des expressions robot
- `docs/friday-ui-prompt-monochrome.md` — prompt UI v2 noir et blanc (direction actuelle)
- `docs/revue-design-hig-v2.md` — revue HIG du prompt monochrome
- `docs/revue-design-hig.md` — revue v1 orange (obsolète)
- `design-system/friday-ai/MASTER.md` — design system v2 monochrome : tokens, typo, accessibilité, conventions macOS (source de vérité UI)
- `reports/Stack vocale et agents Friday.md` — rapport de recherche stack (notes dans `research_notes/`)
- `projet.md`, `memory.md`, `progress.md`, `regle.md`, `ai.md` — fichiers de suivi
- `SOUL.md` — identité de Friday (bloc YAML) ; `config/friday.yaml` — configuration (tiers des actions, domaines autorisés)
- `src/friday/` — code : `config.py`, `soul.py`, `log.py` (structlog), `audit.py` (SQLite WAL chaîné), `conductor.py`, `guardrails/` (`tiers.py`, `tier0.py`, `engine.py`), `__main__.py`
- `voice/` — paquet Swift : `FridayVoiceCore` (machine à états, wake word, protocole), `FridayVoiceKit` (micro, STT, TTS, `VoicePipeline`), `FridayVoice` (binaire piloté par Python), `FridayUICore` (avatar, lien voix → avatar), `FridayApp` (interface SwiftUI avec la voix dans le même processus, cœur Python en sous-processus, raccourci KeyboardShortcuts 1.15.0), `friday-voice-checks`
- `reports/Interface desktop Friday.md` — rapport de recherche UI (notes dans `research_notes/Interface desktop Friday/`)
- `src/friday/claude_brain.py` (`ClaudeCodeBrain`, `PersistentClaudeBrain`), `brain.py` (`LocalBrain`, `HybridBrain`)
- `src/friday/tools/` — outils de Claude : `mcp_server.py` (relais MCP stdio sans dépendance, lancé par Claude Code), `gateway.py` (`ToolGateway` : socket Unix, guardrails, confirmation Tier 1, audit), `builtin.py` (rappels et Calendrier macOS via osascript : `calendar_read` Tier 3, `calendar_create_event` Tier 2 ; météo Open-Meteo, recherche DuckDuckGo)
- `src/friday/dashboard.py` (données réelles du dashboard : message `dashboard`), `voice/Sources/FridayApp/Dashboard.swift` + `DashboardSections.swift` (6 sections), règles UX : `docs/regles-ux-dashboard.md`
- `src/friday/voice/bridge.py` (pont JSON Lines, mode `--voice`), `src/friday/voice/server.py` (`CoreServer`, mode `--serve` lancé par l'app), `src/friday/brain.py` (`LocalBrain`)
- `src/friday/agents/` — agents phase 3 : `registry.py` (`AgentSpec`, `AgentRegistry`, Chercheur/Planificateur (agenda + rappels)/Codeur), `delegation.py` (`AgentRunner` : `claude -p` par délégation, outils `delegate_*`, Validateur)
- `src/friday/memory/` — mémoire phase 4 : `store.py` (`MemoryStore` : faits SQLite + index FTS5, `remember`/`recall`/`forget`/`context_for`, `alearn` en tâche de fond, audit), `extractor.py` (`FactExtractor`, `RuleBasedExtractor`, repli), `claude_extractor.py` (`ClaudeFactExtractor` : `claude -p` haiku one-shot, JSON), `secrets.py` (filtre en dur : aucun secret mémorisé)
- `src/friday/tools/home.py` — domotique phase 6 : `HomeAssistantClient` (REST, jeton lu par `security`), outils `home_states`/`home_light`/`home_switch`/`home_scene`/`home_secure` ; agent `home_controller` (Contrôleur domotique, haiku) dans `registry.py`
- `src/friday/secrets_broker.py` (trousseau), `src/friday/redact.py` (masquage), `src/friday/guardrails/taint.py` (CaMeL light) ; `docs/securite-phase7.md` — menaces couvertes et restantes ; `tests/test_security.py` — tests d'attaque
- `src/friday/tools/comms.py` — phase 8 : Mail, Messages, notifications (agent `communicator`) ; `src/friday/tools/system.py` — `system_read` + `SystemWatcher` (agent `system_monitor`) ; `docs/phase8-communication.md` — bilan fait/reporté ; `README.md` — vue d'ensemble
- `tests/` — pytest (`fake_home_assistant.py` : faux HA REST local) (`.venv/bin/pytest`) ; `data/` — base d'audit locale (ignorée par Git)

## Plan en 8 phases (détail dans la spec, section 11)
1. Fondations (Conductor, config YAML, logging, Guardrails)
2. Voice pipeline
3. LLM & agents
4. Mémoire
5. Interface visuelle (dashboard + overlay + avatar)
6. Domotique
7. Sécurité & hardening
8. Communication & polish

## Décisions majeures
| Date | Décision | Raison |
|------|----------|--------|
| 2026-11-14 | Phase 8 : Mail/Messages macOS, e-mails et messages = sources non fiables et privées, envoi après lecture bloqué (T0-TRIFECTA) | Pas d'OAuth ni de dépendance ; une injection par e-mail ne doit jamais pouvoir exfiltrer |
| 2026-11-14 | Phase 7 : contamination par contexte (Tier 2 → 1), jetons de capacité, Tier 0 sur tout le code et les données, sandbox sans exec/fork/Mach | Une entrée non fiable ne doit jamais déclencher seule une action (Tramèr) ; ergonomie : remise à zéro à chaque demande |
| 2026-11-14 | Domotique par l'API REST de HA derrière la `ToolGateway`, jeton au trousseau, serrures/alarme/volets en Tier 1 (plancher en dur) | Le MCP officiel branché sur Claude Code contournerait guardrails et audit ; pas de nouvelle dépendance |
| 2026-11-12 | Création des fichiers de suivi | Garder le contexte entre sessions |
| 2026-11-13 | Stack révisée (wake word, STT, Redis, pynvml remplacés) | Rapport de recherche |
| 2026-11-13 | UI passée en noir et blanc strict | Prompt v2 de l'utilisateur |
| 2026-11-14 | Cerveau Claude Code headless sans outils, heure/date en local | Choix de l'utilisateur ; aucune action machine avant les guardrails de la phase 3 |
| 2026-11-14 | App = UI + voix dans un processus Swift, Python en sous-processus (`--serve`) | Recommandation du rapport UI ; un seul AVAudioEngine, états voix directs vers l'avatar |
| 2026-11-14 | Outils de Claude = serveur MCP relais → `ToolGateway` du cœur (guardrails + audit), confirmation Tier 1 dans la bulle, refus par défaut après 60 s | Toute action passe par le moteur codé en dur, jamais par le prompt |
| 2026-11-14 | UI en SwiftUI natif plutôt que Tauri | Vrai Liquid Glass, compile avec les CLT, même langage que la voix |
| 2026-11-14 | Voix en Swift natif, cœur Python, cerveau Claude Code | Choix de l'utilisateur ; onnxruntime absent pour Python 3.15 |
| 2026-11-13 | Phase 1 : Tier 0 en code, config qui ne peut que durcir, audit sans texte brut | Sécurité par architecture (rapport) |
| 2026-11-12 | Spec v1 adoptée (`docs/friday-system-prompt.md`) | Document fourni par l'utilisateur |

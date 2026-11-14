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
- Sécurité : « CaMeL light » (valeurs marquées non fiables), passerelle d'outils deny > ask > allow, Trousseau macOS derrière un broker, sandbox-runtime ou Apple `container`, audit SQLite WAL chaîné
- Domotique : MCP officiel Home Assistant + hass-client
- Monitoring : psutil + SMC via ctypes + powermetrics (pynvml abandonné, pas de NVIDIA sur Mac)
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
- `voice/` — paquet Swift : `FridayVoiceCore` (machine à états, wake word, protocole), `FridayVoice` (micro, STT, TTS), `FridayUICore` (machine d'états de l'avatar), `FridayApp` (interface SwiftUI), `friday-voice-checks`
- `reports/Interface desktop Friday.md` — rapport de recherche UI (notes dans `research_notes/Interface desktop Friday/`)
- `src/friday/voice/bridge.py` (pont JSON Lines), `src/friday/brain.py` (`LocalBrain`)
- `tests/` — pytest (`.venv/bin/pytest`) ; `data/` — base d'audit locale (ignorée par Git)

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
| 2026-11-12 | Création des fichiers de suivi | Garder le contexte entre sessions |
| 2026-11-13 | Stack révisée (wake word, STT, Redis, pynvml remplacés) | Rapport de recherche |
| 2026-11-13 | UI passée en noir et blanc strict | Prompt v2 de l'utilisateur |
| 2026-11-14 | UI en SwiftUI natif plutôt que Tauri | Vrai Liquid Glass, compile avec les CLT, même langage que la voix |
| 2026-11-14 | Voix en Swift natif, cœur Python, cerveau Claude Code | Choix de l'utilisateur ; onnxruntime absent pour Python 3.15 |
| 2026-11-13 | Phase 1 : Tier 0 en code, config qui ne peut que durcir, audit sans texte brut | Sécurité par architecture (rapport) |
| 2026-11-12 | Spec v1 adoptée (`docs/friday-system-prompt.md`) | Document fourni par l'utilisateur |

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
- Fichiers protégés contre Friday : `src/friday/guardrails/`, `audit.py`, `config/`, `SOUL.md`, `data/audit.db`, `data/memory.db` (et leurs `-wal`/`-shm`/`-journal`).
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
- Micro avec voice processing = **3 canaux** non entrelacés à 48 kHz ; ne jamais convertir directement vers mono (silence) : prendre le canal 0 (`MicConverter`). `say` ne peut pas tester le micro (l'annulation d'écho retire le son du Mac).
- Claude Code en flux : `-p … --output-format stream-json --verbose --include-partial-messages` ; les deltas sont dans `stream_event.event.delta.text_delta`, la fin dans `type: result`. Latence mesurée : 1re phrase ~4 s, dont ~2,5 s de démarrage du binaire.
- Protocole app ↔ cœur : `chunk{id,text}` (phrase) puis `reply{…, streamed: true}` ; l'app enchaîne les envois à la voix (`inOrder`) pour garder l'ordre.
- Cerveau = **processus Claude Code persistant** (stdin `{"type":"user","message":{"role":"user","content":…}}`, un tour se termine par `type: result`) : 1re phrase ~1,5 s contre ~4 s en one-shot. Un tour à la fois (verrou).
- Outils de Claude : `--tools ""` ne coupe que les outils intégrés ; les outils MCP restent visibles (`mcp__friday__*`) et `--allowedTools mcp__friday` évite les refus de permission en `-p`.
- Le Python de python.org n'a pas de certificats racine : `ssl` charge `/etc/ssl/cert.pem` (sinon CERTIFICATE_VERIFY_FAILED).
- Les cartes de confirmation n'ont **aucun raccourci clavier** : Entrée dans la saisie ne doit jamais autoriser une action Tier 1.
- Rappels via osascript : 1er appel lent (~14 s, lancement de Rappels / autorisation Automatisation).
- 2026-11-14 : mémoire = **SQLite + FTS5** (`unicode61 remove_diacritics 2`), pas de Chroma (onnxruntime absent sous 3.15). Requête : mots vides retirés, racine grossière (mot ≥ 7 lettres → 2 dernières retirées), préfixe `"x"*` ; `recall` en OU, `forget` en ET (évite d'effacer trop). Effacement réel = `PRAGMA secure_delete=ON` + `optimize` FTS5 + `wal_checkpoint(TRUNCATE)`.
- Droit à l'oubli : effacer le fait de `memory.db` ne suffit pas, la conversation persistante de Claude le garde ; `HybridBrain` appelle `reset()` après un oubli.
- Conductor : interface `IntentClassifier` prévue pour brancher semantic-router puis Haiku en phase 3.
- 2026-11-14 : extraction des faits = **Claude Haiku en one-shot séparé** (`claude -p … --no-session-persistence`), lancé après le `reply` ; la conversation persistante n'est jamais touchée. Avec extracteur Claude, `HybridBrain` n'apprend plus par règles à l'énoncé (règles = repli si Claude échoue). Coût : ~4 s de haiku par échange, en fond.
- Secrets : refusés à l'écriture (`SecretRefused`, audit `memory.refused` avec empreinte) quelle que soit la source ; un passage secret n'est jamais envoyé à l'extracteur (`redact_secrets`).
- FTS5 `unicode61` ne décompose pas « œ »/« æ » : l'index et les requêtes passent par `_ligatures` (réindexation auto à l'ouverture).
- `ImageRenderer` (`--snapshot`) ne rend pas le contenu des `ScrollView` : `MemoryPanel(scrolls: false)` pour le rendu.
- 2026-11-14 : agents = **sous-processus `claude -p` one-shot** lancés par les outils `delegate_*` (handoffs-as-tools) ; le Conductor (Claude persistant) n'a plus que `weather_read` + `delegate_*`. Restriction des outils appliquée par la passerelle (registre, `allowed`), pas seulement par `--allowedTools`. Pas de Google Calendar (OAuth) : Planificateur = Rappels macOS.
- Bac à sable du Codeur : `sandbox-exec` avec `(allow default)` puis `deny network*`, `deny file-read*` du HOME, `deny file-write*` sauf le dossier temporaire (la dernière règle qui correspond l'emporte). L'interpréteur est le Python du framework (hors HOME), lancé en `-I`.
- Une délégation coûte ~5 à 15 s (démarrage de `claude -p` + outils) : la spec « Ligue 1 + rappel » prend ~34 s (Chercheur puis Planificateur, en série car le rappel dépend de la date trouvée).
- 2026-11-14 : agenda du Planificateur = **Calendrier macOS via osascript** (`calendar_read`, `calendar_create_event`). Dates passées en composantes (année, mois, jour, h, min), pas en texte (indépendant de la langue). Filtre `whose start date < d2 and end date > d1` par calendrier (~2 s pour 7 jours) ; les occurrences des événements **récurrents ne sont pas développées** (limite AppleScript ; EventKit en Swift si besoin). Le calendrier virtuel « Rappels programmés » se dit modifiable : écarté du choix par défaut (premier calendrier modifiable). Pas de `\` en fin de ligne dans un AppleScript (continuation = `¬`).
- 2026-11-14 : domotique = **API REST de Home Assistant derrière la `ToolGateway`** (stdlib), pas le serveur MCP officiel branché sur Claude Code (il contournerait guardrails/audit/confirmations) ni hass-client (aiohttp, risque sous Python 3.15). Jeton : trousseau, service `friday-home-assistant`, compte `friday` (`security add-generic-password -U -s friday-home-assistant -a friday -w`), lu à chaque appel, jamais en config (`home_assistant.token` lève une erreur), ni logs ni audit.
- Domotique : serrures, alarme et **tous les volets** (`cover.*`, faute de connaître la device_class avant l'appel) passent par `home_secure` (Tier 1, plancher en dur `home.secure`) ; aucun code d'alarme accepté ; une scène qui contient lock/alarme/cover est refusée. Noms d'entités = données non fiables (nettoyés, présentés comme tels).
- 2026-11-14 : phase 7 = **CaMeL light par contexte** (tour du Conductor ou délégation), pas par valeur : sources non fiables codées en dur (`web.search`, `web.read`, `home.read`, `calendar.read`) ; contexte contaminé → Tier 2 devient Tier 1, URL avec > 100 car. de requête+fragment → Tier 1 ; carte de confirmation avec l'action brute. Délégation hérite/rend la contamination ; remise à zéro à chaque `ask` si aucun tour en cours (`CoreServer._turns`).
- Passerelle : identité = **jeton de capacité** (`--token` du relais MCP), le champ `agent` de la requête est ignoré ; jetons de délégation révoqués à `end_run`.
- Sandbox Codeur : le Python du framework relance `Python.app` → autoriser `process-exec` sur tout `Python.framework` ; `(deny mach-lookup)` et `-I -S` ne cassent pas la stdlib.
- Audit : ancre `data/audit.db.head` (id + haché) écrite sous le verrou SQLite ; ancre absente → recréée + événement `audit.anchor_created`. Vérif : `PYTHONPATH=src .venv/bin/python -m friday --verify-audit`.
- Ne pas appeler `setup_logging` dans un test avec `capsys` : structlog garde le flux fermé et casse les tests suivants.
- 2026-11-14 : phase 8 = **Mail et Messages macOS** (osascript, chat.db), pas de Gmail API ni d'IMAP (OAuth). `email.read`/`message.read` sont contaminants et privés (`PRIVATE_SOURCES`) : après lecture, tout outil `external=True` du même contexte est bloqué par T0-TRIFECTA (sans demander). Pour répondre : brouillon `mail_draft` (Tier 1 si contaminé) ou nouvelle demande dictée. Le calendrier n'est pas classé privé (choix d'ergonomie).
- `Tool.external` : drapeau d'envoi hors de la machine, transmis par la passerelle en `external_communication` (plancher Tier 1).
- Lire Messages exige l'Accès complet au disque (`~/Library/Messages/chat.db`, `mode=ro`) ; le texte peut être dans `attributedBody` (typedstream : après `NSString`, `+`, longueur sur 1 octet, ou 0x81 + 2 octets).
- Moniteur : psutil absent (3.15), donc `vm_stat` + `sysctl` (`/usr/sbin`) + `pmset` + `shutil.disk_usage`. `SystemWatcher` ne répète une alerte qu'après sa retombée.
- Scripts Mail et Messages pas encore lancés en réel (éviter les invites d'autorisation sans le maître).
- Messages : lire `~/Library/Messages/chat.db` exige l'**accès complet au disque** pour l'app qui lance Friday (`friday-app` ou le terminal) ; réglage à faire par l'utilisateur.
- L'utilisateur ne veut **pas d'envoi réel** d'e-mail ou d'iMessage en test (14/11).
- 2026-11-14 : **la bulle est masquée quand le dashboard est au premier plan** (`OverlayController.updateVisibility`). Elle est réévaluée sur les notifications NSWindow (clé, fermeture, réduction, occlusion) et NSApplication (active/inactive). La fenêtre SwiftUI `Window(id: "dashboard")` a pour identifiant AppKit un nom qui commence par « dashboard ». Quand `model.dashboardFront` est vrai, les confirmations et le raccourci global vont vers la section Conversations du dashboard.
- Dashboard : message `dashboard` (`src/friday/dashboard.py`), lancé par l'app sans passer par le cerveau. Il renvoie la météo (Open-Meteo, ville `default_city`), l'agenda du jour (même AppleScript que `calendar_read`), le registre des agents et `home_configured`. Chaque source échoue séparément, avec sa raison. L'app le redemande au plus toutes les 10 min.
- AppleScript Calendrier : l'erreur **-600** signifie « Calendrier n'est pas ouvert ». Le dashboard lance alors `open -g -j -a Calendar` (masqué) et réessaie une fois. L'outil `calendar_read` du Planificateur n'a pas encore ce correctif.
- `screencapture` donne une image noire : l'Enregistrement de l'écran n'est pas autorisé. Pour vérifier en réel : `friday-app --dashboard [section]`, plus la liste des fenêtres via `CGWindowListCopyWindowInfo`, qui ne demande pas d'autorisation.
- Les sous-agents (Agent tool) ont été refusés par le classifieur du mode auto le 14/11 : deep-research n'a pas pu tourner.
- 2026-11-14 : un `ScrollView` placé dans une page qui ne défile pas, dans le détail du `NavigationSplitView`, s'affichait **entièrement vide** (bug de l'onglet Mémoire). Règle : une seule zone de défilement par page (`SectionPage(scrolls: true)` + `MemoryPanel(scrolls: false)`). La barre latérale est forcée visible (`columnVisibility: .all`).
- Vérification visuelle réelle sans autorisation : `friday-app --dashboard <section> --selfshot <fichier.png>`. L'app capture sa propre fenêtre via `CGWindowListCreateImage`, appelé par `dlsym` car il est retiré du SDK 15+. `--snapshot` produit aussi `live-*.png` (NSHostingView hors écran), mais ce rendu ne dessine pas le NavigationSplitView.

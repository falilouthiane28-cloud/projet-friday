# Mémoire long terme et shell desktop (assistant IA Python, macOS Apple Silicon) — état novembre 2026

Notes de recherche. Dates de référence : recherche effectuée le 12 novembre 2026. Les informations antérieures à 2025 sont signalées comme telles. Les sources sont majoritairement des docs officielles, des READMEs GitHub et des comparatifs de blogs 2026 (ces derniers sont à prendre avec prudence : chiffres souvent auto-rapportés par les éditeurs).

---

## A1. Mémoire à trois couches : Redis + SQLite + ChromaDB reste-t-il le bon choix local, ou mem0 / Letta / Zep / LanceDB / sqlite-vec simplifient-ils ?

### Takeaway
En novembre 2026, pour un assistant personnel mono-utilisateur sur Mac, la pile « SQLite (faits structurés + historique) + une base vectorielle embarquée » reste le socle le plus simple ; mem0 OSS est la bibliothèque qui apporte le plus de valeur par-dessus (pipeline extraction + réconciliation ADD/UPDATE/DELETE/NONE) tout en restant 100 % locale (Ollama + Chroma/Qdrant). Letta a abandonné son serveur Docker open source et son SDK Python v1 est déprécié ; Zep est orienté serveur/graphe temporel ; Redis n'est pas nécessaire pour un buffer court terme mono-process.

### Cited Findings
- mem0 OSS se présente comme « le même moteur mémoire que la Platform » utilisable en bibliothèque Python (`mem0ai`, `Memory()`) ou serveur Docker Compose. Défauts bibliothèque : LLM OpenAI `gpt-5-mini`, embeddings `text-embedding-3-small`, vector store Qdrant local dans `/tmp/qdrant`, historique SQLite dans `~/.mem0/history.db`, reranker désactivé ; défauts serveur : Postgres + pgvector — [docs.mem0.ai/open-source/overview](https://docs.mem0.ai/open-source/overview)
- Composants mem0 OSS (Python) : vector stores = qdrant, pgvector, chroma, pinecone, redis, weaviate, milvus, elasticsearch ; embedders = openai, gemini, azure_openai, ollama, huggingface, vertexai, aws_bedrock ; LLM = openai, anthropic, gemini, groq, ollama, aws_bedrock, azure_openai, litellm. LanceDB, sqlite-vec et FAISS ne sont PAS listés. La mémoire graphe « ne fait pas partie de l'OSS » (feature Platform) — [docs.mem0.ai/open-source/configuration](https://docs.mem0.ai/open-source/configuration.md)
- Chaque `add()` mem0 exécute un pipeline LLM : extraction de faits, recherche de mémoires sémantiquement proches, puis décision par fait parmi ADD / UPDATE / DELETE / NONE. mem0 annonce une réécriture complète du pipeline mémoire en avril 2026, donc les détails ont pu changer — [dev.to (mukesh_13)](https://dev.to/mukesh_13/mem0-auto-resolves-memory-conflicts-for-you-until-it-silently-deletes-one-you-still-need-4f4m) ; [mem0 changelog](https://docs.mem0.ai/changelog/highlights.md)
- Letta : la page MemGPT/V1 indique que « le SDK V1 est en cours de dépréciation au profit du Letta Agent SDK » ; V1 supporte « memory blocks only », SDK Python = `pip install letta-client` ; le SDK Agent V2 est TypeScript uniquement — [docs.letta.com/concepts/memgpt](https://docs.letta.com/concepts/memgpt)
- Letta self-hosting : « The Docker image is no longer an actively maintained or supported Letta product surface » ; stockage Postgres (+pgvector) uniquement, Ollama comme seul fournisseur local documenté — [docs.letta.com/guides/selfhosting](https://docs.letta.com/guides/selfhosting)
- Zep est un serveur mémoire open source auto-hébergeable bâti sur un graphe de connaissances temporel (Graphiti) qui stocke des fenêtres de validité sur les faits ; Letta est un framework d'agents complet ; mem0 est une couche « vector-first ». Les trois sont Apache-2.0 ; étoiles GitHub (juillet 2026, source secondaire) : mem0 ~60k, Zep/Graphiti ~28k, Letta ~24k — [atlan.com](https://atlan.com/know/best-ai-agent-memory-frameworks-2026/) ; [dev.to (agdex_ai)](https://dev.to/agdex_ai/letta-vs-zepgraphiti-vs-mem0-choosing-an-ai-agent-memory-architecture-155a)
- Benchmarks contestés : mem0 rapporte 93,4 vs Zep 71,2 (LongMemEval, GPT-4o) alors que Zep rapportait 63,8 % vs mem0 49,0 % sur les tâches temporelles (arXiv 2501.13956) ; dispute méthodologique active sur LoCoMo — [mem0.ai](https://mem0.ai/library/agent-memory/zep-vs-mem0-which-ai-memory-layer-should-you-choose) ; contredit par [coworker.ai](https://coworker.ai/blog/mem0-vs-zep-vs-letta)
- sqlite-vec : extension SQLite en C pur, « pre-v1, expect breaking changes », vecteurs float/int8/binary dans des tables virtuelles `vec0`, colonnes metadata/auxiliary/partition key, `pip install sqlite-vec`, 8,3k étoiles, Apache-2.0/MIT — [github.com/asg017/sqlite-vec](https://github.com/asg017/sqlite-vec)
- sqlite-vec : version stable v0.1.9 (2026-03-31), IVF et DiskANN seulement en pré-release, pas de HNSW ; adapté « sous ~100k vecteurs » — [actian.com (comparatif)](https://www.actian.com/blog/developer/comparing-embedded-vector-databases/) ; [aloa.co](https://aloa.co/ai/comparisons/vector-database-comparison/best-embedded-vector-databases)
- ChromaDB : chemin le plus court vers un setup local ; adapté prototypes et RAG mono-nœud ; un ADR d'équipe rapporte des « corruptions HNSW connues à la sortie brutale du process » (expérience d'une seule équipe) — [ADR codesight](https://glama.ai/mcp/servers/@camilojourney/codesight/blob/e68c8f478f02ad3334682785d9e157be0df2afe3/docs/decisions/0001-lancedb-over-chromadb.md) ; [encore.dev](https://encore.dev/articles/best-vector-databases)
- LanceDB : « bibliothèque de retrieval open source embarquée qui tourne dans le process de l'application », sans serveur ; recherche vectorielle, full-text, hybride, reranking, filtrage, SQL — [docs.lancedb.com](https://docs.lancedb.com/)
- LanceDB cité en 2026 comme mieux adapté que Chroma à la croissance sur disque et avec BM25 + vecteur hybride natif — [lancedb.com/lp/vs-chroma](https://lancedb.com/lp/vs-chroma) (source éditeur)

### Inferences
- Pour « Friday » (un seul utilisateur, un seul process Python), Redis est superflu pour le buffer court terme : une deque en mémoire + persistance SQLite suffit ; Redis n'apporte de valeur que si plusieurs process doivent partager le buffer (ex. backend FastAPI + worker vocal séparés). mem0 OSS liste d'ailleurs Redis seulement comme vector store, pas comme buffer.
- mem0 OSS est le meilleur compromis « pipeline prêt » : il fonctionne avec Ollama (LLM + embeddings) et Chroma ou Qdrant local, donc entièrement hors ligne, et gère la réconciliation des faits. Contrepartie : chaque `add()` coûte un appel LLM, et les décisions DELETE sont probabilistes (risque de suppression indue signalé par un retour d'expérience).
- Letta n'est plus un bon choix pour un backend Python local fin 2026 (SDK Python déprécié, image Docker non maintenue, Postgres obligatoire). Zep est surdimensionné (serveur + graphe) pour un assistant personnel, sauf si le raisonnement temporel est central.
- Si l'on veut éviter mem0 et rester minimaliste : SQLite + sqlite-vec (tout dans un seul fichier .db, < 100k vecteurs) est le plus simple ; LanceDB si l'on veut la recherche hybride BM25 et une marge de croissance ; Chroma si l'on veut la compatibilité directe avec mem0 OSS. Noter que mem0 OSS ne supporte ni sqlite-vec ni LanceDB.

### Gaps
- Je n'ai pas pu vérifier la version courante de mem0 OSS ni les détails du pipeline post-réécriture d'avril 2026 (la page overview ne donne pas de numéro de version).
- Aucun benchmark indépendant fiable mem0 vs Zep vs Letta : tous les chiffres trouvés sont auto-rapportés ou issus de blogs.
- Je n'ai pas pu lire la doc LanceDB Python détaillée (types d'index IVF-PQ/HNSW, registre d'embeddings, concurrence multi-process) : la page d'accueil ne les décrit pas.

---

## A2. Modèles d'embeddings locaux sur Apple Silicon (nomic-embed, bge, MLX)

### Takeaway
La voie la plus simple et la mieux intégrée (mem0 la supporte nativement) est Ollama avec `nomic-embed-text` (768 dims, 274 Mo) ou `bge-m3` (1024 dims, ~1,2 Go, multilingue — pertinent pour le français) ; Ollama exploite Metal/MLX sur Apple Silicon. `mlx-embeddings` est l'option MLX pur mais ne liste ni nomic ni bge explicitement.

### Cited Findings
- `mlx-embeddings` (Blaizzy) : `pip install mlx-embeddings`, architectures texte supportées = XLM-RoBERTa, BERT, ModernBERT, plus Qwen3, Qwen3-VL, Llama bidirectionnel, etc. ; outil de conversion avec quantification (affine, mxfp4, nvfp4, mxfp8). Nomic et BGE ne sont pas mentionnés nommément — [github.com/Blaizzy/mlx-embeddings](https://github.com/Blaizzy/mlx-embeddings)
- Spécifications via Ollama (source secondaire) : nomic-embed-text 137M params, 274 Mo, 8 192 tokens, 768 dims, Apache-2.0 ; bge-m3 567M params, ~1,2 Go, 8 192 tokens, 1 024 dims, MIT ; `/api/embed` ne renvoie que le vecteur dense de bge-m3 (pas sparse/multi-vector) — [morphllm.com](https://www.morphllm.com/ollama-embedding-models) ; [insiderllm.com](https://insiderllm.com/guides/embedding-models-rag/)
- Recommandation répétée par plusieurs guides : nomic-embed-text pour l'anglais général, bge-m3 pour le multilingue ; nomic-embed-text-v2-moe (multilingue) serait limité à 512 tokens — [localaimaster.com](https://localaimaster.com/blog/best-ollama-embedding-models)
- Un article affirme qu'Ollama a ajouté MLX comme moteur pour les modèles safetensors (preview 0.19) et qu'à partir de 0.30.0 le backend Metal de llama.cpp est aussi pris en charge pour les GGUF — [buttondown.com/insiderllm](https://buttondown.com/insiderllm/archive/ollama-quietly-changed-how-your-mac-runs-models/) (source unique, non vérifiée contre les release notes Ollama)
- mem0 OSS supporte les embedders `ollama` et `huggingface` en Python — [docs.mem0.ai/open-source/configuration](https://docs.mem0.ai/open-source/configuration.md)

### Inferences
- Pour un assistant francophone, bge-m3 via Ollama est le choix par défaut raisonnable (multilingue, 8k tokens) ; nomic-embed-text si la mémoire est surtout en anglais ou si la RAM est contrainte. BERT/XLM-R étant supportés par mlx-embeddings, les checkpoints bge (BERT) et nomic (BERT modifié) devraient être convertibles, mais cela n'est pas confirmé par le README.

### Gaps
- Aucun benchmark de débit d'embeddings Metal/MLX sur puces M trouvé.
- Pas de confirmation officielle (release notes Ollama) du passage à MLX/Metal.

---

## A3. Pipelines de condensation (conversation → faits structurés), oubli/TTL, gestion des conflits

### Takeaway
mem0 fournit le pipeline de condensation et de réconciliation le plus abouti en open source (ADD/UPDATE/DELETE/NONE, historique par mémoire, `custom_instructions`) ; l'expiration (`expiration_date`) et la décroissance (Memory Decay) sont documentées côté Platform, pas clairement côté OSS, donc un TTL local doit probablement être implémenté soi-même dans SQLite.

### Cited Findings
- mem0 : `expiration_date` masque une mémoire au lieu de la supprimer ; effacer la date la restaure ; « Memory Decay » fait baisser le rang des souvenirs anciens tout en les gardant cherchables ; Delete pour une suppression définitive ; les dates malformées « fail open » (traitées comme non expirées). Ces pages sont sous `/platform/features/` — [docs.mem0.ai memory-expiration](https://docs.mem0.ai/platform/features/memory-expiration) ; [expiration-date](https://docs.mem0.ai/platform/features/expiration-date)
- mem0 : `delete()` accepte `delete_linked` (sans, des faits remplacés peuvent resurgir) ; `m.history(memory_id)` montre les versions antérieures et l'événement (ADD/UPDATE/DELETE) — [docs.mem0.ai update](https://docs.mem0.ai/core-concepts/memory-operations/update.md) ; [dev.to crabtalk](https://dev.to/crabtalk/mem0-what-three-memory-scopes-actually-cost-1kpc)
- Variante graphe mem0ᵍ : « Conflict Detector » (nœuds/arêtes contradictoires) + « Update Resolver » LLM (merge, invalidation, skip) — décisions probabilistes — [dev.to mukesh_13](https://dev.to/mukesh_13/mem0-auto-resolves-memory-conflicts-for-you-until-it-silently-deletes-one-you-still-need-4f4m)
- mem0 OSS « Custom Instructions » : personnalise la façon dont les faits sont extraits du texte — [docs.mem0.ai features](https://docs.mem0.ai/open-source/features/overview.md)
- Zep/Graphiti : faits avec fenêtres de validité temporelle (« ce qui était vrai au T1 ») — [atlan.com](https://atlan.com/know/best-ai-agent-memory-frameworks-2026/)
- Letta (Docker, déprécié) : option MemFS git-backed par agent (`LETTA_MEMFS_SERVICE_URL=local`) — [docs.letta.com/guides/selfhosting](https://docs.letta.com/guides/selfhosting)

### Inferences
- Architecture recommandée pour Friday : (1) buffer court terme = N derniers tours en RAM + table SQLite `turns` ; (2) condensation asynchrone (après chaque session ou toutes les N minutes) via mem0 OSS `add()` avec Ollama, ou via un prompt maison qui produit des faits JSON (sujet, prédicat, valeur, confiance, `valid_from`, `source_turn_id`) insérés dans SQLite ; (3) vecteurs dans Chroma (si mem0) ou sqlite-vec/LanceDB (si pipeline maison).
- TTL/oubli : implémenter soi-même un champ `expires_at` + un score de décroissance (ex. `score * exp(-λ·age)` au moment du rerank) ; l'approche « masquer puis purger » de mem0 est un bon modèle à copier.
- Conflits : garder l'historique (ne jamais écraser), marquer l'ancien fait `superseded_by` ; pour les faits « durs » (adresse, préférences explicites), exiger une confirmation utilisateur avant DELETE plutôt que laisser le LLM décider (risque documenté de suppression silencieuse).

### Gaps
- Je n'ai pas pu confirmer si `expiration_date`/Memory Decay sont disponibles dans la bibliothèque mem0 OSS ou seulement sur la Platform.

---

## B1. Tauri 2 vs Electron pour overlay transparent always-on-top macOS, app barre de menus, hotkey global, micro, RAM à l'idle ; intégration backend Python

### Takeaway
Tauri 2 est le choix le plus léger (20–110 Mo RAM selon la version de macOS pour un overlay réel, vs 128–300 Mo pour Electron) et couvre overlay transparent, tray, hotkey global et sidecar PyInstaller ; les pièges macOS (overlay invisible au-dessus des apps plein écran, icône Dock) ont des correctifs connus (`tauri-nspanel`, `ActivationPolicy::Accessory`). Electron reste plus « clé en main » (API `setAlwaysOnTop` avec niveaux, `visibleOnFullScreen`, vibrancy) au prix de la RAM. Pour un backend Python, le schéma sidecar PyInstaller + WebSocket/FastAPI local fonctionne avec les deux.

### Cited Findings
- Retour d'expérience Tauri v2 overlay (mars 2026, testé Sonoma/Sequoia/Tahoe sur M2) : RAM macOS Sequoia 20–29 Mo, Sonoma 66 Mo, Tahoe 110 Mo (régression webview OS, ~4x) ; Windows 11 ~14 Mo. Problèmes rencontrés sur macOS : overlay invisible au-dessus des apps plein écran → corrigé avec le plugin tiers `tauri-nspanel` (fenêtre convertie en NSPanel) ; app visible dans Dock/Cmd+Tab → `ActivationPolicy::Accessory` ; `backdrop-filter: blur()` cassé avec transparence. Pas de click-through par région natif (workaround : boucle Rust ~60 fps + `setIgnoreCursorEvents`). Craintes qui ne se sont PAS reproduites : perte de transparence en build de production, artefacts d'ombre. Electron rejeté pour ~200–300 Mo de RAM — [dev.to manasightgg](https://dev.to/manasightgg/why-i-chose-tauri-v2-for-a-desktop-overlay-in-2026-597h)
- Comparatif BetterStack (màj 20 juillet 2026, app d'enregistrement d'écran, build macOS) : taille Tauri 57 Mo, Deno Desktop 111 Mo, Electron 323 Mo, Electrobun 418 Mo ; RAM idle Deno 98 Mo, Tauri 109 Mo (36 Mo process principal + helpers WebKit), Electron 128 Mo, Electrobun 208 Mo — [betterstack.com](https://betterstack.com/community/guides/scaling-nodejs/tauri-vs-electron-vs-deno-vs-electrobun/)
- Autres chiffres (blogs 2026, non contrôlés) : 42 Mo vs 168 Mo (Tauri vs Electron 34.x) ; ~80 Mo vs ~160 Mo (Tauri 2.9.6 vs Electron 33.x) ; app vide 4,4 Mo (Tauri 2.12) vs 294 Mo (Electron 44.9.0) — [tech-insider.org](https://tech-insider.org/tauri-vs-electron-2026/) ; [pkgpulse.com](https://www.pkgpulse.com/guides/electron-vs-tauri-2026)
- Tauri config : `app.macOSPrivateApi` « active l'API de fond transparent et met `fullScreenEnabled` à true » ; devenu no-op en Tauri 2.12.1+ car « les API sont toujours activées désormais » — [v2.tauri.app/reference/config](https://v2.tauri.app/reference/config/). (Le post de mars 2026 disait encore que `macOSPrivateApi: true` excluait le Mac App Store ; info antérieure à 2.12.1.)
- Tauri plugin global-shortcut : `tauri-plugin-global-shortcut`, Rust ≥ 1.90, desktop uniquement, JS `register('CommandOrControl+Shift+C', cb)`, permissions explicites par commande dans les capabilities (aucune activée par défaut) — [v2.tauri.app/plugin/global-shortcut](https://v2.tauri.app/plugin/global-shortcut/)
- Tauri sidecar : exécutable externe « écrit dans n'importe quel langage », exemples cités = outils CLI/serveurs API Python empaquetés avec PyInstaller ; déclaré dans `bundle.externalBin`, nommé avec suffixe `-$TARGET_TRIPLE` (`rustc --print host-tuple`) ; `app.shell().sidecar("name").spawn()` donne stdout/stdin ; permissions `shell:allow-execute`/`allow-spawn` avec `"sidecar": true` — [v2.tauri.app/develop/sidecar](https://v2.tauri.app/develop/sidecar/)
- Tauri menu bar : `tauri-plugin-positioner` avec feature `tray-icon` et `on_tray_event` pour `Position::TrayCenter` ; recette = tray icon + fenêtre sans décoration transparente always-on-top + positioner + masquage Dock ; `tauri-nspanel` (auteur ahkohd) convertit la fenêtre en NSPanel, « la partie la plus difficile » — [v2.tauri.app/plugin/positioner](https://v2.tauri.app/plugin/positioner) ; [dev.to hiyoyok](https://dev.to/hiyoyok/complete-guide-to-building-a-macos-menu-bar-app-with-tauri-v2-aji) ; [ahkohd/tauri-macos-menubar-app-example](https://github.com/ahkohd/tauri-macos-menubar-app-example)
- Electron BrowserWindow macOS : `setAlwaysOnTop(flag, level)` avec niveaux `floating`, `status`, `pop-up-menu`, `screen-saver` ; `setVisibleOnAllWorkspaces(true, {visibleOnFullScreen: true})` pour rester au-dessus des apps plein écran ; `setIgnoreMouseEvents(true, {forward: true}) ` ; `invalidateShadow()` pour les artefacts des fenêtres transparentes ; `setVibrancy('hud'|'sidebar'|…)` — [electronjs.org BrowserWindow](https://www.electronjs.org/docs/latest/api/browser-window)
- Electron globalShortcut : `register(accelerator, cb)` après `app.whenReady()` ; échec silencieux si le raccourci est déjà pris ; touches média nécessitent l'autorisation Accessibilité « trusted client » — [electronjs.org global-shortcut](https://www.electronjs.org/docs/latest/api/global-shortcut)
- Tauri utilise le webview OS (WebKit sur macOS), Electron embarque Chromium ; rendu identique partout pour Electron — [betterstack.com](https://betterstack.com/community/guides/scaling-nodejs/tauri-vs-electron-vs-deno-vs-electrobun/)

### Inferences
- Recommandation : Tauri 2 (≥ 2.12.1) + `tauri-nspanel` + `tauri-plugin-positioner` + `tauri-plugin-global-shortcut`, avec le backend Python lancé soit en sidecar PyInstaller (distribution propre), soit en process séparé pendant le dev, exposant FastAPI + WebSocket sur localhost ; le front (dashboard + overlay = deux fenêtres Tauri) s'abonne au WebSocket pour les états de l'avatar. Le micro : préférer la capture côté Python (sounddevice/pyaudio) plutôt que `getUserMedia` dans WKWebView, pour éviter les prompts de permission du webview et garder l'audio dans le pipeline vocal Python ; la permission micro macOS s'applique alors au binaire Python/sidecar (clé `NSMicrophoneUsageDescription` dans l'Info.plist de l'app Tauri si sidecar).
- Attention à macOS Tahoe (26) : régression RAM webview (~110 Mo) — l'avantage Tauri se réduit mais reste net face à Electron.
- Electron reste défendable si l'équipe veut un rendu Chromium garanti (Rive WebGL2, `backdrop-filter`) et des API overlay matures sans plugins tiers ; coût : +100–200 Mo RAM et bundle ~300 Mo.

### Gaps
- Je n'ai pas pu lire la section `WindowConfig` de la référence Tauri (page tronquée) : options `transparent`, `alwaysOnTop`, `visibleOnAllWorkspaces`, `windowEffects` non vérifiées depuis la doc officielle (elles existent d'après les guides communautaires).
- Aucun chiffre de RAM spécifique à une fenêtre overlay transparente pour Electron.
- Accès micro depuis WKWebView dans Tauri (prompts, `NSMicrophoneUsageDescription`) non vérifié dans les sources.

---

## B2. Avatar animé SVG / Lottie / Rive avec 18 états d'yeux : technologie la plus légère et la plus simple à piloter par changements d'état

### Takeaway
Rive est la solution conçue pour un avatar piloté par états (State Machine + inputs booléens/numériques/triggers + Data Binding), avec des fichiers souvent plus petits que Lottie ; Lottie convient aux animations linéaires et LottieFiles a ajouté une State Machine en 2025-2026 mais moins mûre. Pour 18 états d'yeux, l'alternative la plus légère en RAM/CPU reste un SVG inline + CSS/JS (pas de WASM), au prix d'un travail d'animation manuel.

### Cited Findings
- Rive (comparatif éditeur, màj octobre 2026) : Lottie adapté aux animations linéaires « play-once » (loaders, icônes) ; la State Machine Rive gère l'interactivité pilotée par inputs et données en temps réel ; rendu GPU et Data Binding — [rive.app/blog](https://rive.app/blog/rive-as-a-lottie-alternative)
- LottieFiles (màj mars 2026) qualifie la State Machine de Rive de « mature » et indique avoir introduit une State Machine native dans Lottie Creator — [lottiefiles.com](https://lottiefiles.com/blog/lottie-animations/lottiefiles-or-rive)
- Runtime web Rive : `@rive-app/webgl2` recommandé (Rive Renderer, supporte tout ce que l'éditeur produit, dont Vector Feathering) ; `@rive-app/canvas-lite` plus petit si pas de Rive Text/Layouts/Scripting/Audio ; option `autoBind: true` lie automatiquement le ViewModelInstance par défaut ; un `stateMachine` doit être nommé sinon seule la première animation linéaire joue ; WASM préchargeable/auto-hébergeable — [rive.app/docs/runtimes/web/web-js](https://rive.app/docs/runtimes/web/web-js)
- Fichiers Rive « souvent 50 à 70 % plus petits » que l'équivalent Lottie (affirmation d'un article Webflow 2026, non contrôlée) — [pravinkumar.co](https://www.pravinkumar.co/blog/webflow-rive-animations-gsap-data-binding-2026)
- Adoption : lottie-web ~300k téléchargements/semaine vs @rive-app/canvas ~50k — [pkgpulse.com](https://www.pkgpulse.com/guides/lottie-vs-rive-vs-css-animations-web-animation-formats-2026)
- Aucun benchmark indépendant 2026 FPS/CPU/RAM Rive vs Lottie trouvé — [callstack.com](https://callstack.com/blog/lottie-vs-rive-optimizing-mobile-app-animation) (analyse mobile, chiffres non lus)

### Inferences
- Pour 18 états d'yeux : modéliser dans l'éditeur Rive une State Machine avec un input numérique `eyeState` (0–17) ou un ViewModel data-bound ; le front reçoit l'état via WebSocket depuis Python et met à jour l'input — un seul fichier .riv, transitions/blinks gérées dans l'éditeur. Utiliser `@rive-app/canvas-lite` pour le poids minimal si aucun texte/audio Rive ; `webgl2` si Vector Feathering nécessaire (vérifier le support WebGL2 dans WKWebView en fenêtre transparente, non testé).
- Option « zéro dépendance » : SVG inline avec 18 groupes `<g id="eye-…">` et `data-state` sur le root + transitions CSS ; le plus léger en RAM et sans WASM, mais les morphings complexes (blink, émotions) demandent du travail manuel (GSAP/anime.js possibles).
- Lottie : à réserver si les assets viennent d'After Effects ; piloter 18 états via `playSegments` ou plusieurs JSON est plus lourd et moins fluide que la State Machine Rive.

### Gaps
- Page officielle Rive sur les inputs de State Machine non récupérée (404 sur l'URL testée) : l'API exacte (`stateMachineInputs()`, `.value`, `.fire()`) n'a pas pu être citée.
- Pas de taille de bundle officielle pour les runtimes Rive.
- Fonctionnement de WebGL2/WASM Rive dans une fenêtre Tauri transparente non vérifié.

---

## B3. Monitoring système macOS depuis Python : psutil sur Apple Silicon, GPU/température (powermetrics, ioreg/SMC), fenêtre active (pyobjc), notifications

### Takeaway
psutil couvre CPU/RAM/disque/réseau/batterie mais pas les températures ni le GPU Apple ; `powermetrics` (sudo) donne puissance/fréquence/utilisation GPU et « pression thermique », pas de °C ; les températures en °C se lisent sans sudo via le SMC (IOKit/ctypes, comme `agtop`, `apple-smi`, `yamon`). Fenêtre active = `NSWorkspace.sharedWorkspace().frontmostApplication()` + `CGWindowListCopyWindowInfo` (titres soumis à la permission Enregistrement d'écran). Notifications = `desktop-notifier` (UNUserNotificationCenter, nécessite un Python/app signé) ou `macos-notifications` (pyobjc).

### Cited Findings
- `powermetrics -s thermal` rapporte la pression thermique, pas une température en °C ; `asitop`/`metop` exigent sudo car powermetrics requiert root ; ils remontent puissance, fréquence, utilisation — [pypi metop](https://pypi.org/project/metop/) ; [asitop](https://github.com/tlkh/asitop)
- `agtop` lit les températures de die CPU/GPU via bindings IOKit ctypes au service `AppleSMC`, découvre les clés `Tp*`/`Te*` (CPU) et `Tg*` (GPU) au démarrage, sans sudo ; utilise `psutil.cpu_percent(percpu=True)` pour l'activité par cœur — [agtop](https://awesome.ecosyste.ms/projects/github.com%2Fbinlecode%2Fagtop)
- `apple-smi` : pur Python ctypes, « lectures de température GPU/SOC haute précision avec logique de repli de capteurs » — [pypi apple-smi](https://pypi.org/project/apple-smi/) ; `yamon` : moyenne des capteurs SMC en °C, sans sudo sur les Macs supportés — [pypi yamon](https://pypi.org/project/yamon/)
- Contre-point : la doc de benchmarking de Stanford liste la température GPU Apple Silicon comme indisponible (« no temperature reporting, no GPU info ») — [hazyresearch.stanford.edu](https://hazyresearch.stanford.edu/intelligence-per-watt/benchmarking/platform-support/) ; contredit par les outils SMC ci-dessus (dépend des clés exposées par chaque puce)
- psutil : la page d'accueil (release 7.2, section « Migrating to 8.0 ») ne précise pas les restrictions macOS ; les exemples `sensors_temperatures`/`sensors_fans` montrent des capteurs Linux (coretemp, acpitz) — [psutil.io](https://psutil.io/)
- Fenêtre active : `NSWorkspace` frontmostApplication + `CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)` via PyObjC/Quartz ; liste ordonnée avant→arrière ; `kCGWindowName` peut manquer sans permission Enregistrement d'écran ; un thread Apple signale `NSWorkspace` absent d'AppKit avec certains builds Python sur macOS 12.3 (ancien, 2022) — [lzwjava](https://lzwjava.github.io/macos-python-window-capture-en) ; [Apple Developer Forums](https://developer.apple.com/forums/thread/702611) ; [Stack Overflow (miroir)](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/373020/finding-the-current-active-window-in-mac-os-x-using-python)
- `desktop-notifier` : macOS via Notification Center (UNUserNotificationCenter), dépendance `rubicon-objc` ; UNUserNotificationCenter n'autorise que les frameworks/bundles signés, d'où repli sur `NSUserNotificationCenter` (déprécié) si Python n'est pas signé ; releases 3.x → 6.x sur PyPI — [desktop-notifier docs](https://desktop-notifier.readthedocs.io/en/latest/background/platform_support.html) ; [pypi](https://pypi.org/project/desktop-notifier)
- `macos-notifications` : alternative basée sur pyobjc, boutons d'action avec callbacks et réponse — [pypi macos-notifications](https://pypi.org/project/macos-notifications)

### Inferences
- Pour Friday : psutil pour CPU/RAM/disque/réseau/batterie ; `apple-smi` ou copie de l'approche SMC-ctypes pour les °C (sans sudo) ; GPU % via `powermetrics` uniquement si l'on accepte un helper sudo (ou sudoers NOPASSWD limité à powermetrics) — sinon l'utilisation GPU n'est pas accessible sans root ; `ioreg -r -c AGXAccelerator` pourrait exposer des compteurs mais non vérifié ici.
- Si l'app Tauri embarque le sidecar Python, les notifications peuvent passer par Tauri (`tauri-plugin-notification`, bundle signé) plutôt que par Python non signé — ce contournement évite le problème de signature de `desktop-notifier`.
- Fenêtre active : demander la permission Enregistrement d'écran uniquement si les titres de fenêtres sont nécessaires ; le nom d'app seul (NSWorkspace) n'en a pas besoin.

### Gaps
- Je n'ai pas pu lire la page « platform support » de psutil pour confirmer officiellement que `sensors_temperatures`/`sensors_fans` sont Linux-only et l'état de `sensors_battery` sur macOS.
- Fiabilité des clés SMC `Tg*` sur M3/M4/M5 non vérifiée.
- `ioreg` pour l'utilisation GPU : aucune source trouvée dans cette session.

---

## B4. Intégration Home Assistant depuis Python (REST/WebSocket, MQTT via paho/aiomqtt) et serveur MCP Home Assistant

### Takeaway
Home Assistant expose nativement un serveur MCP (depuis 2025.2, OAuth 2.0 + PKCE, outils Assist ou « full admin ») ; pour un contrôle direct en Python, `hass-client` (Music Assistant, WebSocket + REST, màj avril 2026) est le client le plus maintenu ; pour MQTT, `aiomqtt` v3 abandonne paho pour une lib sans-io pure asyncio. `ha-mcp` (communauté, 87 outils, streamable-HTTP) est l'alternative MCP plus riche.

### Cited Findings
- Intégration officielle « Model Context Protocol Server » : HA est le serveur MCP ; auth OAuth 2.0 + PKCE, pas de client secret ; deux jeux d'outils (« Device control » = outils Assist limités aux entités exposées ; « Home Assistant » = lecture de toutes les entités/logs/historique et toute action, compte admin requis) ; URLs individuelles ex. `/api/mcp/assist` ; ressource `homeassistant://assist/context-snapshot` ; supporte Prompts/Tools/Resources, pas Sampling ni Notifications ; introduite en HA 2025.2, qualité Silver, 8,1 % des installations ; Claude Code se connecte avec `--transport http` — [home-assistant.io/integrations/mcp_server](https://www.home-assistant.io/integrations/mcp_server/)
- `ha-mcp` (homeassistant-ai) : « Configure and automate Home Assistant with Claude, ChatGPT… », 87 outils, exécution en serveur streamable-HTTP (intégration in-process, add-on, Docker, `uvx`), stdio possible mais déconseillé, exemples avec `--python 3.14`, guide pour « version 9.0.0 (28 octobre 2026) et ultérieures » — [github.com/homeassistant-ai/ha-mcp](https://github.com/homeassistant-ai/ha-mcp)
- `hass-client` (music-assistant/python-hass-client) : client basique WebSocket + REST, dernière version 1.2.3, màj 2026-04-02, Apache-2.0 — [pypi hass-client](https://pypi.org/project/hass-client/) ; [depscope](https://depscope.dev/pkg/pypi/hass-client)
- `hass-websocket-client` : petit client async (0.2.0), `fetch_states()`, `call_service(domain, service, target, data)` avec token longue durée — [pypi hass-websocket-client](https://pypi.org/project/hass-websocket-client)
- `aiomqtt` : « client MQTT asyncio idiomatique », sans callbacks, MQTTv5, reconnexion auto ; v3 « remplace paho-mqtt par la bibliothèque sans-io mqtt5 » → pure asyncio sans threads ; commande d'installation affichée `pip install aiomqtt==3.0.0-alpha.1` (pré-release) ; BSD-3 — [github.com/empicano/aiomqtt](https://github.com/empicano/aiomqtt)
- Aucun serveur MCP Home Assistant trouvé utilisant aiomqtt ; les implémentations Python (ex. mjrestivo16) utilisent httpx/websockets — [glama.ai mcp-homeassistant](https://glama.ai/mcp/servers/@mjrestivo16/mcp-homeassistant/tree/720495e6d91dd9c43051a152ba843dcf5c24086b)

### Inferences
- Deux chemins complémentaires pour Friday : (a) l'agent LLM parle à HA via le serveur MCP officiel (`/api/mcp/assist` pour un contrôle sûr limité aux entités exposées) ; (b) le backend Python s'abonne aux événements d'état via `hass-client` (WebSocket) pour alimenter le dashboard en temps réel. MQTT n'est utile que si des capteurs publient directement sur un broker (ex. Zigbee2MQTT) ; sinon le WebSocket HA suffit.
- Pour aiomqtt, préférer la dernière 2.x stable en production tant que la 3.0 est en alpha (à vérifier sur PyPI).

### Gaps
- Transport exact (SSE vs streamable HTTP) du serveur MCP officiel HA non précisé sur la page.
- Version stable courante d'aiomqtt non confirmée (page GitHub montre seulement l'alpha 3.0.0).
- Python minimum de `ha-mcp` non indiqué.

---

## Synthèse des recommandations (novembre 2026)

- **Mémoire** : SQLite (faits structurés avec `valid_from`/`expires_at`/`superseded_by`, historique des tours) + mem0 OSS configuré en local (LLM Ollama, embedder Ollama `bge-m3`, vector store Chroma) pour la condensation et la réconciliation ; buffer court terme en mémoire process, Redis abandonné sauf multi-process. Variante minimaliste sans mem0 : SQLite + sqlite-vec. Éviter Letta (SDK Python déprécié, Docker non maintenu) et Zep (surdimensionné).
- **Shell desktop** : Tauri 2 (≥ 2.12.1) avec `tauri-nspanel`, `positioner`, `global-shortcut`, backend Python en sidecar PyInstaller exposant FastAPI + WebSocket local ; Electron seulement si le rendu Chromium garanti prime sur la RAM.
- **Avatar** : Rive (`@rive-app/canvas-lite` ou `webgl2`), State Machine avec input numérique `eyeState` piloté par WebSocket ; SVG+CSS si l'on veut zéro WASM.
- **Monitoring** : psutil + SMC via ctypes (`apple-smi`/approche `agtop`) ; powermetrics seulement avec helper sudo ; pyobjc pour la fenêtre active ; notifications via Tauri plutôt que Python non signé.
- **Home Assistant** : serveur MCP officiel pour l'agent + `hass-client` WebSocket pour le temps réel ; `aiomqtt` seulement si broker MQTT présent.

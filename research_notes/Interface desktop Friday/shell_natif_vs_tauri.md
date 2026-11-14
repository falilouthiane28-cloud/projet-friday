# Shell desktop de Friday : SwiftUI/AppKit natif vs Tauri 2 (vs Electron), novembre 2026

Cible : macOS 26 Tahoe, Apple Silicon. Pipeline vocal en Swift natif (JSON Lines stdin/stdout vers un cœur Python). Design noir et blanc, Liquid Glass seulement sur la barre du haut, la barre de saisie et l'overlay. Seuls les Command Line Tools (CLT) sont installés.

**Recommandation : (a) SwiftUI + AppKit natif, compilé avec SwiftPM.** Un test local avec les CLT seuls (voir la question 3) a compilé et exécuté le vrai Liquid Glass (`glassEffect`, `GlassEffectContainer`, `NSGlassEffectView`) dans un `NSPanel` non activant, sans Xcode. Tauri ne peut qu'approcher le verre en CSS, ou l'obtenir via un plugin tiers qui passe par une API privée. Electron n'apporte rien de plus pour ce projet.

**Banc d'essai local (14 nov. 2026, sur cette machine)** : `xcode-select -p` donne `/Library/Developer/CommandLineTools`. Swift 6.3.3, cible `arm64-apple-macosx26.0`, SDK `MacOSX26.5.sdk`.

## 1. Liquid Glass réel sous macOS 26 : API, variantes, accessibilité ; une WebView peut-elle le reproduire ?

### Takeaway
Le Liquid Glass est une API publique : `Glass`, `glassEffect`, `GlassEffectContainer` côté SwiftUI, `NSGlassEffectView` et `NSGlassEffectContainerView` côté AppKit, toutes disponibles dès macOS 26.0. Le système l'adapte lui-même (lisibilité, clair/sombre, réglages d'accessibilité). Une WebView ne peut que l'approcher avec `backdrop-filter: blur() saturate()`. La réfraction par filtre SVG ne marche pas dans WebKit, le moteur de WKWebView et donc de Tauri.

### Cited Findings
- `struct Glass` est disponible sous macOS 26.0+. Variantes : `.regular` (le matériau standard), `.clear`, `.identity` (le contenu reste « comme si aucun effet n'était appliqué »). Méthodes : `.interactive(Bool)` et `.tint(Color?)`. — [Apple, Glass](https://developer.apple.com/documentation/swiftui/glass.md)
- `GlassEffectContainer` (macOS 26.0+) regroupe les formes en verre. Il fait « morpher » les vues l'une dans l'autre selon leur géométrie. — [Apple, GlassEffectContainer](https://developer.apple.com/documentation/swiftui/glasseffectcontainer.md) ; [Apple, Glass](https://developer.apple.com/documentation/swiftui/glass.md)
- `NSGlassEffectView` (AppKit, macOS 26.0+) est une vue qui « embeds its content view in a dynamic glass effect ». Propriétés : `contentView`, `cornerRadius`, `effectIsInteractive`, `style` (`NSGlassEffectView.Style`), `tintColor`. — [Apple, NSGlassEffectView](https://developer.apple.com/documentation/appkit/nsglasseffectview.md)
- `NSGlassEffectContainerView` est disponible sous macOS 26.0. — [Apple, NSGlassEffectContainerView](https://developer.apple.com/documentation/appkit/nsglasseffectcontainerview.md)
- WWDC25 « Meet Liquid Glass » (session 219) :
  - `.regular` est la variante polyvalente, avec tous les comportements adaptatifs.
  - `.clear` n'a aucun comportement adaptatif et reste toujours plus transparent. Elle ne convient qu'au-dessus d'un contenu riche en médias, vif et contrasté, qui supporte une couche d'assombrissement.
  - Il ne faut pas mélanger les deux variantes. Le verre est réservé à la couche de navigation qui flotte au-dessus du contenu, et ne s'empile pas sur du verre.
  - Source : [WWDC Notes, wwdc25-219](https://wwdcnotes.com/documentation/wwdc25-219-meet-liquid-glass/) ; [vidéo Apple](https://developer.apple.com/videos/play/wwdc2025/219)
- Dans la même session, les éléments en verre peuvent ajouter des ombres, s'éclaircir, ou changer de teinte et de plage dynamique pour rester lisibles. Ils basculent aussi en clair ou sombre à la volée (source secondaire). — [MobileSyrup](https://mobilesyrup.com/2025/06/10/how-apple-is-making-sure-liquid-glass-as-legible-as-possible/)
- Accessibilité :
  - Reduce Transparency rend le verre plus opaque, avec un aspect « givré ».
  - Increase Contrast ajoute des bordures et des couleurs plus franches. Il active aussi automatiquement Reduce Transparency.
  - Un guide tiers affirme que l'adaptation est automatique, sans code.
  - Sources : [TidBITS, oct. 2025](https://tidbits.com/2025/10/09/how-to-turn-liquid-glass-into-a-solid-interface/) ; [guide Medium](https://medium.com/@madebyluddy/overview-37b3685227aa) ; [Create with Swift](https://www.createwithswift.com/exploring-a-new-visual-language-liquid-glass/)
- Contre-point : sur les forums Apple, des développeurs jugent que ces réglages n'atténuent que partiellement le problème. Ils ne rendent pas une interface aussi solide qu'iOS 18. — [Apple Dev Forums 811219](https://developer.apple.com/forums/thread/811219)
- Les versions 26.x ont ajouté un réglage utilisateur du rendu du verre : option teintée, plus contrastée, puis un contrôle de transparence (source secondaire). — [recherche WWDC/TidBITS, ci-dessus](https://tidbits.com/2025/10/09/how-to-turn-liquid-glass-into-a-solid-interface/)
- Web, WebKit :
  - `backdrop-filter: url(#svgFilter)` avec `feDisplacementMap` ne produit rien dans Safari/WebKit. Pire, `@supports` répond vrai, ce qui fausse la détection.
  - Bug WebKit ouvert : [WebKit 245510](https://www2.webkit.org/show_bug.cgi?id=245510). Constat : [DEV, 6 façons](https://dev.to/devyatov/liquid-glass-on-the-web-6-ways-to-build-it-with-css-and-svg-3m07) ; [Mozilla Connect](https://connect.mozilla.org/t5/ideas/support-svg-filters-in-backdrop-filter-for-advanced-glass/m-p/98453)
  - Safari met en cache la sortie des filtres SVG par ID et plafonne la taille d'entrée. Aave a dû passer par WebGL pour réfracter de la vidéo. — [Aave, Building Glass for the Web](https://aave.com/design/building-glass-for-the-web)
  - Le repli habituel sur Safari et Firefox est un simple blur + saturate. — [Liqvued FAQ](https://ivoyt.github.io/liqvued/guide/faq)
- Tauri, verre « natif » : `tauri-plugin-liquid-glass` v0.1.6 (18 déc. 2025) pose un `NSGlassEffectView` derrière une WebView transparente. Il exige `macOSPrivateApi: true` et propose 24 variantes « expérimentales ». Son auteur le décrit comme une API privée, risquée pour l'App Store, et conseille le repli `NSVisualEffectView` en production. — [docs.rs](https://docs.rs/crate/tauri-plugin-liquid-glass/latest)
- **Vérifié localement** : ce code compile et s'exécute avec les CLT seuls, SDK 26.5.
  - `GlassEffectContainer { … .glassEffect(.clear, in: .capsule) … }.glassEffect(.regular.interactive())`
  - `NSGlassEffectView()` avec `cornerRadius` et `contentView = NSHostingView(...)`
  - Cela confirme que `NSGlassEffectView` est bien public dans le SDK. L'aspect « privé » du plugin Tauri tient sans doute à ses variantes internes ou à l'option `macOSPrivateApi` de Tauri. C'est une déduction, à vérifier.

### Inferences
- Pour le style noir et blanc demandé : `.regular` sur la barre du haut et la barre de saisie (fond noir, donc `.clear` est déconseillé faute de contenu vif dessous). Pour l'overlay, `.regular` ou `.regular.tint(.black.opacity(…))`. Les yeux LED blancs restent hors du verre, conformément à la règle « pas de verre sur du verre ».
- Une WebView peut imiter le flou et le dégradé, mais pas la réfraction, le morphing, les reflets dynamiques ni l'adaptation automatique d'accessibilité. Il faudrait refaire à la main `prefers-reduced-transparency` / `prefers-contrast` en CSS.
- Avec le plugin Tauri, la WebView n'est qu'un calque transparent au-dessus d'un seul panneau de verre natif. On perd le verre par élément (barre du haut et barre de saisie séparées) et le morphing.

### Gaps
- Pas de citation Apple de première main (la page « Adopting Liquid Glass » n'a pas pu être lue) confirmant mot pour mot que Reduce Transparency et Increase Contrast sont gérés automatiquement par `glassEffect`. Seules des sources secondaires le disent.
- Liste exacte des cas de `NSGlassEffectView.Style` non lue (probablement `.regular` / `.clear`, à vérifier dans le SDK).
- Aucune étude publiée ne compare visuellement le verre natif et l'approximation CSS dans WKWebView sous macOS 26.

## 2. Overlay flottant : NSPanel, niveaux, Spaces, plein écran, raccourci global ; équivalent Tauri (tauri-nspanel en 2026)

### Takeaway
La recette éprouvée : sous-classe `NSPanel` avec `[.nonactivatingPanel, .borderless]`, niveau `.floating` (ou `.statusBar` s'il faut passer au-dessus de tout), `collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, (.stationary)]`, `NSHostingView` pour le SwiftUI, et `canBecomeKey` surchargé pour la saisie. Le raccourci global passe par le package KeyboardShortcuts (Carbon `RegisterEventHotKey`, sans permission). Côté Tauri, tauri-nspanel v2.1 est maintenu et couvre l'essentiel, mais c'est un pont vers les mêmes appels AppKit.

### Cited Findings
- SwiftUI n'a pas de panneau flottant natif. On sous-classe donc `NSPanel`, on héberge le SwiftUI via `NSHostingView`, et on règle le style, le niveau et l'activation. — [Fazm, floating panel](https://fazm.ai/blog/swiftui-floating-panel) ; [Cindori](https://cindori.com/developer/floating-panel)
- `.nonactivatingPanel` évite d'activer l'application quand le panneau passe devant. Sans lui, une app en plein écran peut quitter son Space. — [Fazm](https://fazm.ai/blog/swiftui-menu-bar-app-floating-window-best-practices)
- Combinaison courante : `.canJoinAllSpaces` + `.fullScreenAuxiliary`. Ajouter `.stationary` corrige le panneau qui glisse en changeant de Space plein écran. — [SO via kiwix](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/68871067/make-nswindow-remain-float-when-space-changes-in-swift) ; [SO 36205834](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/36205834/allow-an-nswindow-nspanel-to-float-above-full-screen-apps)
- Niveaux : les tutoriels utilisent `.floating`. Pour rester au-dessus de tout, on monte à `.mainMenu`, `.statusBar` ou `.screenSaver`. — [Apple Dev Forums 826308](https://developer.apple.com/forums/thread/826308)
- Réglages façon Spotlight : `becomesKeyOnlyIfNeeded = true`, `hidesOnDeactivate = false`, `isMovableByWindowBackground = true`. Surcharger `canBecomeKey` est indispensable pour taper dans un panneau borderless non activant. — [Fazm](https://fazm.ai/blog/swiftui-floating-panel) ; [Cindori](https://cindori.com/developer/floating-panel)
- Question ouverte sur macOS 26 : deux NSPanel en Liquid Glass peuvent-ils afficher tous deux l'apparence « active » ? — [Apple Dev Forums 818901](https://developer.apple.com/forums/thread/818901)
- **Vérifié localement** : ce code compile sous SDK 26.5 avec les CLT.
  - `NSPanel(styleMask: [.nonactivatingPanel, .borderless])`
  - `level = .floating`
  - `collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]`
- Raccourci global :
  - KeyboardShortcuts (sindresorhus) repose sur Carbon `RegisterEventHotKey`. Il est compatible sandbox et Mac App Store, et ne demande aucune permission. — [KeyboardShortcuts](https://swiftpackageregistry.com/sindresorhus/KeyboardShortcuts) ; [guide](https://skillsmp.com/creators/aka-kika/akakika-skills/skills-swift-macos-macos-global-shortcuts)
  - Depuis Sequoia (et donc sous Tahoe), un raccourci composé seulement d'Option et/ou de Shift échoue (erreur -9868). Il faut au moins Cmd ou Ctrl. — [Apple Dev Forums 763878](https://developer.apple.com/forums//thread/763878) ; [issue KeyboardShortcuts 176](https://github.djj45.workers.dev/sindresorhus/KeyboardShortcuts/issues/176)
- tauri-nspanel :
  - Branche maintenue `v2.1`, crate `tauri-nspanel = "2.1"`. API `PanelBuilder` ou conversion d'une fenêtre existante, macro `tauri_panel!` (`can_become_key_window`, `is_floating_panel`), `PanelLevel::Floating`, suivi de la souris, gestion explicite du thread principal. Environ 183 commits, 1 issue ouverte, Renovate. — [GitHub ahkohd/tauri-nspanel](https://github.com/ahkohd/tauri-nspanel)
  - La doc de l'API liste les sujets « nonactivating style mask » et « collection behavior (can_join_all_spaces, full_screen_auxiliary) », mais je n'ai pas pu en lire le détail. — [docs.aremu.dev/tauri-nspanel](https://docs.aremu.dev/tauri-nspanel/)
  - Exemple d'app barre de menus Tauri v2 + nspanel (sept. 2025) : [blog ximei](https://blog-ximei-me.pages.dev/blog/en/2025/0917-tauri-menubar-app) ; [DEV guide](https://dev.to/hiyoyok/complete-guide-to-building-a-macos-menu-bar-app-with-tauri-v2-aji)

### Inferences
- Le natif expose toutes les options directement (niveaux, `collectionBehavior`, focus clavier). Tauri y accède via un plugin tiers d'un seul mainteneur, ce qui ajoute une couche Rust↔ObjC à déboguer.
- Choisir un raccourci avec Cmd ou Ctrl (par ex. ⌃⌥Espace ou ⌘⇧Espace), jamais ⌥ seul.
- Barre de menus : `MenuBarExtra` (SwiftUI) suffit pour l'icône et le menu. L'overlay reste un `NSPanel` séparé, piloté par l'`AppDelegate`.

### Gaps
- Je n'ai trouvé aucun rapport public validant explicitement tauri-nspanel sous macOS 26.
- La date de la dernière release crates.io de tauri-nspanel n'est pas visible.

## 3. SwiftPM sans Xcode (CLT seuls) : bundle .app, Info.plist, signature ad hoc, notarisation, limites

### Takeaway
Oui. SwiftPM compile une app SwiftUI/AppKit avec les CLT seuls ; c'est vérifié sur cette machine. Le `.app` s'assemble avec un script (binaire dans `Contents/MacOS`, `Info.plist`, `codesign --sign -`). La notarisation est inutile en local. Limites réelles : pas de `#Preview` ni de canevas de préviews, pas d'`actool` (catalogues d'assets `.xcassets`, icônes Icon Composer), et Swift Testing ne marche qu'avec des drapeaux supplémentaires.

### Cited Findings
- Flux communautaire : `swift build -c release`, création de `Contents/MacOS` et `Contents/Resources`, copie du binaire, génération de l'`Info.plist`. — [skills.sh, macos-spm-app-packaging](https://skills.sh/patrickserrano/skills/macos-spm-app-packaging) ; [Tessl, guide SPM packaging](https://tessl.io/registry/skills/github/Prisma-Labs-Dev/apple-skills/guide-macos-spm-packaging)
- macOS a besoin d'un `Info.plist` dans le bundle pour reconnaître l'app. On peut compiler et lancer en local sans compte développeur payant, mais pas notariser ni distribuer. — [agentpedia Q&A](https://agentpedia.codes/agent-skills/mobile/macos-spm-app-packaging)
- Générer l'icône `.icns` à partir d'un fichier Icon Composer demande Xcode (`build_icon.sh`). — [Tessl](https://tessl.io/registry/skills/github/Prisma-Labs-Dev/apple-skills/guide-macos-spm-packaging)
- **Tests locaux (CLT, Swift 6.3.3, SDK 26.5) :**
  - `swift build` d'un exécutable SwiftUI + AppKit utilisant `glassEffect`, `GlassEffectContainer`, `phaseAnimator`, `NSPanel` et `NSGlassEffectView` : **OK**. Environ 35 s à froid en debug, 33 s en release. Binaire release de 86 Ko.
  - `xcrun actool` : **absent** (« unable to find utility actool »). Pas de compilation de `.xcassets`.
  - `#Preview` : **erreur** (« plugin for module 'PreviewsMacros' not found »).
  - `swift test` avec `import Testing` : **échoue par défaut** (« no such module 'Testing' »), alors que `Testing.framework` est présent dans `/Library/Developer/CommandLineTools/Library/Developer/Frameworks`. **Contournement validé** :
    `swift test -Xswiftc -F -Xswiftc $F -Xlinker -rpath -Xlinker $F -Xlinker -rpath -Xlinker /Library/Developer/CommandLineTools/Library/Developer/usr/lib`
    avec `F=/Library/Developer/CommandLineTools/Library/Developer/Frameworks`. Résultat : « Test run with 1 test … passed ».
  - `codesign` est présent (`/usr/bin/codesign`). La signature ad hoc `codesign --force --sign - Friday.app` est possible.

### Inferences
- Il faut un bundle signé (même ad hoc) pour les permissions TCC : micro (`NSMicrophoneUsageDescription`), reconnaissance vocale (`NSSpeechRecognitionUsageDescription`). Mettre `LSUIElement = true` pour une app de barre de menus sans icône dans le Dock. Une signature ad hoc change à chaque build et peut faire redemander les permissions TCC. Un certificat auto-signé stable, créé dans Trousseau d'accès, évite ça. C'est une déduction, non vérifiée ici.
- Icône : fournir directement un `.icns` (via `iconutil`, présent dans macOS) au lieu d'un `.xcassets`. Couleurs et images : les mettre en ressources SwiftPM (`Bundle.module`) plutôt qu'en catalogue.
- Préviews : remplacer par du hot-reload manuel (relancer le script) ou par une petite fenêtre « galerie de composants » en mode debug.

### Gaps
- Je n'ai pas consulté de fil Swift Forums officiel sur Swift Testing et les CLT. Le contournement vient de mon test local, pas d'une documentation.

## 4. Intégration avec le binaire vocal Swift et le cœur Python ; empreinte mémoire et CPU

### Takeaway
En natif, l'UI peut absorber le binaire vocal dans le même processus Swift : AVAudioEngine, SpeechAnalyzer et AVSpeechSynthesizer deviennent des modules, ce qui supprime un saut d'IPC. Le Python reste un sous-processus en JSON Lines via `Process` et `Pipe`. Avec Tauri ou Electron, on garde trois runtimes (Rust/Node + WebView, binaire Swift, Python) et un pont IPC de plus. La mémoire au repos est nettement plus basse en natif. Pour Tauri et Electron, les chiffres publiés varient beaucoup.

### Cited Findings
- Better Stack (table référencée macOS) : Tauri ≈ 109 Mo au repos (processus principal + processus WebView), Electron ≈ 128 Mo. — [Better Stack](https://betterstack.com/community/guides/scaling-nodejs/tauri-vs-electron-vs-deno-vs-electrobun/)
- Autres blogs : Tauri 42 Mo contre Electron 168 Mo ; ailleurs, Electron 200–400 Mo contre Tauri 30–80 Mo. Méthodologie non précisée. — [recherche agrégée, tech-insider](https://tech-insider.org/tauri-vs-electron-2026/) ; [DEV gethopp](https://dev.to/gethopp/tauri-vs-electron-performance-bundle-size-and-the-real-trade-offs-1el4)
- Banc d'essai à 6 fenêtres sous macOS : Tauri ≈ 172 Mo, Electron ≈ 409 Mo. Les renderers Chromium consomment environ 2× les processus WKWebView. — [DEV gethopp](https://dev.to/gethopp/tauri-vs-electron-performance-bundle-size-and-the-real-trade-offs-1el4)
- Contre-exemple : pour vscode.dev, Tauri (WebKit) monte à 429 Mo contre 332 Mo pour Electron. — [tauri issue 5889](https://github.com/tauri-apps/tauri/issues/5889)
- Binaire natif de test (SwiftUI + AppKit + verre) : 86 Ko en release (mesure locale). SwiftUI et AppKit sont des frameworks système partagés, absents du binaire.

### Inferences
- Architecture native conseillée : un seul exécutable `Friday.app` en Swift, organisé ainsi.
  - Modules SwiftPM : `FridayUI` (SwiftUI/AppKit), `FridayVoice` (le code vocal actuel), `FridayBridge` (gestion du sous-processus Python via `Process`, `Pipe` et `AsyncStream` sur les lignes JSON).
  - Le binaire vocal actuel peut aussi rester un exécutable séparé au début : l'UI le lance comme le Python. On migre ensuite vers le même processus.
- Ordre de grandeur attendu en natif : quelques dizaines de Mo pour l'UI. Je n'ai trouvé aucune source chiffrée pour une app SwiftUI de barre de menus (voir Gaps). Ce sera bien moins que les ~100 Mo et plus de Tauri, qui en plus ajoute un processus WebKit (WebContent) et un runtime Rust.
- Le CPU au repos dépend surtout de l'avatar animé (question 5) et de la boucle audio, pas du shell.

### Gaps
- Je n'ai trouvé aucun banc d'essai publié qui compare une app native SwiftUI à Tauri et Electron sous macOS 26. À mesurer avec `footprint` / Activity Monitor, en additionnant les processus auxiliaires.

## 5. Avatar SVG animé : Canvas / Shapes / PhaseAnimator / KeyframeAnimator vs SVG dans WebKit ; coût à 60 fps

### Takeaway
En SwiftUI, deux voies : des formes (`Shape`, `Path`) animées par `PhaseAnimator` / `KeyframeAnimator` pour des états discrets (repos, écoute, réflexion, parole), et `Canvas` + `TimelineView(.animation)` pour du dessin procédural image par image (yeux LED qui réagissent au niveau audio). C'est rendu par Core Animation et Metal, sans DOM. Le SVG animé dans WKWebView marche, mais ajoute le processus WebContent et la mise en page DOM. Aucun banc d'essai ne compare directement les deux : il faudra profiler.

### Cited Findings
- `Canvas` est l'option performante pour les dessins complexes (dégradés, nombreuses parties), en échange de la perte des vues et gestes individuels. `TimelineView(.animation)` redessine à environ 60 fps. — [Kodeco, TimelineView & Canvas](https://www.kodeco.com/27594491-using-timelineview-and-canvas-in-swiftui)
- `.drawingGroup()` aplatit les vues en un seul calque, rendu par Metal, pour gagner en performance (résumé WWDC21). — [mackuba, WWDC21 rich graphics](https://mackuba.eu/notes/wwdc21/add-rich-graphics-to-swiftui-app)
- Anecdote : un Canvas plein écran animé en continu a donné une énergie « Very High » et un échauffement « Serious » sur iPhone. La même animation en SwiftUI simple consommait moins. — [Apple Dev Forums 756273](https://developer.apple.com/forums/thread/756273)
- Sur un forum Apple, un développeur fait tourner un calque Canvas à 60 fps et abaisse un calque voisin à 12 fps pour économiser. — [Apple Dev Forums 850664](https://developer.apple.com/forums/thread/850664)
- Depuis iOS 17 / macOS 14, les shaders Metal s'appliquent aux vues SwiftUI (`.colorEffect`, `.layerEffect`) et peuvent être animés via `TimelineView`. Utile pour une lueur ou un halo LED. — [recherche, Hacking with Swift](https://hackingwithswift.com/plus/advanced-swiftui)
- **Vérifié localement** : `phaseAnimator` compile sous SDK 26.5 avec les CLT.

### Inferences
- Pour des yeux LED blancs sur fond noir (formes simples), privilégier :
  - `Shape` / `Capsule` + `PhaseAnimator` pour les états, `KeyframeAnimator` pour le clignement.
  - `Canvas` à cadence adaptative seulement pendant la parole (`TimelineView(.animation(minimumInterval: 1/30))` au repos, 60 fps pendant la parole). On n'anime pas en continu quand Friday est inactive : important pour une app toujours allumée.
- Respecter `accessibilityReduceMotion` (variable d'environnement SwiftUI) pour couper les animations décoratives.
- Les SVG existants peuvent être convertis en `Path` (outils SVG→SwiftUI) ou rendus statiquement. Le SVG animé (SMIL/CSS) n'a pas d'équivalent direct en natif.
- Côté WebView : un `<svg>` animé en CSS transforms/opacity est composité par le GPU dans WebKit et reste léger. Les animations d'attributs SVG (path `d`, filtres) forcent repaint et layout dans le processus WebContent. Déduction générale, non mesurée ici.

### Gaps
- Je n'ai trouvé aucune mesure publiée du CPU/GPU d'un même avatar en SwiftUI Canvas contre SVG dans WKWebView. À profiler avec Instruments (Core Animation, Metal System Trace).
- Electron : je n'ai pas recherché en détail son support Liquid Glass. Il existe des modules tiers fondés sur des API privées, non vérifiés ici. Au vu du point 4 (mémoire Chromium plus élevée) et de l'absence d'avantage sur le verre, Electron est écarté sans recherche approfondie.

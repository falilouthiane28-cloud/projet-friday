# Avatar Friday : 18 expressions animées (visière sombre, yeux LED blancs) — état de l'art nov. 2026

## Q1 — Meilleure technique pour morpher entre des formes d'yeux très différentes (rect → arc → cœur → étoile → X → spirale)

### Takeaway
Aucune technique ne morphe proprement *toutes* ces formes. Un modèle **paramétrique** (yeux en rectangle arrondi + paupières + rotation, à la Cozmo/RoboEyes) couvre bien neutral/happy/sad/angry/confused/shy/surprised/sleeping/wink/thinking/listening avec de vraies interpolations. Les formes symboliques (cœur, étoile, X, spirale, triangle, barre de chargement, lunettes) se gèrent mieux par **crossfade + scale/squash** (≈300 ms), ou par morph flubber/MorphSVG si l'on accepte un rendu « best-guess ». Rive est l'outil le plus complet (State Machine + Data Binding, runtimes MIT), mais impose un éditeur payant pour retirer le splash.

### Cited Findings
- **flubber** interpole des formes arbitraires sans le même nombre de points (il rééchantillonne les deux chemins vers un nombre commun) ; c'est explicitement un « best-guess », pas un mapping garanti — [GitHub veltman/flubber](https://github.com/veltman/flubber) ; [react-graph-gallery](https://react-graph-gallery.com/shape-morphism-for-dataviz-with-react)
- Les libs d'animation génériques (ex. react-spring) ne peuvent pas interpoler deux paths trop différents (nombre de points différent) sans interpolateur dédié — [react-graph-gallery](https://react-graph-gallery.com/course/animation/dealing-with-path)
- Option `maxSegmentLength` pour régler la finesse du rééchantillonnage flubber — [react-graph-gallery](https://react-graph-gallery.com/shape-morphism-for-dataviz-with-react)
- **GSAP + tous les plugins (dont MorphSVG) sont gratuits** y compris en commercial depuis le rachat par Webflow (licence « Standard No Charge » datée du 30/04/2025) ; restriction pour les « Competitive Products » (outils type Webflow) — [CodePen blog](https://blog.codepen.io/2025/05/05/chris-corner-gsap-more-like-freesap/) ; [Webflow forum](https://discourse.webflow.com/t/webflow-makes-gsap-100-free/319967) ; [gsap.com standard license](https://gsap.com/community/standard-license/)
- **Rive — prix officiels** : Free 0 $ (3 fichiers collaboratifs, exports runtime avec splash Rive), Cadet 17 $/siège/mois ou 108 $/an (sans splash, 3 sièges max), Voyager 49 $/siège/mois ou 384 $/an (Libraries, 25 sièges), Enterprise 1 440 $/siège/an (CA > 10 M$) — [Rive docs pricing](https://rive.app/docs/account-admin/pricing.md)
- Agrégateurs tiers donnent des prix contradictoires (Cadet 9 $, Pro 24 $, Voyager 32 $ ou 99 $) — probablement d'anciennes grilles ; se fier à la page Rive — [comparetiers](https://comparetiers.com/tools/rive) ; [toolradar](https://toolradar.com/tools/rive/pricing)
- **Runtimes Rive sous licence MIT**, sans royalties ni frais runtime ; un blog Rive indique que les exports continuent de fonctionner après fin d'abonnement — [rive.app/runtimes](https://rive.app/runtimes) ; [NOTICE OpenHarmony rive](https://gitcode.com/openharmony-tpc/openharmony_tpc_samples/blob/master/ohos_rive/NOTICE) ; [Rive blog plan](https://framer.rive.app/blog/rive-s-new-9-mo-plan)
- Runtime Apple : **Data Binding** (strings, nombres, booléens…) pour piloter le graphique depuis le code ; les view model instances doivent être créées/retenues par le dev (getter `viewModelInstance` déprécié, renvoie nil) — [Rive docs Apple](https://rive.app/docs/runtimes/apple)
- Runtime Web : la v3 du runtime JS jouera la state machine par défaut de l'artboard ; le support de plusieurs state machines simultanées disparaît → utiliser data binding / state machine actions — [Rive web parameters](https://rive.app/docs/runtimes/web/rive-parameters)
- Un build SPI de RiveRuntime (main) a échoué pour Wasm/Swift 6.3 le 24/08/2026 (log isolé) — [Swift Package Index](https://swiftpackageindex.com/builds/EB6D00F2-23BB-463A-8F4E-FF7C695C883A)
- **dotLottie** inclut désormais des state machines (clics, hover, triggers), définies dans Lottie Creator ou dans le manifest ; runtime basé sur ThorVG — [LottieFiles dotLottie](https://lottiefiles.com/dotlottie) ; [LottieFiles vs Rive](https://lottiefiles.com/blog/lottie-animations/lottiefiles-or-rive)
- Taille : un exemple Callstack ~24,37 Ko (Lottie) vs ~2 Ko (Rive) pour la même animation ; runtime Rive ~146 Ko minifié vs Lottie light ~18 Ko (source tierce, approximatif) ; sources majoritairement partisanes — [Callstack](https://callstack.com/blog/lottie-vs-rive-optimizing-mobile-app-animation) ; [learnwithhasan](https://learnwithhasan.com/js-libraries/rive/)
- La plupart des workflows Lottie restent des exports After Effects « cuits », pas des rigs procéduraux (source Rive, partisane) — [Rive blog](https://rive.app/blog/why-importing-lotties-isnt-the-workflow-rive-was-built-for)
- SwiftUI **KeyframeAnimator** : le closure de contenu est réévalué à chaque frame pendant l'animation → éviter tout calcul coûteux dedans ; perfs jugées suffisantes pour animer des entrées d'un `Canvas` — [Apple KeyframeAnimator](https://developer.apple.com/documentation/swiftui/keyframeanimator.md) ; [SwiftUI Garden](https://swiftui-garden.pages.dev/Animations/Animation-playground) ; [WWDC23 10157 notes](https://wwdcnotes.com/notes/wwdc23/10157)

### Inferences
- **Architecture recommandée (hybride)** :
  1. *Couche paramétrique* : chaque œil = `EyeParams { width, height, cornerRadius, offsetX/Y, rotation, upperLidAngle, upperLidHeight, lowerLidHeight (pour arcs « happy »), scale }`. Toutes ces valeurs sont des scalaires → interpolables par un spring (SwiftUI : `Shape` conforme à `Animatable` avec `animatableData` en `AnimatablePair`/vecteur custom ; Web : interpolation JS ou CSS custom properties). Couvre : neutral, happy (paupière inférieure qui monte → arc), sad (paupière haute inclinée vers l'extérieur), angry (paupière inclinée vers l'intérieur), confused (tailles asymétriques), shy (petit + offsetY bas), surprised (grand + cornerRadius max = cercle), sleeping (height → 2 px), wink, thinking (offset + scan), listening (scale).
  2. *Couche glyphes* : cœur, étoile, X, spirale, triangle « ! », barre de progression, lunettes = SVG/Path dédiés. Transition = l'œil paramétrique se « squash » (scaleY→0.1, 120 ms) puis le glyphe pop (scale 0.6→1 avec spring, opacité 0→1, ~180 ms). Visuellement plus net qu'un morph flubber cœur→X qui produit des formes intermédiaires informes.
  3. Morph flubber/MorphSVG réservé aux paires proches (cercle↔cœur, cercle↔étoile) si on veut un effet « wow ».
- **Rive** est le meilleur choix si un designer anime (blend states, listeners, data binding `state`, `audioLevel`), et fonctionne en SwiftUI natif comme en web view avec le même `.riv`. Coût : 17 $/mois (Cadet) pour exporter sans splash ; runtime MIT gratuit. Risque : dépendance à un éditeur propriétaire + évolutions d'API runtime (v3 web, data binding iOS).
- **Lottie/dotLottie** : moins adapté (pas de paramètre continu natif comme audioLevel aussi simple que Rive data binding ; animations pré-cuites).
- **SwiftUI pur** (Canvas + TimelineView pour l'idle, `.animation(.spring(duration: 0.3))` pour les changements d'état, KeyframeAnimator pour blink/wink/dizzy one-shots) : zéro dépendance, 100 % monochrome contrôlé, parfait pour un dev solo. Recommandé si l'UI est native macOS 26.
- Spring 300 ms : SwiftUI `.spring(duration: 0.3, bounce: 0.2)` ; web : GSAP `ease: "back.out(1.4)"`/`elastic` ou un spring JS ; éviter un bounce > 0.3 qui rend angry/sad comiques.

### Gaps
- Pas de benchmark indépendant Rive vs dotLottie vs SwiftUI Canvas sur macOS.
- Documentation Apple sur `Shape.animatableData` non consultée directement dans cette session (connaissance générale de l'API `Animatable`).
- Conditions exactes de licence runtime Rive (texte du LICENSE de rive-ios) non lues en primaire.

## Q2 — Comment font les produits/projets connus, et qu'est-ce qui rend les yeux « vivants » ?

### Takeaway
Cozmo/Vector (Anki) utilisent un visage **100 % procédural** : 43 paramètres (5 visage + 19 par œil : coins, paupières haute/basse, échelle, angle) interpolés entre keyframes, inspiré du livre *Stop Staring* (Jason Osipa). RoboEyes (Arduino, GPL-3.0) reproduit ce principe en simple : rectangles arrondis + humeurs + autoblink/idle aléatoires. La « vie » vient de l'aléa : clignements à intervalle variable, micro-déplacements (saccades), squash & stretch.

### Cited Findings
- Cozmo : visage procédural de **43 paramètres** (5 visage + 19 par œil) ; translate/scale/rotate globaux ; 4 coins contrôlables + paupières haute et basse par œil — [PyCozmo off-board functions](https://pycozmo.readthedocs.io/en/latest/external/offboard_functions.html)
- Paramètres interpolés entre keyframes : le système déplace sa copie de travail de chaque paramètre vers la valeur de la frame suivante sur la durée de la frame — [Vector docs Eye animation](https://randym32.github.io/Anki.Vector.Documentation/tools/Eye%20animation.html)
- Contrôles d'animateur Vector : sourcils, regard (x/y), joues, ouverture (squint, sleepiness), inclinaison, squash & stretch ; outil à sliders worry↔curiosity, mad↔happy, blink rate, gaze — [Vector docs Eye animation](https://randym32.github.io/Anki.Vector.Documentation/tools/Eye%20animation.html)
- L'animateur principal Mooly Segal cite *Stop Staring* (Jason Osipa) comme influence — [Vector character design guide](https://randym32.github.io/Anki.Vector.Documentation/guides/Vector%20character%20design%20guide.html) ; [Design News](https://www.designnews.com/testing-measurement/from-cozmo-to-vector-how-anki-designs-robots-with-emotional-intelligence)
- PyCozmo : 25 classes d'expressions (Amazement, Anger, Asleep, Boredom, Confusion, Happiness, Sadness, Surprise, Suspicion, Tiredness…) sur les mêmes attributs (`center_x/y`, `eye_width/height`, `scale_x/y`, `angle`, `scale_factor_lid_bend`, `scale_factor_lid_height`), basées sur le projet « Expressive Eyes » de Catherine Chambers — [PyCozmo expressions](https://pycozmo.readthedocs.io/en/latest/generated/pycozmo.expressions.expressions.html)
- **FluxGarage RoboEyes** (v1.1.1, 03/09/2025, **GPL-3.0**) : humeurs DEFAULT/TIRED/ANGRY/HAPPY ; one-shots `anim_confused()` (shake horizontal), `anim_laugh()` (shake vertical), `blink()` ; `setAutoblinker(on, interval, variation)` et `setIdleMode(on, interval, variation)` en secondes avec variation aléatoire ; « curiosity » (œil extérieur grandit en regardant sur le côté), flicker, sweat drops, mode cyclope ; framerate max via `begin(w,h,fps)` ; « toutes les transitions d'état sont lissées » — [GitHub RoboEyes](https://github.com/FluxGarage/RoboEyes) ; [arduinolibraries.info](https://www.arduinolibraries.info/libraries/flux-garage-robo-eyes)
- Port MicroPython de RoboEyes — [mchobby/micropython-roboeyes](https://github-users.yhajoa.workers.dev/mchobby/micropython-roboeyes)
- Clignement humain : ~12/min chez l'adulte (≈ toutes les 5 s) ; ~10/min en labo, tombe à 3–4/min en concentration (lecture) ; durée complète ~100–400 ms (≈1/3 s réouverture comprise) — [Kwon et al. 2013, J. R. Soc. Interface](https://discovery-pp.ucl.ac.uk/1396599/1/J._R._Soc._Interface-2013-Kwon-.pdf) ; [Wikipedia Blink](https://en.wikipedia.org/wiki/Blink)
- Saccades : 2–3 par seconde en exploration libre ; microsaccades ~1–2/s en fixation (≈0,5/s lors des brèves fixations en vision libre) — [PMC3625326](https://pmc.ncbi.nlm.nih.gov/articles/PMC3625326) ; [Rucci & Poletti 2015](https://aplab.bcs.rochester.edu/assets/download/PDFs/articles/RucciPoletti15.pdf)

### Inferences
- **Recettes « vivant » pour Friday** :
  - Blink : intervalle de base 4 s (spec) mais **jitter aléatoire ±1,5 s** (ex. uniforme 2,5–5,5 s) + 10–15 % de double-blink. Fermeture ~80–100 ms (ease-in), maintien 30–50 ms, réouverture ~120–150 ms (ease-out) ; squash horizontal léger (width ×1.05) pendant la fermeture.
  - Thinking : le spec « réduit » le blink (cohérent avec 3–4/min en concentration).
  - Saccades idle : petit déplacement (2–6 % de la largeur visière) toutes les 1–3 s, mouvement rapide (~50–80 ms), puis tenue ; les deux yeux bougent ensemble.
  - Micro-motion : « respiration » scale 1.00↔1.02 sur ~4 s (sinus), amplitude ≤ 1–2 px ; anticipation (petit contre-mouvement ~60 ms) avant une grosse transition ; overshoot via spring.
  - Squash & stretch : à l'arrivée d'excited/surprised, scaleY 1.15 puis retour ; à sleeping, aplatir progressivement.
  - Curiosité RoboEyes : l'œil côté regard grandit légèrement (≈+10 %) — parallaxe bon marché.
- Pas d'information primaire trouvée sur EMO (Living.ai) ; s'en tenir à Cozmo/Vector et RoboEyes comme références.
- RoboEyes est GPL-3.0 : s'en inspirer conceptuellement, ne pas copier le code dans une app non-GPL.

### Gaps
- Pas de valeurs numériques officielles Anki (plages des paramètres, durées).
- Aucune source primaire consultée sur EMO/Living.ai ni sur des fichiers Rive communautaires « robot eyes » spécifiques.

## Q3 — État « listening » audio-réactif : mapping RMS micro → échelle des yeux

### Takeaway
Utiliser un **suiveur d'enveloppe RMS avec attaque rapide et relâche plus lente** (référence meter : attaque ~5–10 ms / relâche ~1 s pour un peak meter, 65/65 ms pour un VU). Pour un visuel réactif mais calme : attaque ~30–60 ms, relâche ~150–300 ms, conversion en dB puis mapping vers scale 1.0–1.25, mise à jour à la fréquence d'affichage (60/120 Hz) en interpolant.

### Cited Findings
- Ballistics standard : peak meter IEC 60268-10 « fast » ≈ 5 ms attaque / 1087 ms relâche ; mode lent ≈ 10 / 1450 ms ; VU (IEC 60268-17) 65 ms attaque et relâche — [DSP Concepts Audio Weaver Meter](https://documentation.dspconcepts.com/awe-designer/8.D.2.7/meter)
- Enveloppe RMS : coefficients d'attaque et relâche séparés appliqués à la puissance (valeur au carré), choix selon que la puissance instantanée dépasse l'enveloppe, puis racine carrée pour l'affichage — [oximedia-metering rms_envelope.rs](https://docs.rs/crate/oximedia-metering/latest/source/src/rms_envelope.rs)
- JUCE `BallisticsFilter` : attaque/relâche en ms, mode RMS pour estimer la valeur moyenne — [JUCE docs](https://docs.juce.com/master/classdsp_1_1BallisticsFilter.html)
- rAF suit la fréquence d'affichage (60, 120, 144 Hz) → calculer la progression sur le timestamp, pas le nombre de frames — [MDN requestAnimationFrame](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame)

### Inferences
- **Pipeline proposé** :
  1. Capture : `AVAudioEngine` tap (buffer 1024 @ 48 kHz ≈ 21 ms) ou Web Audio `AnalyserNode.getFloatTimeDomainData` ; RMS par buffer.
  2. dB = 20·log10(rms + 1e-9) ; normaliser `level = clamp((dB − (−55)) / (−10 − (−55)), 0, 1)` (plancher ≈ −55 dBFS sous le bruit de fond, plafond −10 dBFS ; idéalement plancher adaptatif = bruit mesuré + 6 dB).
  3. Enveloppe one-pole : `coef = exp(−Δt / τ)`, τ_attack ≈ 40 ms, τ_release ≈ 200 ms ; `env = level > env ? a·env + (1−a)·level : r·env + (1−r)·level`.
  4. Mapping : `scale = 1.0 + 0.25·pow(env, 0.6)` (courbe gamma pour que la voix faible se voie) ; option : léger « dilatation » de base 1.1 dès l'entrée en listening.
  5. Rendu : lire `env` à chaque frame (TimelineView `.animation` / CADisplayLink / rAF) ; ne PAS passer chaque buffer dans un spring SwiftUI (re-render coûteux) ; dans Rive, pousser `audioLevel` (number) via data binding ~30–60 Hz.
- Transmettre le niveau audio du thread audio au thread UI via valeur atomique/lock-free, pas via `@Published` à chaque buffer.
- Plafonner l'amplitude pour éviter que des pics répétés créent un « flash » (cf. Q4) — la variation d'échelle n'est pas un flash de luminance, mais garder un mouvement doux.

### Gaps
- Pas de source spécifique sur les valeurs utilisées par Siri/Alexa/Google pour leurs orbes audio-réactifs ; les valeurs 40/200 ms sont une inférence à partir des standards de metering.

## Q4 — Accessibilité : Reduce Motion, état non transmis par l'animation seule, photosensibilité

### Takeaway
Avec Reduce Motion : garder les **formes** (l'expression reste lisible), remplacer springs/rotations/scans/pulsations par des **fondus courts ou changements instantanés**, supprimer saccades, rotation des spirales et pulsation audio. Toujours doubler l'état par un **libellé texte + annonce VoiceOver**. Alerte/erreur : pas plus de 3 flashs/s (WCAG 2.3.1) — en pratique, pas de clignotement du tout ou ≤ 2 Hz doux.

### Cited Findings
- HIG Motion : quand Reduce Motion est actif, minimiser ou éliminer les animations — [Apple HIG Motion](https://developer-mdn.apple.com/design/human-interface-guidelines/foundations/motion)
- SwiftUI : `@Environment(\.accessibilityReduceMotion)` ; éviter surtout les grosses animations et celles simulant la 3D ; les animations custom doivent être désactivées/remplacées par le dev lui-même — [Create with Swift](https://www.createwithswift.com/ensure-visual-accessibility-supporting-reduced-motion-preferences-in-swiftui/) ; [Use Your Loaf](https://useyourloaf.com/blog/reducing-motion-of-animations/)
- Schéma Apple : zooms/mouvements en couches remplacés par des fondus (crossfade) — [Revert to Saved](https://reverttosaved.com/2023/09/27/apple-reduce-motion-and-the-battle-for-vestibular-accessibility/) ; [Apple accessibility-dev list](https://lists.apple.com/archives/accessibility-dev/2017/Dec/msg00007.html)
- App Store Connect publie des critères d'évaluation « Reduced Motion » ; recommandation de détecter le réglage système — [App Store Connect Help](https://developer.apple.com/help/app-store-connect/manage-app-accessibility/reduced-motion-evaluation-criteria)
- **WCAG 2.3.1 (niveau A)** : rien ne doit flasher plus de 3 fois par seconde, sauf sous les seuils. Flash général = paire de variations opposées de luminance relative ≥ 10 % du max avec l'état sombre < 0,80. Alternative : surface de flash simultanée ≤ 0,006 sr (25 % d'un champ de 10°), référence 341 × 256 px CSS (87 296 px²) — [W3C Understanding 2.3.1](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html)
- Flash rouge : R/(R+G+B) ≥ 0,8 avec différence de chromaticité > 0,2 — pertinent pour l'indicateur rouge système — [W3C Understanding 2.3.1](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html)

### Inferences
- **Table Reduce Motion proposée** :
  - Garder : formes statiques de chaque état, changement d'état en fondu 150–200 ms (ou instantané), barre de progression (elle transmet de l'info, avance sans rebond), blink (option : le garder, il est petit — ou le désactiver).
  - Remplacer : spring 300 ms → fondu linéaire ; dizzy spirale rotative → spirale fixe ; thinking scan → yeux décalés fixes ; cool reflet mobile → reflet statique ; sleeping respiration → statique ; listening pulsation → dilaté fixe + petit indicateur de niveau discret (ou statique).
  - Supprimer : saccades idle, squash & stretch, shake, overshoot.
  - Web : `@media (prefers-reduced-motion: reduce)` + `matchMedia(...).addEventListener('change')` pour basculer à chaud.
- **Ne pas transmettre l'état par l'animation seule** : libellé texte discret sous la visière (« J'écoute… », « Erreur micro ») ; `accessibilityLabel` = « Friday, état : écoute » ; `AccessibilityNotification.Announcement` (SwiftUI) ou `aria-live="polite"` (web) pour listening/alert/error uniquement (pas pour chaque changement idle, sinon spam) ; `assertive` pour error. WCAG 1.4.1 (pas l'info par la couleur seule) concerne aussi les pastilles vert/jaune/rouge → toujours une icône/texte.
- **Alert/error** : yeux blancs sur fond sombre = gros contraste de luminance → tout clignotement compte comme flash. Préférer : apparition unique + pulsation d'opacité douce (ex. 1 cycle/s, entre 100 % et 70 % → variation < 10 % du max évitée ou très lente) ; jamais > 3 Hz ; la zone visière restera de toute façon probablement < 341×256 px, mais ne pas s'appuyer sur l'exception.
- WCAG 2.2.2 (Pause, Stop, Hide) : une animation automatique > 5 s présentée en parallèle d'autres contenus doit pouvoir être mise en pause — l'idle continu de l'avatar le justifie : prévoir un réglage « Animations de l'avatar : complètes / réduites / désactivées ».

### Gaps
- Texte primaire de WCAG 2.2.2 non re-consulté dans cette session (exigence citée de mémoire : > 5 s, démarrage automatique, en parallèle d'autre contenu).
- Pas de guide Apple spécifique aux avatars/personnages animés.

## Q5 — Performance d'une animation continue dans une app toujours active

### Takeaway
Le coût principal vient d'animer en permanence à 60–120 Hz alors que rien ne change. Animer **par événements** (springs sur changement d'état, blink ponctuel) plutôt qu'une boucle continue ; limiter l'idle à 30 fps ; **mettre en pause** quand la fenêtre est cachée/occultée/en veille ; transform/opacity uniquement côté web ; time-based (timestamps) pour gérer 120 Hz ProMotion.

### Cited Findings
- rAF est mis en pause dans la plupart des navigateurs en onglet d'arrière-plan ou iframe cachée ; fréquence = refresh de l'écran ; animer selon le timestamp sinon l'animation est plus rapide sur écran 120 Hz — [MDN requestAnimationFrame](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame)
- TimelineView : SwiftUI met à jour toutes les vues dans son closure, même celles qui ne changent pas → garder le closure minimal — [Kodeco TimelineView & Canvas](https://www.kodeco.com/27594491-using-timelineview-and-canvas-in-swiftui?page=1)
- KeyframeAnimator : contenu réévalué à chaque frame pendant l'animation, éviter le travail coûteux — [SwiftUI Garden](https://swiftui-garden.pages.dev/Animations/Animation-playground)
- PhaseAnimator : rapports de développeurs d'une animation qui continue après dismiss de la vue (crash/retain) ; pas de fix officiel → l'arrêter explicitement — [Apple forums 737403](https://developer.apple.com/forums/thread/737403) ; [Apple forums 737912](https://developer.apple.com/forums/thread/737912)
- Checklist perf (source secondaire) : PhaseAnimator toujours actif, blur/shadow par élément = signaux d'alerte — [skillselion ios-animation](https://skillselion.com/skills/existential-birds/beagle/ios-animation-implementation)
- RoboEyes plafonne explicitement le framerate (`begin(w, h, maxFramerate)`) — [GitHub RoboEyes](https://github.com/FluxGarage/RoboEyes)

### Inferences
- **SwiftUI (macOS 26)** :
  - États : `withAnimation(.spring(duration: 0.3))` sur un `@State var params` → SwiftUI n'anime que pendant 300 ms puis s'arrête (coût nul au repos).
  - Idle (blink, saccades) : tâche `Task` avec `try await Task.sleep(for: .seconds(random))` qui déclenche un one-shot (KeyframeAnimator avec `trigger:`), plutôt qu'une TimelineView `.animation` permanente.
  - Continu nécessaire uniquement pour : listening (niveau audio), dizzy (rotation), thinking (scan), loading, cool (reflet) → `TimelineView(.animation(minimumInterval: 1/30, paused: !isActive))` + `Canvas` ; `paused` piloté par `scenePhase`, `NSWindow.occlusionState` (`didChangeOcclusionStateNotification`), mini-fenêtre fermée, écran verrouillé.
  - Éviter blur/shadow animés ; le « glow » LED = calque flou statique pré-rendu (ou `.shadow` non animé), monochrome blanc.
  - Mesurer avec Instruments (SwiftUI template, Animation Hitches) ; viser < 1–2 % CPU au repos.
- **Web view (WKWebView/Tauri/Electron)** :
  - Animer `transform`/`opacity` (composités GPU) ; les morphs de `d` SVG déclenchent repaint → les limiter aux transitions de 300 ms ; `will-change: transform` uniquement sur les éléments animés en continu (pas partout, coût mémoire).
  - Canvas 2D/WebGL pour listening si beaucoup de frames ; ou SVG avec une seule propriété `transform: scale(var(--lvl))`.
  - `document.visibilitychange` + `IntersectionObserver` pour suspendre ; rAF basé timestamp ; plafonner à 30 fps pour l'idle via accumulation du delta.
  - Rive : `rive.pause()` quand caché ; le renderer Rive est GPU.
- **State machine** (applicable aux deux UIs) :
  - Priorités : `error`/`alert` (P0) > `listening` (P1, entrée immédiate sur wake word, sans attendre la fin d'une transition : interrompre le spring en cours, SwiftUI le fait nativement en reprenant la vélocité) > `loading`/`thinking` (P2) > émotions (P3) > idle `neutral`/`sleeping` (P4).
  - Une requête de priorité inférieure à l'état courant est mise en file ou ignorée ; alert/error ne sont quittés que par acquittement ou timeout explicite.
  - Règle d'arêtes interdites : table `forbidden = {(sleeping, angry), …}` → insertion automatique d'un état intermédiaire `neutral` (≈300 ms + 300 ms).
  - Timer de retour : tout état émotionnel P3 → `neutral` après 10 s (timer réarmé à chaque nouvel état) ; `neutral` → `sleeping` après N minutes d'inactivité.
  - Modélisation : `enum FaceState` + fonction pure `reduce(state, event) -> (state, [effects])`, testable unitairement ; même logique portable en TypeScript (XState possible côté web).

### Gaps
- Aucune mesure publiée du coût CPU/GPU de TimelineView/Canvas sur macOS 26 vs Rive vs WKWebView pour ce type d'avatar.
- Confirmation officielle que TimelineView suspend son planning quand la vue est hors écran non trouvée → utiliser explicitement `paused:`.

# UX et design visuel d'un assistant vocal desktop permanent (Friday) : overlay flottant + dashboard, monochrome sombre « Liquid Glass » (état novembre 2026)

Note de méthode : les pages Apple HIG ne se chargent pas en WebFetch (rendu JS). Les citations HIG viennent de la copie locale du skill `apple-design` (pages extraites de developer.apple.com, avec URL source et date de dernière modification Apple, ex. Materials mis à jour le 2025-09-09). Les ratios de contraste ci-dessous ont été **calculés** avec la formule de luminance relative WCAG 2.x (script Python local). Ce sont des valeurs dérivées, pas citées d'une source.

## 1. Comment les assistants actuels présentent les états vocaux sur desktop

### Takeaway
En 2026, le modèle dominant sur Mac est le suivant : un raccourci global configurable (souvent Option+Espace) ouvre une mini-fenêtre flottante, séparée de la fenêtre complète, avec un push-to-talk (maintien de Fn) en complément ou à la place du mot d'activation. Les fournisseurs documentent la possibilité d'interrompre l'assistant pendant qu'il parle (barge-in), mais je n'ai trouvé aucune documentation primaire sur les indicateurs visuels détaillés (orbe, transcript partiel). Le seul signal de confidentialité micro garanti est le point orange du système, que l'app ne peut pas masquer.

### Cited Findings
- ChatGPT macOS : une « companion window » reste devant toutes les autres fenêtres et s'ouvre avec Option+Espace (notes de version 2024) — [OpenAI Help, release notes macOS](https://help.openai.com/en/articles/9703738-chatgpt-macos-app-release-notes)
- ChatGPT Advanced Voice sur desktop : une expérience en fenêtre compacte et flottante remplace l'ancien plein écran — [TestingCatalog](https://testingcatalog.com/chatgpt-desktop-adds-advanced-voice-mode-prepares-to-launch-voice-clips)
- ChatGPT Voice (GPT-Live) est arrivé sur les apps desktop macOS et Windows le 23 juillet 2026 (v26.715). Pendant une session, l'utilisateur peut « interrupt a response, ask follow-up questions, or redirect work in progress ». La voix complète exige une nouvelle conversation, sinon seule la dictée est proposée. « Screen context » (macOS) inspecte la fenêtre au premier plan et demande les permissions Screen Recording et Accessibility — [Let's Data Science](https://letsdatascience.com/news/openai-brings-gpt-live-voice-to-desktop-apps-7f9c9e21)
- Raccourci ChatGPT Voice configurable dans Réglages > Voice pour invoquer la voix depuis une autre app — [Noqta](https://noqta.tn/en/news/openai-chatgpt-voice-desktop-gpt-live-codex-2026) (page en HTTP 410 au moment de la vérification, info obtenue uniquement via l'extrait de recherche)
- Gemini pour Mac (app native, avril 2026) : Option+Espace ouvre un mini-chat flottant depuis n'importe où, Option+Shift+Espace ouvre la fenêtre complète, raccourcis personnalisables. Un appui long sur Fn lance la voix et la dictée dans n'importe quelle app (« Speak to Window ») — [iGeeksBlog](https://www.igeeksblog.com/google-gemini-macos-app-launch/) ; [HotHardware](https://hothardware.com/news/google-now-lets-mac-users-talk-to-gemini-in-virtually-any-app) ; [Gemini for macOS](https://gemini.google/in/mac/). Les dates de lancement de la voix diffèrent selon les sources (avril ou 29 juillet 2026).
- Raycast : dictée globale sur Mac (v0.57, 8 mai 2026), déclenchée par un raccourci « from anywhere » sans ouvrir Raycast, texte collé dans l'app active, dictée possible directement dans le composeur AI Chat. Screen Awareness (v0.71, août 2026). Transcriptions stockées localement, audio non conservé — [Raycast changelog 0.57](https://www.raycast.com/changelog/macos/0-57) ; [Raycast manual, Dictation](https://manual.raycast.com/ai/dictation) ; [Raycast changelog 0.71](https://www.raycast.com/changelog/macos/0-71)
- Siri sur macOS 26 (Tahoe) : pas de refonte, seulement une nouvelle icône. Le nouveau Siri a été repoussé — [TidBITS](https://tidbits.com/?p=70657) ; [MacRumors](https://www.macrumors.com/2025/06/09/apple-unveils-macos-tahoe-26/)
- macOS 27 « Golden Gate » (WWDC juin 2026) : app Siri autonome à interface de type chatbot, conversations synchronisées via iCloud, Spotlight ouvre sur « Search or Ask » et route les requêtes IA vers Siri, Liquid Glass ajusté pour la lisibilité (meilleur contraste, curseur de teinte) — [iPhone in Canada](https://www.iphoneincanada.ca/2026/06/08/apple-unveils-macos-27-golden-gate-with-new-ai-siri/) ; [Tom's Hardware](https://www.tomshardware.com/software/macos/apple-demonstrates-cross-platform-siri-upgrades-in-macos-27-golden-gate-at-wwdc-update-brings-liquid-glass-improvements-and-unifies-ai-strategy) ; [TechCrunch](https://techcrunch.com/2026/09/14/macos-27-new-siri-takes-on-ai-productivity-apps/) (sources de presse secondaires, pas de documentation Apple consultée)
- NN/g : Siri émet un bip à deux tons après le mot d'activation pour signaler l'écoute. Echo coupe sa propre parole quand il détecte le mot d'activation (le modèle du barge-in). « If a screen is available, it's usually best to include a visual signifier. » Les earcons seuls « do not convey enough information » et doivent être accompagnés de signifiants verbaux — [NN/g, Audio Signifiers](https://www.nngroup.com/articles/audio-signifiers-voice-interaction/)
- NN/g : sur Echo, la visibilité de l'état se limite à un anneau lumineux animé, « a far cry from the rich textual feedback possible with a screen ». Les assistants ne marchent bien que pour des requêtes simples — [NN/g, Voice interaction UX](https://www.nngroup.com/articles/voice-interaction-ux/) ; [NN/g, Intelligent assistant usability](https://www.nngroup.com/articles/intelligent-assistant-usability/)
- Point orange macOS : il indique que le micro est utilisé. Depuis macOS 13.3, Control Center liste les apps qui utilisent micro, caméra ou audio système. Il n'existe aucun moyen officiel de le masquer — [Apple Mac Help](https://support.apple.com/en-nz/guide/mac-help/mchl50f94f8f) ; [MacRumors](https://www.macrumors.com/how-to/menu-bar-dot-explanation/) ; [TechFinitive](https://www.techfinitive.com/explainers/turn-off-orange-dot-mac-screen/)
- Une fenêtre d'explication peut précéder l'alerte système micro, mais toute fenêtre qui imite l'alerte ou offre une incitation entraîne un rejet. Le texte de justification doit être précis : l'exemple « Microphone access is needed for a better experience » est marqué ✗ — [Apple HIG, Privacy](https://developer.apple.com/design/human-interface-guidelines/privacy)

### Inferences
- Pour Friday : Option+Espace pour l'overlay et Option+Shift+Espace pour le dashboard s'alignent sur ChatGPT et Gemini. Option+Espace est déjà pris par ces apps, donc il faut le rendre configurable et gérer les conflits.
- Push-to-talk (maintien d'une touche) par défaut et mot d'activation en option. L'écoute continue maintient le point orange allumé en permanence, ce qui crée de l'anxiété côté confidentialité (déduit des sources sur le point orange).
- Les états vocaux doivent combiner trois canaux : forme et animation de l'avatar, libellé texte (« J'écoute… », « Je réfléchis… », « Je parle — Échap pour couper ») et earcon court. NN/g dit que le son seul ne suffit pas.
- Barge-in : pendant que Friday parle, un bouton « Interrompre » visible (icône carré stop + libellé) et la touche Échap ou un nouvel appui sur le raccourci. Couper le TTS dès que la voix utilisateur est détectée.
- Transcript partiel : afficher la transcription en direct dans la bulle utilisateur en style « brouillon » (italique ou soulignement pointillé, opacité ≥0,55), puis la figer à la fin de l'énoncé. C'est un pattern déduit, aucune documentation primaire ne le décrit.
- Indicateur micro propre à l'app : une pastille « micro actif » (icône micro + texte « Micro ouvert ») dans l'overlay et dans la barre du dashboard, qui double le point orange système sans le contredire. Un état « Micro coupé » explicite (icône barrée) est aussi nécessaire.

### Gaps
- Je n'ai trouvé aucune documentation primaire (OpenAI, Google, Apple) décrivant précisément les animations listening/thinking/speaking ni l'affichage des transcripts partiels sur desktop en 2026.
- Copilot desktop (« Hey Copilot ») et Alexa+ web : aucune source exploitable trouvée dans le budget de recherche.
- Le raccourci par défaut actuel de ChatGPT Voice n'est pas confirmé.

## 2. Patterns d'overlay/HUD sur macOS

### Takeaway
D'après la HIG, un panneau flottant doit rester petit, avoir un titre court, peu de couleur, et ne devenir fenêtre clé (key window) que lorsqu'un champ texte demande la saisie. Le style HUD sombre translucide est réservé aux contextes justifiés. Le Liquid Glass appartient à la couche fonctionnelle flottante, ce qui correspond exactement à l'overlay, et non aux cartes de contenu du dashboard.

### Cited Findings
- Un panneau macOS « floats above other open windows ». Il peut adopter un style sombre translucide de type HUD — [Apple HIG, Panels](https://developer.apple.com/design/human-interface-guidelines/panels)
- HUD : « Prefer standard panels », « Use color sparingly in HUDs » (de petites touches de couleur à fort contraste suffisent), « Keep HUDs small… Don't let a HUD obscure the content » — [Apple HIG, Panels](https://developer.apple.com/design/human-interface-guidelines/panels)
- Un panneau a besoin d'une barre de titre pour que l'utilisateur puisse le positionner. Titre court (un nom), référencé dans les menus comme « Show X » — [Apple HIG, Panels](https://developer.apple.com/design/human-interface-guidelines/panels)
- Une seule fenêtre clé à la fois. Certains panneaux ne deviennent clés que lorsque l'utilisateur clique dans la barre de titre ou dans un composant qui demande une saisie clavier, comme un champ texte — [Apple HIG, Windows](https://developer.apple.com/design/human-interface-guidelines/windows)
- « Avoid changing focus without people's interaction » — [Apple HIG, Focus and selection](https://developer.apple.com/design/human-interface-guidelines/focus-and-selection)
- La touche Échap annule l'action ou le processus en cours (table des raccourcis système). Il ne faut pas écraser les raccourcis système, et l'app doit fonctionner avec Full Keyboard Access — [Apple HIG, Keyboards](https://developer.apple.com/design/human-interface-guidelines/keyboards) ; [Apple HIG, Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- Liquid Glass : « forms a distinct functional layer for controls and navigation elements… that floats above the content layer ». « Don't use Liquid Glass in the content layer. » « Use Liquid Glass effects sparingly » — [Apple HIG, Materials](https://developer.apple.com/design/human-interface-guidelines/materials)
- Variante *clear* réservée aux éléments au-dessus de fonds visuellement riches. Si le fond est clair : « consider adding a dark dimming layer of 35% opacity ». Les grands éléments (barres latérales) sont plus opaques pour rester lisibles — [Apple HIG, Materials](https://developer.apple.com/design/human-interface-guidelines/materials) ; [Apple HIG, Color](https://developer.apple.com/design/human-interface-guidelines/color)
- Gemini sépare le mini-chat flottant (Option+Espace) de la fenêtre complète (Option+Shift+Espace) — [iGeeksBlog](https://www.igeeksblog.com/google-gemini-macos-app-launch/)
- Code AppKit : NSWindow.StyleMask `hudWindow` — [Apple docs](https://developer.apple.com/documentation/appkit/nswindow/stylemask-swift.struct/hudwindow)

### Inferences
- Overlay de 380×680 : c'est une hauteur importante pour un « HUD ». Je recommande trois états :
  - (a) une pilule compacte d'environ 380×64 (avatar + statut + micro) quand Friday est inactif ou écoute ;
  - (b) une version étendue de 380×680 avec la conversation ;
  - (c) un masquage automatique après N secondes d'inactivité, sauf si l'overlay est épinglé.
- Comportement de fenêtre :
  - NSPanel non activant (`.nonactivatingPanel`), qui ne devient clé que lorsque l'utilisateur clique dans le champ de saisie ;
  - niveau `.floating` ;
  - déplaçable par la barre de titre ou l'en-tête avatar, position mémorisée ;
  - collectionBehavior `canJoinAllSpaces` + `fullScreenAuxiliary`.
- Position par défaut : en haut à droite, sous la barre de menus (zone des notifications), avec une marge d'environ 16 px. On évite le centre, qui masque le contenu (« Don't let a HUD obscure the content »).
- Clavier :
  - le raccourci global bascule l'affichage ;
  - Échap coupe d'abord la parole, puis réduit l'overlay, puis le masque (escalade progressive) ;
  - Tab parcourt avatar → pills → champ → envoyer ;
  - ⌘↩ envoie, ⌘. arrête la génération (convention macOS d'annulation, déduite).
- Comme l'overlay flotte au-dessus d'autres apps (fonds clairs possibles), sa « glass » doit inclure un voile sombre (voir les calculs en section 4). C'est le cas où la recommandation Apple d'un « dimming layer » s'applique.

### Gaps
- Je n'ai pas trouvé de guidelines chiffrées Apple sur la taille idéale d'un panneau HUD ni sur les délais de masquage automatique.
- Sessions WWDC 2025/2026 sur Liquid Glass et AppKit non consultées en détail (contenu vidéo).

## 3. Densité d'information du dashboard et visualisation monochrome des stats système

### Takeaway
Un widget mérite sa place s'il est consulté souvent ou s'il déclenche une action, comme la météo, le prochain événement ou l'activité de Friday. Les stats système doivent être lisibles sans couleur : valeur numérique d'abord, barre ou sparkline ensuite, seuils marqués par la forme ou une icône. Le vert, jaune et rouge ne servent qu'en redondance.

### Cited Findings
- HIG : « Convey information with more than color alone… Offer visual indicators, like distinct shapes or icons » — [Apple HIG, Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- HIG Liquid Glass Color : réserver la couleur aux « status indicators or primary actions ». Une app essentiellement monochrome peut utiliser une couleur d'accent — [Apple HIG, Color](https://developer.apple.com/design/human-interface-guidelines/color)
- Fond des widgets et cartes du dashboard : « use standard materials for elements in the content layer », pas le Liquid Glass — [Apple HIG, Materials](https://developer.apple.com/design/human-interface-guidelines/materials)
- Seuils de temps de réponse attribués à Nielsen : 0,1 s, 1 s, 10 s (source secondaire) — [uxdesign.cc](https://uxdesign.cc/the-waiting-problem-in-ai-products-e7c11fd5a825)

### Inferences
- Stats système en monochrome :
  - valeur en chiffres tabulaires (`font-variant-numeric: tabular-nums`) et libellé ;
  - barre horizontale fine avec piste à blanc 0,14 et remplissage à blanc 0,85 (ratio remplissage/piste ≥3:1, voir section 4) ;
  - sparkline de 60 s en trait de 1,5 px ;
  - au-delà d'un seuil, un motif hachuré sur la barre, une icône ⚠ et le mot « élevé ». La couleur jaune ou rouge n'est que redondante.
- Rafraîchissement limité à environ 1 Hz pour les chiffres. Ne pas animer chaque tick quand Reduce Motion est actif.
- Widgets prioritaires : (1) prochain événement d'agenda, (2) météo actuelle avec une ligne de prévision, (3) activité de Friday (tâches en cours ou récentes), (4) stats système compactes à gauche. Le graphique d'activité ne se justifie que s'il est actionnable (filtre ou clic vers l'historique). Sinon, il vaut mieux un compteur.
- Respecter les tailles : un dashboard de 1440×900 avec trois colonnes est dense. Garder un seul point focal, l'avatar et la saisie au centre, et des widgets secondaires en texte de 13 pt minimum.

### Gaps
- Je n'ai pas trouvé de recherche NN/g spécifique à 2026 sur les dashboards personnels ni sur les « hubs » d'assistant. Les recommandations ci-dessus sont des inférences.

## 4. Accessibilité d'une UI monochrome sombre : contrastes exacts, états sans couleur, focus, fallbacks

### Takeaway
Sur #000, le blanc doit être à une opacité d'au moins 0,46 pour atteindre 4,5:1 et d'au moins 0,59 pour 7:1, le ratio recommandé par Apple pour le petit texte sur couleurs custom. Le tertiaire à 0,35 ne donne que 3,0:1, il faut donc monter à 0,60. Sur une glass flottant au-dessus d'une fenêtre claire, il faut un voile noir d'au moins 75 à 80 % pour garder le texte lisible. Il faut gérer `prefers-reduced-transparency`, `prefers-contrast: more` et `prefers-reduced-motion`, ou les flags NSWorkspace en natif.

### Cited Findings
- Seuils utilisés par Apple (Accessibility Inspector, WCAG AA) : texte jusqu'à 17 pt, 4,5:1 ; 18 pt, 3:1 ; gras, 3:1. Si l'app n'atteint pas ces seuils par défaut, elle doit au moins proposer un schéma plus contrasté quand Increase Contrast est activé — [Apple HIG, Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- Dark Mode : « no lower than 4.5:1… For custom foreground and background colors, strive for a contrast ratio of 7:1, especially in small text ». Tester avec Increase Contrast et Reduce Transparency, séparément et ensemble — [Apple HIG, Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode)
- Vibrancy : éviter le niveau quaternaire sur les matériaux thin et ultraThin, « because the contrast is too low ». Les matériaux plus épais donnent un meilleur contraste pour le texte — [Apple HIG, Materials](https://developer.apple.com/design/human-interface-guidelines/materials)
- Reduce Motion : réduire les animations automatiques et répétitives (zoom, mise à l'échelle, mouvement périphérique) — [Apple HIG, Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- WCAG 2.2 SC 2.4.13 Focus Appearance (AAA) : la zone de l'indicateur doit être au moins un périmètre de 2 px CSS, avec un contraste d'au moins 3:1 entre les mêmes pixels à l'état focus et non-focus — [W3C Understanding 2.4.13](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance.html). Le critère 1.4.11 Non-text Contrast s'applique aussi aux indicateurs de focus (même page). Le ratio de 3:1 du 1.4.11 n'a pas été revérifié sur la page W3C, voir Gaps.
- HIG : utiliser un focus ring pour les champs texte et un surlignage pour les lignes de liste — [Apple HIG, Focus and selection](https://developer.apple.com/design/human-interface-guidelines/focus-and-selection)
- `prefers-contrast` : valeurs `no-preference | more | less | custom`. `custom` correspond à `forced-colors: active`. Baseline « widely available » depuis mai 2022 — [MDN prefers-contrast](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-contrast)
- `prefers-reduced-transparency` : support limité. Chrome et Edge 118 ou 119 selon la source. Firefox est implémenté d'après Bugzilla mais marqué non supporté sur web-features. **Safari non supporté** d'après caniuse (iOS jusqu'en 26.x/27.x) — [web-features explorer](https://web-platform-dx.github.io/web-features-explorer/features/prefers-reduced-transparency) ; [caniuse](https://caniuse.com/mdn-css_at-rules_media_prefers-reduced-transparency) ; [Bugzilla 1736914](https://bugzilla.mozilla.org/show_bug.cgi?id=1736914) ; [Chrome blog](https://developer.chrome.com/blog/css-prefers-reduced-transparency) ; [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-transparency)
- Natif AppKit : `NSWorkspace.shared.accessibilityDisplayShouldReduceTransparency`, `…ShouldIncreaseContrast`, `…ShouldReduceMotion` et la notification `accessibilityDisplayOptionsDidChangeNotification`. Ce sont des noms d'API connus, issus de la documentation AppKit, mais la page n'a pas été rechargée pendant cette session : à vérifier.

### Contrastes calculés (formule WCAG, blanc à opacité α composé sur le fond)
| α texte blanc | sur #000 | sur glass 0,04 (#0A0A0A) | sur glass 0,08 (#141414) | sur glass 0,14 (#242424) |
|---|---|---|---|---|
| 0,35 | 3,01 | 3,14 | 3,22 | 3,17 |
| 0,45 | 4,41 | 4,50 | 4,52 | 4,30 |
| 0,50 | 5,28 | 5,33 | 5,30 | 4,97 |
| 0,55 | 6,27 | 6,26 | 6,16 | 5,70 |
| 0,60 | 7,37 | 7,30 | 7,12 | 6,50 |
| 0,70 | 9,96 | 9,70 | 9,32 | 8,31 |
| 0,90 | 16,75 | 15,92 | 14,92 | 12,84 |
| 1,00 | 21,00 | 19,78 | 18,36 | 15,58 |

- α minimal pour 3:1, 4,5:1 et 7:1 : sur #000, 0,35, 0,46 et 0,59 ; sur glass 0,14, 0,34, 0,47 et 0,63.
- Bordure de panneau à blanc 0,14 sur #000 : 1,35:1. C'est purement décoratif. Une bordure qui délimite un contrôle interactif doit atteindre 3:1, soit un blanc ≥0,35.
- Focus ring à blanc α sur #000 : α 0,30 donne 2,46 (insuffisant), α 0,35 donne 3,01, α 0,5 donne 5,28. Recommandation : anneau de 2 px à blanc 1,0 (ou ≥0,6) avec un décalage (offset) de 2 px.
- **Overlay au-dessus d'une fenêtre blanche** (pire cas, glass blanc 0,10 sur voile noir t) :
  - voile 60 %, texte blanc 1,0 : 4,59 ;
  - voile 75 %, texte blanc 0,9 : 6,63, et texte 0,55 : 3,62 ;
  - voile 85 %, texte 0,55 : 4,60, et texte 0,9 : 9,31.
  Le flou réduit les extrêmes, donc ce calcul est conservateur.

### Inferences
- Échelle d'opacité proposée :
  - primaire 1,0 ;
  - secondaire 0,72 (≥9:1) ;
  - tertiaire 0,60 (≥6,5:1 même sur glass 0,14) ;
  - désactivé 0,38, réservé aux éléments inactifs (WCAG exempte les composants désactivés).
  Supprimer le 0,35 pour tout texte informatif.
- Glass de l'overlay : `background: rgba(10,10,10,0.78)`, puis `backdrop-filter: blur(30px) saturate(120%)`, puis un liseré intérieur `inset 0 0 0 1px rgba(255,255,255,0.12)`. Le dashboard reste sur #000 avec des cartes opaques #0D0D0D, sans blur (couche de contenu).
- États sans couleur ni opacité seule : combiner une icône distincte, un libellé texte et une variation de graisse ou de forme :
  - écoute : onde, contour plein ;
  - réflexion : trois points, tirets ;
  - parle : barres d'égaliseur ;
  - erreur : triangle + texte ;
  - hors ligne : icône barrée.
  Le vert, jaune et rouge restent en redondance (pastille + icône + mot).
- CSS de repli :
  - `@media (prefers-reduced-transparency: reduce)` : `backdrop-filter: none` et fond opaque #111 ;
  - Safari ne supporte pas cette requête. Dans une WebView (Tauri ou Electron sur WKWebView), il faut lire le flag natif et poser une classe `.reduce-transparency` sur `<html>` ;
  - `@media (prefers-contrast: more)` : texte secondaire et tertiaire à 1,0, bordures à 0,6, focus à 3 px ;
  - `@media (prefers-reduced-motion: reduce)` : avatar statique avec changement d'expression en fondu de 150 ms maximum, pas de pulsation ni d'onde continue. L'état passe alors par l'icône et le texte.
- Natif : observer `NSWorkspace.accessibilityDisplayOptionsDidChangeNotification` et relayer les valeurs au front.

### Gaps
- La table de compatibilité MDN exacte (versions Safari et Firefox) n'a pas pu être chargée. Vérifier si WKWebView expose `prefers-contrast` selon le réglage « Augmenter le contraste » de macOS (non confirmé par la source).
- Le texte du ratio 3:1 du SC 1.4.11 et celui du SC 2.4.11 n'ont pas été revérifiés sur la page W3C pendant cette session.
- APCA est mentionné par Apple mais aucune valeur Lc n'a été calculée.

## 5. Lisibilité des bulles de chat et du transcript, affichage de l'activité des agents

### Takeaway
Pour une conversation IA, il faut viser des réponses lisibles comme du texte (peu de bulle côté IA), du streaming accessible, des statuts spécifiques plutôt que « Traitement… », et des contrôles Interrompre/Réessayer près du contenu. L'activité des sous-agents se montre par une ligne de statut repliable, pas par un flux permanent.

### Cited Findings
- « Consider giving specific, reassuring feedback during generation… instead of "Processing…", say "Finding substitutions for ingredients" » — [Apple HIG, Generative AI](https://developer.apple.com/design/human-interface-guidelines/generative-ai)
- Placer « Edit, Undo, Retry, or Adjust near generated content ». Garder l'utilisateur en contrôle et indiquer clairement où l'IA intervient — [Apple HIG, Generative AI](https://developer.apple.com/design/human-interface-guidelines/generative-ai)
- Prévenir que l'IA peut se tromper, être transparent sur ce qui est envoyé au serveur — [Apple HIG, Generative AI](https://developer.apple.com/design/human-interface-guidelines/generative-ai)
- Le streaming pose problème aux lecteurs d'écran et appelle des alternatives accessibles. Le chiffre « perçu 40–60 % plus rapide » n'est pas vérifié — [Setproduct](https://www.setproduct.com/blog/ai-chat-interface-ui-design) (source secondaire)
- Résumé des constats NN/g sur les interfaces de chat IA : « people get lost when scrolling » dans les longs flux de réponses — [Goodreads, blog de J. Nielsen](https://www.goodreads.com/author_blog_posts/25649271-usable-chat-interfaces-to-ai-models) (source secondaire)
- Transcripts : utiles pour relire un contenu long et le surligner pendant la lecture audio — [Apple HIG, Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)

### Inferences
- Dans l'overlay de 380 px :
  - bulles utilisateur alignées à droite, largeur max 80 %, fond blanc 0,10 ;
  - réponses de Friday à gauche, sans bulle ou avec un fond très léger, largeur pleine, texte à 1,0 ;
  - 15 px minimum, interligne 1,45.
  Dans le dashboard, limiter la colonne de texte à environ 60–70 caractères (≈640 px).
- Streaming :
  - afficher le texte par mots ou blocs (pas caractère par caractère) avec un curseur fin à la fin ;
  - `aria-live="polite"` sur un résumé de fin de réponse plutôt que sur chaque token (pour VoiceOver) ;
  - auto-scroll seulement si l'utilisateur est déjà en bas, sinon un bouton « ↓ Nouveau message ».
- Synchronisation voix et texte : surligner discrètement la phrase prononcée (soulignement ou graisse, pas la couleur). Désactiver cet effet si Reduce Motion est actif.
- Horodatage : regrouper par blocs (« 14:32 ») et afficher l'heure exacte au survol ou au focus. Ne pas l'afficher sur chaque bulle.
- Activité des agents : une ligne compacte sous l'avatar, « ◐ Agenda — recherche de créneaux… », avec une icône par agent, le nom et une action spécifique (HIG). Cette ligne se déplie en liste (agent, statut, durée) au clic. Une fois la tâche terminée, elle devient une puce « ✓ 3 étapes » repliée dans la réponse. Jamais plus d'une ligne visible par défaut.
- Quick pills : 3 ou 4 maximum, contextuelles, avec un contour à blanc ≥0,35 (contrôle interactif, ≥3:1) et un libellé texte, pas seulement une icône.

### Gaps
- Article NN/g primaire sur l'UX des chats IA et du streaming non récupéré (seulement des résumés secondaires).
- Pas de documentation primaire OpenAI, Google ou Raycast sur l'affichage multi-agent dans leurs apps desktop.

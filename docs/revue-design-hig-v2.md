# Revue design : Friday AI monochrome (v2)

> Revue HIG Apple (skill apple-design) du prompt `docs/friday-ui-prompt-monochrome.md` : dashboard, overlay, grille d'expressions.
> Plateforme : macOS, Tauri 2 ou Electron (webview). Contrastes calculés depuis les valeurs CSS, opacités composées sur #000.
> Limites : pas de maquette rendue. Alignement et hiérarchie réels non vérifiables, à revoir sur les premiers écrans.
> Remplace `docs/revue-design-hig.md` (direction orange abandonnée).

## Résumé

Note globale : **Critical issues**. La thèse s'est encore resserrée : un visage blanc dans le noir, rien d'autre. C'est plus fort que la version orange, parce que la seule lumière de l'écran devient Friday lui-même. Trois problèmes d'accessibilité bloquent : le texte tertiaire et les placeholders, l'anneau de focus quasi invisible, et des états signalés uniquement par opacité. La règle « Glass everywhere » contredit frontalement Apple et coûtera cher en GPU.

## Critique

- **Texte tertiaire et placeholders sous le minimum.** `--text-tertiary` 0.35 donne `#595959` : **3,00:1** sur #000 et **2,74:1** sur une bulle 0.06. Il sert aux labels de stats, aux placeholders et aux captions.
  Pourquoi : `accessibility.md` exige 4,5:1 pour le texte courant, et `dark-mode.md › Dark Mode colors` vise 7:1 pour les couleurs custom : « strive for a contrast ratio of 7:1, especially in small text ». La règle 9 du prompt dit aussi 4,5:1.
  Fix : `--text-tertiary: rgba(255,255,255,0.55)` → `#8C8C8C`, **6,25:1** sur #000 et **5,2:1** sur une surface 0.10. `--text-disabled` 0.20 (1,66:1) peut rester, le texte désactivé est exempté.

- **Anneau de focus invisible.** Focus de l'input : bordure 0.30 = `#4C4C4C`, **2,45:1** sur #000, plus un halo 0.06 imperceptible. Sous le seuil de 3:1 attendu pour un indicateur non textuel. Les boutons n'ont aucun style de focus défini.
  Pourquoi : `accessibility.md` impose une navigation clavier complète, et `cross-platform.md › Desktop` demande un focus visible. Règle 9 du prompt : « Focus visible (ring blanc) ».
  Fix : `:focus-visible { outline: 2px solid rgba(255,255,255,0.85); outline-offset: 2px; }` sur tout interactif. Bordure de focus de l'input à 0.55 minimum (**6,25:1**).

- **États portés par l'opacité seule.** Les 3 dots de la top bar (blanc = actif, 0.20 = inactif, **1,66:1**) n'ont ni forme ni libellé. L'état « Écoute » est porté uniquement par la waveform et le micro pulsant.
  Pourquoi : `color.md › Best practices` : « Avoid relying solely on color to differentiate between objects, indicate interactivity, or communicate essential information ». `motion.md › Best practices` : « avoid using it as the only way to communicate important information ».
  Fix : dots remplacés par 3 icônes avec libellés au survol et `aria-label` (micro barré ou non, nuage plein ou barré). Sous l'avatar, une ligne texte d'état en `aria-live="polite"` : « À l'écoute », « Je réfléchis », « Hors ligne ».

- **Aucune réponse aux réglages d'accessibilité.** Le prompt anime en boucle 18 avatars (vibration, rotation 360°, flash, clignotement rapide) sans fallback Réduire les animations, Réduire la transparence ou Augmenter le contraste.
  Pourquoi : `accessibility.md` : « When this setting is active, ensure your app or game responds by reducing automatic and repetitive animations, including zooming, scaling, and peripheral motion ». `liquid-glass.md › Review checklist › 5` : opaque pour Réduire la transparence, bordures renforcées pour Augmenter le contraste.
  Fix : `@media (prefers-reduced-motion: reduce)` qui fige la grille sur la pose de chaque état et réduit les transitions à un fondu de 150 ms. Le flash « Erreur » et le clignotement « Alerte » deviennent statiques. `@media (prefers-contrast: more)` : bordures à 0.30, tertiaire à 0.70. Réduire la transparence : sur Tauri/macOS, lire `accessibilityDisplayShouldReduceTransparency` côté natif et poser `data-reduce-transparency` sur `<html>`. Le glass devient alors `#1C1C1E` opaque.

## Améliorations

- **High : « Glass everywhere » contredit Apple.** La règle 3 met le verre sur panneaux, cartes, boutons, inputs, bulles, cellules de la grille. La hiérarchie de profondeur empile jusqu'à 5 niveaux de flou, avec jusqu'à 80 px de blur.
  Pourquoi : `liquid-glass.md › Where the material belongs` : « Don't use Liquid Glass in the content layer » et « Use Liquid Glass effects sparingly ». Checklist 2 : « Glass stacked on glass blurs the hierarchy the material exists to create ».
  Fix : garder la profondeur par luminosité (règle 6, qui est juste) mais avec des **surfaces opaques** : `#0A0A0A`, `#141414`, `#1C1C1E`, `#2C2C2E`. Le verre reste sur trois éléments : top bar, barre de saisie, fenêtre overlay. Sur fond #000 pur, un `backdrop-filter` ne floute que du noir, donc il est invisible et ne coûte que du GPU.

- **High : utiliser le matériau natif pour l'overlay.**
  Pourquoi : `liquid-glass.md › Tauri and Electron` : « Prefer real system materials over CSS imitation ». Le matériau natif suit Réduire la transparence tout seul.
  Fix : Tauri, crate `window-vibrancy` avec `NSVisualEffectMaterial::HudWindow`. Electron, `vibrancy: 'hud'`. Le contenu HTML de l'overlay n'utilise alors aucun `backdrop-filter`.

- **High : emojis comme icônes.** Les quick actions `[⚡][📁][🔍][⚙️]` sont des emojis en couleur. Ils violent la règle noir et blanc et l'usage d'icônes au trait.
  Pourquoi : `icons.md › Best practices` : « all interface icons in your app need to use a consistent size, level of detail, stroke thickness (or weight), and perspective ». Et : « match the weights of interface icons and adjacent text ».
  Fix : Lucide en SVG, stroke 1.5, 20 px, `currentColor` : `zap`, `folder`, `search`, `settings`. Chaque bouton garde un libellé visible.

- **High : conventions macOS absentes.** Il n'y a ni menu bar, ni raccourcis, ni réglages, et la poignée de drag est custom.
  Pourquoi : `designing-for-macos.md › Best practices` : « Use the menu bar to give people easy access to all the commands they need ». `windows.md › Best practices` : « Avoid creating custom window UI ».
  Fix : faire une app de barre de menus avec une icône Friday monochrome. Le menu propose : Afficher le dashboard, Écouter ⌘⇧F, Mode silencieux, Réglages ⌘,, Quitter ⌘Q. Le dashboard est une fenêtre standard avec les feux natifs. Sur l'overlay, garder la poignée comme repère visuel, mais la zone de drag est une bande de 28 px en `-webkit-app-region: drag`. Le contraste de la poignée passe de 0.20 (**1,46:1**) à 0.40.

- **Medium : polices SF Pro nommées dans la pile.** `'SF Pro Display'` n'est pas résolu par nom dans un webview. La licence Apple ne permet pas non plus de l'embarquer pour un usage hors plateformes Apple.
  Pourquoi : `typography.md › Using system fonts` : SF est la police système, accessible comme police système.
  Fix : `--font-body: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;` et `--font-mono: ui-monospace, 'SF Mono', 'JetBrains Mono', monospace;`. Le système choisit Display ou Text automatiquement grâce aux tailles optiques dynamiques.

- **Medium : tailles iOS sur macOS.** L'input est en 17 px et les boutons en 15 px, ce qui correspond à l'échelle iOS. La règle 5 cite « Dynamic Type ».
  Pourquoi : `typography.md › Ensuring legibility` : macOS a un défaut de 13 pt et un minimum de 10 pt.
  Fix : c'est un choix acceptable pour une app vocale lue à distance, mais il faut l'assumer. Échelle proposée : body 15, input 15, caption 12, title1 28, title2 22. Ne jamais descendre sous 12 px, et pas de graisse inférieure à 400.

- **Medium : le rouge a deux sens.** « En colère » ajoute une bordure rouge, alors que le rouge est réservé aux erreurs système (règle 1).
  Pourquoi : `color.md › Best practices` : « Avoid using the same color to mean different things ».
  Fix : supprimer la bordure rouge. La colère se lit par la forme des sourcils et le tremblement, ce qui est déjà distinct.

- **Medium : grille de 18 avatars animés en continu.** Elle pose des problèmes de mouvement périphérique et de performance : 18 SVG avec filtre de flou et 18 panneaux `backdrop-filter`.
  Pourquoi : `motion.md › Best practices` : « Don't add motion for the sake of adding motion ».
  Fix : par défaut, chaque cellule montre la pose statique de son état. L'animation se joue au survol ou au focus, ou via un bouton « Tout animer ». Les cellules sont opaques, sans verre.

- **Medium : cibles des pills de l'overlay.** Avec un padding de 8 px et une police caption de 12 px, une pill fait environ 32 px de haut. C'est correct en hauteur, mais la rangée est scrollable horizontalement sans indicateur visible.
  Pourquoi : `accessibility.md` fixe la taille de contrôle sur macOS à 28×28 pt par défaut et 20×20 au minimum. Il demande aussi environ 12 pt d'espace autour d'un élément avec bezel.
  Fix : 8 px d'écart minimum et 3 pills visibles au maximum. Pas de scroll horizontal : l'excédent va dans un bouton « Plus ».

- **Low : `transition: all`.** Cette propriété anime aussi la mise en page. Limiter à `background-color, border-color, transform`.
- **Low : bordures de 0,5 px.** Elles disparaissent sur un écran externe non Retina. Utiliser 1 px avec une opacité réduite, ou `0.5px` seulement sous `@media (min-resolution: 2dppx)`.
- **Low : mini bar-chart sans valeurs.** Six barres blanches sans axe ni libellé n'apportent aucune information. Ajouter le jour sous chaque barre et la valeur au survol, ou supprimer le widget.

## Notes de craft

- **Point de vue : fort, et meilleur que la v1.** Dans un écran entièrement noir, la seule lumière, ce sont les yeux de Friday. C'est la signature, et elle est cohérente avec le personnage, une présence plutôt qu'une interface. Pour la tenir, tout ce qui brille autant que les yeux doit disparaître. Le logo « FRIDAY » en blanc pur 18 px dans la top bar concurrence l'avatar : passez-le à text-secondary, ou retirez-le du dashboard (`branding.md › Best practices` : « Ensure branding always defers to content »).
- **Template : non.** Le noir pur avec du blanc seul échappe au cliché « quasi-noir + un accent vif ». Le risque inverse est de ressembler à un écran de verrouillage générique. La forme des yeux et le glow suffisent à l'éviter.
- **Glow des yeux** : `--eye-glow` 0.20 avec feGaussianBlur 3 est juste. C'est le seul élément lumineux autorisé à avoir un halo, n'en mettez nulle part ailleurs.
- **À retirer** : la salutation en deux lignes (« Bonjour, Thaïne. » + « Comment puis-je vous aider ? »). La seconde ligne répète le placeholder de l'input. Gardez la première.
- **Planche de référence** (`img/avatar-expressions-reference.jpg`) : les formes bleues s'adaptent directement en blanc. Les cœurs rouges de l'état « Amour » doivent devenir blancs pour respecter la règle 1.

## Ce qui marche

- La profondeur par luminosité (règle 6) : bon principe, à appliquer avec des surfaces opaques plutôt qu'avec du flou.
- Le texte secondaire 0.60 : **7,37:1** sur #000 et **6,73:1** sur surface 0.06, à garder.
- Les couleurs de statut Apple passent toutes : vert **9,46:1**, jaune **14,88:1**, rouge **6,16:1**.
- Les règles de transition des états : 300 ms, pas d'Endormi vers En colère, Alerte et Erreur prioritaires, retour à Neutre après 10 s. À garder telles quelles.
- La règle 8 (`transform` et `will-change`) et la règle 10 (tokens partout).

## Notes plateforme

- Tauri 2 / macOS : le webview est WebKit, donc `prefers-reduced-transparency` n'est pas disponible. Le réglage se lit côté natif. Pour un overlay visible au-dessus des apps plein écran, il faut `tauri-nspanel`, et `ActivationPolicy::Accessory` pour masquer l'icône du Dock.
- Electron : `vibrancy` natif et `prefers-reduced-transparency` sont disponibles, au prix d'environ 100 à 250 Mo de RAM en plus.
- Sur un fond #000 pur, tout `backdrop-filter` est invisible. C'est la raison technique la plus simple pour abandonner « Glass everywhere ».

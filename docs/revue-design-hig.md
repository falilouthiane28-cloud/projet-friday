# Revue design : Friday AI (dashboard + overlay)

> Revue HIG Apple (skill apple-design) de la section 5 de `docs/friday-system-prompt.md`.
> Artefact revu : tokens CSS, layouts décrits en texte, planche d'expressions `img/avatar-expressions-reference.jpg`.
> Plateforme : macOS, Tauri 2 ou Electron (webview). Contrastes calculés depuis les hex de la spec, pas estimés.
> Limites : pas de maquette, donc pas de revue d'alignement ni de hiérarchie réelle. À refaire sur les premiers écrans.

## Résumé

Note globale : **Needs work**. La thèse est claire et bonne : un assistant qui se résume à un visage, les yeux orange comme seul élément signature, tout le reste en verre sombre et silencieux. Deux problèmes bloquent : le texte tertiaire ne passe pas le contraste minimal, et un bouton orange avec texte blanc est illisible. Le reste relève de la discipline Liquid Glass (verre partout, y compris dans le contenu) et des conventions macOS (menu bar, fenêtre native, réglages système).

## Critique (à corriger avant tout écran)

- **Texte tertiaire illisible.** `--text-tertiary: rgba(255,255,255,0.35)` sur `#08080E` donne `#5E5E62`, soit **3,09:1**. Apple exige 4,5:1 pour le texte jusqu'à 17 pt, et vise 7:1 en mode sombre pour les couleurs custom.
  Pourquoi : `dark-mode.md › Dark Mode colors` : « make sure the contrast ratio between colors is no lower than 4.5:1. For custom foreground and background colors, strive for a contrast ratio of 7:1 ».
  Fix : `--text-tertiary: rgba(255,255,255,0.48)` → `#7F7F82`, **5,0:1**. Monter `--text-secondary` à 0.65 → `#A9A9AB`, **8,5:1**. Le tertiaire reste réservé aux labels non essentiels (horodatage, unités).

- **Texte blanc sur bouton orange.** `#FFFFFF` sur `#FF8A00` = **2,36:1**. Tout CTA « orange plein + libellé blanc » est illisible.
  Pourquoi : `accessibility.md` (contraste 4,5:1) et `color.md › Best practices` : « To emphasize primary actions, apply color to the background rather than to symbols or text ».
  Fix : libellé `#08080E` sur fond `#FF8A00`, **8,45:1**. Ajouter un token `--accent-on: #08080E`.

- **Pas de réponse aux réglages d'accessibilité.** La spec définit `backdrop-filter: blur(40px)` et des animations (respiration, waveform, pulse) sans fallback pour Réduire la transparence, Augmenter le contraste, Réduire les animations.
  Pourquoi : `liquid-glass.md › Review checklist › 5` : « Reduce Transparency gets an opaque fallback, Increase Contrast gets stronger fills and borders, Reduce Motion drops morphing and refraction animation ». Et `liquid-glass.md › Tauri and Electron` : `prefers-reduced-transparency` n'existe pas dans le webview WebKit de Tauri sur macOS, il faut lire `accessibilityDisplayShouldReduceTransparency` côté natif et le passer à la page.
  Fix : trois media queries (`prefers-reduced-motion`, `prefers-contrast: more`) plus un attribut `data-reduce-transparency` posé par le backend ; en fallback, `--bg-glass` devient opaque `#14141C` et les bordures montent à 0.2.

## Améliorations

- **High : le verre est utilisé dans la couche contenu.** La spec met `.glass-panel` sur les cartes météo, calendrier, activité et les bulles de chat. Apple réserve le verre à la couche fonctionnelle (barres, panneaux flottants).
  Pourquoi : `liquid-glass.md › Where the material belongs` : « Don't use Liquid Glass in the content layer ». Et `› Restraint` : « More than the few most important functional elements is a defect ».
  Fix : verre uniquement sur la barre supérieure, la barre de saisie vocale et l'overlay lui-même (sa fenêtre). Les cartes et bulles passent en surfaces opaques `#0D0D15` / `#12121A` avec bordure `rgba(255,255,255,0.08)`. Bonus : `backdrop-filter` sur des cartes au-dessus d'un avatar animé coûte cher en GPU.

- **High : utiliser le matériau natif plutôt qu'une imitation CSS.** La fenêtre overlay doit être une vraie fenêtre vibrancy.
  Pourquoi : `liquid-glass.md › Tauri and Electron` : « Prefer real system materials over CSS imitation » ; Tauri : crate `window-vibrancy` (NSVisualEffectView), Electron : option `vibrancy`. Le matériau natif respecte Réduire la transparence tout seul.
  Fix : overlay = fenêtre transparente + vibrancy `hud-window` ou `under-window`, contenu HTML sans `backdrop-filter`.

- **High : conventions macOS absentes de la spec.** Rien sur la menu bar, les raccourcis clavier, la fenêtre native, les réglages.
  Pourquoi : `designing-for-macos.md › Best practices` : « Use the menu bar to give people easy access to all the commands » ; `windows.md › Best practices` : « Avoid creating custom window UI ». `cross-platform.md › Desktop` : menu natif complet, raccourcis standard, contrôles de fenêtre standard, réglages sous le menu de l'app.
  Fix : app de barre de menus (icône Friday dans la menu bar, menu : Afficher le dashboard, Écouter ⌘⇧F, Mode silencieux, Réglages ⌘,, Quitter). Le dashboard est une fenêtre standard redimensionnable avec feux natifs ; aucune « poignée de drag » custom sur l'overlay, on utilise `-webkit-app-region: drag` sur une zone de titre.

- **Medium : budget couleur orange.** La spec met l'orange sur le glow hover de chaque élément interactif, les bordures actives, le logo, le gradient et les yeux. Un seul sens par couleur.
  Pourquoi : `color.md › Best practices` : « Avoid using the same color to mean different things » et « Refrain from adding color to the background of multiple controls ».
  Fix : orange = les yeux (état de Friday) + une seule action primaire par vue + indicateurs de statut. Hover/focus des contrôles en blanc 0.06 → 0.10, pas en orange. Logo en monochrome blanc 0.95.

- **Medium : taille de police de base et poids.** La spec a `--text-xs: 0.75rem` (12 px) et une font display Space Grotesk sans poids précisé. Minimum macOS 10 pt, défaut 13 pt ; éviter les graisses light.
  Pourquoi : `typography.md › Ensuring legibility` : macOS défaut 13 pt, minimum 10 pt ; « avoid Ultralight, Thin, and Light font weights ».
  Fix : corps à 14 px (`--text-base: 0.875rem`), xs à 12 px réservé aux métriques mono, aucun poids < 400. Garder Inter pour l'UI, Space Grotesk seulement pour la salutation et le logo (brand dans le contenu, pas dans les contrôles).

- **Medium : cibles et espacement.** Les « pills d'actions rapides » de l'overlay (380 px de large) risquent de passer sous 28×28 pt.
  Pourquoi : `accessibility.md` : desktop défaut 28×28 pt, minimum 20×20 pt ; « Consider spacing between controls as important as size », ~12 pt autour d'un élément avec bezel.
  Fix : pills 32 px de haut minimum, 8 px entre elles, max 4 visibles, overflow dans un menu.

- **Medium : aucune info portée par la couleur seule.** Statuts success/warning/error/info sont définis uniquement par couleur, et l'état de Friday par la couleur des yeux (halo rouge = colère).
  Pourquoi : `accessibility.md` : « Convey information with more than color alone ».
  Fix : chaque statut a un symbole (SF Symbols ou Lucide) + libellé ; chaque état d'avatar a une forme d'yeux distincte (c'est déjà le cas dans la table des 18 états, à conserver) et un libellé texte lisible par lecteur d'écran (`aria-live="polite"` sur « Friday écoute »).

- **Low : écran vide et chargement.** Rien n'est dit sur l'état avant le wake word, ni pendant un appel d'outil > 300 ms.
  Jugement (pas de page HIG chargée pour ce point) : l'avatar en état « Chargement » + un texte court « Je vérifie… » suffit ; pas de spinner.

## Notes de craft

- **Point de vue : fort.** Un visage et rien d'autre. C'est ce dont on se souviendra. Tenir la ligne : si un écran a besoin d'un titre « Friday » en plus des yeux, c'est que les yeux ne suffisent pas, et c'est les yeux qu'il faut corriger.
- **Template détecté : partiel.** « Quasi-noir + un accent vif » est l'un des trois looks générés par défaut. Ce qui sauve Friday, c'est que l'accent n'est pas décoratif : l'orange est la couleur des yeux, donc de l'état interne. Retirer l'orange de partout ailleurs (voir budget couleur) rend ce choix lisible.
- **Planche de référence** : les expressions en bleu de `img/avatar-expressions-reference.jpg` fonctionnent bien en forme ; les passer en `#FF8A00` avec un glow `rgba(255,138,0,0.15)` et vérifier qu'En colère garde une forme angulaire sans dépendre du rouge.
- **À retirer** : le gradient `--accent-gradient` (135°, FF8A00 → FF6B00). Deux oranges, aucun sens. Un seul orange.

## Ce qui marche

- Hiérarchie texte en trois niveaux d'opacité : bon principe, seules les valeurs sont à remonter.
- Palette de statut Apple (`#34C759`, `#FFD60A`, `#FF453A`, `#64D2FF`) : toutes passent sur le fond (9,0 / 14,2 / 5,9 / 11,6:1).
- Transitions 300 ms ease-spring entre états des yeux, retour à Neutre après 10 s, priorité Alerte/Erreur : à conserver tel quel.
- Overlay 380×680 compact avec entrée micro en bas : cohérent avec un usage « toujours visible ».

## Notes plateforme

- Tauri 2 sur macOS : webview WebKit, donc `prefers-reduced-transparency` non disponible ; lire le réglage côté Rust/Swift et l'injecter.
- Electron : `vibrancy` natif disponible, `prefers-reduced-transparency` fonctionne dans Chromium.
- Un `backdrop-filter` au-dessus d'un avatar animé en permanence est le pire cas GPU : raison de plus pour ne garder du verre que sur les barres.

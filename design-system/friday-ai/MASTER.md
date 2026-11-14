# Design System : Friday AI (MASTER, v2 monochrome)

> Source de vérité pour toute l'UI. Direction : `docs/friday-ui-prompt-monochrome.md`, corrigée par la revue HIG `docs/revue-design-hig-v2.md`. Remplace la v1 orange du 2026-11-12. Les pages dans `pages/` surchargent ce fichier.
> Tous les contrastes sont calculés (WCAG) sur les valeurs ci-dessous.

## Thèse
Friday est un visage dans le noir. Les yeux LED blancs sont la seule lumière de l'écran : seuls eux ont un halo. Tout le reste est noir, opaque et silencieux. Aucune couleur sauf les trois couleurs de statut Apple, réservées aux alertes système.

## Couleurs

### Surfaces (opaques, profondeur par luminosité)
| Niveau | Usage | Token | Dark | Light |
|---|---|---|---|---|
| 0 | Fond de fenêtre | `--surface-0` | `#000000` | `#F5F5F7` |
| 1 | Panneaux latéraux | `--surface-1` | `#0A0A0A` | `#FFFFFF` |
| 2 | Cartes, bulles Friday | `--surface-2` | `#141414` | `#FFFFFF` |
| 3 | Cartes élevées, bulles utilisateur, boutons | `--surface-3` | `#1C1C1E` | `#F2F2F7` |
| 4 | Menus, popovers, tooltips | `--surface-4` | `#2C2C2E` | `#FFFFFF` |

Hover d'un contrôle : un niveau au-dessus de sa surface. Actif : retour à la surface de base + `scale(0.98)`.

### Texte
| Rôle | Token | Dark | 0 | 1 | 2 | 3 | 4 | Light |
|---|---|---|---|---|---|---|---|---|
| Primaire | `--text-primary` | `#FFFFFF` | 21,0 | 19,8 | 18,4 | 17,0 | 13,9 | `#1D1D1F` (15,5:1) |
| Secondaire | `--text-secondary` | `#999999` | 7,4 | 7,0 | 6,5 | 6,0 | 4,9 | `#515154` (7,9:1) |
| Tertiaire | `--text-tertiary` | `#8C8C8C` | 6,3 | 5,9 | 5,5 | 5,1 | **4,1 ✗** | `#6E6E73` (4,7:1) |
| Désactivé | `--text-disabled` | `#333333` | exempté | | | | | `#C7C7CC` |

Règle : **pas de texte tertiaire sur le niveau 4** (4,1:1). Sur menus et tooltips, utiliser le secondaire.
Placeholders = `--text-tertiary`. Jamais d'opacité sur du texte : des hex opaques uniquement, pour que le contraste ne dépende pas du fond.

### Bordures et focus
| Rôle | Token | Dark | Note |
|---|---|---|---|
| Séparateur | `--divider` | `#1A1A1A` | décoratif |
| Bordure de surface | `--border` | `#262626` | décoratif |
| Bordure de champ | `--border-field` | `#4D4D4D` | 2,5:1, complétée par le fond du champ |
| Focus clavier | `--focus-ring` | `#D9D9D9` | 14,9:1 sur 0, 9,9:1 sur 4 |
| Poignée overlay | `--handle` | `#7A7A7A` | ≥ 3:1 sur niveau 3 |

### Statut (seules couleurs autorisées)
| Rôle | Token | Valeur | 0 | 2 | 4 |
|---|---|---|---|---|---|
| Succès | `--status-success` | `#34C759` | 9,5 | 8,3 | 6,3 |
| Avertissement | `--status-warning` | `#FFD60A` | 14,9 | 13,1 | 9,9 |
| Erreur | `--status-error` | `#FF453A` | 6,2 | 5,4 | **4,1 ✗** |
| Info | `--status-info` | `#999999` | 7,4 | 6,5 | 4,9 |

Règles :
- Une couleur de statut est toujours accompagnée d'une icône et d'un libellé.
- Sur le niveau 4, l'icône garde la couleur mais le libellé passe en `--text-primary`.
- Le rouge signifie erreur système uniquement, jamais une émotion de l'avatar.

### Avatar
| Token | Valeur |
|---|---|
| `--eye` | `#FFFFFF` (opacité 0.95) |
| `--eye-glow` | `rgba(255,255,255,0.20)`, `feGaussianBlur stdDeviation=3` |
| `--helmet` | `#0A0A0A` |
| `--visor` | `#000000` |

Le halo est réservé aux yeux. Aucun autre élément de l'interface ne brille.

### Supprimé par rapport au prompt
- `--bg-glass*` sur cartes, boutons, inputs et bulles : remplacés par les surfaces opaques.
- Les opacités sur le texte : remplacées par des hex.
- La bordure rouge de « En colère ».
- Les bordures de 0,5 px : 1 px partout, 0,5 px seulement sous `@media (min-resolution: 2dppx)`.

## Matériau (Liquid Glass)
- Verre seulement sur 3 éléments de la couche fonctionnelle : top bar du dashboard, barre de saisie vocale, fenêtre overlay.
- Overlay : matériau natif, pas de CSS. Tauri : crate `window-vibrancy`, `NSVisualEffectMaterial::HudWindow`. Electron : `vibrancy: 'hud'`.
- Top bar et barre de saisie (webview) : `background: rgba(28,28,30,0.72); backdrop-filter: blur(24px) saturate(1.4); -webkit-backdrop-filter: blur(24px) saturate(1.4); border: 1px solid #262626;`. Le contenu qui défile passe dessous.
- Aucun verre empilé sur du verre. Aucun verre sur fond #000 pur sans contenu derrière.

## Typographie
- Police : `--font-ui: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;`. Le système choisit SF Pro Text ou Display par taille optique. Ne jamais nommer « SF Pro » dans la pile.
- Mono (heure, métriques, code) : `--font-mono: ui-monospace, 'SF Mono', 'JetBrains Mono', monospace;`.
- Graisses : 400, 500, 600, 700. Jamais en dessous de 400.

| Style | Token | Taille / interligne | Graisse | Usage |
|---|---|---|---|---|
| Title 1 | `--type-title1` | 28 / 34 | 700 | Salutation |
| Title 2 | `--type-title2` | 22 / 28 | 600 | Température, titres de section |
| Headline | `--type-headline` | 15 / 20 | 600 | Titres de widgets |
| Body | `--type-body` | 15 / 22 | 400 | Texte, bulles, input |
| Callout | `--type-callout` | 14 / 20 | 400 | Navigation |
| Caption | `--type-caption` | 12 / 16 | 500 | Labels, pills, noms d'états |
| Mono | `--type-mono` | 13 / 18 | 500 | Horloge, valeurs système |

Plancher : 12 px. Le minimum macOS est 10 pt, Friday reste au-dessus pour une lecture à distance.
Logo « FRIDAY » : 15 px, 600, tracking 0.12em, majuscules, `--text-secondary`. Il ne concurrence pas les yeux.

## Icônes
- Lucide en SVG, `stroke-width: 1.5`, 20 px (16 px en caption), `currentColor`. Jamais d'emoji.
- Actions rapides : `zap`, `folder`, `search`, `settings`. Pills overlay : `bell`, `check-square`, `sticky-note`.
- Statut top bar : `wifi` / `wifi-off`, `mic` / `mic-off`, `cpu`. Chaque icône a un `aria-label` et une infobulle.
- Tout bouton icône a un libellé visible ou un `aria-label`.

## Espacement, rayons, cibles
- Échelle : 4 · 8 · 12 · 16 · 24 · 32 · 48.
- Rayons : 8 boutons et pills compacts · 12 inputs et cartes · 16 bulles · 20 barres en verre et overlay · 999 dots.
- Bulles : Friday `16 16 16 4`, utilisateur `16 16 4 16`.
- Cibles : 28×28 pt par défaut, 20×20 minimum (macOS). Boutons 36 px de haut, pills 32 px, 8 px d'écart minimum.

## Mouvement
| Token | Valeur |
|---|---|
| `--ease-default` | `cubic-bezier(0.25,0.1,0.25,1)` |
| `--ease-smooth` | `cubic-bezier(0.4,0,0.2,1)` |
| `--ease-spring` | `cubic-bezier(0.175,0.885,0.32,1.275)` |
| `--dur-instant` | 100 ms (press) |
| `--dur-fast` | 200 ms (hover, focus) |
| `--dur-normal` | 300 ms (changement d'état des yeux) |
| `--dur-slow` | 500 ms (apparition de fenêtre) |

- Transitions limitées à `background-color, border-color, color, opacity, transform`. Jamais `transition: all`.
- Avatar : `transform` et `opacity` uniquement, `will-change: transform` sur les yeux, 60 fps.
- Idle : clignement 4 s + respiration scale 1 → 1.02 sur 6 s.
- Waveform d'écoute : 30 barres 2 px, gap 3 px, `--text-primary`, hauteur pilotée par le niveau audio.
- Grille d'expressions : pose statique par défaut, animation au survol ou au focus de la cellule, ou via un bouton « Tout animer ».

## Accessibilité (obligatoire)
- `:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }` sur tout élément interactif. Jamais `outline: none` sans remplacement.
- L'état de Friday est toujours écrit sous l'avatar, dans une région `aria-live="polite"` : « À l'écoute », « Je réfléchis », « Hors ligne », etc.
- `@media (prefers-reduced-motion: reduce)` : plus de vibration, rotation, flash ni clignotement rapide. Changement d'état en fondu de 150 ms, waveform remplacée par un indicateur statique « À l'écoute ».
- `@media (prefers-contrast: more)` : `--text-tertiary: #B3B3B3` (10,0:1), `--border: #4D4D4D`, `--divider: #333333`.
- Réduire la transparence : sur Tauri/macOS, lire `NSWorkspace.accessibilityDisplayShouldReduceTransparency` côté natif et poser `data-reduce-transparency` sur `<html>`. Le verre devient `--surface-3` opaque. Sur Electron, utiliser `prefers-reduced-transparency`.
- Navigation complète au clavier, ordre de tabulation : top bar, navigation, saisie, actions, widgets.

## Conventions macOS
- App de barre de menus (`ActivationPolicy::Accessory`, pas d'icône Dock). Menu : Afficher le dashboard · Écouter ⌘⇧F · Mode silencieux ⌘⇧M · Réglages… ⌘, · Quitter Friday ⌘Q.
- Dashboard : fenêtre standard redimensionnable, feux natifs, titre masqué, pas de chrome custom.
- Overlay : `tauri-nspanel` pour rester visible au-dessus des apps plein écran. La zone de drag est une bande de 28 px en `-webkit-app-region: drag`, avec la poignée 40×4 px au centre.
- Réglages dans une fenêtre dédiée, pas dans le dashboard.
- L'app suit l'apparence système, sans bascule clair/sombre interne. La version claire existe via les tokens Light.

## Layouts

### Dashboard (1280–1920 px)
```
┌──────────────────────────────────────────────────────────────┐
│ ●●● (feux)  FRIDAY        14:32         [wifi][mic][cpu]      │ top bar 52 px, verre
├──────────┬──────────────────────────────────┬────────────────┤
│ Nav 240  │            (avatar 180)          │ Widgets 300    │
│ surface-1│     État : « À l'écoute »        │ surface-2      │
│          │      Bonjour, Thaïne.            │ Météo          │
│ ──────── │  ┌────────────────────────┐ [mic]│ Agenda         │
│ CPU ▓▓░  │  │ Parle-moi…             │      │ Activité       │
│ RAM ▓░░  │  └────────────────────────┘      │                │
│ Disque   │  [zap] [folder] [search] [gear]  │                │
└──────────┴──────────────────────────────────┴────────────────┘
```
- < 1280 px : la colonne widgets passe sous le centre. < 960 px : la navigation devient une barre d'icônes de 56 px.
- Barres système : piste `--surface-3`, remplissage `--text-secondary`, valeur en mono, libellé caption tertiaire. Au-delà du seuil d'alerte, le remplissage passe en couleur de statut et une icône s'ajoute.
- Widget Activité : 6 barres avec le jour en caption dessous et la valeur au survol. Sinon on le retire.
- Une seule ligne de salutation. Le placeholder porte l'invitation.

### Overlay (380×680, fixe)
```
┌────────────────────────────┐
│          ────              │ bande de drag 28 px
│        (avatar 80)         │
│   Friday · ● En ligne      │ icône + texte
│ ┌────────────────────────┐ │
│ │ [bulle Friday surf-2]  │ │ fil scrollable
│ │      [bulle user surf-3]│ │
│ └────────────────────────┘ │
│ [bell Rappel] [✓ Tâche] [⋯]│ 3 pills max + Plus
│ ┌──────────────────┐ [mic] │ saisie en verre
└────────────────────────────┘
```

### Grille d'expressions (1440×720)
- 6×3, gap 20, padding 40. Cellules `--surface-2` de 160×160, rayon 12, sans verre.
- Nom de l'état en caption secondaire sous l'avatar.
- La cellule est un bouton focusable qui joue l'animation au focus.

## Avatar : adaptations des 18 états
- Les formes de la planche `img/avatar-expressions-reference.jpg` passent du bleu au blanc. Les cœurs rouges de « Amour » deviennent blancs.
- « En colère » se lit par les sourcils angulaires et le tremblement, sans rouge.
- « Alerte » et « Erreur » gardent la priorité. Avec reduced motion, leur clignotement et leur flash deviennent statiques.
- Rendu : SVG inline pour démarrer. Rive est possible plus tard avec une state machine à une entrée `eyeState` (0–17).

## Checklist avant livraison
- [ ] Aucun texte en opacité, uniquement des hex opaques
- [ ] Pas de texte tertiaire ni de libellé rouge sur le niveau 4
- [ ] Verre limité à la top bar, la saisie et l'overlay natif
- [ ] Aucun emoji, icônes Lucide 1.5 avec libellés
- [ ] `:focus-visible` présent partout
- [ ] Reduced motion, contrast et transparency testés
- [ ] Menu bar complet et raccourcis fonctionnels
- [ ] Dashboard testé à 960, 1280, 1440 et 1920 px
- [ ] Avatar à 60 fps avec la grille ouverte

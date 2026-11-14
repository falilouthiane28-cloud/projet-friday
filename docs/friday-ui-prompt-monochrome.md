# FRIDAY AI — System Prompt UI/UX (monochrome)

> Prompt fourni par l'utilisateur le 2026-11-13. Remplace la direction orange de la spec v1 (section 5). Revue HIG : `docs/revue-design-hig-v2.md`.

Tu es un développeur frontend expert. Tu vas construire l'interface de **FRIDAY**, un assistant IA personnel toujours actif sur desktop, inspiré de J.A.R.V.I.S. (Iron Man). L'interface suit **strictement** le design system Apple (Liquid Glass, SF Pro, hiérarchie de profondeur) dans une palette **noir et blanc uniquement**.

## 1. DESIGN SYSTEM — Apple Monochrome Liquid Glass

### Palette (STRICTE — noir, blanc, transparent uniquement)

```css
:root {
  --bg-primary: #000000;
  --bg-secondary: #0A0A0A;
  --bg-tertiary: #111111;
  --bg-glass: rgba(255, 255, 255, 0.04);
  --bg-glass-hover: rgba(255, 255, 255, 0.08);
  --bg-glass-active: rgba(255, 255, 255, 0.12);

  --text-primary: #FFFFFF;
  --text-secondary: rgba(255, 255, 255, 0.60);
  --text-tertiary: rgba(255, 255, 255, 0.35);
  --text-disabled: rgba(255, 255, 255, 0.20);

  --border-glass: rgba(255, 255, 255, 0.08);
  --border-hover: rgba(255, 255, 255, 0.15);
  --border-active: rgba(255, 255, 255, 0.25);
  --divider: rgba(255, 255, 255, 0.06);

  --status-success: #34C759;
  --status-warning: #FFD60A;
  --status-error: #FF453A;
  --status-info: rgba(255, 255, 255, 0.60);

  --eye-color: #FFFFFF;
  --eye-glow: rgba(255, 255, 255, 0.20);
  --eye-bright: rgba(255, 255, 255, 0.95);

  --font-display: 'SF Pro Display', 'Inter', -apple-system, sans-serif;
  --font-body: 'SF Pro Text', 'Inter', -apple-system, sans-serif;
  --font-mono: 'SF Mono', 'JetBrains Mono', monospace;

  --ease-default: cubic-bezier(0.25, 0.1, 0.25, 1);
  --ease-spring: cubic-bezier(0.175, 0.885, 0.32, 1.275);
  --ease-smooth: cubic-bezier(0.4, 0, 0.2, 1);
  --duration-instant: 100ms;
  --duration-fast: 200ms;
  --duration-normal: 350ms;
  --duration-slow: 500ms;
}
```

**Règle absolue** : si un élément n'est pas noir, blanc ou transparent, il n'a pas sa place, sauf les 3 couleurs de statut Apple (vert, jaune, rouge) réservées aux alertes système.

### Effets Liquid Glass

```css
.glass-panel {
  background: rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(40px) saturate(150%);
  -webkit-backdrop-filter: blur(40px) saturate(150%);
  border: 0.5px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 0.5px 0 rgba(255, 255, 255, 0.06);
}
.glass-elevated {
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(60px) saturate(180%);
  border: 0.5px solid rgba(255, 255, 255, 0.12);
  border-radius: 24px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5), inset 0 0.5px 0 rgba(255, 255, 255, 0.08);
}
.glass-button {
  background: rgba(255, 255, 255, 0.08);
  border: 0.5px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px; color: #FFFFFF;
  font: 500 15px/20px var(--font-body);
  padding: 10px 20px;
  transition: all 200ms var(--ease-smooth); cursor: pointer;
}
.glass-button:hover { background: rgba(255,255,255,0.14); border-color: rgba(255,255,255,0.20); }
.glass-button:active { background: rgba(255,255,255,0.06); transform: scale(0.98); }
.glass-input {
  background: rgba(255, 255, 255, 0.04);
  border: 0.5px solid rgba(255, 255, 255, 0.10);
  border-radius: 12px; color: #FFFFFF; caret-color: #FFFFFF;
  font: 400 17px/24px var(--font-body); padding: 12px 16px;
}
.glass-input:focus { outline: none; border-color: rgba(255,255,255,0.30); box-shadow: 0 0 0 3px rgba(255,255,255,0.06); }
```

### Hiérarchie de profondeur

| Niveau | Usage | Opacité bg | Blur | Border |
|---|---|---|---|---|
| 0 | Fond | #000000 | — | — |
| 1 | Surface | 0.04 | 20px | 0.06 |
| 2 | Panneau | 0.06 | 40px | 0.08 |
| 3 | Carte élevée | 0.08 | 60px | 0.10 |
| 4 | Modal/Overlay | 0.10 | 80px | 0.12 |
| 5 | Tooltip | 0.14 | 20px | 0.15 |

## 2. AVATAR

Robot au casque sombre, costume noir, **yeux LED blancs**, SVG animé. 18 états (forme des yeux · animation · déclencheur) :

| État | Yeux | Animation | Déclencheur |
|---|---|---|---|
| Neutre | Rectangles arrondis (rx 4) | Clignement 4 s | Défaut |
| Joyeux | Arcs vers le haut | Pulse doux | Tâche réussie |
| Amour | Cœurs | Scale 1→1.1 | Compliment |
| Excité | Étoiles 5 branches | Vibration ±2px | Bonne nouvelle |
| Pensif | Réduits, décalés à droite | Gauche-droite lent | Recherche |
| Confus | Tailles asymétriques | Rotation ±5° | Requête ambiguë |
| Endormi | Lignes horizontales | Breathing 1→1.02 (6 s) | Veille |
| En colère | Sourcils angulaires, yeux réduits | Tremblement, bordure rouge | Sécurité violée |
| Triste | Arcs tombants, regard bas | Pulsation lente, opacité réduite | Échec |
| Chargement | Barre de progression | Remplissage en boucle | Tâche longue |
| Alerte | Triangle d'exclamation | Clignotement blanc→dim | Alerte système |
| Clin d'œil | Un fermé, un ouvert | 150 ms + retour | Confirmation |
| Surpris | Grands cercles | Scale 1→1.3 | Inattendu |
| Étourdi | Spirales | Rotation 360°/2 s | Erreur système |
| Timide | Réduits, bas | translateY +3px | Gêne |
| Cool | Lunettes (rects larges) | Reflet en gradient | Détente |
| Erreur | X | Flash opacité | Crash |
| Écoute | Dilatés | Au rythme audio | Écoute vocale |

SVG de base : viewBox 200×200, casque `path` #0A0A0A, visière `rect` 90×45 rx 12 #000, yeux `rect` 22×18 rx 4 blancs opacité 0.95 avec `<animate>` de clignement 4 s, filtre `eye-glow` (feGaussianBlur 3).

Transitions : 300 ms ease-spring ; pas Endormi → En colère direct ; Alerte et Erreur prioritaires ; retour Neutre après 10 s ; Écoute immédiate au wake word.

## 3. DASHBOARD (1440×900), fond #000

- Top bar 56 px glass niveau 1 : logo « FRIDAY » (display 18 px semibold, tracking 0.12em, majuscules) · horloge mono 15 px text-secondary · 3 dots online/mic/system (blanc = actif, 0.20 = inactif).
- Gauche 260 px glass niveau 2, padding 16 : nav icônes + labels 15 px text-secondary (hover text-primary + glass-hover), séparateur divider, stats système (labels caption1 text-tertiary, barres piste 0.06 / fill 0.60, valeurs mono).
- Centre : avatar 180×180 + eye-glow ; « Bonjour, Thaïne. » title1 display bold ; « Comment puis-je vous aider ? » body text-secondary ; glass-input max 500 px, placeholder text-tertiary, micro à droite ; waveform 30 barres 2 px gap 3 ; 4 quick actions glass-button `[⚡][📁][🔍][⚙️]` + labels caption1.
- Droite 300 px glass niveau 2 : widgets glass-panel gap 12 (météo title2, calendrier heure mono + titre body, activité mini bar-chart 6 barres blanches).

## 4. OVERLAY (380×680), glass niveau 3, draggable

Drag handle 40×4 px 0.20 · avatar 80×80 · « Friday » + dot « En ligne » · chat : bulle Friday glass 0.06 radius 16/16/16/4 text-secondary, bulle user glass 0.10 radius 16/16/4/16 text-primary, scrollbar 4 px 0.15 · pills [Rappel][Tâche][Note] (8×14 px caption1, rangée scrollable) · input glass + micro 24×24 pulsant à l'écoute.

## 5. GRILLE D'EXPRESSIONS (1440×720)

6×3, gap 20, padding 40 ; cellule glass-panel 160×160 avec avatar animé en continu + nom en caption. Rangées : Neutre, Joyeux, Amour, Excité, Pensif, Confus / Endormi, En colère, Triste, Chargement, Alerte, Clin d'œil / Surpris, Étourdi, Timide, Cool, Erreur, Écoute.

## 6. STACK

Electron ou Tauri ; HTML/CSS/JS vanilla ou React/Svelte ; avatar SVG inline CSS/SMIL ; SF Pro → Inter, SF Mono → JetBrains Mono ; icônes style SF Symbols stroke 1.5 ; pas de librairie UI.

## 7. RÈGLES

1. Noir et blanc strict (sauf vert/jaune/rouge statut).
2. Apple-first : chaque composant ressemble à une app Apple native en dark mode.
3. Glass everywhere : panneaux, cartes, boutons, inputs.
4. Animations intentionnelles uniquement.
5. Échelle Apple Dynamic Type ; titres SF Pro Display bold, corps SF Pro Text regular.
6. Profondeur par luminosité (plus élevé = plus clair + plus de blur).
7. Dashboard 1280–1920 px ; overlay taille fixe draggable.
8. Avatar 60 fps, `will-change` + `transform`.
9. Contraste 4.5:1 texte courant, focus visible (ring blanc).
10. Variables CSS partout, pas de valeurs magiques.

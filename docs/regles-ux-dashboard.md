# Règles UX du dashboard et de la bulle

> 2026-11-14. Règles du chantier « UX premium » de `voice/Sources/FridayApp/`. Source de vérité visuelle : `design-system/friday-ai/MASTER.md`. Références HIG lues via le skill apple-design : `sidebars.md`, `toolbars.md`, `panels.md`, `liquid-glass.md`.

## Organisation du travail (agents)
- **Agent principal** : la session qui code. Il lit `ai.md`, suit `regle.md`, puis ce fichier.
- **Sous-agents** (définis dans `.claude/agents/`) :
  - `friday-ux-reviewer` (lecture seule) : audite une vue SwiftUI selon MASTER.md et la HIG, puis rend des constats chiffrés ;
  - `friday-swiftui-builder` : implémente une vue isolée, compile et rend un `--snapshot`.
- On ne lance un sous-agent que sur demande explicite (`regle.md` §3). Dans la session du 14/11, le classifieur a refusé leur lancement : le travail a été fait par l'agent principal.

## Règles
1. **Une seule lumière** : seuls les yeux de l'avatar brillent. Tout le reste est noir, opaque et monochrome. La couleur est réservée aux statuts (jaune ≥ 90 %, rouge en cas d'erreur), toujours accompagnée d'une icône.
2. **Le verre ne va que sur les barres** : barre d'outils système, barre de saisie et fenêtre de la bulle. Les cartes restent opaques (surface 2, bord #262626, rayon 12).
3. **Aucune donnée factice** : chaque carte affiche une donnée réelle, sinon un état de chargement, sinon la raison de l'absence (« Accès au Calendrier refusé… »). Ne jamais afficher « Données de démonstration ».
4. **Chaque contrôle mène quelque part**. Sinon, on le retire. Les suggestions de l'accueil envoient une vraie demande et ouvrent Conversations, où la réponse s'affiche.
5. **Bulle et dashboard ne se superposent jamais.** Quand le dashboard est au premier plan (app active, fenêtre visible, non réduite), la bulle disparaît en fondu de 150 ms. Elle revient dès que le dashboard est fermé, réduit, ou que l'app passe en arrière-plan. Les cartes de confirmation et le raccourci global vont alors vers la section Conversations du dashboard.
6. **La barre d'outils sert aux actions, pas à l'information** (`toolbars.md`). L'horloge est sortie de la barre d'outils : la date et l'heure s'affichent au-dessus de l'avatar.
7. **La barre latérale reste à un seul niveau**, avec des SF Symbols et des raccourcis ⌘1 à ⌘6. Les jauges système vont en pied : elles ne sont pas critiques (`sidebars.md` › Desktop).
8. **Accessibilité** : chaque bouton icône a un libellé, chaque tuile se lit comme un seul élément (titre + valeur + détail), les mouvements sont réduits quand l'utilisateur l'a demandé (fondu de la bulle coupé), et le texte tertiaire n'est jamais posé sur la surface 4.
9. **Vérification** : `swift build -c release`, `swift run friday-voice-checks`, `.venv/bin/pytest`, `friday-app --snapshot <dossier>` (les sections sont rendues une à une, car ImageRenderer ne rend ni NavigationSplitView ni ScrollView), `friday-app --dashboard [section]` en réel. `screencapture` donne un écran noir tant que l'Enregistrement de l'écran n'est pas autorisé.

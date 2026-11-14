# Règles de travail

## 1. Mise à jour des fichiers de suivi
À chaque grosse modification (nouvelle fonctionnalité, changement de structure, décision importante) :
1. `progress.md` — ajouter une entrée datée.
2. `memory.md` — ajouter les faits/décisions durables.
3. `projet.md` — mettre à jour stack, structure ou décisions si elles ont changé.
Ne pas réécrire les fichiers entiers : ajouter ou modifier seulement les lignes concernées.

## 2. Bascule de session à 70 % de contexte
Quand le contexte de la session atteint environ 70 % :
1. Mettre à jour `progress.md` (section « En cours » : état exact, prochaine étape précise).
2. Mettre à jour `memory.md` avec les faits appris dans la session.
3. Dire à l'utilisateur : « Contexte à 70 %, fichiers à jour, ouvrir une nouvelle session. »
4. La nouvelle session démarre en lisant `ai.md` uniquement (qui pointe vers les autres fichiers).

## 3. Économie de tokens
- Lire `ai.md` au démarrage, puis seulement les fichiers nécessaires à la tâche.
- Ne jamais relire un fichier déjà lu dans la session sauf s'il a changé.
- Réponses courtes, pas de récapitulatif redondant.
- Pas de sous-agents sauf demande explicite.

## 4. Langue
Tout en français (fichiers, commits, réponses).

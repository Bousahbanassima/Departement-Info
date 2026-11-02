# Analyse et conception — première tranche

## Hypothèses à valider

L'université doit confirmer les rôles et délégations réelles, les niveaux de confidentialité, les règles de justification, les délais, les textes disciplinaires, les catégories de décisions, les modèles officiels, les obligations de protection des données et les durées de conservation. Le prototype ne fixe aucun seuil d'absence ni conséquence et ne prononce aucune sanction. Un changement de statut n'est pas une décision officielle. Les données sont fictives.

## Matrice des droits effectivement implémentés

| Fonction | Admin | Chef | Adjoint | Scolarité | Enseignant | Étudiant | Examens | Commission |
|---|---|---|---|---|---|---|---|---|
| Tableau de bord | global | global | global | global | personnel | personnel | global pédagogique | limité |
| Étudiants : lecture | tous | tous | tous | tous | groupes enseignés | soi | tous | non |
| Étudiants : création | oui | oui | oui | oui | non | non | non | non |
| Enseignants : lecture | tous | tous | tous | tous | soi | non | tous | non |
| Enseignants : création | oui | oui | oui | oui | non | non | non | non |
| Séances : lecture | toutes | toutes | toutes | toutes | propres | groupe | toutes | non |
| Absences étudiantes : lecture | toutes | toutes | toutes | toutes | propres séances | soi | toutes | non |
| Absences étudiantes : création/correction | oui | oui | oui | oui | propres séances | non | non | non |
| Justificatifs : lecture/décision | oui | oui | oui | oui | non | lecture/dépôt personnel | non | non |
| Absences enseignants : lecture/déclaration | toutes | toutes | toutes | toutes | soi | non | non | non |
| Absences enseignants : changement d’état | oui | oui | oui | oui | non | non | non | non |
| Récupération : proposition | oui | oui | oui | oui | soi | non | non | non |
| Récupération : validation/réalisation | oui | oui | oui | oui | non | non | non | non |
| Discipline : création | oui | oui | oui | non | non | non | non | non |
| Discipline : lecture/suivi | tous | tous | tous | non | non | non | non | attribués |
| Journal d'audit | oui | non | non | non | non | non | non | non |
| Notifications | personnelles | personnelles | personnelles | personnelles | personnelles | personnelles | personnelles | personnelles |

Il s'agit d'une matrice de prototype codée en dur, pas d'un RBAC configurable à permissions granulaires. Les accès aux dossiers par les responsables administratifs sont globaux dans cette démonstration ; un modèle de délégation et d'attribution plus fin est nécessaire avant un usage réel.

## Workflows réalisés

1. Un enseignant ou agent autorisé déclare une absence pour un étudiant du groupe de la séance ; l'unicité étudiant/séance/date est imposée. Une notification est créée si l'étudiant possède un compte lié.
2. L'étudiant dépose un justificatif pour une absence non justifiée. Le statut passe en attente et la scolarité reçoit une notification. Un agent autorisé accepte ou refuse avec motif ; l'absence devient respectivement justifiée ou non justifiée et l'étudiant est notifié. Les décisions précédentes restent en base.
3. Un responsable ouvre un dossier et l'attribue à un membre de commission. Le membre attribué ou un responsable peut modifier le statut avec motif ; l'historique et un audit sont conservés. Une notification neutre est envoyée au membre. Il n'y a ni décision automatique ni processus officiel complet.

4. Une absence étudiante peut être annulée puis rétablie par un utilisateur habilité, avec motif et historique. L’annulation est bloquée si un justificatif existe, pour éviter de modifier silencieusement une procédure engagée. Une absence annulée est exclue des statistiques et des demandes de justificatif.
5. L’enseignant déclare une séance non assurée pour ses propres séances, ou un agent administratif enregistre une situation constatée. Une récupération est proposée, contrôlée contre les conflits connus, validée administrativement et enregistrée comme effectuée après réalisation. Chaque transition est historisée. Ce workflow ne vaut pas validation de justificatif médical ni modification de l’emploi du temps.

## Modèle et architecture

`schema.sql` est la source de vérité du schéma initial SQLite. Les tables `users`, `groups`, `students`, `teachers`, `sessions`, `absences`, `justifications`, `teacher_absences`, `discipline`, `discipline_history`, `notifications`, `audit` possèdent des clés primaires et des clés étrangères activées à chaque connexion. Les relations à données importantes utilisent `RESTRICT` ou le comportement `NO ACTION`, pas de suppression en cascade. Les matricules, noms de comptes, références disciplinaires et triplets d'absence sont uniques. Les migrations SQL versionnées dans `migrations/` ajoutent notamment les corrections, événements et récupérations ; `schema_migrations` suit leur application. Il n’existe pas encore de mécanisme d’archivage.

L'application Flask rend les pages Jinja et valide les opérations sur le serveur. SQLite stocke les données ; les pièces sont privées dans `instance/uploads/`. Les mots de passe sont hachés par Werkzeug, les requêtes SQL paramétrées, les templates échappés par défaut et les formulaires protégés par jeton CSRF. Les sessions sont signées, avec cookies HttpOnly et SameSite. Ces mesures constituent un socle, non une garantie de conformité ou de sécurité de production.

## Étapes suivantes recommandées

1. Valider les procédures et la matrice d'habilitations avec l'université ; définir les règles et paramètres sans automatiser les sanctions.
2. Mettre en place PostgreSQL et des migrations adaptées, une gestion des comptes et permissions granulaires, la limitation des connexions, le durcissement des sessions, l'audit complet et le stockage chiffré.
3. Compléter les dossiers et workflows prioritaires (corrections des absences avec justificatif, pièces, validations, attributions fines, historique disciplinaire consultable), puis les emplois du temps et la détection de conflits.
4. Ajouter examens, charges, documents, exports, sauvegardes et tests de restauration, puis effectuer tests d'intégration, revue de sécurité et validation institutionnelle.

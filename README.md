# InfoDept — socle de démonstration

InfoDept est un **prototype fonctionnel à données fictives**, pas une application prête pour les données réelles de l’UHBC. Il couvre une première tranche des besoins ; les fonctions manquantes ci-dessous ne doivent pas être considérées comme livrées. Les noms, dossiers et situations sont fictifs. Aucun seuil ni sanction n'est calculé automatiquement.

## Démarrage local

Python 3.11+ :

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Ouvrir http://localhost:5000. La base SQLite et les pièces déposées sont créées dans `instance/`. Au premier démarrage seulement, le schéma et les données fictives sont initialisés. Pour réinitialiser la démonstration, arrêter le serveur puis supprimer le fichier `instance/infodept.db` et le contenu de `instance/uploads/`.

Comptes fictifs : `admin`, `chef`, `adjoint`, `scolarite`, `enseignant`, `etudiant`, `examens`, `commission` ; mot de passe temporaire commun **`demo1234`**. Ces identifiants sont strictement réservés au développement. La démo ne permet pas de changer les mots de passe. Aucun compte de démo ne doit être utilisé en production.

Alternative : `docker compose up --build`, puis http://localhost:5000. Le volume `infodept-data` conserve la base et les fichiers. `docker compose down -v` efface ce volume.

## Guide rapide

- **Administration / scolarité** : ouvrir Étudiants pour rechercher ou ajouter une fiche ; Absences étudiantes pour enregistrer une absence ; Justificatifs pour accepter ou refuser une demande avec motif. Le tableau de bord et les notifications reflètent les données en base.
- **Enseignant** : consulter son profil, ses groupes, ses séances et les absences de ses séances ; déclarer une absence pour un étudiant du groupe correspondant. La déclaration vérifie l'affectation de l'enseignant, le groupe et les doublons. Une erreur peut être annulée ou rétablie avec motif obligatoire et historique. Une absence liée à un justificatif ne peut pas être annulée dans ce prototype. Dans Absences enseignants, déclarer une séance non assurée et proposer une récupération ; seul le personnel administratif peut la valider ou la marquer effectuée.
- **Étudiant** : consulter son propre dossier, son planning et ses absences ; déposer un motif et éventuellement une pièce PDF/PNG/JPEG pour une absence non justifiée. Suivre la décision et les notifications.
- **Chef / adjoint / administrateur** : ouvrir un dossier disciplinaire, l'attribuer à un membre de commission et mettre à jour son suivi avec un motif. Un membre de commission ne voit que les dossiers qui lui sont attribués. Ces opérations ne constituent pas une décision officielle.
- **Administrateur** : consulter le journal d'audit. Déconnexion depuis l'icône en haut à droite.

Les pièces sont stockées hors du répertoire statique, sous un nom aléatoire, et servies après contrôle d'accès. Taille maximale de requête : 5 Mo ; une signature PDF, PNG ou JPEG est exigée. Ceci ne remplace pas un contrôle antivirus ni une validation approfondie du contenu.

## Périmètre effectif et limites

**Opérationnel dans cette démonstration :** connexion par session ; contrôle de rôle côté serveur sur les routes ; listes d'étudiants et enseignants ; ajout et recherche d'étudiants, ajout d'enseignants ; consultation de séances ; création, filtrage et correction tracée d'absences étudiantes ; déclaration et suivi d'absences enseignants et de récupérations avec détection de conflits limitée ; dépôt et décision de justificatifs avec téléchargement protégé ; notifications internes ; création, attribution, consultation et changement de statut de dossiers disciplinaires ; audit des actions implémentées. Les indicateurs affichés proviennent de la base et sont limités aux données visibles du rôle.

**Partiel :** fiches enseignants sans modification ni archivage ; absences enseignants sans pièces justificatives ni validation documentaire ; emploi du temps hebdomadaire en lecture seule ; dossier disciplinaire limité à une description et un statut ; pas de vue de l'historique disciplinaire dans l'interface, bien que les changements de statut soient enregistrés. Les dates des absences étudiantes ne sont pas contrôlées contre le jour hebdomadaire ; le planning de démonstration n'est pas un calendrier institutionnel. Les rôles sont codés dans l'application et ne sont pas administrables ; le rôle « examens » a uniquement les accès de consultation pédagogique prévus dans la matrice.

**Non implémenté :** modification/archivage des fiches, import, pagination, filtre par période, modification de date/séance d'une absence, correction d'une absence liée à un justificatif, demande d'informations complémentaires, pièces justificatives enseignants, remplacements, édition des emplois du temps et détection complète de conflits, gestion complète des pièces/séances/décisions/recours disciplinaires, examens et notes, charges, secrétariat documentaire, modèles, exports PDF/Excel, emails, gestion des comptes, sauvegardes automatiques, API REST, PostgreSQL et intégration SSO. Aucun bouton ne prétend fournir ces opérations.

## Conception, hypothèses et sécurité

Voir [docs/CONCEPTION.md](docs/CONCEPTION.md) pour la matrice effective, les workflows, le schéma et les ambiguïtés institutionnelles. Le socle utilise Flask et SQLite plutôt que Next.js/FastAPI/PostgreSQL pour fournir une application simple à démarrer et testable ; ce choix est adapté à une démonstration mono-instance, pas au déploiement multi-utilisateur institutionnel. Le schéma initial et les migrations SQL versionnées sont appliqués au démarrage, en conservant les données. Il n'y a pas d'API publique documentée : le serveur rend les pages HTML et traite les formulaires.

**Ne pas déployer en production ni saisir de données réelles.** La démo utilise des comptes et un secret par défaut, ne dispose pas de limitation des tentatives de connexion, de rotation/révocation complète des sessions, de scan antivirus, de chiffrement au repos, d'une politique de rétention ou d'une gestion des habilitations suffisamment granulaire. Le stockage local et l'audit ne sont pas durcis contre un administrateur système. Les pièces sensibles ne doivent pas y être déposées. La conformité à la réglementation algérienne et aux règles UHBC doit être étudiée et validée avec les responsables compétents avant tout usage réel. `ALLOW_EMBED=1` désactive la protection contre l'intégration en iframe pour l'aperçu uniquement.

Le service Flask intégré n'est pas un serveur de production. Un futur déploiement nécessite notamment HTTPS via un proxy, `HTTPS_ONLY=1`, un secret fort externe, des identifiants uniques, une base PostgreSQL et ses migrations, des sauvegardes chiffrées et testées, un stockage privé et des contrôles de sécurité et d'habilitation supplémentaires. `.env.example` documente les variables disponibles ; elles doivent être chargées par l'environnement (le fichier n'est pas chargé automatiquement).

## Tests

```sh
.venv/bin/pytest -q
```

Les tests couvrent les accès par rôle, l'isolation des étudiants, l'accès de la commission, le contrôle CSRF, la saisie et les doublons d'absences, les corrections, le cycle de décision d'un justificatif, les récupérations et la migration d'une ancienne base. Ils ne constituent pas un audit de sécurité complet.

## Sauvegarde de développement

Arrêter le serveur avant de copier ensemble `instance/infodept.db` et `instance/uploads/` dans un emplacement privé. Pour restaurer, arrêter le serveur, replacer les deux éléments, puis redémarrer et vérifier le contenu. Une procédure institutionnelle devra inclure chiffrement, contrôle des accès, conservation et tests réguliers de restauration. Ne jamais sauvegarder une base active par simple copie sans procédure cohérente.

## Séances non assurées et récupérations : règles et limites

La déclaration d'une séance non assurée est unique par séance et date ; pour les nouvelles déclarations, la date doit correspondre au jour hebdomadaire de la séance. L'enseignant ne peut déclarer et consulter que ses séances. L'administration peut enregistrer une séance constatée et changer son état avec motif. « Justifiée » est un état saisi manuellement : cette version ne permet pas de déposer ou vérifier de justificatif enseignant. Ne saisissez pas d'informations médicales dans les motifs.

Une récupération est proposée pour une absence donnée, sans modifier l'emploi du temps. Une personne administrative la passe de « Proposée » à « Programmée », puis, après réalisation, à « Effectuée ». Une proposition peut être annulée par l'enseignant concerné ; l'administration peut annuler une proposition ou une séance programmée. Les actions nécessitent un motif et sont historisées. Une seule récupération non annulée est admise par absence. Les conflits sont vérifiés à la proposition et à la validation pour l'enseignant, le groupe et la salle, sur les séances hebdomadaires et les récupérations non annulées. La comparaison des salles est textuelle, sans référentiel ni gestion des capacités ; les jours fériés, disponibilités, sous-groupes, annulations ponctuelles et changements futurs de planning ne sont pas modélisés. Les propositions ne sont pas visibles dans la page de l'emploi du temps. Les horaires de l'emploi du temps initial sont considérés valables toutes les semaines, ce qui peut produire des conflits à vérifier manuellement.

Les migrations sont dans `migrations/` et sont appliquées une seule fois, dans une transaction par fichier, au démarrage. **Sauvegardez d'abord la base et les pièces.** La migration `001` ajoute un index d'unicité sur les absences enseignants : si une ancienne base contient déjà plusieurs lignes pour la même séance et date, elle échouera sans appliquer cette migration ; analyser et résoudre ces doublons avant de réessayer. Elle ne supprime aucune ligne.

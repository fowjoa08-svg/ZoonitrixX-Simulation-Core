# ZOONITRIX X — Manifeste d'état

Moteur de jeu fictif. Statistiques de combat, pas des mesures de laboratoire. Backend graphique : `NULL_SINK`. Aucun rendu n'a été lancé.

- Version : `ZX-1.0.0`
- Horodatage : 2026-09-22T12:08:49-04:00 (America/Toronto)
- Forme active : `ALIEN_X_TARDIGRADE` — Alien X Tardigrade, index neuronal 4
- Cooldown effectif : **0 s** (catalogue 30 s, supprimé)
- Quantum contractuel : **0.001 s** · calcul mesuré : 10853 ns (10.9 µs)
- Taille graphique : **1.75 m** (enveloppe native 0.0005 m)
- Posture finale : **Bipède de combat** — Membres supérieurs libres, type Terra Formars
- Passive : **Survie Absolue**

## 1. Architecture

Quatre modules, une direction de dépendance, aucune boucle.

```
database_registry.py        vérité catalogue, identifiants seulement dans l'inventaire
        |
        v
biomnitrix_processor.py     ZX-FUSE-02 + porte ZX-LOCK-01 (un slot de fusion)
        |
        v
master_control_bci.py       index neuronal, cooldown 0, menus non appelés (un slot hôte)
        |
        v
main_pipeline.py            boot, preuves, JSON, manifeste — les bibliothèques se taisent
```

Le Master Control ne publie pas une taille. Il appelle la même porte que la fusion. Il n'y a pas de drapeau de contournement : un paramètre non écrit ne peut pas être activé.

Bornes chaudes, constantes quel que soit le nombre d'appels :

| Ressource | Borne |
| --- | --- |
| Profils catalogue | 5 |
| Slot hôte | 1 |
| Slot de fusion | 1 |
| Anneau d'événements | 8 |
| Passifs par profil | ≤ 12 |
| Jetons par profil | ≤ 16 |
| Jetons d'environnement | ≤ 8 |
| Parents retenus | 2 (immédiats seulement) |
| Identifiant de fusion | ≤ 64 caractères |

## 2. Lois

- Fusion numérique : `min(100, max(A, B) + 0.25 × min(A, B))`. Le brut est archivé dans le résultat, le stocké est plafonné.
- Fusion texte : union ordonnée des jetons séparés par ` / `, plafond 8.
- Passifs : union stable, ordre du parent A puis du parent B, doublons retirés.
- Modificateurs : couche séparée. Bonus de multiplicateurs additionnés, plats sommés, drapeaux en OU. Jamais réinjectés dans le socle.
- Verrou de taille : si l'enveloppe est < 0.01 m, > 3.00 m, ou cosmique, la taille graphique devient 1.75 m / 5'9".
- Verrou de squelette : posture finale « Bipède de combat », Membres supérieurs libres, type Terra Formars. Inconditionnel dès que l'appareil parle.
- Cooldown : le catalogue le porte. Seul le BCI l'écrit à 0. La fusion hérite du max des parents.

## 3. Inventaire neuronal

L'inventaire est un tuple d'identifiants. Les profils ne sont pas copiés dedans.

| Index | Taxon | Nom | Force | Vitesse | Résistance | Taille native | Classe | CD catalogue |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | `Acinonyx_jubatus` | Guépard | 44 | 96 | 36 | 0.875 m | nominal | 1.5 s |
| 1 | `Basiliscus_basiliscus` | Lézard basilic | 20 | 70 | 30 | 0.75 m | nominal | 2 s |
| 2 | `Panthera_tigris` | Tigre | 84 | 66 | 74 | 1.00 m | nominal | 3 s |
| 3 | `Fossil_Rex` | Tyrannosaure | 97 | 42 | 93 | 5.50 m | géant | 8 s |
| 4 | `ALIEN_X_TARDIGRADE` | Alien X Tardigrade | 100 | 100 | 100 | 0.0005 m | microscopique / cosmique | 30 s |

### Index 0 — `Acinonyx_jubatus`

- Nom : Guépard
- Socle : Force 44 · Vitesse 96 · Résistance 36
- Environnement : savane ouverte / poursuite cinétique
- Passifs : Buff de vitesse cinétique
- Jetons : buff_vitesse_cinetique
- Modificateurs : vitesse_cinetique_mult=1.5
- Taille native : 0.875 m · classe enveloppe : nominal
- Posture native : quadrupède cursorial
- Cooldown catalogue : 1.5 s
- Note : Socle de vitesse élevé. Le buff cinétique est un modificateur de couche combat, non réinjecté dans le socle.

### Index 1 — `Basiliscus_basiliscus`

- Nom : Lézard basilic
- Socle : Force 20 · Vitesse 70 · Résistance 30
- Environnement : ripisylve / surface liquide
- Passifs : Hydro-foulée
- Jetons : hydro_foulee
- Modificateurs : vitesse_surface_liquide_mult=1
- Taille native : 0.75 m · classe enveloppe : nominal
- Posture native : quadrupède scansorial
- Cooldown catalogue : 2 s
- Note : Hydro-foulée : vitesse maximale sur l'eau égale au socle Vitesse. La course terrestre n'est pas modifiée.

### Index 2 — `Panthera_tigris`

- Nom : Tigre
- Socle : Force 84 · Vitesse 66 · Résistance 74
- Environnement : forêt dense / embuscade
- Passifs : Mode Bégalosaure
- Jetons : mode_begalosaure
- Modificateurs : degats_physiques_mult=1.75
- Taille native : 1.00 m · classe enveloppe : nominal
- Posture native : quadrupède d'embuscade
- Cooldown catalogue : 3 s
- Note : Mode Bégalosaure : multiplicateur de dégâts physiques appliqué à Force, sans réécriture de Force.

### Index 3 — `Fossil_Rex`

- Nom : Tyrannosaure
- Socle : Force 97 · Vitesse 42 · Résistance 93
- Environnement : plaine crétacée / mêlée lourde
- Passifs : Armure osseuse, Bonus de morsure
- Jetons : armure_osseuse, bonus_morsure
- Modificateurs : morsure_mult=2.25, armure_osseuse_flat=28
- Taille native : 5.50 m · classe enveloppe : géant
- Posture native : bipède caudal lourd
- Cooldown catalogue : 8 s
- Note : Armure osseuse additive et bonus de morsure. Silhouette catalogue 5.50 m, au-dessus du seuil géant. Le verrou n'est pas appliqué dans le registre : il parle à la sortie appareil.

### Index 4 — `ALIEN_X_TARDIGRADE`

- Nom : Alien X Tardigrade
- Socle : Force 100 · Vitesse 100 · Résistance 100
- Environnement : vide spatial / 0 atm / températures extrêmes / anaérobie
- Passifs : Survie Absolue
- Jetons : survie_absolue, resistance_0_atm, immunite_vide_spatial, immunite_temperatures_extremes, respiration_anaerobie
- Modificateurs : survie_absolue=1
- Taille native : 0.0005 m · classe enveloppe : microscopique / cosmique
- Posture native : barillet octopode / entité cosmique
- Cooldown catalogue : 30 s
- Note : Le Fleuron. Survie Absolue : résistance à 0 atm, immunité au vide spatial, immunité aux températures extrêmes, respiration anaérobie. Corps 0.50 mm et enveloppe cosmique. Le registre dit la vérité biologique de jeu ; l'appareil recalibre à la sortie.

## 4. Activation Master Control — Alien X Tardigrade

Appel exécuté : `brainwave_input_trigger(4)`. Les menus physiques n'ont pas été invoqués. Compteur d'ouverture de menu après le commit : 0.

- Index : 4
- Taxon : `ALIEN_X_TARDIGRADE`
- Étape de sortie : device
- Cooldown effectif : 0 s (suppression : oui)
- Quantum : 0.001 s · mesuré : 10853 ns (10.9 µs) · dans le quantum : oui
- Socle inchangé : Force 100 · Vitesse 100 · Résistance 100
- Environnement : vide spatial / 0 atm / températures extrêmes / anaérobie
- Survie Absolue : Résistance à 0 atm, Immunité au vide spatial, Immunité aux températures extrêmes, Respiration anaérobie
- Enveloppe native : 0.0005 m (corps tardigrade) · drapeau cosmique : oui
- Raisons du verrou de taille : microscopique, géant, enveloppe_cosmique
- Taille graphique publiée : 1.75 m (1.75 m / 5'9")
- Posture native auditée : barillet octopode / entité cosmique
- Posture finale : Bipède de combat — Membres supérieurs libres, type Terra Formars
- Anneau d'événements : une empreinte compacte. Le profil complet vit dans le slot hôte, pas dans l'anneau.

Le registre catalogue n'a pas été réécrit. Hauteur catalogue du Fleuron après activation : 0.0005 m, verrou catalogue : non.

## 5. Démonstration du processeur double-noyau

La fusion des socles numériques est commutative. L'identifiant et l'ordre des passifs ne le sont pas. Les deux démonstrations ci-dessous sont l'ordre A puis B, passé par la porte de verrou.

### Acinonyx_jubatus × Basiliscus_basiliscus — nominal, squelette seul

- Identifiant : `Acinonyx_jubatus×Basiliscus_basiliscus`
- Parents immédiats : Acinonyx_jubatus × Basiliscus_basiliscus
- Loi : ZX-FUSE-02
- Force 49 (brut 49) · Vitesse 100 (brut 113.5) · Résistance 43.5 (brut 43.5)
- Environnement : savane ouverte / poursuite cinétique / ripisylve / surface liquide
- Passifs combinés : Buff de vitesse cinétique, Hydro-foulée
- Enveloppe native : 0.875 m · taille graphique : 0.875 m
- Verrou de taille : non engagé (—)
- Posture finale : Bipède de combat — Membres supérieurs libres, type Terra Formars
- Verrou de squelette : engagé
- Cooldown catalogue hérité (max des parents, non soumis au BCI ici) : 2 s
- Indices dérivés : dégâts physiques 49 · morsure 49 · vitesse effective 100 · vitesse sur eau 100

### Panthera_tigris × Fossil_Rex — géant recalibré, Bégalosaure osseux

- Identifiant : `Panthera_tigris×Fossil_Rex`
- Parents immédiats : Panthera_tigris × Fossil_Rex
- Loi : ZX-FUSE-02
- Force 100 (brut 118) · Vitesse 76.5 (brut 76.5) · Résistance 100 (brut 111.5)
- Environnement : forêt dense / embuscade / plaine crétacée / mêlée lourde
- Passifs combinés : Mode Bégalosaure, Armure osseuse, Bonus de morsure
- Enveloppe native : 5.50 m · taille graphique : 1.75 m
- Verrou de taille : engagé (géant)
- Posture finale : Bipède de combat — Membres supérieurs libres, type Terra Formars
- Verrou de squelette : engagé
- Cooldown catalogue hérité (max des parents, non soumis au BCI ici) : 8 s
- Indices dérivés : dégâts physiques 175 · morsure 225 · vitesse effective 76.5 · vitesse sur eau 0

Le guépard-basilic reste à hauteur d'enveloppe nominale : le verrou de taille ne s'engage pas. Le verrou de squelette s'engage quand même. Le tigre-rex porte une enveloppe de 5.50 m : la taille graphique est recalibrée à 1.75 m / 5'9". Mode Bégalosaure, armure osseuse et bonus de morsure sont tous présents.

## 6. Preuve de borne mémoire

Quatre mille fusions contre cent, slot unique, GC entre les deux mesures. Une liste d'historique ferait croître le second delta avec le nombre d'appels. Le delta inclut le slot de fusion et le bruit de tracemalloc, pas une courbe.

- Delta résident après 100 fusions : 1534 octets
- Delta résident après 4000 fusions : 1566 octets
- Écart absolu : 32 octets
- Verdict : O(1) tenu

## 7. Artefacts

| Fichier | SHA-256 |
| --- | --- |
| `state/registry.json` | `dcffa744609c8adca523978d2e2560d21c552d6b19058b354a456fe0ad3462f3` |
| `state/inventory.json` | `7e5a1867a8d00cc0814cc5106faf1f5726313c36ed5d4272800cd55993d694dd` |
| `state/fusion_acinonyx_basiliscus.json` | `b086faba24403518f333bdf78b304a67b1cbe5d7517634309f377987f56e1c7a` |
| `state/fusion_panthera_rex.json` | `6c43c0593a95e08b48d13c68e5c43be178c27816a5a566f9ac53fbe1097e3816` |
| `state/bci_activation.json` | `2882f3c82b16c8f130149ac53584df65bfa852b2a1a218873d567d978bef4532` |
| `state/memory_bound.json` | `0cfa85498690b50f31d81d5c3689dc7fcf72b3b6f85b7c89760c01a218ac2719` |
| `state/invariants.json` | `65f46d7f6f8b05b5695bd70b5c231a9193f2c50514a445c39cd026df3f18128e` |
| `state/engine_state.json` | `842db6f16d0d98798dc2be0667edbd1b99e90d1917c29c3c573633d06d1b165f` |

## 8. Invariants

- [PASS] le menu physique s'ouvre si on l'appelle — invocations sonde = 1
- [PASS] index 99 rejeté sans commit
- [PASS] booléen rejeté (True n'est pas l'index 1)
- [PASS] index négatif rejeté sans commit
- [PASS] mémoire de fusion bornée (100 vs 4000) — deltas 1534 / 1566 octets
- [PASS] dictionnaires d'entrée non mutés
- [PASS] clé supplémentaire Perception fusionnée — valeur 90.0
- [PASS] échec de fusion : le slot précédent n'est pas écrasé
- [PASS] fusion numérique commutative
- [PASS] libellé de fusion non commutatif
- [PASS] passifs du couple vitesse/eau tous présents
- [PASS] verrou de taille silencieux sur enveloppe nominale
- [PASS] verrou de squelette engagé même sans recalibrage de taille
- [PASS] résolution objet et taxon_id équivalentes
- [PASS] Bégalosaure osseux : passifs combinés et taille recalibrée
- [PASS] plafond de socle sans perte du brut — stocké 100.0, brut 118.0
- [PASS] identifiant de fusion profonde borné à 64 caractères — ZX-e0015313abf8
- [PASS] parents immédiats seulement
- [PASS] index 4 commet le Fleuron
- [PASS] cooldown forcé à 0
- [PASS] quantum contractuel 0.001 s et calcul à l'intérieur — 10853 ns (10.9 µs)
- [PASS] menus non invoqués par le déclencheur
- [PASS] Fleuron recalibré à 1.75 m, socle immunitaire intact
- [PASS] catalogue non muté par la matérialisation
- [PASS] porte de verrou idempotente
- [PASS] slot hôte unique et anneau compact
- [PASS] loi de fusion estampillée
- [PASS] backend de rendu non armé

Bilan : 28/28 invariants tenus.

---

ZOONITRIX X · cellule d'architecture logicielle · document généré par `main_pipeline.py`.

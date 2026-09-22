# =============================================================================
# ALCHEMAX — Division Systèmes Neuronaux / Programme ZOONITRIX X
# Protocole ZX-REG-01 — Registre ADN de combat
# Moteur de jeu fictif. Statistiques de gameplay uniquement.
# Aucune procédure biologique. Aucun backend de rendu.
# =============================================================================
"""Registre immutable des profils de combat ZOONITRIX X.

Responsabilité unique : la vérité catalogue. Ce module ne connaît ni les
verrous de l'appareil, ni la puce BCI, ni le disque. Il expose des profils
gelés et une vue d'inventaire par identifiants.

Mémoire : cinq profils alloués à l'import, jamais recopiés par
``load_inventory``. La recherche est un accès dictionnaire, O(1), indépendant
du nombre d'appels de fusion en aval.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterator, Mapping

__all__ = (
    "TOKEN_LABELS",
    "IMMUNITY_TOKENS",
    "REGISTRY",
    "REGISTRY_ORDER",
    "CombatProfile",
    "RegistryKeyError",
    "get_profile",
    "iter_catalogue",
    "load_inventory",
    "resolve_profile",
)


class RegistryKeyError(KeyError):
    """Taxon absent ou registre incohérent. Aucun profil partiel n'est publié."""


# Libellés d'affichage. La chaîne passive reste la surface joueur ;
# le jeton est le contrat machine, stable sous fusion.
TOKEN_LABELS: Mapping[str, str] = MappingProxyType(
    {
        "buff_vitesse_cinetique": "Buff de vitesse cinétique",
        "hydro_foulee": "Hydro-foulée (vitesse maximale sur l'eau)",
        "mode_begalosaure": "Mode Bégalosaure (multiplicateur de dégâts physiques)",
        "armure_osseuse": "Armure osseuse",
        "bonus_morsure": "Bonus de morsure",
        "survie_absolue": "Survie Absolue",
        "resistance_0_atm": "Résistance à 0 atm",
        "immunite_vide_spatial": "Immunité au vide spatial",
        "immunite_temperatures_extremes": "Immunité aux températures extrêmes",
        "respiration_anaerobie": "Respiration anaérobie",
    }
)

# Sous-ensemble immunitaire du Fleuron. Séparé des autres jetons pour que le
# manifeste puisse déplier « Survie Absolue » sans dupliquer son titre.
IMMUNITY_TOKENS: tuple[str, ...] = (
    "resistance_0_atm",
    "immunite_vide_spatial",
    "immunite_temperatures_extremes",
    "respiration_anaerobie",
)

# Ordre = contrat d'index neuronal ZX-BCI-01. L'index 4 est le Fleuron.
_EXPECTED_ORDER: tuple[str, ...] = (
    "Acinonyx_jubatus",
    "Basiliscus_basiliscus",
    "Panthera_tigris",
    "Fossil_Rex",
    "ALIEN_X_TARDIGRADE",
)


def _round6(value: float) -> float:
    """Coupe la poussière binaire à l'écriture. Le socle reste la source."""
    return round(float(value), 6)


@dataclass(frozen=True, slots=True)
class CombatProfile:
    """Profil de combat gelé.

    Deux couches, une seule direction d'écriture :

    * socle ADN — Force, Vitesse, Résistance, Environnement, passifs, taille
      native, posture native ;
    * sortie appareil — taille graphique, posture finale, drapeaux de verrou.

    Le catalogue publie la sortie égale au socle et ``output_stage="catalogue"``.
    Seul le processeur a le droit de republier un profil en ``"device"``.
    Les modificateurs ne sont jamais réinjectés dans le socle : une couche,
    une source de vérité.
    """

    taxon_id: str
    common_name: str
    force: float
    vitesse: float
    resistance: float
    environnement: str
    passives: tuple[str, ...]
    capability_tokens: tuple[str, ...]
    modifiers: tuple[tuple[str, float], ...]
    native_height_m: float
    native_posture: str
    cosmic_envelope: bool
    catalogue_cooldown_s: float
    origin: str
    parents: tuple[str, ...]
    fusion_law: str
    stat_raw: tuple[tuple[str, float], ...]
    extra_stats: tuple[tuple[str, float | str], ...]
    graphic_height_m: float
    size_lock_engaged: bool
    size_lock_reasons: tuple[str, ...]
    posture_finale: str
    posture_detail: str
    skeleton_lock_engaged: bool
    output_stage: str
    audit_flags: tuple[str, ...]
    design_note: str

    def stat_dict(self) -> dict[str, float | str]:
        """Dictionnaire de stats. Nouvel objet à chaque appel : le socle gelé n'est pas exposé."""
        stats: dict[str, float | str] = {
            "Force": self.force,
            "Vitesse": self.vitesse,
            "Résistance": self.resistance,
            "Environnement": self.environnement,
        }
        for key, value in self.extra_stats:
            stats[key] = value
        return stats

    def modifier_map(self) -> dict[str, float]:
        return dict(self.modifiers)

    def as_dict(self) -> dict[str, object]:
        """Instantané JSON-compatible. Aucune référence vivante vers le registre."""
        return {
            "taxon_id": self.taxon_id,
            "common_name": self.common_name,
            "origin": self.origin,
            "output_stage": self.output_stage,
            "parents": list(self.parents),
            "fusion_law": self.fusion_law,
            "stats": {
                "Force": _round6(self.force),
                "Vitesse": _round6(self.vitesse),
                "Résistance": _round6(self.resistance),
                "Environnement": self.environnement,
            },
            "stat_raw": {key: _round6(value) for key, value in self.stat_raw},
            "extra_stats": {key: value for key, value in self.extra_stats},
            "passives": list(self.passives),
            "capability_tokens": list(self.capability_tokens),
            "modifiers": {key: _round6(value) for key, value in self.modifiers},
            "native_height_m": _round6(self.native_height_m),
            "graphic_height_m": _round6(self.graphic_height_m),
            "size_lock_engaged": self.size_lock_engaged,
            "size_lock_reasons": list(self.size_lock_reasons),
            "native_posture": self.native_posture,
            "posture_finale": self.posture_finale,
            "posture_detail": self.posture_detail,
            "skeleton_lock_engaged": self.skeleton_lock_engaged,
            "cosmic_envelope": self.cosmic_envelope,
            "catalogue_cooldown_s": _round6(self.catalogue_cooldown_s),
            "audit_flags": list(self.audit_flags),
            "design_note": self.design_note,
        }


def _catalogue(
    *,
    taxon_id: str,
    common_name: str,
    force: float,
    vitesse: float,
    resistance: float,
    environnement: str,
    passives: tuple[str, ...],
    capability_tokens: tuple[str, ...],
    modifiers: tuple[tuple[str, float], ...],
    native_height_m: float,
    native_posture: str,
    cosmic_envelope: bool,
    catalogue_cooldown_s: float,
    design_note: str,
) -> CombatProfile:
    """Construit une entrée catalogue. La sortie appareil n'est pas encore parlée."""
    return CombatProfile(
        taxon_id=taxon_id,
        common_name=common_name,
        force=force,
        vitesse=vitesse,
        resistance=resistance,
        environnement=environnement,
        passives=passives,
        capability_tokens=capability_tokens,
        modifiers=modifiers,
        native_height_m=native_height_m,
        native_posture=native_posture,
        cosmic_envelope=cosmic_envelope,
        catalogue_cooldown_s=catalogue_cooldown_s,
        origin="catalogue",
        parents=(),
        fusion_law="",
        stat_raw=(
            ("Force", force),
            ("Vitesse", vitesse),
            ("Résistance", resistance),
        ),
        extra_stats=(),
        graphic_height_m=native_height_m,
        size_lock_engaged=False,
        size_lock_reasons=(),
        posture_finale=native_posture,
        posture_detail="",
        skeleton_lock_engaged=False,
        output_stage="catalogue",
        audit_flags=(),
        design_note=design_note,
    )


def _build_registry() -> dict[str, CombatProfile]:
    """Assemble le registre dans l'ordre neuronal. Échoue fermé si le contrat casse."""
    profiles = (
        # Buff cinétique. Le ×1.5 est une couche combat : Vitesse reste 96.
        _catalogue(
            taxon_id="Acinonyx_jubatus",
            common_name="Guépard",
            force=44.0,
            vitesse=96.0,
            resistance=36.0,
            environnement="savane ouverte / poursuite cinétique",
            passives=("Buff de vitesse cinétique",),
            capability_tokens=("buff_vitesse_cinetique",),
            modifiers=(("vitesse_cinetique_mult", 1.5),),
            native_height_m=0.875,
            native_posture="quadrupède cursorial",
            cosmic_envelope=False,
            catalogue_cooldown_s=1.5,
            design_note=(
                "Socle de vitesse élevé. Le buff cinétique est un modificateur "
                "de couche combat, non réinjecté dans le socle."
            ),
        ),
        # Hydro-foulée : facteur 1.0 sur l'eau, course terrestre inchangée.
        _catalogue(
            taxon_id="Basiliscus_basiliscus",
            common_name="Lézard basilic",
            force=20.0,
            vitesse=70.0,
            resistance=30.0,
            environnement="ripisylve / surface liquide",
            passives=("Hydro-foulée",),
            capability_tokens=("hydro_foulee",),
            modifiers=(("vitesse_surface_liquide_mult", 1.0),),
            native_height_m=0.75,
            native_posture="quadrupède scansorial",
            cosmic_envelope=False,
            catalogue_cooldown_s=2.0,
            design_note=(
                "Hydro-foulée : vitesse maximale sur l'eau égale au socle Vitesse. "
                "La course terrestre n'est pas modifiée."
            ),
        ),
        # Mode Bégalosaure : multiplicateur de dégâts physiques, Force intacte.
        _catalogue(
            taxon_id="Panthera_tigris",
            common_name="Tigre",
            force=84.0,
            vitesse=66.0,
            resistance=74.0,
            environnement="forêt dense / embuscade",
            passives=("Mode Bégalosaure",),
            capability_tokens=("mode_begalosaure",),
            modifiers=(("degats_physiques_mult", 1.75),),
            native_height_m=1.0,
            native_posture="quadrupède d'embuscade",
            cosmic_envelope=False,
            catalogue_cooldown_s=3.0,
            design_note=(
                "Mode Bégalosaure : multiplicateur de dégâts physiques appliqué "
                "à Force, sans réécriture de Force."
            ),
        ),
        # Silhouette 5.5 m : classe géante au sens du verrou (> 3 m), pas ici.
        _catalogue(
            taxon_id="Fossil_Rex",
            common_name="Tyrannosaure",
            force=97.0,
            vitesse=42.0,
            resistance=93.0,
            environnement="plaine crétacée / mêlée lourde",
            passives=("Armure osseuse", "Bonus de morsure"),
            capability_tokens=("armure_osseuse", "bonus_morsure"),
            modifiers=(
                ("morsure_mult", 2.25),
                ("armure_osseuse_flat", 28.0),
            ),
            native_height_m=5.5,
            native_posture="bipède caudal lourd",
            cosmic_envelope=False,
            catalogue_cooldown_s=8.0,
            design_note=(
                "Armure osseuse additive et bonus de morsure. Silhouette catalogue "
                "5.50 m, au-dessus du seuil géant. Le verrou n'est pas appliqué "
                "dans le registre : il parle à la sortie appareil."
            ),
        ),
        # Le Fleuron. Corps tardigrade + enveloppe cosmique. Immunités = jetons.
        _catalogue(
            taxon_id="ALIEN_X_TARDIGRADE",
            common_name="Alien X Tardigrade",
            force=100.0,
            vitesse=100.0,
            resistance=100.0,
            environnement="vide spatial / 0 atm / températures extrêmes / anaérobie",
            passives=("Survie Absolue",),
            capability_tokens=(
                "survie_absolue",
                "resistance_0_atm",
                "immunite_vide_spatial",
                "immunite_temperatures_extremes",
                "respiration_anaerobie",
            ),
            modifiers=(("survie_absolue", 1.0),),
            native_height_m=0.0005,
            native_posture="barillet octopode / entité cosmique",
            cosmic_envelope=True,
            catalogue_cooldown_s=30.0,
            design_note=(
                "Le Fleuron. Survie Absolue : résistance à 0 atm, immunité au vide "
                "spatial, immunité aux températures extrêmes, respiration anaérobie. "
                "Corps 0.50 mm et enveloppe cosmique. Le registre dit la vérité "
                "biologique de jeu ; l'appareil recalibre à la sortie."
            ),
        ),
    )
    by_id = {profile.taxon_id: profile for profile in profiles}
    if len(by_id) != len(profiles):
        raise RegistryKeyError("collision d'identifiant dans le catalogue")
    ordered: dict[str, CombatProfile] = {}
    for taxon_id in _EXPECTED_ORDER:
        try:
            ordered[taxon_id] = by_id.pop(taxon_id)
        except KeyError as exc:
            raise RegistryKeyError(f"taxon contractuel absent : {taxon_id}") from exc
    if by_id:
        raise RegistryKeyError(f"taxons hors contrat d'index : {tuple(by_id)}")
    return ordered


def _validate(profile: CombatProfile) -> None:
    """Garde de boot. Un socle hors plage ne quitte pas l'import."""
    for name, value in (
        ("Force", profile.force),
        ("Vitesse", profile.vitesse),
        ("Résistance", profile.resistance),
    ):
        if not 0.0 <= value <= 100.0:
            raise RegistryKeyError(f"{profile.taxon_id} : {name} hors plage 0–100")
    if profile.native_height_m <= 0.0:
        raise RegistryKeyError(f"{profile.taxon_id} : taille native non positive")
    if profile.catalogue_cooldown_s < 0.0:
        raise RegistryKeyError(f"{profile.taxon_id} : cooldown catalogue négatif")
    if not profile.passives:
        raise RegistryKeyError(f"{profile.taxon_id} : passif manquant")
    if profile.output_stage != "catalogue" or profile.skeleton_lock_engaged:
        raise RegistryKeyError(f"{profile.taxon_id} : le catalogue ne porte pas le verrou")
    unknown = [token for token in profile.capability_tokens if token not in TOKEN_LABELS]
    if unknown:
        raise RegistryKeyError(f"{profile.taxon_id} : jetons sans libellé {unknown}")


_BUILT = _build_registry()
for _profile in _BUILT.values():
    _validate(_profile)

# Vue lecture seule. Un appelant ne peut pas insérer un sixième taxon par accident.
REGISTRY: Mapping[str, CombatProfile] = MappingProxyType(_BUILT)
REGISTRY_ORDER: tuple[str, ...] = tuple(REGISTRY)


def get_profile(taxon_id: str) -> CombatProfile:
    """Accès O(1). Ne copie pas le profil : l'objet gelé est partagé."""
    try:
        return REGISTRY[taxon_id]
    except KeyError as exc:
        known = ", ".join(REGISTRY_ORDER)
        raise RegistryKeyError(
            f"Taxon absent du registre : {taxon_id!r}. Connus : {known}."
        ) from exc


def iter_catalogue() -> Iterator[CombatProfile]:
    """Flux catalogue. Un profil à la fois, aucune liste intermédiaire."""
    for taxon_id in REGISTRY_ORDER:
        yield REGISTRY[taxon_id]


def load_inventory() -> tuple[str, ...]:
    """Inventaire neuronal : identifiants seulement.

    Les profils restent dans le registre. L'inventaire ne les duplique pas.
    L'index passé à ``brainwave_input_trigger`` est la position dans ce tuple.
    """
    return REGISTRY_ORDER


def resolve_profile(value: CombatProfile | str) -> CombatProfile:
    """Accepte un objet gelé ou un taxon_id. Refuse tout le reste, sans coercion."""
    if isinstance(value, CombatProfile):
        return value
    if isinstance(value, str):
        return get_profile(value)
    raise TypeError(
        "profil attendu : CombatProfile ou taxon_id (str), "
        f"reçu {type(value).__name__}"
    )

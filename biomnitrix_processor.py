# =============================================================================
# ALCHEMAX — Division Systèmes Neuronaux / Programme ZOONITRIX X
# Protocole ZX-FUSE-02 — Fusion double-noyau
# Protocole ZX-LOCK-01 — Verrous physiques de l'appareil
# Moteur de jeu fictif. Aucun maillage, aucun pixel, aucun thread de rendu.
# =============================================================================
"""Processeur de fusion et porte de sortie de l'appareil.

Deux lois, aucune exception écrite :

* ZX-FUSE-02 — fusionne les dictionnaires de stats et unionne les passifs.
  Le récessif contribue d'un quart. Le plafond 100 arrête l'inflation.
* ZX-LOCK-01 — à la sortie, et seulement à la sortie :
  - taille : un enveloppe microscopique ou géante est recalibrée à 1.75 m ;
  - squelette : la posture publiée est « Bipède de combat ».

Il n'existe pas de paramètre ``bypass``. On ne peut pas activer ce qui n'est
pas écrit. Le Master Control court-circuite les menus ; il ne négocie pas
ces verrous, parce qu'il n'a pas de poignée pour le faire.

Mémoire chaude, par appel : un résultat, un slot écrasé, des champs plafonnés.
Pas d'historique de fusion. Pas de lignée profonde : deux parents immédiats.
Un tampon global réutilisé a été refusé : il économise une allocation
négligeable et introduit une course. La borne réelle est l'absence d'historique.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace

from database_registry import (
    CombatProfile,
    iter_catalogue,
    resolve_profile,
)

__all__ = (
    "HUMAN_MEAN_HEIGHT_M",
    "HUMAN_MEAN_HEIGHT_LABEL",
    "POSTURE_LOCK",
    "POSTURE_LOCK_DETAIL",
    "MICRO_HEIGHT_M",
    "GIANT_HEIGHT_M",
    "STAT_CAP",
    "RECESSIVE_WEIGHT",
    "FUSION_LAW_ID",
    "MULT_CAP",
    "FLAT_CAP",
    "FusionInputError",
    "BiomnitrixProcessor",
    "apply_hard_constraints",
    "clear_fusion_slot",
    "derived_indices",
    "envelope_class",
    "fuse_profiles",
    "last_fusion",
    "merge_stat_dicts",
    "validate_catalogue_modifiers",
)

# Couple de désignation protocolaire. 5'9" n'est pas une conversion :
# 1.75 * 3.28084 ne doit pas « corriger » la constante. La valeur opératoire
# unique est 1.75. L'étiquette impériale voyage avec elle, sans second calcul.
HUMAN_MEAN_HEIGHT_M: float = 1.75
HUMAN_MEAN_HEIGHT_LABEL: str = "1.75 m / 5'9\""
POSTURE_LOCK: str = "Bipède de combat"
POSTURE_LOCK_DETAIL: str = "Membres supérieurs libres, type Terra Formars"

# Seuils d'enveloppe. 1 cm sépare « petit animal » et « microscopique ».
# 3 m sépare « grande faune » et « géant ». Un drapeau cosmique force « géant ».
MICRO_HEIGHT_M: float = 0.01
GIANT_HEIGHT_M: float = 3.0

STAT_CAP: float = 100.0
RECESSIVE_WEIGHT: float = 0.25
FUSION_LAW_ID: str = "ZX-FUSE-02"
MULT_CAP: float = 3.0
FLAT_CAP: float = 80.0

MAX_PASSIVES: int = 12
MAX_TOKENS: int = 16
MAX_ENV_TOKENS: int = 8
MAX_EXTRA_STATS: int = 8
MAX_FUSION_ID_CHARS: int = 64
MAX_TEXT_CHARS: int = 96

# Grammaire fermée des modificateurs. Une clé non classée n'a pas de loi :
# on refuse, on n'invente pas une moyenne par défaut.
MULT_KEYS = frozenset(
    {
        "vitesse_cinetique_mult",
        "degats_physiques_mult",
        "morsure_mult",
    }
)
MAX_KEYS = frozenset({"vitesse_surface_liquide_mult"})
FLAT_KEYS = frozenset({"armure_osseuse_flat"})
FLAG_KEYS = frozenset({"survie_absolue"})
_KNOWN_MODIFIERS = MULT_KEYS | MAX_KEYS | FLAT_KEYS | FLAG_KEYS

_CANONICAL_NUMERIC = ("Force", "Vitesse", "Résistance")
_CANONICAL_TEXT = ("Environnement",)
_CANONICAL = _CANONICAL_NUMERIC + _CANONICAL_TEXT

MODIFIER_LABELS: dict[str, str] = {
    "vitesse_cinetique_mult": "Buff de vitesse cinétique (×)",
    "vitesse_surface_liquide_mult": "Hydro-foulée, facteur de vitesse sur l'eau",
    "degats_physiques_mult": "Mode Bégalosaure, dégâts physiques (×)",
    "morsure_mult": "Bonus de morsure (×)",
    "armure_osseuse_flat": "Armure osseuse (plat)",
    "survie_absolue": "Survie Absolue (drapeau)",
}


class FusionInputError(ValueError):
    """Entrée de fusion illégale.

    Levée avant l'écriture du slot. L'échec ne remplace pas le dernier résultat.
    """


def envelope_class(height_m: float, cosmic_envelope: bool) -> str:
    """Étiquette d'audit. Ce n'est pas la porte de verrou.

    La porte lit ``_size_reasons`` et recalibre. Ici on publie chaque critère
    distinct, pour qu'un corps de 0,50 mm à enveloppe cosmique ne soit pas
    réduit au seul mot « géant ».
    """
    parts: list[str] = []
    if height_m < MICRO_HEIGHT_M:
        parts.append("microscopique")
    if height_m > GIANT_HEIGHT_M:
        parts.append("géant")
    if cosmic_envelope:
        parts.append("cosmique")
    if not parts:
        return "nominal"
    return " / ".join(parts)


def _size_reasons(height_m: float, cosmic_envelope: bool) -> tuple[str, ...]:
    """Raisons stables. L'ordre est contractuel : micro, puis géant, puis cosmos."""
    reasons: list[str] = []
    if height_m < MICRO_HEIGHT_M:
        reasons.append("microscopique")
    if height_m > GIANT_HEIGHT_M or cosmic_envelope:
        reasons.append("géant")
    if cosmic_envelope:
        reasons.append("enveloppe_cosmique")
    return tuple(reasons)


def apply_hard_constraints(profile: CombatProfile) -> CombatProfile:
    """Porte de sortie ZX-LOCK-01. Idempotente. Sans paramètre de contournement.

    Le verrou lit ``native_height_m`` et ``cosmic_envelope``. Il n'écrit jamais
    la hauteur native : une seconde passe relit la même vérité et republie la
    même sortie. La posture finale est inconditionnelle.
    """
    reasons = _size_reasons(profile.native_height_m, profile.cosmic_envelope)
    graphic = HUMAN_MEAN_HEIGHT_M if reasons else profile.native_height_m
    return replace(
        profile,
        graphic_height_m=graphic,
        size_lock_engaged=bool(reasons),
        size_lock_reasons=reasons,
        posture_finale=POSTURE_LOCK,
        posture_detail=POSTURE_LOCK_DETAIL,
        skeleton_lock_engaged=True,
        output_stage="device",
    )


def _cap_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _union(left: tuple[str, ...], right: tuple[str, ...], limit: int) -> tuple[tuple[str, ...], bool]:
    """Union stable, ordre A puis B, plafond inclus. O(plafond), pas O(historique)."""
    merged: list[str] = []
    seen: set[str] = set()
    truncated = False
    for item in left + right:
        if item in seen:
            continue
        if len(merged) >= limit:
            truncated = True
            break
        seen.add(item)
        merged.append(item)
    return tuple(merged), truncated


def _fuse_text(left: str, right: str) -> tuple[str, bool]:
    """Fusionne un champ texte tokenisé par `` / ``. Plafond : MAX_ENV_TOKENS."""
    tokens: list[str] = []
    seen: set[str] = set()
    truncated = False
    for source in (left, right):
        for raw in source.split(" / "):
            token = raw.strip()
            if not token or token in seen:
                continue
            if len(tokens) >= MAX_ENV_TOKENS:
                truncated = True
                break
            seen.add(token)
            tokens.append(token)
        if truncated:
            break
    return " / ".join(tokens), truncated


def fuse_stat(value_a: float, value_b: float) -> tuple[float, float]:
    """ZX-FUSE-02 : dominant + 0.25 × récessif, plafonné à 100.

    Retourne ``(stocké, brut)``. Le brut est conservé pour l'audit : le plafond
    ne doit pas effacer la trace de l'overflow.
    """
    if value_a < 0.0 or value_b < 0.0:
        raise FusionInputError("stat numérique négative refusée")
    if value_a >= value_b:
        dominant, recessive = value_a, value_b
    else:
        dominant, recessive = value_b, value_a
    raw = dominant + RECESSIVE_WEIGHT * recessive
    stored = STAT_CAP if raw > STAT_CAP else raw
    return round(stored, 6), round(raw, 6)


def merge_stat_dicts(
    dict_a: dict[str, float | str],
    dict_b: dict[str, float | str],
) -> tuple[dict[str, float | str], dict[str, float], tuple[str, ...]]:
    """Fusion dynamique de deux dictionnaires de stats. Ne mémorise rien.

    Les clés canoniques sont exigées et traitées dans un ordre fixe.
    Toute clé supplémentaire présente dans l'union est fusionnée, puis
    l'union est plafonnée à ``MAX_EXTRA_STATS``. Les dictionnaires d'entrée
    ne sont pas mutés.
    """
    for key in _CANONICAL:
        if key not in dict_a or key not in dict_b:
            raise FusionInputError(f"clé canonique absente : {key}")

    merged: dict[str, float | str] = {}
    raw_numeric: dict[str, float] = {}
    for key in _CANONICAL_NUMERIC:
        stored, raw = fuse_stat(float(dict_a[key]), float(dict_b[key]))
        merged[key] = stored
        raw_numeric[key] = raw

    environnement, env_truncated = _fuse_text(
        str(dict_a["Environnement"]),
        str(dict_b["Environnement"]),
    )
    merged["Environnement"] = environnement

    extra_keys = sorted((set(dict_a) | set(dict_b)) - set(_CANONICAL))
    flags: list[str] = []
    if env_truncated:
        flags.append("environnement_plafonne")
    if len(extra_keys) > MAX_EXTRA_STATS:
        extra_keys = extra_keys[:MAX_EXTRA_STATS]
        flags.append("stats_supplementaires_plafonnees")

    for key in extra_keys:
        left = dict_a.get(key, 0.0 if _is_numeric_side(dict_a, dict_b, key) else "")
        right = dict_b.get(key, 0.0 if _is_numeric_side(dict_a, dict_b, key) else "")
        if _is_number(left) and _is_number(right):
            stored, raw = fuse_stat(float(left), float(right))
            merged[key] = stored
            raw_numeric[key] = raw
        elif isinstance(left, str) and isinstance(right, str):
            text, truncated = _fuse_text(left, right)
            merged[key] = text
            if truncated:
                flags.append("environnement_plafonne")
        else:
            raise FusionInputError(f"types incompatibles sur la clé supplémentaire {key!r}")

    return merged, raw_numeric, tuple(dict.fromkeys(flags))


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_numeric_side(
    dict_a: dict[str, float | str],
    dict_b: dict[str, float | str],
    key: str,
) -> bool:
    for source in (dict_a, dict_b):
        if key in source and _is_number(source[key]):
            return True
    return False


def fuse_modifiers(
    left: tuple[tuple[str, float], ...],
    right: tuple[tuple[str, float], ...],
) -> tuple[tuple[str, float], ...]:
    """Fusionne la couche combat. Les clés sont triées : le résultat est déterministe.

    * multiplicateurs : bonus additifs, identité 1.0 non stockée, plafond 3 ;
    * max : le meilleur facteur gagne, 0 signifie absent ;
    * plats : somme, plafond 80 ;
    * drapeaux : présence, valeur 1.
    """
    map_a = dict(left)
    map_b = dict(right)
    fused: list[tuple[str, float]] = []
    for key in sorted(set(map_a) | set(map_b)):
        if key in MULT_KEYS:
            value = 1.0 + (map_a.get(key, 1.0) - 1.0) + (map_b.get(key, 1.0) - 1.0)
            if value > MULT_CAP:
                value = MULT_CAP
            if value == 1.0:
                continue
        elif key in MAX_KEYS:
            value = max(map_a.get(key, 0.0), map_b.get(key, 0.0))
            if value == 0.0:
                continue
        elif key in FLAT_KEYS:
            value = map_a.get(key, 0.0) + map_b.get(key, 0.0)
            if value > FLAT_CAP:
                value = FLAT_CAP
            if value == 0.0:
                continue
        elif key in FLAG_KEYS:
            if key not in map_a and key not in map_b:
                continue
            value = 1.0
        else:
            raise FusionInputError(
                f"Modificateur sans loi de fusion : {key}. "
                "Enregistrer la clé avant de l'émettre."
            )
        fused.append((key, round(value, 6)))
    return tuple(fused)


def _fusion_taxon_id(profile_a: CombatProfile, profile_b: CombatProfile) -> str:
    """Identifiant lisible si court, sinon condensat fixe. Jamais plus de 64 caractères."""
    raw = f"{profile_a.taxon_id}×{profile_b.taxon_id}"
    if len(raw) <= MAX_FUSION_ID_CHARS:
        return raw
    # 12 hex : assez pour l'audit sandbox, constant en taille. Pas une sécurité cryptographique.
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"ZX-{digest}"


def _merge_biological(profile_a: CombatProfile, profile_b: CombatProfile) -> CombatProfile:
    """Assemble le socle fusionné. N'applique pas les verrous. N'écrit pas le slot."""
    merged, raw_numeric, audit_flags = merge_stat_dicts(
        profile_a.stat_dict(),
        profile_b.stat_dict(),
    )
    passives, passives_cut = _union(profile_a.passives, profile_b.passives, MAX_PASSIVES)
    tokens, tokens_cut = _union(
        profile_a.capability_tokens,
        profile_b.capability_tokens,
        MAX_TOKENS,
    )
    flags = list(audit_flags)
    if passives_cut:
        flags.append("passifs_plafonnes")
    if tokens_cut:
        flags.append("jetons_plafonnes")

    extra = tuple(
        (key, merged[key])
        for key in merged
        if key not in _CANONICAL
    )
    envelope_height = max(profile_a.native_height_m, profile_b.native_height_m)
    # Cooldown catalogue hérité = max. La suppression à 0 est le travail du BCI,
    # pas celui de la fusion. On ne cumule pas : fusionner n'est pas une peine.
    cooldown = max(profile_a.catalogue_cooldown_s, profile_b.catalogue_cooldown_s)
    native_posture = _cap_text(
        f"{profile_a.native_posture} + {profile_b.native_posture}",
        MAX_TEXT_CHARS,
    )
    return CombatProfile(
        taxon_id=_fusion_taxon_id(profile_a, profile_b),
        common_name=_cap_text(
            f"{profile_a.common_name} × {profile_b.common_name}",
            MAX_TEXT_CHARS,
        ),
        force=float(merged["Force"]),
        vitesse=float(merged["Vitesse"]),
        resistance=float(merged["Résistance"]),
        environnement=str(merged["Environnement"]),
        passives=passives,
        capability_tokens=tokens,
        modifiers=fuse_modifiers(profile_a.modifiers, profile_b.modifiers),
        native_height_m=envelope_height,
        native_posture=native_posture,
        cosmic_envelope=profile_a.cosmic_envelope or profile_b.cosmic_envelope,
        catalogue_cooldown_s=cooldown,
        origin="fusion",
        parents=(profile_a.taxon_id, profile_b.taxon_id),
        fusion_law=FUSION_LAW_ID,
        stat_raw=tuple((key, raw_numeric[key]) for key in _CANONICAL_NUMERIC),
        extra_stats=extra,
        graphic_height_m=envelope_height,
        size_lock_engaged=False,
        size_lock_reasons=(),
        posture_finale=native_posture,
        posture_detail="",
        skeleton_lock_engaged=False,
        output_stage="biological_merge",
        audit_flags=tuple(dict.fromkeys(flags)),
        design_note=(
            "Fusion double-noyau. Socle = dominant + 0.25 × récessif, plafond 100. "
            "Les modificateurs restent en couche combat."
        ),
    )


def derived_indices(profile: CombatProfile) -> dict[str, float]:
    """Indices dérivés, calculés à la lecture. Jamais réécrits dans le socle."""
    mods = profile.modifier_map()
    speed_raw = profile.vitesse * mods.get("vitesse_cinetique_mult", 1.0)
    resist_raw = profile.resistance + mods.get("armure_osseuse_flat", 0.0)
    water_factor = mods.get("vitesse_surface_liquide_mult", 0.0)
    return {
        "vitesse_effective_brute": round(speed_raw, 6),
        "vitesse_effective": round(min(STAT_CAP, speed_raw), 6),
        "degats_physiques_bruts": round(
            profile.force * mods.get("degats_physiques_mult", 1.0),
            6,
        ),
        "morsure_brute": round(profile.force * mods.get("morsure_mult", 1.0), 6),
        "resistance_armee_brute": round(resist_raw, 6),
        "resistance_armee": round(min(STAT_CAP, resist_raw), 6),
        "vitesse_sur_eau": round(profile.vitesse * water_factor, 6),
    }


def validate_catalogue_modifiers() -> None:
    """Boot : chaque modificateur catalogue doit avoir une loi de fusion."""
    for profile in iter_catalogue():
        for key, _value in profile.modifiers:
            if key not in _KNOWN_MODIFIERS:
                raise FusionInputError(
                    f"{profile.taxon_id} : modificateur non classé {key}"
                )


class BiomnitrixProcessor:
    """Double noyau. Un objet résultat, un slot. L'appel précédent est abandonné."""

    __slots__ = ("_slot",)

    def __init__(self) -> None:
        self._slot: CombatProfile | None = None

    def fuse(self, profile_A: CombatProfile | str, profile_B: CombatProfile | str) -> CombatProfile:
        """Fusionne puis passe la porte ZX-LOCK-01. Le slot n'est écrit qu'à la fin."""
        resolved_a = resolve_profile(profile_A)
        resolved_b = resolve_profile(profile_B)
        merged = _merge_biological(resolved_a, resolved_b)
        projected = apply_hard_constraints(merged)
        # Unique écriture mémoire longue. Pas d'append.
        self._slot = projected
        return projected

    def last(self) -> CombatProfile | None:
        return self._slot

    def clear(self) -> None:
        self._slot = None


_PROCESSOR = BiomnitrixProcessor()


def fuse_profiles(profile_A: CombatProfile | str, profile_B: CombatProfile | str) -> CombatProfile:
    """Contrat public ZX-FUSE-02.

    ``profile_A`` et ``profile_B`` sont un ``CombatProfile`` ou un taxon_id.
    Les stats sont fusionnées par dictionnaire, les passifs sont unionnés,
    les deux verrous physiques sont appliqués au résultat.
    """
    return _PROCESSOR.fuse(profile_A, profile_B)


def last_fusion() -> CombatProfile | None:
    """Dernier résultat seulement. L'historique n'existe pas."""
    return _PROCESSOR.last()


def clear_fusion_slot() -> None:
    """Oublie le slot. Utilisé par la preuve mémoire, pas par le gameplay."""
    _PROCESSOR.clear()


validate_catalogue_modifiers()

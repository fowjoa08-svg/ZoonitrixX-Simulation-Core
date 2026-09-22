#!/usr/bin/env python3
# =============================================================================
# ALCHEMAX — Division Systèmes Neuronaux / Programme ZOONITRIX X
# Protocole ZX-PIPE-01 — Pipeline de boot, preuve, persistance
# Les bibliothèques ne parlent pas. Le pipeline parle, une fois, puis se tait.
# Backend graphique : NULL_SINK. Aucun thread de rendu n'est armé.
# =============================================================================
"""Initialise ZOONITRIX X, charge l'inventaire, active le Fleuron par index.

Usage :
    python main_pipeline.py

Écrit ``ZOONITRIX_X_MANIFEST.md`` et les instantanés JSON sous ``state/``.
Le pipeline ne garde pas l'historique des fusions : chaque appel chaud laisse
un seul slot, la persistance est la frontière disque.
"""

from __future__ import annotations

import gc
import hashlib
import json
import sys
import tracemalloc
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from biomnitrix_processor import (
    FUSION_LAW_ID,
    GIANT_HEIGHT_M,
    HUMAN_MEAN_HEIGHT_LABEL,
    HUMAN_MEAN_HEIGHT_M,
    MICRO_HEIGHT_M,
    POSTURE_LOCK,
    POSTURE_LOCK_DETAIL,
    RECESSIVE_WEIGHT,
    STAT_CAP,
    apply_hard_constraints,
    clear_fusion_slot,
    derived_indices,
    envelope_class,
    fuse_profiles,
    last_fusion,
    merge_stat_dicts,
)
from database_registry import (
    IMMUNITY_TOKENS,
    REGISTRY_ORDER,
    TOKEN_LABELS,
    CombatProfile,
    get_profile,
    iter_catalogue,
    load_inventory,
)
from master_control_bci import (
    EVENT_RING_CAPACITY,
    TRANSFORMATION_LATENCY_S,
    NeuralChip,
    NeuralIndexError,
    TriggerResult,
    bind_chip,
    brainwave_input_trigger,
)

# Politique sandbox. Ce nom n'est pas un import : rien n'est chargé derrière.
RENDER_BACKEND = "NULL_SINK"
ENGINE_VERSION = "ZX-1.0.0"
STAMP_TZ = ZoneInfo("America/Toronto")
ROOT = Path("/home/user")
STATE_DIR = ROOT / "state"
MANIFEST_PATH = ROOT / "ZOONITRIX_X_MANIFEST.md"

Check = tuple[str, bool, str]


def write_json(path: Path, payload: object) -> str:
    """Écrit un JSON canonique et retourne le SHA-256 des octets fichier."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fmt_stat(value: float) -> str:
    """Décimales utiles seulement. 1.75 reste 1.75, pas 1.7500."""
    rounded = round(float(value), 4)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.4f}".rstrip("0").rstrip(".")


def _fmt_m(value: float) -> str:
    rounded = round(float(value), 6)
    if rounded < 0.01:
        return f"{rounded:.4f} m"
    if abs(rounded - round(rounded, 2)) < 1e-9:
        return f"{rounded:.2f} m"
    return f"{rounded:.3f} m"


def _oui(flag: bool) -> str:
    return "oui" if flag else "non"


def _fmt_ns(elapsed_ns: int) -> str:
    return f"{elapsed_ns} ns ({elapsed_ns / 1000:.1f} µs)"


def _resident_delta(iterations: int) -> int:
    """Delta tracemalloc après GC. Une fuite d'historique se voit entre 100 et 4000."""
    clear_fusion_slot()
    gc.collect()
    tracemalloc.start()
    gc.collect()
    baseline = tracemalloc.get_traced_memory()[0]
    left = get_profile("Panthera_tigris")
    right = get_profile("Fossil_Rex")
    for index in range(iterations):
        fuse_profiles(left, right)
        if index % 250 == 0:
            gc.collect()
    gc.collect()
    current = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    clear_fusion_slot()
    gc.collect()
    return current - baseline


def _profile_block(profile: CombatProfile, index: int) -> list[str]:
    classe = envelope_class(profile.native_height_m, profile.cosmic_envelope)
    tokens = ", ".join(profile.capability_tokens)
    modifiers = ", ".join(
        f"{key}={_fmt_stat(value)}" for key, value in profile.modifiers
    ) or "—"
    return [
        f"### Index {index} — `{profile.taxon_id}`",
        "",
        f"- Nom : {profile.common_name}",
        f"- Socle : Force {_fmt_stat(profile.force)} · "
        f"Vitesse {_fmt_stat(profile.vitesse)} · "
        f"Résistance {_fmt_stat(profile.resistance)}",
        f"- Environnement : {profile.environnement}",
        f"- Passifs : {', '.join(profile.passives)}",
        f"- Jetons : {tokens}",
        f"- Modificateurs : {modifiers}",
        f"- Taille native : {_fmt_m(profile.native_height_m)} · classe enveloppe : {classe}",
        f"- Posture native : {profile.native_posture}",
        f"- Cooldown catalogue : {_fmt_stat(profile.catalogue_cooldown_s)} s",
        f"- Note : {profile.design_note}",
        "",
    ]


def _fusion_block(title: str, profile: CombatProfile) -> list[str]:
    raw = dict(profile.stat_raw)
    indices = derived_indices(profile)
    reasons = ", ".join(profile.size_lock_reasons) if profile.size_lock_reasons else "—"
    lines = [
        f"### {title}",
        "",
        f"- Identifiant : `{profile.taxon_id}`",
        f"- Parents immédiats : {' × '.join(profile.parents)}",
        f"- Loi : {profile.fusion_law}",
        f"- Force {_fmt_stat(profile.force)} (brut {_fmt_stat(raw['Force'])}) · "
        f"Vitesse {_fmt_stat(profile.vitesse)} (brut {_fmt_stat(raw['Vitesse'])}) · "
        f"Résistance {_fmt_stat(profile.resistance)} (brut {_fmt_stat(raw['Résistance'])})",
        f"- Environnement : {profile.environnement}",
        f"- Passifs combinés : {', '.join(profile.passives)}",
        f"- Enveloppe native : {_fmt_m(profile.native_height_m)} · "
        f"taille graphique : {_fmt_m(profile.graphic_height_m)}",
        f"- Verrou de taille : {'engagé' if profile.size_lock_engaged else 'non engagé'} "
        f"({reasons})",
        f"- Posture finale : {profile.posture_finale} — {profile.posture_detail}",
        f"- Verrou de squelette : {'engagé' if profile.skeleton_lock_engaged else 'non engagé'}",
        f"- Cooldown catalogue hérité (max des parents, non soumis au BCI ici) : "
        f"{_fmt_stat(profile.catalogue_cooldown_s)} s",
        f"- Indices dérivés : dégâts physiques {_fmt_stat(indices['degats_physiques_bruts'])} · "
        f"morsure {_fmt_stat(indices['morsure_brute'])} · "
        f"vitesse effective {_fmt_stat(indices['vitesse_effective'])} · "
        f"vitesse sur eau {_fmt_stat(indices['vitesse_sur_eau'])}",
        "",
    ]
    return lines


def render_manifest(ctx: dict[str, object]) -> str:
    """Manifeste opérateur. Tous les chiffres viennent du contexte d'exécution."""
    trigger: TriggerResult = ctx["trigger"]  # type: ignore[assignment]
    form = trigger.form
    hydro: CombatProfile = ctx["hydro"]  # type: ignore[assignment]
    beast: CombatProfile = ctx["beast"]  # type: ignore[assignment]
    checks: list[Check] = ctx["checks"]  # type: ignore[assignment]
    hashes: dict[str, str] = ctx["hashes"]  # type: ignore[assignment]
    memory = ctx["memory"]
    stamp: str = ctx["stamp"]  # type: ignore[assignment]
    immunities = [
        TOKEN_LABELS[token]
        for token in form.capability_tokens
        if token in IMMUNITY_TOKENS
    ]
    lines: list[str] = [
        "# ZOONITRIX X — Manifeste d'état",
        "",
        "Moteur de jeu fictif. Statistiques de combat, pas des mesures de laboratoire. "
        f"Backend graphique : `{RENDER_BACKEND}`. Aucun rendu n'a été lancé.",
        "",
        f"- Version : `{ENGINE_VERSION}`",
        f"- Horodatage : {stamp} (America/Toronto)",
        f"- Forme active : `{trigger.taxon_id}` — {form.common_name}, index neuronal {trigger.neuron_id}",
        f"- Cooldown effectif : **{trigger.cooldown_s:g} s** "
        f"(catalogue {_fmt_stat(trigger.catalogue_cooldown_s)} s, supprimé)",
        f"- Quantum contractuel : **{trigger.latency_contract_s:.3f} s** · "
        f"calcul mesuré : {_fmt_ns(trigger.compute_elapsed_ns)}",
        f"- Taille graphique : **{_fmt_m(form.graphic_height_m)}** "
        f"(enveloppe native {_fmt_m(form.native_height_m)})",
        f"- Posture finale : **{form.posture_finale}** — {form.posture_detail}",
        f"- Passive : **{', '.join(form.passives)}**",
        "",
        "## 1. Architecture",
        "",
        "Quatre modules, une direction de dépendance, aucune boucle.",
        "",
        "```",
        "database_registry.py        vérité catalogue, identifiants seulement dans l'inventaire",
        "        |",
        "        v",
        "biomnitrix_processor.py     ZX-FUSE-02 + porte ZX-LOCK-01 (un slot de fusion)",
        "        |",
        "        v",
        "master_control_bci.py       index neuronal, cooldown 0, menus non appelés (un slot hôte)",
        "        |",
        "        v",
        "main_pipeline.py            boot, preuves, JSON, manifeste — les bibliothèques se taisent",
        "```",
        "",
        "Le Master Control ne publie pas une taille. Il appelle la même porte que la fusion. "
        "Il n'y a pas de drapeau de contournement : un paramètre non écrit ne peut pas être activé.",
        "",
        "Bornes chaudes, constantes quel que soit le nombre d'appels :",
        "",
        "| Ressource | Borne |",
        "| --- | --- |",
        f"| Profils catalogue | {len(REGISTRY_ORDER)} |",
        "| Slot hôte | 1 |",
        "| Slot de fusion | 1 |",
        f"| Anneau d'événements | {EVENT_RING_CAPACITY} |",
        "| Passifs par profil | ≤ 12 |",
        "| Jetons par profil | ≤ 16 |",
        "| Jetons d'environnement | ≤ 8 |",
        "| Parents retenus | 2 (immédiats seulement) |",
        "| Identifiant de fusion | ≤ 64 caractères |",
        "",
        "## 2. Lois",
        "",
        f"- Fusion numérique : `min({_fmt_stat(STAT_CAP)}, max(A, B) + {RECESSIVE_WEIGHT:g} × min(A, B))`. "
        "Le brut est archivé dans le résultat, le stocké est plafonné.",
        "- Fusion texte : union ordonnée des jetons séparés par ` / `, plafond 8.",
        "- Passifs : union stable, ordre du parent A puis du parent B, doublons retirés.",
        "- Modificateurs : couche séparée. Bonus de multiplicateurs additionnés, "
        "plats sommés, drapeaux en OU. Jamais réinjectés dans le socle.",
        f"- Verrou de taille : si l'enveloppe est < {MICRO_HEIGHT_M:.2f} m, > {GIANT_HEIGHT_M:.2f} m, "
        f"ou cosmique, la taille graphique devient {HUMAN_MEAN_HEIGHT_LABEL}.",
        f"- Verrou de squelette : posture finale « {POSTURE_LOCK} », {POSTURE_LOCK_DETAIL}. "
        "Inconditionnel dès que l'appareil parle.",
        "- Cooldown : le catalogue le porte. Seul le BCI l'écrit à 0. La fusion hérite du max des parents.",
        "",
        "## 3. Inventaire neuronal",
        "",
        "L'inventaire est un tuple d'identifiants. Les profils ne sont pas copiés dedans.",
        "",
        "| Index | Taxon | Nom | Force | Vitesse | Résistance | Taille native | Classe | CD catalogue |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, taxon_id in enumerate(REGISTRY_ORDER):
        profile = get_profile(taxon_id)
        lines.append(
            f"| {index} | `{taxon_id}` | {profile.common_name} | "
            f"{_fmt_stat(profile.force)} | {_fmt_stat(profile.vitesse)} | "
            f"{_fmt_stat(profile.resistance)} | {_fmt_m(profile.native_height_m)} | "
            f"{envelope_class(profile.native_height_m, profile.cosmic_envelope)} | "
            f"{_fmt_stat(profile.catalogue_cooldown_s)} s |"
        )
    lines.append("")
    for index, taxon_id in enumerate(REGISTRY_ORDER):
        lines.extend(_profile_block(get_profile(taxon_id), index))

    lines.extend(
        [
            "## 4. Activation Master Control — Alien X Tardigrade",
            "",
            "Appel exécuté : `brainwave_input_trigger(4)`. "
            "Les menus physiques n'ont pas été invoqués. "
            f"Compteur d'ouverture de menu après le commit : {trigger.menu_invocations}.",
            "",
            f"- Index : {trigger.neuron_id}",
            f"- Taxon : `{trigger.taxon_id}`",
            f"- Étape de sortie : {form.output_stage}",
            f"- Cooldown effectif : {trigger.cooldown_s:g} s "
            f"(suppression : {_oui(trigger.cooldown_suppressed)})",
            f"- Quantum : {trigger.latency_contract_s:.3f} s · "
            f"mesuré : {_fmt_ns(trigger.compute_elapsed_ns)} · "
            f"dans le quantum : {_oui(trigger.compute_elapsed_ns / 1_000_000_000 < trigger.latency_contract_s)}",
            f"- Socle inchangé : Force {_fmt_stat(form.force)} · "
            f"Vitesse {_fmt_stat(form.vitesse)} · "
            f"Résistance {_fmt_stat(form.resistance)}",
            f"- Environnement : {form.environnement}",
            f"- Survie Absolue : {', '.join(immunities)}",
            f"- Enveloppe native : {_fmt_m(form.native_height_m)} "
            f"(corps tardigrade) · drapeau cosmique : {_oui(form.cosmic_envelope)}",
            f"- Raisons du verrou de taille : {', '.join(form.size_lock_reasons)}",
            f"- Taille graphique publiée : {_fmt_m(form.graphic_height_m)} "
            f"({HUMAN_MEAN_HEIGHT_LABEL})",
            f"- Posture native auditée : {form.native_posture}",
            f"- Posture finale : {form.posture_finale} — {form.posture_detail}",
            "- Anneau d'événements : une empreinte compacte. Le profil complet vit dans le slot hôte, pas dans l'anneau.",
            "",
            "Le registre catalogue n'a pas été réécrit. "
            f"Hauteur catalogue du Fleuron après activation : "
            f"{_fmt_m(get_profile('ALIEN_X_TARDIGRADE').native_height_m)}, "
            f"verrou catalogue : {_oui(get_profile('ALIEN_X_TARDIGRADE').size_lock_engaged)}.",
            "",
            "## 5. Démonstration du processeur double-noyau",
            "",
            "La fusion des socles numériques est commutative. L'identifiant et l'ordre des passifs ne le sont pas. "
            "Les deux démonstrations ci-dessous sont l'ordre A puis B, passé par la porte de verrou.",
            "",
        ]
    )
    lines.extend(
        _fusion_block(
            "Acinonyx_jubatus × Basiliscus_basiliscus — nominal, squelette seul",
            hydro,
        )
    )
    lines.extend(
        _fusion_block(
            "Panthera_tigris × Fossil_Rex — géant recalibré, Bégalosaure osseux",
            beast,
        )
    )
    lines.extend(
        [
            "Le guépard-basilic reste à hauteur d'enveloppe nominale : le verrou de taille ne s'engage pas. "
            "Le verrou de squelette s'engage quand même. Le tigre-rex porte une enveloppe de 5.50 m : "
            f"la taille graphique est recalibrée à {HUMAN_MEAN_HEIGHT_LABEL}. "
            "Mode Bégalosaure, armure osseuse et bonus de morsure sont tous présents.",
            "",
            "## 6. Preuve de borne mémoire",
            "",
            "Quatre mille fusions contre cent, slot unique, GC entre les deux mesures. "
            "Une liste d'historique ferait croître le second delta avec le nombre d'appels. "
            "Le delta inclut le slot de fusion et le bruit de tracemalloc, pas une courbe.",
            "",
            f"- Delta résident après 100 fusions : {memory['delta_100']} octets",
            f"- Delta résident après 4000 fusions : {memory['delta_4000']} octets",
            f"- Écart absolu : {memory['spread']} octets",
            f"- Verdict : {memory['verdict']}",
            "",
            "## 7. Artefacts",
            "",
            "| Fichier | SHA-256 |",
            "| --- | --- |",
        ]
    )
    for name, digest in hashes.items():
        lines.append(f"| `{name}` | `{digest}` |")
    lines.extend(["", "## 8. Invariants", ""])
    failed = 0
    for name, passed, detail in checks:
        mark = "PASS" if passed else "FAIL"
        if not passed:
            failed += 1
        suffix = f" — {detail}" if detail else ""
        lines.append(f"- [{mark}] {name}{suffix}")
    lines.extend(
        [
            "",
            f"Bilan : {len(checks) - failed}/{len(checks)} invariants tenus.",
            "",
            "---",
            "",
            "ZOONITRIX X · cellule d'architecture logicielle · document généré par `main_pipeline.py`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    stamp = datetime.now(STAMP_TZ).isoformat(timespec="seconds")
    inventory = load_inventory()
    chip = NeuralChip(inventory)
    bind_chip(chip)

    checks: list[Check] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        checks.append((name, bool(condition), detail))

    # Le menu sait s'ouvrir. On le prouve désarmé, puis on le réarme avant le commit.
    chip.menu.armed = False
    chip.menu.open_selector()
    physical_probe = chip.menu.invocations
    chip.menu.invocations = 0
    chip.menu.armed = True
    check(
        "le menu physique s'ouvre si on l'appelle",
        physical_probe == 1,
        f"invocations sonde = {physical_probe}",
    )

    host_before = chip.host
    rejected_index = False
    try:
        brainwave_input_trigger(99)
    except NeuralIndexError:
        rejected_index = True
    rejected_bool = False
    try:
        brainwave_input_trigger(True)  # type: ignore[arg-type]
    except TypeError:
        rejected_bool = True
    rejected_negative = False
    try:
        brainwave_input_trigger(-1)
    except NeuralIndexError:
        rejected_negative = True
    check("index 99 rejeté sans commit", rejected_index and chip.host is host_before)
    check("booléen rejeté (True n'est pas l'index 1)", rejected_bool and chip.host is host_before)
    check("index négatif rejeté sans commit", rejected_negative and chip.host is host_before)

    # Preuve mémoire avant les démonstrations persistées. Le slot est vidé ensuite.
    delta_100 = _resident_delta(100)
    delta_4000 = _resident_delta(4000)
    spread = abs(delta_4000 - delta_100)
    # 4000 objets retenus pesteraient des mégaoctets. 256 Ko d'écart absorbe le bruit
    # de tracemalloc sans laisser passer un historique.
    memory_ok = spread < 262_144 and delta_4000 < 262_144
    memory = {
        "iterations_a": 100,
        "iterations_b": 4000,
        "delta_100": delta_100,
        "delta_4000": delta_4000,
        "spread": spread,
        "verdict": "O(1) tenu" if memory_ok else "BORNE ROMPUE",
        "threshold_bytes": 262_144,
    }
    check(
        "mémoire de fusion bornée (100 vs 4000)",
        memory_ok,
        f"deltas {delta_100} / {delta_4000} octets",
    )

    # Fusion dynamique hors catalogue : une clé supplémentaire doit passer, les entrées rester intactes.
    synthetic_a: dict[str, float | str] = {
        "Force": 10.0,
        "Vitesse": 10.0,
        "Résistance": 10.0,
        "Environnement": "a",
        "Perception": 40.0,
    }
    synthetic_b: dict[str, float | str] = {
        "Force": 20.0,
        "Vitesse": 20.0,
        "Résistance": 20.0,
        "Environnement": "b",
        "Perception": 80.0,
    }
    snapshot_a = dict(synthetic_a)
    merged_synth, raw_synth, _flags = merge_stat_dicts(synthetic_a, synthetic_b)
    check("dictionnaires d'entrée non mutés", synthetic_a == snapshot_a)
    check(
        "clé supplémentaire Perception fusionnée",
        merged_synth.get("Perception") == 90.0 and raw_synth.get("Perception") == 90.0,
        f"valeur {merged_synth.get('Perception')}",
    )

    slot_before_error = fuse_profiles("Acinonyx_jubatus", "Basiliscus_basiliscus")
    error_preserved = False
    try:
        fuse_profiles("taxon_inexistant", "Acinonyx_jubatus")
    except Exception:
        error_preserved = last_fusion() is slot_before_error
    check("échec de fusion : le slot précédent n'est pas écrasé", error_preserved)

    hydro = fuse_profiles("Acinonyx_jubatus", "Basiliscus_basiliscus")
    hydro_reverse = fuse_profiles("Basiliscus_basiliscus", "Acinonyx_jubatus")
    check(
        "fusion numérique commutative",
        hydro.force == hydro_reverse.force
        and hydro.vitesse == hydro_reverse.vitesse
        and hydro.resistance == hydro_reverse.resistance,
    )
    check(
        "libellé de fusion non commutatif",
        hydro.taxon_id != hydro_reverse.taxon_id and hydro.passives != hydro_reverse.passives,
    )
    check(
        "passifs du couple vitesse/eau tous présents",
        set(hydro.passives) == {"Buff de vitesse cinétique", "Hydro-foulée"},
    )
    check(
        "verrou de taille silencieux sur enveloppe nominale",
        (not hydro.size_lock_engaged) and hydro.graphic_height_m == 0.875,
    )
    check(
        "verrou de squelette engagé même sans recalibrage de taille",
        hydro.skeleton_lock_engaged and hydro.posture_finale == POSTURE_LOCK,
    )

    beast = fuse_profiles(get_profile("Panthera_tigris"), get_profile("Fossil_Rex"))
    beast_by_str = fuse_profiles("Panthera_tigris", "Fossil_Rex")
    check(
        "résolution objet et taxon_id équivalentes",
        beast.force == beast_by_str.force and beast.passives == beast_by_str.passives,
    )
    check(
        "Bégalosaure osseux : passifs combinés et taille recalibrée",
        set(beast.passives) == {"Mode Bégalosaure", "Armure osseuse", "Bonus de morsure"}
        and beast.graphic_height_m == HUMAN_MEAN_HEIGHT_M
        and beast.size_lock_engaged
        and "géant" in beast.size_lock_reasons
        and beast.posture_finale == POSTURE_LOCK
        and beast.posture_detail == POSTURE_LOCK_DETAIL,
    )
    check(
        "plafond de socle sans perte du brut",
        beast.force == STAT_CAP and dict(beast.stat_raw)["Force"] == 118.0,
        f"stocké {beast.force}, brut {dict(beast.stat_raw)['Force']}",
    )

    deep = fuse_profiles(hydro, beast)
    check(
        "identifiant de fusion profonde borné à 64 caractères",
        len(deep.taxon_id) <= 64 and deep.taxon_id.startswith("ZX-"),
        deep.taxon_id,
    )
    check("parents immédiats seulement", len(deep.parents) == 2)

    # Réécriture officielle de l'ordre A×B après les tests qui ont écrasé le slot.
    hydro = fuse_profiles("Acinonyx_jubatus", "Basiliscus_basiliscus")
    beast = fuse_profiles("Panthera_tigris", "Fossil_Rex")

    catalogue_fleuron = get_profile("ALIEN_X_TARDIGRADE")
    trigger = brainwave_input_trigger(4)
    check("index 4 commet le Fleuron", trigger.taxon_id == "ALIEN_X_TARDIGRADE" and trigger.neuron_id == 4)
    check("cooldown forcé à 0", trigger.cooldown_s == 0.0 and trigger.cooldown_suppressed)
    check(
        "quantum contractuel 0.001 s et calcul à l'intérieur",
        trigger.latency_contract_s == TRANSFORMATION_LATENCY_S
        and trigger.compute_elapsed_ns / 1_000_000_000 < TRANSFORMATION_LATENCY_S,
        _fmt_ns(trigger.compute_elapsed_ns),
    )
    check("menus non invoqués par le déclencheur", trigger.menu_invocations == 0 and chip.menu.invocations == 0)
    check(
        "Fleuron recalibré à 1.75 m, socle immunitaire intact",
        trigger.form.graphic_height_m == HUMAN_MEAN_HEIGHT_M
        and trigger.form.native_height_m == catalogue_fleuron.native_height_m
        and set(IMMUNITY_TOKENS).issubset(trigger.form.capability_tokens)
        and "Survie Absolue" in trigger.form.passives
        and trigger.form.posture_finale == POSTURE_LOCK,
    )
    check(
        "catalogue non muté par la matérialisation",
        catalogue_fleuron.size_lock_engaged is False
        and catalogue_fleuron.output_stage == "catalogue"
        and catalogue_fleuron.graphic_height_m == 0.0005
        and get_profile("ALIEN_X_TARDIGRADE") is catalogue_fleuron,
    )
    projected_twice = apply_hard_constraints(trigger.form)
    check(
        "porte de verrou idempotente",
        projected_twice.graphic_height_m == trigger.form.graphic_height_m
        and projected_twice.force == trigger.form.force
        and projected_twice.native_height_m == trigger.form.native_height_m
        and projected_twice.posture_finale == POSTURE_LOCK,
    )
    check(
        "slot hôte unique et anneau compact",
        chip.host is trigger and len(chip.event_log()) == 1,
    )
    check("loi de fusion estampillée", beast.fusion_law == FUSION_LAW_ID and hydro.fusion_law == FUSION_LAW_ID)
    check("backend de rendu non armé", RENDER_BACKEND == "NULL_SINK")

    hashes: dict[str, str] = {}
    artefacts = {
        "state/registry.json": {
            "protocol": "ZX-REG-01",
            "profiles": [profile.as_dict() for profile in iter_catalogue()],
        },
        "state/inventory.json": {
            "protocol": "ZX-BCI-01",
            "indices": [
                {
                    "neuron_id": index,
                    "taxon_id": taxon_id,
                    "common_name": get_profile(taxon_id).common_name,
                }
                for index, taxon_id in enumerate(inventory)
            ],
        },
        "state/fusion_acinonyx_basiliscus.json": {
            "protocol": "ZX-FUSE-02",
            "profile": hydro.as_dict(),
            "derived": derived_indices(hydro),
        },
        "state/fusion_panthera_rex.json": {
            "protocol": "ZX-FUSE-02",
            "profile": beast.as_dict(),
            "derived": derived_indices(beast),
        },
        "state/bci_activation.json": trigger.as_dict(),
        "state/memory_bound.json": memory,
        "state/invariants.json": {
            "checks": [
                {"name": name, "passed": passed, "detail": detail}
                for name, passed, detail in checks
            ]
        },
    }
    for relative, payload in artefacts.items():
        hashes[relative] = write_json(ROOT / relative, payload)

    engine_state = {
        "version": ENGINE_VERSION,
        "stamp": stamp,
        "render_backend": RENDER_BACKEND,
        "active_taxon": trigger.taxon_id,
        "neuron_id": trigger.neuron_id,
        "cooldown_s": trigger.cooldown_s,
        "latency_contract_s": trigger.latency_contract_s,
        "compute_elapsed_ns": trigger.compute_elapsed_ns,
        "graphic_height_m": trigger.form.graphic_height_m,
        "posture_finale": trigger.form.posture_finale,
        "fusion_slot_taxon": None if last_fusion() is None else last_fusion().taxon_id,
        "event_log": list(chip.event_log()),
        "artefacts_sha256": hashes,
    }
    hashes["state/engine_state.json"] = write_json(STATE_DIR / "engine_state.json", engine_state)

    # Le manifeste est écrit après les JSON pour pouvoir y citer leurs condensats.
    # Son propre condensat n'est pas auto-référent.
    manifest = render_manifest(
        {
            "trigger": trigger,
            "hydro": hydro,
            "beast": beast,
            "checks": checks,
            "hashes": hashes,
            "memory": memory,
            "stamp": stamp,
        }
    )
    MANIFEST_PATH.write_text(manifest, encoding="utf-8")

    failed = [name for name, passed, _detail in checks if not passed]
    print(f"ZOONITRIX X {ENGINE_VERSION} — pipeline terminé")
    print(f"forme active : {trigger.taxon_id} (index {trigger.neuron_id})")
    print(f"cooldown     : {trigger.cooldown_s:g} s")
    print(f"quantum      : {trigger.latency_contract_s:.3f} s · mesuré {trigger.compute_elapsed_ns} ns")
    print(f"taille       : {trigger.form.graphic_height_m} m · posture {trigger.form.posture_finale}")
    print(f"mémoire      : {memory['verdict']} · écart {spread} octets")
    print(f"invariants   : {len(checks) - len(failed)}/{len(checks)}")
    print(f"manifeste    : {MANIFEST_PATH}")
    if failed:
        print("ÉCHECS : " + " ; ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

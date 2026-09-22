# =============================================================================
# ALCHEMAX — Division Systèmes Neuronaux / Programme ZOONITRIX X
# Protocole ZX-BCI-01 — Master Control par la pensée
# Simulation d'interface. `neuron_id` est un index d'inventaire, pas une
# adresse corticale. Aucune fréquence, aucun implant, aucun signal réel.
# =============================================================================
"""Master Control simulé : sélection d'index, cooldown nul, menus non appelés.

Le quantum de transformation est 0.001 s. C'est un contrat d'interface, pas
un ``sleep``. Endormir le fil serait une latence théâtrale et un risque de
timeout sandbox. La forme est commise dans le quantum ; le temps CPU mesuré
est rapporté à part, pour qu'on ne confonde pas le contrat et la mesure.

Ce module ne recalcule pas les stats et ne réimplémente pas les verrous.
La seule publication légale de la taille graphique passe par
``apply_hard_constraints``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from biomnitrix_processor import apply_hard_constraints
from database_registry import CombatProfile, get_profile

__all__ = (
    "TRANSFORMATION_LATENCY_S",
    "EVENT_RING_CAPACITY",
    "MenuBypassError",
    "NeuralIndexError",
    "NeuralChip",
    "PhysicalMenu",
    "TriggerResult",
    "bind_chip",
    "bound_chip",
    "brainwave_input_trigger",
)

# Quantum protocolaire. Comparer à cette constante, pas à une division recalculée.
TRANSFORMATION_LATENCY_S: float = 0.001
EVENT_RING_CAPACITY: int = 8


class NeuralIndexError(IndexError):
    """Index hors inventaire. L'état hôte n'a pas été écrit."""


class MenuBypassError(RuntimeError):
    """Le menu physique armé a été ouvert. Le Master Control ne doit jamais l'atteindre."""


class PhysicalMenu:
    """Menu physique de l'appareil. Présent pour être contourné, pas pour être utilisé.

    S'il est armé, l'ouvrir lève. Le déclencheur neuronal n'a pas d'appel vers
    ``open_selector``. Si une édition future en ajoute un, le pipeline casse.
    C'est le but du tripwire.
    """

    __slots__ = ("armed", "invocations")

    def __init__(self) -> None:
        self.armed = True
        self.invocations = 0

    def open_selector(self) -> None:
        self.invocations += 1
        if self.armed:
            raise MenuBypassError(
                "Menu physique armé. Le Master Control n'a pas le droit de l'ouvrir."
            )


class _Ring:
    """Anneau fixe. Capacité choisie à la construction, jamais réallouée."""

    __slots__ = ("_buf", "_i", "_n")

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("anneau de capacité nulle")
        self._buf: list[dict[str, object] | None] = [None] * capacity
        self._i = 0
        self._n = 0

    def push(self, item: dict[str, object]) -> None:
        self._buf[self._i] = item
        self._i = (self._i + 1) % len(self._buf)
        if self._n < len(self._buf):
            self._n += 1

    def items(self) -> tuple[dict[str, object], ...]:
        capacity = len(self._buf)
        start = (self._i - self._n) % capacity
        return tuple(
            self._buf[(start + offset) % capacity]  # type: ignore[misc]
            for offset in range(self._n)
        )


@dataclass(frozen=True, slots=True)
class TriggerResult:
    """Commit neuronal. Un seul de ces objets est retenu par la puce."""

    neuron_id: int
    taxon_id: str
    catalogue_cooldown_s: float
    cooldown_s: float
    cooldown_suppressed: bool
    menu_bypassed: bool
    menu_invocations: int
    latency_contract_s: float
    compute_elapsed_ns: int
    form: CombatProfile
    inventory_size: int

    def as_dict(self) -> dict[str, object]:
        elapsed_s = self.compute_elapsed_ns / 1_000_000_000
        return {
            "neuron_id": self.neuron_id,
            "taxon_id": self.taxon_id,
            "catalogue_cooldown_s": self.catalogue_cooldown_s,
            "cooldown_s": self.cooldown_s,
            "cooldown_suppressed": self.cooldown_suppressed,
            "menu_bypassed": self.menu_bypassed,
            "menu_invocations": self.menu_invocations,
            "latency_contract_s": self.latency_contract_s,
            "compute_elapsed_ns": self.compute_elapsed_ns,
            "compute_elapsed_s": elapsed_s,
            "within_quantum": elapsed_s < self.latency_contract_s,
            "inventory_size": self.inventory_size,
            "form": self.form.as_dict(),
        }


def _compact(result: TriggerResult) -> dict[str, object]:
    """Empreinte d'anneau. Pas le profil complet : l'anneau ne devient pas une seconde base."""
    return {
        "neuron_id": result.neuron_id,
        "taxon_id": result.taxon_id,
        "cooldown_s": result.cooldown_s,
        "latency_contract_s": result.latency_contract_s,
        "compute_elapsed_ns": result.compute_elapsed_ns,
        "graphic_height_m": result.form.graphic_height_m,
        "posture_finale": result.form.posture_finale,
        "size_lock_engaged": result.form.size_lock_engaged,
    }


class NeuralChip:
    """Puce simulée. Un slot hôte. Un anneau de 8. Inventaire = tuple d'identifiants."""

    __slots__ = ("inventory", "menu", "_host", "_ring")

    def __init__(self, inventory: tuple[str, ...]) -> None:
        if not inventory:
            raise NeuralIndexError("inventaire vide : aucun index sélectionnable")
        # On vérifie les identifiants au boot, pas au moment du déclencheur.
        for taxon_id in inventory:
            get_profile(taxon_id)
        self.inventory = inventory
        self.menu = PhysicalMenu()
        self._host: TriggerResult | None = None
        self._ring = _Ring(EVENT_RING_CAPACITY)

    @property
    def host(self) -> TriggerResult | None:
        return self._host

    def event_log(self) -> tuple[dict[str, object], ...]:
        return self._ring.items()

    def trigger(self, neuron_id: int) -> TriggerResult:
        """Sélectionne une forme par index. Menus non appelés. Cooldown forcé à 0.

        Validation avant toute écriture. Un index illégal laisse le slot hôte
        tel qu'il était.
        """
        self._reject_illegal_index(neuron_id)
        started = time.perf_counter_ns()
        taxon_id = self.inventory[neuron_id]
        catalogue = get_profile(taxon_id)
        # Aucune affectation directe de la taille graphique dans cette fonction.
        projected = apply_hard_constraints(catalogue)
        elapsed_ns = time.perf_counter_ns() - started
        result = TriggerResult(
            neuron_id=neuron_id,
            taxon_id=taxon_id,
            catalogue_cooldown_s=catalogue.catalogue_cooldown_s,
            cooldown_s=0.0,
            cooldown_suppressed=True,
            menu_bypassed=True,
            menu_invocations=self.menu.invocations,
            latency_contract_s=TRANSFORMATION_LATENCY_S,
            compute_elapsed_ns=elapsed_ns,
            form=projected,
            inventory_size=len(self.inventory),
        )
        # Commit unique, après construction complète.
        self._host = result
        self._ring.push(_compact(result))
        return result

    def _reject_illegal_index(self, neuron_id: object) -> None:
        # True est un int en Python (True == 1). Sans ce rejet, l'index 1
        # partirait sur un booléen. On refuse la coercion.
        if isinstance(neuron_id, bool) or not isinstance(neuron_id, int):
            raise TypeError(
                "neuron_id doit être un index entier. "
                "Un booléen n'est pas un index : True == 1 est un piège, il est rejeté."
            )
        if neuron_id < 0 or neuron_id >= len(self.inventory):
            last = len(self.inventory) - 1
            raise NeuralIndexError(
                f"index {neuron_id} hors inventaire [0, {last}]. Aucune forme commise."
            )


_CHIP: NeuralChip | None = None


def bind_chip(chip: NeuralChip) -> None:
    """Publie la puce que le contrat fonctionnel doit voir. Une seule à la fois."""
    global _CHIP
    _CHIP = chip


def bound_chip() -> NeuralChip:
    if _CHIP is None:
        raise RuntimeError(
            "Puce BCI non initialisée. Construire un NeuralChip et appeler bind_chip."
        )
    return _CHIP


def brainwave_input_trigger(neuron_id: int) -> TriggerResult:
    """Contrat public ZX-BCI-01.

    Court-circuite les menus physiques, force ``cooldown = 0``, et commet la
    forme d'index ``neuron_id`` dans le quantum de 0.001 s. L'index 4 du
    contrat catalogue est ``ALIEN_X_TARDIGRADE``.
    """
    return bound_chip().trigger(neuron_id)

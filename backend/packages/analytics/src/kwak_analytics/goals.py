"""The chance of reaching each goal (spec §4.12 F-ANA-7, invariant §8.35), on the projection's
engine: the goal's envelope is held as its own amount on each funding line, growing with that
line's category draws (the same streams, seed and engine version as F-SIM-4, so lines of one
category move together); each month it receives a monthly amount, split across its lines by
their shares of the rises, until the target is reached. The chance is the share of outcomes
that reach the target at least once by the deadline. Current euros, as the targets."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import numpy as np
from kwak_core.money import quantize
from kwak_core.projection import Assumption, monthly_params

from kwak_analytics.montecarlo import DEFAULT_SEED, PATHS, Category, draw, streams

ZERO = Decimal(0)


@dataclass(frozen=True)
class GoalLine:
    category_id: UUID
    """Its draws are the category's: lines of one category move together."""
    assumption: Assumption
    held: Decimal
    """What the goal's envelope holds on the line now."""
    share: Decimal
    """Of the goal's new money, the shares of the rises normalised to sum to 1."""


@dataclass(frozen=True)
class GoalChance:
    chance: Decimal
    """The share of outcomes that reach the target at least once by the deadline."""
    certain: bool
    """No funding line has any volatility: every outcome is the same."""
    short: Decimal
    """When certain: by how much the best month falls short of the target (0 if reached)."""


def chance_of_goal(
    lines: Sequence[GoalLine],
    *,
    target: Decimal,
    monthly: Decimal,
    months: int,
    paths: int = PATHS,
    seed: int = DEFAULT_SEED,
) -> GoalChance:
    """`monthly`: the planned allocation or the required effort (F-GOAL-6, F-GOAL-5), never the
    actual effort, which already holds past returns the draws would count twice."""
    certain = all(line.assumption.volatility == 0 for line in lines)
    if certain:
        paths = 1
    categories = list(dict.fromkeys(line.category_id for line in lines))
    column = [categories.index(line.category_id) for line in lines]
    generators = streams(
        [Category(c, None, ZERO, Assumption(ZERO, ZERO), ZERO) for c in categories], seed
    )
    params = [monthly_params(line.assumption) for line in lines]
    mu = np.array([float(m) for m, _ in params])
    sigma = np.array([float(s) for _, s in params])
    share = np.array([float(line.share) for line in lines])
    held = np.tile(np.array([float(line.held) for line in lines]), (paths, 1))
    goal = float(target)
    best = held.sum(axis=1)
    for _ in range(months):
        z = draw(generators, paths)[:, column]
        held = held * np.exp(mu + sigma * z) + float(monthly) * share
        best = np.maximum(best, held.sum(axis=1))
    reached = best >= goal - 0.005
    chance = Decimal(int(reached.sum())) / Decimal(paths)
    short = max(ZERO, quantize(Decimal(repr(goal - float(best[0]))))) if certain else ZERO
    return GoalChance(chance, certain, short)

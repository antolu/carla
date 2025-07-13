"""Reinforcement learning environment for brewing optimization."""

from __future__ import annotations

import random

from .models import BrewAction, BrewEvaluation, BrewState

# Evaluation constants
IDEAL_METRIC_MIN = 5
IDEAL_METRIC_MAX = 6
ACCEPTABLE_METRIC_MIN = 4
ACCEPTABLE_METRIC_MAX = 7

# Channeling thresholds
LOW_CHANNELING_THRESHOLD = 3
HIGH_CHANNELING_THRESHOLD = 7

# Brew time thresholds (seconds)
IDEAL_BREW_TIME_MIN = 25
IDEAL_BREW_TIME_MAX = 35
MIN_BREW_TIME = 20
MAX_BREW_TIME = 45

# Date parsing threshold
MAX_SHORT_DATE_LENGTH = 10

# Removed bean freshness constants - agent will learn these relationships


class BrewingEnvironment:
    """Environment for brewing parameter optimization."""

    # Action space bounds
    GRIND_SIZE_BOUNDS = (1, 30)  # 1=very fine, 30=very coarse (integer settings)
    BREW_VOLUME_BOUNDS = (25.0, 50.0)  # ml
    COFFEE_DOSE_BOUNDS = (15.0, 25.0)  # g

    # Discretization for Q-learning
    GRIND_SIZE_STEPS = 30
    BREW_VOLUME_STEPS = 10
    COFFEE_DOSE_STEPS = 10

    def __init__(self) -> None:
        self.action_space_size = (
            self.GRIND_SIZE_STEPS *
            self.BREW_VOLUME_STEPS *
            self.COFFEE_DOSE_STEPS
        )

    def state_to_key(self, state: BrewState) -> str:
        """Convert state to string key for Q-table."""
        return f"{state.is_first_brew}_{min(state.days_since_roast, 30)}"

    def action_to_key(self, action: BrewAction) -> str:
        """Convert action to string key for Q-table."""
        grind_idx = self._discretize_grind(action.grind_size)
        volume_idx = self._discretize_volume(action.brew_volume)
        dose_idx = self._discretize_dose(action.coffee_dose)
        return f"{grind_idx}_{volume_idx}_{dose_idx}"

    def action_from_indices(self, grind_idx: int, volume_idx: int, dose_idx: int) -> BrewAction:
        """Create action from discrete indices."""
        grind_size = self._undiscretize_grind(grind_idx)
        brew_volume = self._undiscretize_volume(volume_idx)
        coffee_dose = self._undiscretize_dose(dose_idx)

        return BrewAction(
            grind_size=grind_size,
            brew_volume=brew_volume,
            coffee_dose=coffee_dose
        )

    def get_random_action(self) -> BrewAction:
        """Generate a random valid action."""
        grind_size = random.randint(*self.GRIND_SIZE_BOUNDS)
        brew_volume = random.uniform(*self.BREW_VOLUME_BOUNDS)
        coffee_dose = random.uniform(*self.COFFEE_DOSE_BOUNDS)

        return BrewAction(
            grind_size=grind_size,
            brew_volume=brew_volume,
            coffee_dose=coffee_dose
        )

    def get_baseline_action(self, state: BrewState) -> BrewAction:
        """Get neutral baseline action using standard espresso values."""
        return BrewAction(
            grind_size=15,    # Neutral middle of 1-30 range - to be learned
            brew_volume=40.0, # Standard espresso volume
            coffee_dose=18.0  # Standard espresso dose
        )

    def calculate_reward(self, evaluation: BrewEvaluation) -> float:
        """Calculate reward from user evaluation."""
        if evaluation.overall_experience is not None:
            # Primary reward from overall experience
            reward = (evaluation.overall_experience - 5.5) / 4.5  # Scale to [-1, 1]
        else:
            # Fallback: average of available metrics
            reward = self._calculate_metrics_reward(evaluation)

        # Apply bonuses/penalties
        reward += self._calculate_channeling_bonus(evaluation)
        reward += self._calculate_brew_time_bonus(evaluation)

        return max(-1.0, min(1.0, reward))

    def _calculate_metrics_reward(self, evaluation: BrewEvaluation) -> float:
        """Calculate reward from taste metrics."""
        metrics = []
        for value in [
            evaluation.bitterness,
            evaluation.acidity,
            evaluation.taste_strength
        ]:
            if value is not None:
                # For these metrics, ideal range is balanced
                if IDEAL_METRIC_MIN <= value <= IDEAL_METRIC_MAX:
                    metrics.append(0.5)
                elif ACCEPTABLE_METRIC_MIN <= value <= ACCEPTABLE_METRIC_MAX:
                    metrics.append(0.2)
                else:
                    metrics.append(-0.2)

        return sum(metrics) / len(metrics) if metrics else 0.0

    def _calculate_channeling_bonus(self, evaluation: BrewEvaluation) -> float:
        """Calculate channeling bonus/penalty."""
        if evaluation.channeling is None:
            return 0.0
        if evaluation.channeling <= LOW_CHANNELING_THRESHOLD:
            return 0.1  # Bonus for low channeling
        if evaluation.channeling >= HIGH_CHANNELING_THRESHOLD:
            return -0.2  # Penalty for high channeling
        return 0.0

    def _calculate_brew_time_bonus(self, evaluation: BrewEvaluation) -> float:
        """Calculate brew time bonus/penalty."""
        if evaluation.brew_time is None:
            return 0.0
        if IDEAL_BREW_TIME_MIN <= evaluation.brew_time <= IDEAL_BREW_TIME_MAX:
            return 0.1
        if evaluation.brew_time < MIN_BREW_TIME or evaluation.brew_time > MAX_BREW_TIME:
            return -0.1
        return 0.0

    def _discretize_grind(self, grind_size: int) -> int:
        """Discretize grind size to index."""
        min_val, max_val = self.GRIND_SIZE_BOUNDS
        idx = int((grind_size - min_val) / (max_val - min_val) * (self.GRIND_SIZE_STEPS - 1))
        return max(0, min(self.GRIND_SIZE_STEPS - 1, idx))

    def _discretize_volume(self, brew_volume: float) -> int:
        """Discretize brew volume to index."""
        min_val, max_val = self.BREW_VOLUME_BOUNDS
        idx = int((brew_volume - min_val) / (max_val - min_val) * (self.BREW_VOLUME_STEPS - 1))
        return max(0, min(self.BREW_VOLUME_STEPS - 1, idx))

    def _discretize_dose(self, coffee_dose: float) -> int:
        """Discretize coffee dose to index."""
        min_val, max_val = self.COFFEE_DOSE_BOUNDS
        idx = int((coffee_dose - min_val) / (max_val - min_val) * (self.COFFEE_DOSE_STEPS - 1))
        return max(0, min(self.COFFEE_DOSE_STEPS - 1, idx))

    def _undiscretize_grind(self, idx: int) -> int:
        """Convert grind index back to integer value."""
        min_val, max_val = self.GRIND_SIZE_BOUNDS
        grind_float = min_val + (idx / (self.GRIND_SIZE_STEPS - 1)) * (max_val - min_val)
        return int(round(grind_float))

    def _undiscretize_volume(self, idx: int) -> float:
        """Convert volume index back to continuous value."""
        min_val, max_val = self.BREW_VOLUME_BOUNDS
        return min_val + (idx / (self.BREW_VOLUME_STEPS - 1)) * (max_val - min_val)

    def _undiscretize_dose(self, idx: int) -> float:
        """Convert dose index back to continuous value."""
        min_val, max_val = self.COFFEE_DOSE_BOUNDS
        return min_val + (idx / (self.COFFEE_DOSE_STEPS - 1)) * (max_val - min_val)


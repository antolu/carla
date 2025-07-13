"""Reinforcement learning agent for brewing optimization."""

from __future__ import annotations

import random
from collections import defaultdict

from .env import BrewingEnvironment
from .models import BrewAction, BrewEvaluation, BrewState


class BrewingAgent:
    """Q-learning agent for brewing parameter optimization."""

    def __init__(
        self,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        epsilon: float = 0.1,
        epsilon_decay: float = 0.995,
        min_epsilon: float = 0.01
    ):
        self.env = BrewingEnvironment()
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.min_epsilon = min_epsilon

        # Q-table: dict[state_key][action_key] = q_value
        self.q_table: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

        # Track last action for learning
        self.last_state_key: str | None = None
        self.last_action_key: str | None = None

    def suggest_action(self, state: BrewState) -> BrewAction:
        """Suggest an action based on current state."""
        state_key = self.env.state_to_key(state)

        # Epsilon-greedy action selection
        if random.random() < self.epsilon:
            # Explore: random action
            action = self.env.get_random_action()
        else:
            # Exploit: best known action or baseline
            action = self._get_best_action(state_key, state)

        # Store for learning
        self.last_state_key = state_key
        self.last_action_key = self.env.action_to_key(action)

        return action

    def learn_from_evaluation(self, evaluation: BrewEvaluation) -> None:
        """Update Q-table based on user evaluation."""
        if self.last_state_key is None or self.last_action_key is None:
            return

        reward = self.env.calculate_reward(evaluation)

        # Q-learning update: Q(s,a) += alpha[r + gamma*max(Q(s',a')) - Q(s,a)]
        # Since we don't have a next state, we use just the immediate reward
        current_q = self.q_table[self.last_state_key][self.last_action_key]
        new_q = current_q + self.learning_rate * (reward - current_q)
        self.q_table[self.last_state_key][self.last_action_key] = new_q

        # Decay epsilon
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)

    def get_q_table(self) -> dict:
        """Get the current Q-table for persistence."""
        # Convert defaultdict to regular dict for JSON serialization
        return {
            state_key: dict(actions)
            for state_key, actions in self.q_table.items()
        }

    def load_q_table(self, q_table_data: dict) -> None:
        """Load Q-table from persistence."""
        self.q_table = defaultdict(lambda: defaultdict(float))
        for state_key, actions in q_table_data.items():
            for action_key, q_value in actions.items():
                self.q_table[state_key][action_key] = q_value

    def _get_best_action(self, state_key: str, state: BrewState) -> BrewAction:
        """Get the best action for a state based on Q-values."""
        state_q_values = self.q_table[state_key]

        if not state_q_values:
            # No experience with this state, use baseline
            return self.env.get_baseline_action(state)

        # Find action with highest Q-value
        best_action_key = max(state_q_values.keys(), key=lambda k: state_q_values[k])

        # Convert action key back to action
        try:
            grind_idx, volume_idx, dose_idx = map(int, best_action_key.split("_"))
            return self.env.action_from_indices(grind_idx, volume_idx, dose_idx)
        except (ValueError, IndexError):
            # Fallback if action key is malformed
            return self.env.get_baseline_action(state)

    def get_action_recommendations(self, state: BrewState, top_k: int = 3) -> list[tuple[BrewAction, float]]:
        """Get top K action recommendations with their Q-values."""
        state_key = self.env.state_to_key(state)
        state_q_values = self.q_table[state_key]

        if not state_q_values:
            # No experience, return baseline
            baseline = self.env.get_baseline_action(state)
            return [(baseline, 0.0)]

        # Sort actions by Q-value
        sorted_actions = sorted(
            state_q_values.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        recommendations = []
        for action_key, q_value in sorted_actions:
            try:
                grind_idx, volume_idx, dose_idx = map(int, action_key.split("_"))
                action = self.env.action_from_indices(grind_idx, volume_idx, dose_idx)
                recommendations.append((action, q_value))
            except (ValueError, IndexError):
                continue

        return recommendations if recommendations else [(self.env.get_baseline_action(state), 0.0)]

    def reset_last_action(self) -> None:
        """Reset tracking of last action (e.g., when switching users)."""
        self.last_state_key = None
        self.last_action_key = None


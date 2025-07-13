"""Data models for CARLA brewing system."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# Rating constants
MIN_RATING = 1
MAX_RATING = 10


@dataclass
class BrewAction:
    """Action parameters for brewing espresso."""
    grind_size: float  # Most important parameter
    brew_volume: float  # ml
    coffee_dose: float  # g


@dataclass
class BrewState:
    """State information for brewing context."""
    is_first_brew: bool
    days_since_roast: int

    @classmethod
    def from_roast_date(cls, roast_date: datetime, *, is_first_brew: bool) -> BrewState:
        """Create state from roast date."""
        days_since = (datetime.now() - roast_date).days
        return cls(is_first_brew=is_first_brew, days_since_roast=days_since)


@dataclass
class BrewEvaluation:
    """User feedback for a brew."""
    bitterness: int | None = None  # 1-10
    acidity: int | None = None  # 1-10
    taste_strength: int | None = None  # 1-10
    overall_experience: int | None = None  # 1-10
    brew_time: float | None = None  # seconds
    channeling: int | None = None  # 1-10, optional

    def __post_init__(self) -> None:
        """Validate rating values."""
        for field_name, value in [
            ("bitterness", self.bitterness),
            ("acidity", self.acidity),
            ("taste_strength", self.taste_strength),
            ("overall_experience", self.overall_experience),
            ("channeling", self.channeling),
        ]:
            if value is not None and not (MIN_RATING <= value <= MAX_RATING):
                msg = f"{field_name} must be between {MIN_RATING} and {MAX_RATING}, got {value}"
                raise ValueError(msg)

        if self.brew_time is not None and self.brew_time <= 0:
            msg = f"brew_time must be positive, got {self.brew_time}"
            raise ValueError(msg)


@dataclass
class BrewRecord:
    """Complete record of a brew with action, state, and optional evaluation."""
    action: BrewAction
    state: BrewState
    timestamp: datetime
    evaluation: BrewEvaluation | None = None

    def __post_init__(self) -> None:
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()


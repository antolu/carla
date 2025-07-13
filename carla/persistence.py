"""Persistence layer for CARLA data storage."""

from __future__ import annotations

import json
import pickle
from datetime import datetime
from pathlib import Path

from .models import BrewAction, BrewEvaluation, BrewRecord, BrewState


class UserStorage:
    """Handles storage for a specific user."""

    def __init__(self, username: str):
        self.username = username
        self.base_path = Path.home() / ".carla" / username
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.brew_records_file = self.base_path / "brew_records.json"
        self.q_table_file = self.base_path / "q_table.pkl"
        self.settings_file = self.base_path / "settings.json"

    def save_brew_record(self, record: BrewRecord) -> None:
        """Save a brew record to storage."""
        records = self.load_brew_records()
        records.append(self._record_to_dict(record))

        with open(self.brew_records_file, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, default=str)

    def load_brew_records(self) -> list[dict]:
        """Load all brew records."""
        if not self.brew_records_file.exists():
            return []

        with open(self.brew_records_file, encoding="utf-8") as f:
            return json.load(f)

    def get_last_brew_record(self) -> BrewRecord | None:
        """Get the most recent brew record."""
        records = self.load_brew_records()
        if not records:
            return None

        return self._dict_to_record(records[-1])

    def update_last_brew_evaluation(self, evaluation: BrewEvaluation) -> bool:
        """Update the evaluation of the last brew record."""
        records = self.load_brew_records()
        if not records:
            return False

        records[-1]["evaluation"] = self._evaluation_to_dict(evaluation)

        with open(self.brew_records_file, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, default=str)

        return True

    def save_q_table(self, q_table: dict) -> None:
        """Save Q-table to storage."""
        with open(self.q_table_file, "wb") as f:
            pickle.dump(q_table, f)

    def load_q_table(self) -> dict:
        """Load Q-table from storage."""
        if not self.q_table_file.exists():
            return {}

        with open(self.q_table_file, "rb") as f:
            return pickle.load(f)

    def save_settings(self, settings: dict) -> None:
        """Save user settings."""
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, default=str)

    def load_settings(self) -> dict:
        """Load user settings."""
        if not self.settings_file.exists():
            return {}

        with open(self.settings_file, encoding="utf-8") as f:
            return json.load(f)

    def get_roast_date(self) -> datetime | None:
        """Get the current roast date from settings."""
        settings = self.load_settings()
        roast_date_str = settings.get("roast_date")
        if roast_date_str:
            return datetime.fromisoformat(roast_date_str)
        return None

    def set_roast_date(self, roast_date: datetime) -> None:
        """Set the roast date in settings."""
        settings = self.load_settings()
        settings["roast_date"] = roast_date.isoformat()
        self.save_settings(settings)

    def _record_to_dict(self, record: BrewRecord) -> dict:
        """Convert BrewRecord to dictionary for JSON storage."""
        return {
            "action": {
                "grind_size": record.action.grind_size,
                "brew_volume": record.action.brew_volume,
                "coffee_dose": record.action.coffee_dose,
            },
            "state": {
                "is_first_brew": record.state.is_first_brew,
                "days_since_roast": record.state.days_since_roast,
            },
            "timestamp": record.timestamp.isoformat(),
            "evaluation": self._evaluation_to_dict(record.evaluation) if record.evaluation else None,
        }

    def _evaluation_to_dict(self, evaluation: BrewEvaluation) -> dict:
        """Convert BrewEvaluation to dictionary."""
        return {
            "bitterness": evaluation.bitterness,
            "acidity": evaluation.acidity,
            "taste_strength": evaluation.taste_strength,
            "overall_experience": evaluation.overall_experience,
            "brew_time": evaluation.brew_time,
            "channeling": evaluation.channeling,
        }

    def _dict_to_record(self, data: dict) -> BrewRecord:
        """Convert dictionary to BrewRecord."""

        action = BrewAction(**data["action"])
        state = BrewState(**data["state"])
        timestamp = datetime.fromisoformat(data["timestamp"])

        evaluation = None
        if data.get("evaluation"):
            evaluation = BrewEvaluation(**data["evaluation"])

        return BrewRecord(action=action, state=state, timestamp=timestamp, evaluation=evaluation)


class StorageManager:
    """Manages storage for all users."""

    def __init__(self) -> None:
        self._current_user: str | None = None
        self._user_storage: UserStorage | None = None
        self._global_config_file = Path.home() / ".carla" / "config.json"

    def switch_user(self, username: str) -> None:
        """Switch to a different user."""
        self._current_user = username
        self._user_storage = UserStorage(username)
        self.set_last_user(username)

    @property
    def current_user(self) -> str | None:
        """Get current username."""
        return self._current_user

    @property
    def storage(self) -> UserStorage:
        """Get current user storage."""
        if self._user_storage is None:
            msg = "No user selected. Use switch_user() first."
            raise ValueError(msg)
        return self._user_storage

    def list_users(self) -> list[str]:
        """List all users with stored data."""
        carla_dir = Path.home() / ".carla"
        if not carla_dir.exists():
            return []

        return [d.name for d in carla_dir.iterdir() if d.is_dir()]

    def get_last_user(self) -> str | None:
        """Get the last used username from global config."""
        if not self._global_config_file.exists():
            return None

        try:
            with open(self._global_config_file, encoding="utf-8") as f:
                config = json.load(f)
            return config.get("last_user")
        except (json.JSONDecodeError, OSError):
            return None

    def set_last_user(self, username: str) -> None:
        """Set the last used username in global config."""
        # Ensure .carla directory exists
        self._global_config_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing config or create new one
        config = {}
        if self._global_config_file.exists():
            try:
                with open(self._global_config_file, encoding="utf-8") as f:
                    config = json.load(f)
            except (json.JSONDecodeError, OSError):
                config = {}

        # Update and save
        config["last_user"] = username
        try:
            with open(self._global_config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except OSError:
            pass  # Silently fail if can't write config

    def auto_load_user(self) -> bool:
        """Automatically load the last user if available."""
        last_user = self.get_last_user()
        if last_user and last_user in self.list_users():
            self.switch_user(last_user)
            return True
        return False


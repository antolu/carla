"""Interactive CLI for CARLA brewing agent."""

from __future__ import annotations

import cmd
import sys
from datetime import datetime

from dateutil import parser as date_parser

from .agent import BrewingAgent
from .export import DataExporter
from .models import MAX_RATING, MIN_RATING, BrewEvaluation, BrewRecord, BrewState
from .persistence import StorageManager

# Date parsing threshold
MAX_SHORT_DATE_LENGTH = 10

# Export command arguments
EXPORT_ARGS_COUNT = 2


class CarlaShell(cmd.Cmd):
    """Interactive shell for CARLA brewing optimization."""

    intro = "\nType 'help' for commands.\n"
    prompt = "(carla) "

    def __init__(self) -> None:
        super().__init__()
        self.storage_manager = StorageManager()
        self.agent = BrewingAgent()
        self.exporter = DataExporter(self.storage_manager)
        self.last_suggested_record: BrewRecord | None = None
        self._setup_user()

    def do_switch_user(self, username: str) -> None:
        """Switch to a different user profile."""
        if not username.strip():
            print("Usage: switch_user <username>")
            return

        username = username.strip()
        self.storage_manager.switch_user(username)

        # Load user's Q-table
        q_table_data = self.storage_manager.storage.load_q_table()
        self.agent.load_q_table(q_table_data)
        self.agent.reset_last_action()

        print(f"Switched to user: {username}")

        # Show roast date if set
        roast_date = self.storage_manager.storage.get_roast_date()
        if roast_date:
            days_since = (datetime.now() - roast_date).days
            print(f"Current roast date: {roast_date.strftime('%Y-%m-%d')} ({days_since} days ago)")
        else:
            print("No roast date set. Use 'set_roast_date' to set it.")

    def do_suggest(self, _: str) -> None:
        """Suggest brewing parameters based on current state."""
        if not self._check_user():
            return

        # Get roast date
        roast_date = self.storage_manager.storage.get_roast_date()
        if not roast_date:
            print("Please set roast date first using 'set_roast_date YYYY-MM-DD'")
            return

        # Ask for is_first_brew
        first_brew_input = input("Is this the first brew after starting the machine? (y/n, default: n): ").strip().lower()
        if not first_brew_input:
            is_first_brew = False  # Default to no
        else:
            is_first_brew = first_brew_input in {"y", "yes", "1", "true"}

        # Create state
        state = BrewState.from_roast_date(roast_date, is_first_brew=is_first_brew)

        # Get suggestion
        action = self.agent.suggest_action(state)

        # Create and store brew record
        self.last_suggested_record = BrewRecord(
            action=action,
            state=state,
            timestamp=datetime.now()
        )

        # Save to storage
        self.storage_manager.storage.save_brew_record(self.last_suggested_record)

        # Display suggestion
        print("\n📊 Brew Suggestion:")
        print(f"  Grind Size: {action.grind_size} (1=very fine, 30=very coarse)")
        print(f"  Brew Volume: {action.brew_volume:.1f} ml")
        print(f"  Coffee Dose: {action.coffee_dose:.1f} g")
        print("\nState Context:")
        print(f"  First brew after startup: {'Yes' if state.is_first_brew else 'No'}")
        print(f"  Days since roast: {state.days_since_roast}")
        print("\nBrew your coffee and use 'evaluate' to provide feedback!")

    def do_evaluate(self, _: str) -> None:
        """Evaluate the last suggested brew."""
        if not self._check_user():
            return

        last_record = self.storage_manager.storage.get_last_brew_record()
        if not last_record:
            print("No brew to evaluate. Use 'suggest' first.")
            return

        if last_record.evaluation is not None:
            print("Last brew has already been evaluated.")
            return

        print("Please rate your brew (1-10 scale, press Enter for defaults):")

        evaluation = BrewEvaluation()

        # Collect ratings
        evaluation.bitterness = self._get_rating("Bitterness (1=none, 10=very bitter)", default=5)
        evaluation.acidity = self._get_rating("Acidity (1=none, 10=very acidic)", default=5)
        evaluation.taste_strength = self._get_rating("Taste Strength (1=weak, 10=very strong)", default=6)
        evaluation.overall_experience = self._get_rating("Overall Experience (1=poor, 10=excellent)", default=7)

        # Optional metrics
        evaluation.channeling = self._get_rating("Channeling (1=none, 10=severe) [optional]")

        brew_time_input = input("Brew time in seconds [optional, default: 30]: ").strip()
        if not brew_time_input:
            evaluation.brew_time = 30.0  # Default brew time
        elif brew_time_input:
            try:
                evaluation.brew_time = float(brew_time_input)
            except ValueError:
                print("Invalid brew time, using default of 30 seconds.")
                evaluation.brew_time = 30.0

        # Update storage
        self.storage_manager.storage.update_last_brew_evaluation(evaluation)

        # Learn from evaluation
        self.agent.learn_from_evaluation(evaluation)

        # Save updated Q-table
        self.storage_manager.storage.save_q_table(self.agent.get_q_table())

        print("\n✅ Evaluation recorded! The agent will learn from your feedback.")

        # Show reward for transparency
        reward = self.agent.env.calculate_reward(evaluation)
        print(f"Calculated reward: {reward:.2f} (range: -1.0 to 1.0)")

    def do_set_roast_date(self, date_str: str) -> None:
        """Set the roast date for current beans (flexible date formats accepted)."""
        if not self._check_user():
            return

        if not date_str.strip():
            print("Usage: set_roast_date <date>")
            print("Examples: '2024-01-15', 'Jan 15', '15/01', 'yesterday'")
            return

        try:
            # Parse with dateutil for flexible formats
            parsed_date = date_parser.parse(date_str.strip(), default=datetime.now())

            # If no year was provided, use current year
            current_year = datetime.now().year
            if (
                parsed_date.year != current_year
                and len(date_str.strip()) <= MAX_SHORT_DATE_LENGTH
                and abs(parsed_date.year - current_year) > 1
            ):
                parsed_date = parsed_date.replace(year=current_year)

            # Convert to date only (no time)
            roast_date = datetime.combine(parsed_date.date(), datetime.min.time())

            self.storage_manager.storage.set_roast_date(roast_date)
            days_since = (datetime.now() - roast_date).days
            print(f"Roast date set to {roast_date.strftime('%Y-%m-%d')} ({days_since} days ago)")
        except (ValueError, TypeError):
            print(f"Could not parse date '{date_str}'. Try formats like:")
            print("  '2024-01-15', 'Jan 15', '15/01/2024', 'yesterday'")

    def do_get_roast_date(self, _: str) -> None:
        """Show the current roast date."""
        if not self._check_user():
            return

        roast_date = self.storage_manager.storage.get_roast_date()
        if roast_date:
            days_since = (datetime.now() - roast_date).days
            print(f"Current roast date: {roast_date.strftime('%Y-%m-%d')} ({days_since} days ago)")
        else:
            print("No roast date set.")

    def do_save(self, _: str) -> None:
        """Save current state (Q-table is auto-saved after each evaluation)."""
        if not self._check_user():
            return

        self.storage_manager.storage.save_q_table(self.agent.get_q_table())
        print("✅ State saved.")

    def do_stats(self, _: str) -> None:
        """Show learning statistics."""
        if not self._check_user():
            return

        records = self.storage_manager.storage.load_brew_records()
        evaluated_records = [r for r in records if r.get("evaluation")]

        print("\n📈 Learning Statistics:")
        print(f"  Total brews: {len(records)}")
        print(f"  Evaluated brews: {len(evaluated_records)}")
        print(f"  Q-table states: {len(self.agent.q_table)}")
        print(f"  Current epsilon: {self.agent.epsilon:.3f}")

        if evaluated_records:
            avg_overall = sum(
                r["evaluation"]["overall_experience"]
                for r in evaluated_records
                if r["evaluation"]["overall_experience"] is not None
            ) / len(evaluated_records)
            print(f"  Average overall rating: {avg_overall:.1f}/10")

    def do_users(self, _: str) -> None:
        """List all users with stored data."""
        users = self.storage_manager.list_users()
        if users:
            print("Users with stored data:")
            for user in users:
                marker = " (current)" if user == self.storage_manager.current_user else ""
                print(f"  - {user}{marker}")
        else:
            print("No users found.")

    def do_export(self, args: str) -> None:
        """Export brew data to file. Usage: export <format> <filename>"""
        if not self._check_user():
            return

        parts = args.strip().split()
        if len(parts) != EXPORT_ARGS_COUNT:
            print("Usage: export <format> <filename>")
            print("Formats: csv, json, txt")
            print("Examples:")
            print("  export csv my_brews.csv")
            print("  export json backup.json")
            print("  export txt brew_log.txt")
            return

        format_type, filename = parts
        format_type = format_type.lower()

        try:
            if format_type == "csv":
                self.exporter.export_to_csv(filename)
                print(f"✅ Exported to {filename} (CSV format)")
            elif format_type == "json":
                self.exporter.export_to_json(filename)
                print(f"✅ Exported to {filename} (JSON format)")
            elif format_type == "txt":
                self.exporter.export_to_text(filename)
                print(f"✅ Exported to {filename} (Text format)")
            else:
                print("Invalid format. Use: csv, json, or txt")
        except Exception as e:
            print(f"Export failed: {e}")

    def do_exit(self, _: str) -> bool:
        """Exit CARLA."""
        print("Thanks for using CARLA! ☕")
        return True

    def do_quit(self, _: str) -> bool:
        """Exit CARLA."""
        return self.do_exit(_)

    def do_EOF(self, _: str) -> bool:  # noqa: N802
        """Handle Ctrl+D."""
        print()
        return self.do_exit(_)

    def _check_user(self) -> bool:
        """Check if a user is selected."""
        if self.storage_manager.current_user is None:
            print("No user selected. Use 'switch_user <username>' first.")
            return False
        return True

    def _get_rating(self, prompt: str, default: int | None = None) -> int | None:
        """Get a rating from user input."""
        while True:
            if default is not None:
                full_prompt = f"{prompt} (default: {default})"
            else:
                full_prompt = prompt
            response = input(f"{full_prompt}: ").strip()

            if not response:
                return default

            try:
                rating = int(response)
                if MIN_RATING <= rating <= MAX_RATING:
                    return rating
                print(f"Please enter a number between {MIN_RATING} and {MAX_RATING}.")
            except ValueError:
                print("Please enter a valid number or press Enter to skip.")

    def emptyline(self) -> bool:
        """Do nothing on empty line."""
        return False

    def default(self, line: str) -> None:
        """Handle unknown commands."""
        print(f"Unknown command: {line}. Type 'help' for available commands.")

    def _setup_user(self) -> None:
        """Set up user on startup - auto-load last user or prompt for new one."""
        if self.storage_manager.auto_load_user():
            current_user = self.storage_manager.current_user
            print(f"\n👋 Hello {current_user}!")
            print("If this isn't you, use 'switch_user <name>' to change.")

            # Load user's Q-table
            q_table_data = self.storage_manager.storage.load_q_table()
            self.agent.load_q_table(q_table_data)
            self.agent.reset_last_action()
        else:
            # No previous user or user data doesn't exist
            users = self.storage_manager.list_users()
            if users:
                print("\n👋 Welcome back to CARLA!")
                print(f"Existing users: {', '.join(users)}")
                username = input("Enter your username (or a new one): ").strip()
            else:
                print("\n👋 Welcome to CARLA!")
                username = input("Enter your username: ").strip()

            if username:
                self.storage_manager.switch_user(username)
                print(f"Hello {username}!")

                # Load user's Q-table
                q_table_data = self.storage_manager.storage.load_q_table()
                self.agent.load_q_table(q_table_data)
                self.agent.reset_last_action()
            else:
                print("No username provided. You can use 'switch_user <name>' later.")

    def get_names(self) -> list[str]:
        """Get command names, filtering out EOF."""
        names = super().get_names()
        return [name for name in names if name != "do_EOF"]


def run_cli() -> None:
    """Run the CARLA interactive CLI."""
    try:
        CarlaShell().cmdloop()
    except KeyboardInterrupt:
        print("\nThanks for using CARLA! ☕")
        sys.exit(0)


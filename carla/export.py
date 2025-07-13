"""Export functionality for CARLA brew data."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from .persistence import StorageManager


class DataExporter:
    """Export brew data to various formats."""

    def __init__(self, storage_manager: StorageManager):
        self.storage_manager = storage_manager

    def export_to_csv(self, output_path: Path | str) -> None:
        """Export all brew records to CSV format."""
        if not self.storage_manager.current_user:
            msg = "No user selected"
            raise ValueError(msg)

        records = self.storage_manager.storage.load_brew_records()
        output_path = Path(output_path)

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            if not records:
                csvfile.write("No brew records found\n")
                return

            fieldnames = [
                "timestamp", "grind_size", "brew_volume", "coffee_dose",
                "is_first_brew", "days_since_roast", "bitterness", "acidity",
                "taste_strength", "overall_experience", "brew_time", "channeling"
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for record in records:
                row = {
                    "timestamp": record["timestamp"],
                    "grind_size": record["action"]["grind_size"],
                    "brew_volume": record["action"]["brew_volume"],
                    "coffee_dose": record["action"]["coffee_dose"],
                    "is_first_brew": record["state"]["is_first_brew"],
                    "days_since_roast": record["state"]["days_since_roast"],
                }

                if record.get("evaluation"):
                    eval_data = record["evaluation"]
                    row.update({
                        "bitterness": eval_data.get("bitterness"),
                        "acidity": eval_data.get("acidity"),
                        "taste_strength": eval_data.get("taste_strength"),
                        "overall_experience": eval_data.get("overall_experience"),
                        "brew_time": eval_data.get("brew_time"),
                        "channeling": eval_data.get("channeling"),
                    })

                writer.writerow(row)

    def export_to_json(self, output_path: Path | str) -> None:
        """Export all brew records to JSON format."""
        if not self.storage_manager.current_user:
            msg = "No user selected"
            raise ValueError(msg)

        records = self.storage_manager.storage.load_brew_records()
        output_path = Path(output_path)

        export_data = {
            "user": self.storage_manager.current_user,
            "exported_at": datetime.now().isoformat(),
            "total_records": len(records),
            "records": records
        }

        with open(output_path, "w", encoding="utf-8") as jsonfile:
            json.dump(export_data, jsonfile, indent=2, default=str)

    def export_to_text(self, output_path: Path | str) -> None:
        """Export all brew records to human-readable text format."""
        if not self.storage_manager.current_user:
            msg = "No user selected"
            raise ValueError(msg)

        records = self.storage_manager.storage.load_brew_records()
        output_path = Path(output_path)

        with open(output_path, "w", encoding="utf-8") as textfile:
            textfile.write("CARLA Brew Records Export\n")
            textfile.write(f"User: {self.storage_manager.current_user}\n")
            textfile.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            textfile.write(f"Total Records: {len(records)}\n")
            textfile.write("=" * 60 + "\n\n")

            if not records:
                textfile.write("No brew records found.\n")
                return

            for i, record in enumerate(records, 1):
                textfile.write(f"Brew #{i}\n")
                textfile.write(f"Date: {record['timestamp']}\n")
                textfile.write("Action:\n")
                textfile.write(f"  Grind Size: {record['action']['grind_size']:.1f}\n")
                textfile.write(f"  Brew Volume: {record['action']['brew_volume']:.1f} ml\n")
                textfile.write(f"  Coffee Dose: {record['action']['coffee_dose']:.1f} g\n")
                textfile.write("State:\n")
                textfile.write(f"  First Brew: {record['state']['is_first_brew']}\n")
                textfile.write(f"  Days Since Roast: {record['state']['days_since_roast']}\n")

                if record.get("evaluation"):
                    eval_data = record["evaluation"]
                    textfile.write("Evaluation:\n")
                    if eval_data.get("bitterness") is not None:
                        textfile.write(f"  Bitterness: {eval_data['bitterness']}/10\n")
                    if eval_data.get("acidity") is not None:
                        textfile.write(f"  Acidity: {eval_data['acidity']}/10\n")
                    if eval_data.get("taste_strength") is not None:
                        textfile.write(f"  Taste Strength: {eval_data['taste_strength']}/10\n")
                    if eval_data.get("overall_experience") is not None:
                        textfile.write(f"  Overall Experience: {eval_data['overall_experience']}/10\n")
                    if eval_data.get("brew_time") is not None:
                        textfile.write(f"  Brew Time: {eval_data['brew_time']} seconds\n")
                    if eval_data.get("channeling") is not None:
                        textfile.write(f"  Channeling: {eval_data['channeling']}/10\n")
                else:
                    textfile.write("Evaluation: Not evaluated\n")

                textfile.write("-" * 40 + "\n\n")


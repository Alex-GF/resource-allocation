import csv
import os
from typing import Dict, Any, Optional


def save_results_to_csv(
    result_obj: Dict[str, Any],
    scenario_id: str,
    RESULTS_DIR: str,
    filename: str = "results.csv",
    *,
    include_filter: bool = True,
) -> None:
    """
    Store the execution result of a scenario into a CSV file.

    Assumptions:
      - result_obj is a Python dictionary (already parsed)
      - one row corresponds to one scenario execution

    Enhancements:
      - Optionally flattens and appends `result_obj["filter"]` for debugging:
          - filter_maxPrice
          - filter_maxSubscriptionSize
          - filter_features (kept as list -> CSV cell will contain Python list repr)
          - filter_usageLimits_* (flattened dict)
    """

    def _flatten_dict(prefix: str, dct: Any) -> Dict[str, Any]:
        if not isinstance(dct, dict):
            return {}
        return {f"{prefix}{k}": v for k, v in dct.items()}

    def _extract_filter_fields(obj: Dict[str, Any]) -> Dict[str, Any]:
        if not include_filter:
            return {}

        filt = obj.get("filter")
        if not isinstance(filt, dict):
            return {}

        filter_row: Dict[str, Any] = {
            "filter_maxPrice": filt.get("maxPrice", ""),
            "filter_maxSubscriptionSize": filt.get("maxSubscriptionSize", ""),
            # Keep as object (list) — csv will write its repr; useful for debugging
            "filter_features": filt.get("features", []),
        }

        # Flatten filter.usageLimits dict into columns
        filter_row.update(_flatten_dict("filter_usageLimits_", filt.get("usageLimits", {})))
        return filter_row

    try:
        result = result_obj["result"]
        time_elapsed = result_obj["time"]

        optimal = result["result"]["optimal"]
        subscription = optimal["subscription"]

        # Flatten subscription usage limits: list[dict] -> dict
        usage_limits = {
            key: value
            for limit in subscription.get("usageLimits", [])
            for key, value in limit.items()
        }

        row = {
            "scenario_id": scenario_id,
            "job_id": result.get("jobId"),
            "status": result.get("status"),
            "submitted_at": result.get("submittedAt"),
            "started_at": result.get("startedAt"),
            "completed_at": result.get("completedAt"),
            "time_seconds": time_elapsed,
            "cost": optimal.get("cost"),
            # Keep as objects (list) — csv will write their repr
            "add_ons": subscription.get("addOns", []),
            "features": subscription.get("features", []),
            **usage_limits,
            **_extract_filter_fields(result_obj),
        }

    except KeyError:
        # If any expected key is missing, write a minimal row containing only scenario_id
        os.makedirs(RESULTS_DIR, exist_ok=True)
        csv_path = os.path.join(RESULTS_DIR, filename)
        file_exists = os.path.isfile(csv_path)

        # Try to preserve existing headers if file exists
        fieldnames: Optional[list[str]] = None
        if file_exists:
            try:
                with open(csv_path, mode="r", newline="", encoding="utf-8") as rf:
                    reader = csv.DictReader(rf)
                    fieldnames = reader.fieldnames
            except Exception:
                fieldnames = None

        if not fieldnames:
            fieldnames = ["scenario_id"]

        with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()

            minimal_row = {fn: "" for fn in fieldnames}
            minimal_row["scenario_id"] = scenario_id
            writer.writerow(minimal_row)
        return

    os.makedirs(RESULTS_DIR, exist_ok=True)
    csv_path = os.path.join(RESULTS_DIR, filename)
    file_exists = os.path.isfile(csv_path)

    # Preserve prior headers if the file already exists, and merge new keys if needed.
    existing_fieldnames: Optional[list[str]] = None
    if file_exists:
        try:
            with open(csv_path, mode="r", newline="", encoding="utf-8") as rf:
                reader = csv.DictReader(rf)
                existing_fieldnames = reader.fieldnames
        except Exception:
            existing_fieldnames = None

    if existing_fieldnames:
        # Keep existing order, append any new keys at the end.
        fieldnames = list(existing_fieldnames)
        for k in row.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    else:
        fieldnames = list(row.keys())

    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        # Ensure we write all columns even if this row lacks some existing ones.
        full_row = {fn: "" for fn in fieldnames}
        full_row.update(row)
        writer.writerow(full_row)
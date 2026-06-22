import json
import time
from typing import Any, Dict, Optional

import requests


def optimize(
    prime_instance_url: str,
    pricing_instance_path: str,
    request: Dict[str, Any],
    *,
    poll_interval_seconds: float = 0.1,
    timeout_seconds: Optional[float] = 600.0,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """
    Launches an asynchronous pricing optimization job (operation=optimal, solver=minizinc,
    objective=minimize) and polls until the job reaches COMPLETED or FAILED.

    Parameters
    ----------
    prime_instance_url:
        Base URL of the API instance, e.g., "http://localhost:3000/".
    pricing_instance_path:
        Local filesystem path to the pricing YAML file to upload as multipart form-data.
    request:
        Filter criteria payload (Python dict) to be JSON-encoded into the "filters" form field.
    poll_interval_seconds:
        Sleep time between polling attempts.
    timeout_seconds:
        Maximum time to wait. If None, waits indefinitely.
    session:
        Optional requests.Session for connection pooling and custom configuration.

    Returns
    -------
    Dict[str, Any]
        The final job details response (COMPLETED includes "result"; FAILED includes "error").

    Raises
    ------
    requests.HTTPError
        On non-success HTTP responses.
    FileNotFoundError
        If pricing_instance_path does not exist or cannot be opened.
    TimeoutError
        If timeout_seconds is reached before terminal status.
    ValueError
        If the response is missing jobId or has an unexpected status.
    """
    http = session or requests.Session()
    base = prime_instance_url.rstrip("/")
    post_url = f"{base}/pricing/analysis"

    # 1) Submit job (multipart/form-data)
    filters_json = json.dumps(request, ensure_ascii=False)

    data = {
        "operation": "optimal",
        "solver": "minizinc",
        "filters": filters_json,
        "objective": "minimize",
    }

    with open(pricing_instance_path, "rb") as f:
      files = {
        # (filename, fileobj, content_type)
        "pricingFile": ("pricing.yml", f, "application/x-yaml"),
      }
      submit_resp = http.post(post_url, data=data, files=files, timeout=30)
      try:
        submit_resp.raise_for_status()
      except requests.HTTPError as e:
        if submit_resp.status_code >= 400:
          print(f"Error {submit_resp.status_code}: {submit_resp.text}")
        raise

    submit_payload = submit_resp.json()
    job_id = submit_payload.get("jobId")
    if not job_id:
      raise ValueError(f"Missing 'jobId' in job creation response: {submit_payload}")

    # 2) Poll job status until COMPLETED or FAILED
    get_url = f"{base}/pricing/analysis/{job_id}"
    start = time.monotonic()

    while True:
        status_resp = http.get(get_url, timeout=30)
        status_resp.raise_for_status()
        payload = status_resp.json()

        status = payload.get("status")
        if status in ("COMPLETED", "FAILED"):
            return payload

        if status not in ("PENDING", "RUNNING"):
            raise ValueError(f"Unexpected job status '{status}' for jobId={job_id}: {payload}")

        if timeout_seconds is not None and (time.monotonic() - start) >= timeout_seconds:
            raise TimeoutError(
                f"Timed out after {timeout_seconds}s waiting for jobId={job_id} to complete. "
                f"Last status: {status}"
            )

        time.sleep(poll_interval_seconds)
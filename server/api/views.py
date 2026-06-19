"""HTTP views.

A thin layer over the existing engine. ``run_debate`` already encapsulates data
loading, the offline-or-live client choice, and the full pipeline, so the view
just parses query parameters and serialises the result. Each request is handled
in its own worker thread, and the engine manages its own event loop, so a plain
synchronous view is the simplest correct shape here.
"""

from __future__ import annotations

from django.http import JsonResponse

from boardroom.runner import run_debate

MAX_ROUNDS = 3


def health(request):
    return JsonResponse({"status": "ok"})


def debate(request, ticker: str):
    rounds = _parse_rounds(request.GET.get("rounds"))
    csv = request.GET.get("csv") or None

    try:
        result, used_offline, usage = run_debate(ticker, rounds=rounds, csv=csv)
    except ValueError as exc:
        # Bad ticker or no data: a client error, not a server fault.
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:  # noqa: BLE001 - never leak a stack trace as HTML
        return JsonResponse({"error": f"Unexpected error: {exc}"}, status=500)

    payload = result.model_dump()
    payload["offline"] = used_offline
    payload["usage"] = usage.as_dict()
    return JsonResponse(payload)


def _parse_rounds(raw: str | None) -> int:
    try:
        rounds = int(raw) if raw is not None else 1
    except (TypeError, ValueError):
        return 1
    return max(0, min(MAX_ROUNDS, rounds))

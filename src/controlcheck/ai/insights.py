from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


_MAX_TOP_FINDINGS = 20
_MAX_LIST_ITEMS = 3


def _value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def build_insight_input(
    *,
    project_name: str,
    findings: Iterable[Any],
    unavailable_domains: list[str] | None = None,
) -> dict[str, Any]:
    """Build a bounded, workbook-free factual package for an insight model."""
    finding_list = list(findings)
    severity_counts = Counter(str(_value(item, "severity", "observation")).lower() for item in finding_list)
    category_counts = Counter(str(_value(item, "category", "other")).lower() for item in finding_list)
    seen_rules: set[str] = set()
    top_findings: list[dict[str, str]] = []
    severity_order = {"critical": 0, "warning": 1, "observation": 2}
    ordered = sorted(
        finding_list,
        key=lambda item: (
            severity_order.get(str(_value(item, "severity", "observation")).lower(), 9),
            str(_value(item, "rule_id", "")),
            str(_value(item, "id", "")),
        ),
    )
    for item in ordered:
        rule_id = str(_value(item, "rule_id", ""))
        if not rule_id or rule_id in seen_rules:
            continue
        seen_rules.add(rule_id)
        finding_id = _value(item, "id")
        if finding_id is None:
            continue
        top_findings.append(
            {
                "finding_id": str(finding_id),
                "rule_id": rule_id,
                "category": str(_value(item, "category", "other")).lower(),
                "severity": str(_value(item, "severity", "observation")).lower(),
                "title": str(_value(item, "title", "Finding"))[:200],
                "recommendation": str(_value(item, "recommendation", "Review the supporting finding."))[:300],
            }
        )
        if len(top_findings) >= _MAX_TOP_FINDINGS:
            break

    limitation_map = {
        "cost": "Cost data is not available.",
        "progress": "Progress data is not available.",
        "schedule": "Schedule data is not available.",
        "data_quality": "Data quality coverage is not available.",
    }
    limitations = [
        limitation_map[domain]
        for domain in (unavailable_domains or [])
        if domain in limitation_map
    ]
    return {
        "project_name": project_name[:250],
        "finding_count": len(finding_list),
        "severity_counts": dict(severity_counts),
        "category_counts": dict(category_counts),
        "top_findings": top_findings,
        "data_limitations": limitations,
    }


def parse_insight_response(response: dict[str, Any], *, allowed_finding_ids: set[str]) -> dict[str, Any]:
    """Normalize model output and reject references outside the selected run."""
    def text(name: str) -> str:
        value = response.get(name, "")
        return value.strip()[:1200] if isinstance(value, str) else ""

    def text_list(name: str) -> list[str]:
        value = response.get(name, [])
        if not isinstance(value, list):
            return []
        return [item.strip()[:300] for item in value if isinstance(item, str) and item.strip()][:_MAX_LIST_ITEMS]

    referenced = response.get("finding_ids", [])
    if not isinstance(referenced, list):
        referenced = []
    finding_ids = [str(item) for item in referenced if str(item) in allowed_finding_ids][:_MAX_TOP_FINDINGS]
    return {
        "executive_summary": text("executive_summary"),
        "top_risks": text_list("top_risks"),
        "priority_actions": text_list("priority_actions"),
        "data_limitations": text_list("data_limitations"),
        "finding_ids": finding_ids,
    }
import json
from collections.abc import Callable
from urllib.request import Request, urlopen


class OpenAIInsightClient:
    """Small server-side OpenAI client that only accepts curated insight facts."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gpt-4.1-mini",
        base_url: str = "https://api.openai.com/v1",
        request: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._request = request or self._post

    def generate(self, facts: dict[str, Any], *, allowed_finding_ids: set[str]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are ControlCheck AI Insight. Respond only in Indonesian JSON with keys "
                        "executive_summary, top_risks, priority_actions, data_limitations, finding_ids. "
                        "Use only the supplied facts. Do not invent values or references. "
                        "If cost or progress data is unavailable, state that limitation clearly."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(facts, ensure_ascii=False, separators=(",", ":")),
                },
            ],
        }
        response = self._request(payload)
        try:
            content = response["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("AI provider returned an invalid insight response") from exc
        if not isinstance(parsed, dict):
            raise ValueError("AI provider returned an invalid insight response")
        return parse_insight_response(parsed, allowed_finding_ids=allowed_finding_ids)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f'{self.base_url}/chat/completions',
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed OpenAI endpoint
            return json.loads(response.read().decode("utf-8"))

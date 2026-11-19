"""Сборка текста Prometheus из простой словарной модели.

Намеренно без prometheus_client: формат экспозиции несложен, а самостоятельная
сборка текста помогает понять, что именно видит Prometheus (задание task_114).
"""
from typing import Dict, Iterable, List, Sequence, Tuple

DEFAULT_BUCKETS: Tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
INF = float("inf")


def _labels(labels: Dict[str, str]) -> str:
    if not labels:
        return ""
    parts = [f'{key}="{str(value).replace(chr(34), chr(92) + chr(34))}"' for key, value in sorted(labels.items())]
    return "{" + ",".join(parts) + "}"


def _value(number: float) -> str:
    if number == INF:
        return "+Inf"
    if float(number).is_integer():
        return str(int(number))
    return f"{number:.6g}"


def counter(name: str, help_text: str, series: Iterable[Tuple[Dict[str, str], float]]) -> List[str]:
    lines = [f"# HELP {name} {help_text}", f"# TYPE {name} counter"]
    for labels, value in series:
        lines.append(f"{name}{_labels(labels)} {_value(value)}")
    return lines


def gauge(name: str, help_text: str, series: Iterable[Tuple[Dict[str, str], float]]) -> List[str]:
    lines = [f"# HELP {name} {help_text}", f"# TYPE {name} gauge"]
    for labels, value in series:
        lines.append(f"{name}{_labels(labels)} {_value(value)}")
    return lines


def histogram(
    name: str,
    help_text: str,
    series: Iterable[Tuple[Dict[str, str], Sequence[float]]],
    buckets: Tuple[float, ...] = DEFAULT_BUCKETS,
) -> List[str]:
    """series: пары (labels, список сырых значений в секундах)."""
    lines = [f"# HELP {name} {help_text}", f"# TYPE {name} histogram"]
    for labels, values in series:
        values = [float(v) for v in values]
        total = sum(values)
        for bound in buckets:
            bucket_labels = {**labels, "le": _value(bound)}
            count = sum(1 for v in values if v <= bound)
            lines.append(f"{name}_bucket{_labels(bucket_labels)} {count}")
        inf_labels = {**labels, "le": "+Inf"}
        lines.append(f"{name}_bucket{_labels(inf_labels)} {len(values)}")
        lines.append(f"{name}_sum{_labels(labels)} {_value(total)}")
        lines.append(f"{name}_count{_labels(labels)} {len(values)}")
    return lines

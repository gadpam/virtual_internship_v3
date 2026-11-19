#!/usr/bin/env python3
"""Проверка артефактов сборки (task_265, task_266, task_267).

Сверяет содержимое каталога артефактов с манифестом: наличие файлов, размер,
контрольные суммы SHA-256, версия конфигурации, воспроизводимость. Ненулевой
код возврата, если что-то не совпало — чтобы CI останавливал релиз.

Пример:
    python3 check_artifacts.py ../../build --manifest ../../build/manifest.json
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(build_dir: Path, manifest_path: Path) -> Dict[str, object]:
    errors: List[str] = []
    warnings: List[str] = []

    if not build_dir.exists():
        return {"ok": False, "errors": [f"каталог артефактов не найден: {build_dir}"], "warnings": []}
    if not manifest_path.exists():
        return {"ok": False, "errors": [f"манифест не найден: {manifest_path}"], "warnings": []}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return {"ok": False, "errors": [f"манифест не является JSON: {error}"], "warnings": []}

    artifacts = manifest.get("artifacts", [])
    if not artifacts:
        errors.append("в манифесте нет ни одного артефакта")

    for entry in artifacts:
        name = entry.get("file", "")
        path = build_dir / name
        if not path.exists():
            errors.append(f"артефакт отсутствует: {name}")
            continue
        size = path.stat().st_size
        expected_size = entry.get("sizeBytes")
        if expected_size is not None and size != int(expected_size):
            errors.append(f"{name}: размер {size} != ожидаемый {expected_size}")
        expected_sha = entry.get("sha256")
        actual_sha = sha256(path)
        if expected_sha and actual_sha != expected_sha:
            errors.append(f"{name}: SHA-256 не совпадает (ожидали {expected_sha[:16]}…, получили {actual_sha[:16]}…)")
        if size == 0:
            warnings.append(f"{name}: нулевой размер — вероятно, сборка не удалась")

    version = manifest.get("version")
    if not version:
        errors.append("в манифесте не указана версия")
    built_at = manifest.get("builtAt")
    if not built_at:
        warnings.append("в манифесте нет builtAt — воспроизводимость не проверить")

    stray = sorted({p.relative_to(build_dir).as_posix()
                    for p in build_dir.rglob("*") if p.is_file()
                    and p.relative_to(build_dir).as_posix() not in {a.get("file") for a in artifacts}
                    and p.name != manifest_path.name})
    if stray:
        warnings.append(f"файлы вне манифеста: {', '.join(stray[:10])}"
                        + ("…" if len(stray) > 10 else ""))

    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "artifacts": len(artifacts), "version": version}


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка артефактов сборки")
    parser.add_argument("build_dir", help="каталог с артефактами (internship/build)")
    parser.add_argument("--manifest", default=None, help="путь к manifest.json (по умолчанию build_dir/manifest.json)")
    args = parser.parse_args()

    build_dir = Path(args.build_dir)
    manifest_path = Path(args.manifest) if args.manifest else build_dir / "manifest.json"
    report = check(build_dir, manifest_path)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    for error in report["errors"]:
        print(f"ОШИБКА: {error}", file=sys.stderr)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

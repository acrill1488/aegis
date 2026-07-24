from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import httpx

from aegis.config.services import get_service_base_url, load_services_config

from .catalog import ManifestRegistry
from .models import CheckResult, DiagnosticReport, PackageManifest
from .resolver import DependencyResolver
from .state import InstalledState


class HealthChecker:
    def __init__(self, registry: ManifestRegistry, state: InstalledState, resolver: DependencyResolver):
        self.registry = registry
        self.state = state
        self.resolver = resolver

    def package(self, manifest: PackageManifest) -> DiagnosticReport:
        checks = self.resolver.system_checks(manifest)
        health = manifest.healthcheck
        if health.type == "http":
            try:
                if health.service:
                    base = get_service_base_url(health.service)
                else:
                    base = str(manifest.config.get("service_url", "")).rstrip("/")
                url = f"{base}/{(health.endpoint or '').lstrip('/')}"
                response = httpx.get(url, timeout=5, trust_env=False)
                checks.append(CheckResult(name=f"health:{manifest.id}", ok=response.status_code == health.expected_status, details=f"{url} returned {response.status_code}"))
            except Exception as exc:
                checks.append(CheckResult(name=f"health:{manifest.id}", ok=False, details=str(exc)))
        elif health.type == "command":
            result = subprocess.run(health.command, check=False, capture_output=True, text=True)
            checks.append(CheckResult(name=f"health:{manifest.id}", ok=result.returncode == 0, details=(result.stdout or result.stderr).strip()))
        elif health.type == "path":
            exists = Path(health.path or "").exists()
            checks.append(CheckResult(name=f"health:{manifest.id}", ok=exists, details=health.path or "path missing"))
        elif health.type == "provider":
            try:
                if manifest.id == "paddleocr":
                    from aegis.providers.paddleocr import PaddleOCRProvider

                    provider_health = PaddleOCRProvider().health()
                    checks.append(CheckResult(name="health:paddleocr", ok=bool(provider_health["available"]), details=f"{provider_health['status']}: {provider_health.get('message', '')}".strip()))
                else:
                    checks.append(CheckResult(name=f"health:{manifest.id}", ok=True, details="Provider health is checked by its runtime"))
            except Exception as exc:
                checks.append(CheckResult(name=f"health:{manifest.id}", ok=False, details=str(exc)))
        else:
            checks.append(CheckResult(name=f"health:{manifest.id}", ok=True, details="No external health check required"))
        return DiagnosticReport(ok=all(item.ok or not item.required for item in checks), checks=checks)

    def system(self) -> DiagnosticReport:
        checks = [
            CheckResult(name="Python", ok=sys.version_info >= (3, 12), details=sys.version.split()[0]),
            CheckResult(name="Docker", ok=shutil.which("docker") is not None, required=False, details="Optional unless required by an installed package"),
            CheckResult(name="GPU", ok=shutil.which("nvidia-smi") is not None, required=False, details="Optional unless required by an installed package"),
            CheckResult(name="Workspace", ok=self.state.path.parent.exists(), details=str(self.state.path.parent)),
        ]
        try:
            config = load_services_config()
            checks.append(CheckResult(name="Configuration", ok=True, details=str(config.path)))
        except Exception as exc:
            checks.append(CheckResult(name="Configuration", ok=False, details=str(exc)))
        try:
            installed = self.state.list()
            checks.append(CheckResult(name="Registry", ok=True, details=f"{len(installed)} installed package(s)"))
            for item in installed:
                try:
                    report = self.package(self.registry.get(item.component))
                    checks.extend(report.checks)
                except Exception as exc:
                    checks.append(CheckResult(name=f"package:{item.component}", ok=False, details=str(exc)))
        except Exception as exc:
            checks.append(CheckResult(name="Registry", ok=False, details=str(exc)))
        for name in ("Provider", "Models", "Workflow"):
            checks.append(CheckResult(name=name, ok=True, required=False, details="Validated through installed package manifests"))
        return DiagnosticReport(ok=all(item.ok or not item.required for item in checks), checks=checks)

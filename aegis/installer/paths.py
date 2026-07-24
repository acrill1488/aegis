from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from aegis.config.services import get_services_config_path


@dataclass(frozen=True)
class InstallerPaths:
    workspace: Path
    state_dir: Path
    manifests: Path
    installed: Path
    rollbacks: Path
    log: Path
    services_config: Path

    @classmethod
    def resolve(cls) -> "InstallerPaths":
        configured = os.environ.get("AEGIS_WORKSPACE")
        if configured:
            workspace = Path(configured).expanduser()
        else:
            workspace = get_services_config_path().parent.parent
        state_dir = Path(os.environ.get("AEGIS_INSTALLER_STATE", workspace / ".aegis" / "installer"))
        manifests = Path(
            os.environ.get("AEGIS_PACKAGE_REGISTRY", Path(__file__).with_name("manifests"))
        )
        return cls(
            workspace=workspace,
            state_dir=state_dir,
            manifests=manifests,
            installed=state_dir / "installed.json",
            rollbacks=state_dir / "rollbacks",
            log=state_dir / "installer.log",
            services_config=get_services_config_path(),
        )

    def ensure(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.rollbacks.mkdir(parents=True, exist_ok=True)

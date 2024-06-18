# Copyright 2022-2024 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import re

from ramble.application import ApplicationError
from ramble.pkgmankit import *

from ramble.error import RambleError
from ramble.util.executable import which
from ramble.util.hashing import hash_file, hash_string
from ramble.util.logger import logger

from spack.util.executable import Executable
import llnl.util.filesystem as fs


class Pip(PackageManagerBase):
    """Pip package manager class definition"""

    name = "pip"

    def __init__(self, file_path):
        super().__init__(file_path)

        self.runner = PipRunner()

    register_builtin(
        "pip_activate", required=True, depends_on=["builtin::env_vars"]
    )

    def pip_activate(self):
        self.runner.configure_env(self.app_inst.expander.env_path)
        return self.runner.generate_activate_command()

    register_builtin(
        "pip_deactivate",
        required=False,
        depends_on=["package_manager_builtin::pip::pip_activate"],
    )

    def pip_deactivate(self):
        return self.runner.generate_deactivate_command()

    register_phase("software_create_env", pipeline="setup")

    def _software_create_env(self, workspace, app_inst=None):
        """Create the virtual env for the experiment"""

        logger.msg("Creating venv + pip environment")

        env_path = self.app_inst.expander.env_path
        if not env_path:
            raise ApplicationError("Ramble env_path is set to None")

        cache_tupl = ("pip-env", env_path)
        if workspace.check_cache(cache_tupl):
            logger.debug("{cache_tupl} already in cache")
            return
        else:
            workspace.add_to_cache(cache_tupl)

        self.runner.set_dry_run(workspace.dry_run)
        self.runner.create_env(env_path)

        env_context = self.app_inst.expander.expand_var_name(
            self.keywords.env_name
        )
        require_env = self.environment_required()
        software_envs = workspace.software_environments
        software_env = software_envs.render_environment(
            env_context, self.app_inst.expander, self, require=require_env
        )
        if software_env:
            for pkg_spec in software_envs.package_specs_for_environment(
                software_env
            ):
                self.runner.add_spec(pkg_spec)
            self.runner.generate_requirement_file()

    register_phase(
        "software_install", pipeline="setup", run_after=["software_create_env"]
    )

    def _software_install(self, workspace, app_inst=None):
        """Install packages using pip"""
        logger.msg("Installing packages")

        env_path = self.app_inst.expander.env_path
        if not env_path:
            raise ApplicationError("Ramble env_path is set to None")

        cache_tupl = ("pip-install", env_path)
        if workspace.check_cache(cache_tupl):
            logger.debug("{cache_tupl} already in cache")
            return
        else:
            workspace.add_to_cache(cache_tupl)

        if self.environment_required():
            self.runner.set_dry_run(workspace.dry_run)
            self.runner.configure_env(env_path)
            self.runner.install()

    def get_spec_str(self, pkg, all_pkgs, compiler):
        """Return a spec string for the given pkg

        Args:
            pkg (RenderedPackage): Reference to a rendered package
            all_pkgs (dict): All related packages
            compiler (boolean): True if this pkg is used as a compiler
        """
        return pkg.spec

    def populate_inventory(
        self, workspace, force_compute=False, require_exist=False
    ):
        """Add software environment information to hash inventory"""

        env_path = self.app_inst.expander.env_path
        self.runner.set_dry_run(workspace.dry_run)
        self.runner.configure_env(env_path)

        pkgman_version = self.runner.get_version()

        self.app_inst.hash_inventory["package_manager"].append(
            {
                "name": self.name,
                "version": pkgman_version,
                "digest": hash_string(pkgman_version),
            }
        )
        self.app_inst.hash_inventory["software"].append(
            {
                "name": self.runner.env_path.replace(
                    workspace.root + os.path.sep, ""
                ),
                "digest": self.runner.inventory_hash(),
            }
        )


class PipRunner:
    """Runner for executing pip+venv commands."""

    _venv_name = ".venv"
    _requirement_file_name = "requirements.txt"
    _lock_file_name = "requirements.lock"

    def __init__(self, dry_run=False):
        cmds = ["python3", "python"]
        # Set up python for bootstrapping
        for c in cmds:
            self.bs_python = which(c, required=False)
            if self.bs_python:
                break
        if not self.bs_python:
            raise RunnerError("python is not found in path")
        self.env_path = None
        self.configs = []
        self.dry_run = dry_run
        self.specs = set()
        self.installed = False

    def configure_env(self, path):
        """Configure the venv path for subsequent commands"""
        self.env_path = path

    def set_dry_run(self, dry_run=False):
        """Set the dry_run state of this pip runner"""
        self.dry_run = dry_run

    def create_env(self, env_path):
        """Ensure a venv environment is created"""
        if os.path.exists(env_path) and not os.path.isdir(env_path):
            raise RunnerError(f"Unable to create environment {env_path}")

        if not os.path.exists(env_path):
            fs.mkdirp(env_path)

        if not self.dry_run:
            if not os.path.exists(os.path.join(env_path, self._venv_name)):
                self.bs_python(
                    "-m", "venv", os.path.join(env_path, self._venv_name)
                )

        # Ensure subsequent commands use the created env now.
        self.env_path = env_path

    def _get_venv_python(self):
        if self.dry_run:
            return self.bs_python.copy()
        return Executable(
            os.path.join(self.env_path, self._venv_name, "bin", "python")
        )

    def install(self):
        """Invoke pip install"""
        self._check_env_configured()
        if self.installed:
            logger.debug("Installation already done, skipping")
            return
        req_file = os.path.join(self.env_path, self._requirement_file_name)
        if not os.path.exists(req_file):
            raise RunnerError(f"{req_file} does not exist")
        installer = self._get_venv_python()
        installer.add_default_arg("-m")
        installer.add_default_arg("pip")
        install_args = ["install", "-r", req_file]
        freeze_args = ["freeze", "-r", req_file]
        if self.dry_run:
            self._dry_run_print(installer, install_args)
            self._dry_run_print(installer, freeze_args)
        else:
            installer(*install_args)
            lock_file = os.path.join(self.env_path, self._lock_file_name)
            with open(lock_file, "w") as f:
                installer(*freeze_args, output=f)
        self.installed = True

    def _get_activate_script_path(self):
        return os.path.join(self.env_path, self._venv_name, "bin", "activate")

    def _check_env_configured(self):
        """Check if virtual env is configured"""
        if not self.env_path:
            raise RunnerError("env_path is not configured")
        if self.dry_run:
            return
        script_path = self._get_activate_script_path()
        if not os.path.exists(script_path):
            raise RunnerError("virtual env is not configured")

    def generate_activate_command(self):
        """Generate a command to activate a virtual env"""
        return [f"source {self._get_activate_script_path()}"]

    def generate_deactivate_command(self):
        """Generate a command to deactivate a virtual env"""
        return ["deactivate"]

    def _generate_requirement_content(self):
        contents = os.linesep.join(sorted(self.specs))
        contents += os.linesep
        return contents

    def generate_requirement_file(self):
        """Generate a requirements.txt file"""
        self._check_env_configured()
        contents = self._generate_requirement_content()
        req_file = os.path.join(self.env_path, self._requirement_file_name)
        lock_file = os.path.join(self.env_path, self._lock_file_name)
        if os.path.exists(req_file) and os.path.exists(lock_file):
            existing_req_mtime = os.path.getmtime(req_file)
            existing_lock_mtime = os.path.getmtime(lock_file)
            if existing_lock_mtime >= existing_req_mtime:
                with open(req_file, "r") as f:
                    if f.read() == contents:
                        self.installed = True
                        logger.debug("requirement file already up-to-date")
                        return
        with open(req_file, "w") as f:
            f.write(contents)

    def add_spec(self, spec):
        """Add a package spec to the pip environment"""
        self._check_env_configured()
        self.specs.add(spec)

    def get_version(self):
        exe = self._get_venv_python()
        out = exe("-m", "pip", "--version", output=str)
        match = re.search(r"pip (?P<version>[\d.]+) from", out).group(
            "version"
        )
        return match

    def inventory_hash(self):
        """Create a hash for ramble inventory purposes"""
        self._check_env_configured()
        if self.dry_run:
            return hash_string(self._generate_requirement_content())
        else:
            return hash_file(os.path.join(self.env_path, self._lock_file_name))

    def _dry_run_print(self, executable, args):
        logger.msg(f"DRY-RUN: would run {executable}")
        logger.msg(f"         with args: {args}")


class RunnerError(RambleError):
    """Raised when a problem occurs with a pip+venv environment"""

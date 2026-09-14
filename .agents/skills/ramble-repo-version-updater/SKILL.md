---
name: ramble-repo-version-updater
description: "Update known versions of Ramble repository objects (applications, modifiers, etc.) that are already available in package managers like Spack, ensuring backwards compatibility and updating object definitions."
license: Apache-2.0 or MIT
---

# Ramble Repo Object Version Updater

This skill guides you through updating known versions of Ramble repository objects (applications, base applications, modifiers, and package managers).

---

## 1. Scope & Guardrails

> [!IMPORTANT]
> **Scope Boundaries**:
> - **In Scope**: Updating Ramble repository object definitions (adding `version(...)` directives, updating software specs, and applying `with when()` conditionals) for versions already available in upstream package managers (e.g., Spack).
> - **Out of Scope**: Updating package managers themselves (such as authoring new Spack recipes or modifying Spack package repositories to support new upstream versions). If an upstream version is not yet supported in the package manager recipe, that update must occur upstream in the package manager project first.

---

## 2. Core Workflow & Procedure

Updating an object version follows a structured process:

1. **Identify Target Object & Current Capabilities**
2. **Discover Available Versions from Package Manager & Upstream**
3. **Conduct Breakage & Compatibility Audit**
4. **Update Object Definition & Conditionalize Directives**
5. **Validate with Ramble Tooling & Dry-Runs**
6. **Run Unit Tests, Style Checks, and Completion Updates**

---

### Step 1: Identify Target Object & Current Definition

1. **Locate the Definition File**:
   - Built-in Applications: `var/ramble/repos/builtin/applications/<name>/application.py`
   - Built-in Modifiers: `var/ramble/repos/builtin/modifiers/<name>/modifier.py`
   - For repository layout and base class details, see [.agents/skills/ramble-definition-author/SKILL.md](../ramble-definition-author/SKILL.md).

2. **Inspect Current Capabilities via CLI**:
   Run verbose info to review registered versions, workloads, variables, FOMs, and specs:
   ```bash
   ramble info -v <name>
   ```

---

### Step 2: Discover Available Versions

1. **Query Package Managers**:
   - For Spack, inspect package recipes and available versions:
     ```bash
     spack info <name>
     ```
     Refer to [.agents/skills/ramble-spack-integration/SKILL.md](../ramble-spack-integration/SKILL.md) for Spack environment and spec details.
   - Note version-dependent variants, dependencies (`depends_on(...)`), or patches in the package recipe.

2. **Examine Upstream Source & Release Notes**:
   - Find the upstream repository (listed in the object class docstring or Spack package metadata).
   - Review release tags, `CHANGELOG.md`, `RELEASENOTES.md`, and commit logs between the existing and new version tags.

---

### Step 3: Conduct Breakage & Compatibility Audit

Before modifying the definition, consult [.agents/skills/ramble-compatibility-auditor/SKILL.md](../ramble-compatibility-auditor/SKILL.md) to perform a systematic audit comparing the new version with existing versions:

- **Static Audit Scope**: Audit executable binary names, CLI flags, workloads, workload variables, input files, environment variables, compiler requirements, and software specs.
- **Dynamic Execution Boundary**: Identifying runtime output formatting changes or regex extractions requires executing the application. If dynamic validation is needed, coordinate with [.agents/skills/ramble-experiment-runner/SKILL.md](../ramble-experiment-runner/SKILL.md) and [.agents/skills/ramble-results-analyzer/SKILL.md](../ramble-results-analyzer/SKILL.md).

---

### Step 4: Update Object Definition & Apply `when()` Handling

#### 1. Add Version Directives
Declare new versions using the `version(...)` directive in the class body.
- `preferred` defaults to `False`. Omit `preferred=False` and only specify `preferred=True` on the single version designated as the default:
  ```python
  version("2026.0", description="Version 2026.0 of Gromacs")
  version("2025.3", description="Version 2025.3 of Gromacs", preferred=True)
  ```

#### 2. Update Software Specifications
- **Parameterized Specs**: If using Ramble templating syntax (e.g., `software_spec("app-{application::app::version}", pkg_spec="app@{application::app::version}")`), verify that the spec remains valid for the new version.
- **Explicit Version Specs**: If dependencies or compilers change across versions:
  ```python
  with when("package_manager_family=spack"):
      with when("@2.2.0:"):
          software_spec("heffte", pkg_spec="heffte@2.2.0: +fftw +cuda", compiler="gcc14")
      with when("@:2.1.0"):
          software_spec("heffte", pkg_spec="heffte@:2.1.0 +fftw", compiler="gcc11")
  ```

#### 3. Conditionalize Changed Directives with `when()`
Use `with when("@<version_spec>"):` blocks or inline `when=[...]` arguments to preserve backwards compatibility:

- `@2.2.0:` : Version 2.2.0 and newer
- `@:2.1.0` : Version 2.1.0 and older
- `@1.2.0:2.0.0` : Version range
- `@2.2.0` : Exact version

##### Example: Conditional Executable & Workload
```python
# Older versions
with when("@:2.1.0"):
    executable("speed3d", "{heffte_path}/bin/speed3d {fft} {dim_x} {dim_y} {dim_z}", use_mpi=True)
    workload("speed3d", executables=["speed3d"])

# Newer versions
with when("@2.2.0:"):
    executable("convolution", "{heffte_path}/share/heffte/benchmarks/convolution {fft} {precision} {dim_x} {dim_y} {dim_z} -{reorder} -n{num_runs}", use_mpi=True)
    workload("convolution", executables=["convolution"])
```

##### Example: Conditional Workload Variable Defaults
```python
with when("@:2.0.0"):
    workload_variable("solver_backend", default="legacy_cpu", values=["legacy_cpu", "openmp"], workload_group="all_workloads")

with when("@2.1.0:"):
    workload_variable("solver_backend", default="hybrid_omp", values=["hybrid_omp", "cuda", "rocm"], workload_group="all_workloads")
```

For full details on directive categories, consult [.agents/skills/ramble-definition-author/SKILL.md](../ramble-definition-author/SKILL.md).

---

### Step 5: Validate via Ramble Tooling & Dry-Runs

1. **Verify Definition Rendering**:
   ```bash
   ramble info -v <name>
   ```
   Confirm all versions, workloads, variables, and specs render cleanly without exceptions.

2. **Check Software Conflicts**:
   ```bash
   ramble software-definitions --summary
   ramble software-definitions --conflicts
   ```

3. **Validate Workspace Dry-Run**:
   Use workspace commands to test concretization and script generation without executing software:
   ```bash
   ramble workspace create -d /tmp/test_ws
   ramble -D /tmp/test_ws workspace manage experiments <app_name> --workload-filter <workload>
   ramble -D /tmp/test_ws workspace info
   ramble -D /tmp/test_ws workspace setup --dry-run
   ```
   For workspace setup patterns, see [.agents/skills/ramble-workspace-wizard/SKILL.md](../ramble-workspace-wizard/SKILL.md) and [.agents/skills/ramble-experiment-runner/SKILL.md](../ramble-experiment-runner/SKILL.md).

---

### Step 6: Code Style, Unit Tests, and Completion Updates

1. **Run Unit Tests**:
   ```bash
   ramble unit-test -k <name>
   ```
2. **Run Style Checks & Fix Violations**:
   ```bash
   ramble style --fix <path_to_modified_file>
   ```
   Refer to [.agents/skills/ramble-developer/SKILL.md](../ramble-developer/SKILL.md) for pytest fixtures, mock guidelines, and styling tools.
3. **Update Shell Completion Scripts (If CLI Options Changed)**:
   If any CLI arguments, options, or commands were modified or added:
   ```bash
   ramble commands --update-completion
   ```

---

## 3. Agent Execution Checklist

Before concluding any version update task, verify:
- [ ] New versions discovered from package manager (e.g. Spack recipe) and upstream repository.
- [ ] Upstream changelog and release notes audited using [.agents/skills/ramble-compatibility-auditor/SKILL.md](../ramble-compatibility-auditor/SKILL.md).
- [ ] `version(...)` directives added; `preferred=True` specified only when setting the default version (never add `preferred=False`).
- [ ] `with when("@<version_spec>"):` conditions applied to divergent executables, workloads, variables, input files, or FOMs.
- [ ] Backwards compatibility with older supported versions preserved.
- [ ] `ramble info -v <name>` executes successfully and renders all workloads and versions.
- [ ] `ramble software-definitions --conflicts` passes without errors.
- [ ] `ramble workspace setup --dry-run` succeeds on a test workspace.
- [ ] `ramble unit-test -k <name>` passes.
- [ ] `ramble style <path>` passes without style violations.

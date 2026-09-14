---
name: ramble-compatibility-auditor
description: "Audit Ramble repository object definitions (applications, modifiers, etc.) for compatibility, upstream breakage, deprecations, and consistency across versions and package manager changes."
license: Apache-2.0 or MIT
---

# Ramble Compatibility Auditor Guide

This skill provides procedural guidelines for performing breakage and compatibility audits on Ramble repository object definitions (applications, base applications, modifiers, package managers, and workflow managers).

It can be used standalone (e.g., during PR reviews, continuous data gathering, regression triage) or as part of version updates.

---

## 1. Audit Scope & Verification Boundary

When auditing an object definition, distinguish between **static analysis** and **dynamic execution**:

- **Static Audit (Safe & Fast)**: Inspecting CLI options, changelogs, package manager recipes, software specs, and validating workspace generation via `ramble workspace setup --dry-run`. This does not execute application binaries or require target hardware/licenses.
- **Dynamic Execution Audit**: Verifying runtime output format changes, Figure of Merit (FOM) regex extraction, and success criteria during live runs. For live execution and results parsing, coordinate with [.agents/skills/ramble-experiment-runner/SKILL.md](../ramble-experiment-runner/SKILL.md) and [.agents/skills/ramble-results-analyzer/SKILL.md](../ramble-results-analyzer/SKILL.md).

---

## 2. Upstream Change & Breakage Audit Checklist

Audit the target object definition across the following dimensions:

| Dimension | Inspection Focus | Potential Breaking Changes | Mitigation via Ramble Directives |
| :--- | :--- | :--- | :--- |
| **CLI & Executables** | Executable binary names, subcommands, and flags | Binary renamed (e.g., `app_win` vs `app64_win`), altered flag syntax (e.g., `-n` replaced with `-np`), reordered arguments | Conditional `executable(...)` via `with when("@<ver>:"):` |
| **Workloads & Groups** | Workload names, supported test cases, datasets | New benchmark added, obsolete workload removed, workload group contents shifted | Conditional `workload(...)` and `workload_group(...)` |
| **Workload Variables** | Variable defaults and allowed values (`values=[...]`) | New mandatory configuration parameter, default value changed, flag options modified | Conditional `workload_variable(...)` |
| **Input Files & Templates** | Input deck syntax, benchmark datasets | Input deck format changed, dataset URL or hash updated | Conditional `input_file(...)` or `register_template(...)` |
| **Environment Variables** | Runtime env vars (OpenMP, MPI, CUDA, ROCm) | Deprecated environment variable, new mandatory tuning parameter | Conditional `environment_variable(...)` |
| **Dependencies & Compilers** | Required language standard, MPI backend, libraries | Upstream requires newer C++ standard (needs newer compiler spec), or new required library | Conditional `define_compiler(...)` or `software_spec(...)` |
| **Figures of Merit (FOMs)** | stdout / stderr / log file output formatting | Output text changed (e.g., `Time: 1.23s` vs `Elapsed Time (s): 1.23`), units changed (ms vs s) | Conditional `figure_of_merit(...)` |
| **Success Criteria** | Verification strings & exit indicators | Verification message wording updated (e.g., `PASSED` vs `Verification Successful`) | Conditional `success_criteria(...)` |

---

## 3. Audit Procedure & Tooling

Follow these steps to conduct a systematic audit:

### Step 1: Inspect Current Object Definition via CLI
Run verbose info to review registered versions, workloads, executables, variables, FOMs, and specs:
```bash
ramble info -v <object_name>
```

### Step 2: Audit Package Manager Recipes & Dependencies
Query the package manager to inspect version-dependent variants, dependencies, and patches.
- For Spack, consult [.agents/skills/ramble-spack-integration/SKILL.md](../ramble-spack-integration/SKILL.md) and run:
  ```bash
  spack info <object_name>
  ```
- Inspect package recipe differences (e.g., `git diff` on `packages/<object_name>/package.py` in Spack) for new flags, changed dependencies (`depends_on(...)`), or removed options across versions.

### Step 3: Audit Upstream Source & Release Channels
- Locate upstream repository links and release notes from the object definition docstring or package manager metadata.
- Review changelogs (`CHANGELOG.md`, `NEWS`, `RELEASENOTES.md`), GitHub/GitLab release notes, and commit diffs between relevant version tags to detect CLI or input deck changes.

### Step 4: Verify Software Spec Consistency
Confirm that software specifications introduce no naming or version conflicts across the repository:
```bash
ramble software-definitions --summary
ramble software-definitions --conflicts
```

### Step 5: Validate via Workspace Dry-Run
Create an isolated test workspace to verify that Ramble can concretize, expand variables, and generate execution scripts without error:
```bash
# Create an empty test workspace
ramble workspace create -d /tmp/test_ws

# Add experiment for the audited object and workload
ramble -D /tmp/test_ws workspace manage experiments <app_name> --workload-filter <workload>

# Validate experiment configuration
ramble -D /tmp/test_ws workspace info

# Test dry-run setup
ramble -D /tmp/test_ws workspace setup --dry-run
```

---

## 4. Applying Remediations

When breaking changes or version divergences are discovered:
1. Use Ramble's `with when("@<ver>"):` conditional directives or inline `when=[...]` parameters to maintain compatibility across all supported versions.
2. Refer to [.agents/skills/ramble-definition-author/SKILL.md](../ramble-definition-author/SKILL.md) for directive syntax, `when()` version-spec patterns (`@2.2.0:`, `@:2.1.0`), and inheritance rules.
3. For unit testing and style validation, refer to [.agents/skills/ramble-developer/SKILL.md](../ramble-developer/SKILL.md).

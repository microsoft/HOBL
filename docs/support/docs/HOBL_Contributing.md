# Contributing

Thank you for your interest in HOBL. Contributions are welcome across the
framework, test scenarios, tools, utilities, and documentation.

HOBL controls and measures physical test devices. Changes can install software,
modify system configuration, run remote commands, and affect shared toolchains.
Please read the safety and scenario guidance below before making changes.

## Table of contents

- [Code of conduct](#code-of-conduct)
- [Security and support](#security-and-support)
- [Before starting work](#before-starting-work)
- [Governance](#governance)
- [Ways to contribute](#ways-to-contribute)
- [Development setup](#development-setup)
- [Repository overview](#repository-overview)
- [Making a change](#making-a-change)
- [Scenario contribution requirements](#scenario-contribution-requirements)
- [Testing and validation](#testing-and-validation)
- [Documentation and dependencies](#documentation-and-dependencies)
- [Submitting a pull request](#submitting-a-pull-request)
- [Contributor License Agreement](#contributor-license-agreement)

## Code of conduct

This project has adopted the [Microsoft Open Source Code of
Conduct](https://opensource.microsoft.com/codeofconduct/). For more information, see the
[Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com).

## Security and support

Use [GitHub Issues](https://github.com/microsoft/HOBL/issues) for reproducible
bugs and feature requests. For help using HOBL, contact
[HOBLsupport@microsoft.com](mailto:HOBLsupport@microsoft.com). See
[Support](HOBL_Support.md) for the full support information.

HOBL uses [SimpleRemote](https://github.com/microsoft/SimpleRemote) to run commands and access files on test devices without authentication. Use HOBL only on dedicated test devices connected to an isolated, trusted lab network. Never use a personal or production computer as a device under test (DUT).

## Before starting work

Search [open and closed issues](https://github.com/microsoft/HOBL/issues) before
filing a new issue or beginning a significant change. This helps avoid duplicate
work and gives maintainers an opportunity to confirm the problem and approach.

Open or comment on an issue before implementing:

- new scenarios or substantial scenario behavior changes;
- changes to result formats, metrics, parameters, or test methodology;
- changes that install software or alter DUT configuration;
- broad refactors or changes affecting both Windows and macOS; or
- changes that add, replace, or redistribute third-party software.

Small documentation fixes and narrowly scoped bug fixes can usually go directly
to a pull request. If an issue is already assigned, coordinate with the assignee
before starting work.

Remove credentials, confidential information, personal data, machine names,
network details, and other sensitive content before attaching logs or images.
Use reactions instead of comments such as "+1" when you have no additional
diagnostic information to add.

## Governance

HOBL uses a maintainer-led, open development model. Technical proposals,
implementation decisions, and reviews take place through GitHub issues and pull
requests whenever practical so that the reasoning and resulting expectations
remain visible to contributors.

Maintainers are stewards of the project and are responsible for ensuring that
contributions uphold HOBL's scenario-development [tenets](#scenario-design-tenets), the
[HOBL Design Philosophy](HOBL_Design_Philosophy.md), and the
project's standards for safety, impartiality, reliability, repeatability, data
quality, maintainability, and user experience. This responsibility includes:

- setting and communicating technical direction and release expectations;
- evaluating whether proposals serve HOBL users and preserve trustworthy,
  comparable measurements;
- ensuring that scenarios remain impartial across manufacturers, devices,
  architectures, platforms, and silicon implementations;
- requiring appropriate design discussion, validation, documentation,
  ownership, and support plans;
- coordinating changes that affect power baselines or cross-platform behavior;
- reviewing contributions consistently, regardless of whether they originate
  from Microsoft or the community; and
- maintaining the health, security, licensing compliance, and long-term
  sustainability of the repository.

Contributors are encouraged to propose alternatives, identify tradeoffs, and
participate in technical discussion. Maintainers should seek practical
consensus and explain significant decisions in the associated issue or pull
request. When consensus cannot be reached, the maintainers make the final
decision based on the project's tenets, available evidence, user impact, and
long-term maintenance cost.

Approval is not based solely on whether a change functions in one environment.
Maintainers may request revisions, additional validation, consolidation with
existing components, a committed support owner, or deferral to an appropriate
release. They may decline or revert a change that compromises HOBL's principles,
result comparability, reliability, safety, or maintainability, including when a
problem becomes apparent only after the change is merged.

Scenario ownership is shared governance in practice. Contributors and
sponsoring teams are expected to maintain and support the scenarios they add,
while maintainers ensure that this ownership remains active and that
repository-wide standards are applied consistently.

## Ways to contribute

Useful contributions include:

- improving documentation and examples;
- reporting reproducible bugs;
- proposing test scenarios or measurement improvements;
- fixing framework, UI, tool, or scenario defects;
- improving Windows and macOS parity;
- adding validation, diagnostics, or actionable error reporting; and
- reviewing and testing open pull requests on supported hardware.

New scenarios should represent realistic user activity, produce repeatable
results, minimize measurement overhead, and follow the design principles in
[HOBL Design Philosophy](HOBL_Design_Philosophy.md).

## Development setup

HOBL's host runs on Windows 10 or Windows 11. Scenario execution may target
Windows or macOS DUTs. A complete end-to-end validation generally requires a
dedicated DUT and, for hosted operation, a private network between the host and
DUT.

1. Fork [microsoft/HOBL](https://github.com/microsoft/HOBL).
2. Clone your fork and add the upstream repository:

   ```powershell
   git clone https://github.com/<your-account>/HOBL.git
   cd hobl
   git remote add upstream https://github.com/microsoft/HOBL.git
   ```

3. Create a focused branch from the latest `main`:

   ```powershell
   git fetch upstream
   git switch -c <issue-number>-<short-description> upstream/main
   ```

4. Follow the applicable setup documentation:
   - [Setup](HOBL_Setup.md)
   - [Usage](HOBL_Usage.md)
   - [Creating Scenarios](HOBL_ScenarioMaker.md)
   - [Command-based Scenario Guide](HOBL_Command_Scenario_Guide.md)
   - [UI-based Scenario Guide](HOBL_UI_Scenario_Guide.md)

Do not assume that a default installation path exists. Discover installed tools,
verify paths before using them, and preserve support for custom drives and
installation directories.

## Repository overview

| Path | Purpose |
| --- | --- |
| `core/` | Core HOBL framework code |
| `scenarios/windows/` | Windows scenarios and shared scenario libraries |
| `scenarios/macos/` | macOS scenarios and resources |
| `testplans/` | Test-plan definitions |
| `profile_templates/` | Reusable HOBL profile templates |
| `providers/` | ETL trace providers |
| `tools/` | Modules that run with scenarios to change settings, collect data, control equipment, etc. |
| `ScenarioMaker/` | Scenario authoring application |
| `docs/support/docs/` | User and contributor documentation |
| `utilities/` | Microsoft, open-source, and third-party utilities |

Read nearby implementations before adding a new pattern. Reuse the framework's
existing scenario lifecycle, logging helpers, parameter handling, remote
execution helpers, and result conventions.

## Making a change

Keep each pull request focused on one problem. Avoid unrelated formatting,
renaming, generated-file, or cleanup changes.

For code and scripts:

- preserve existing behavior unless the issue calls for a behavior change;
- validate inputs, command exit codes, required files, and discovered paths;
- fail early with an actionable error instead of silently continuing;
- support the architectures and platforms already supported by the affected
  component;
- avoid hardcoded credentials, user-specific paths, machine names, addresses,
  and drive letters;
- update comments and documentation affected by the change; and
- never include test results, logs, screenshots, or datasets containing
  sensitive or confidential information.

For PowerShell scenario scripts, error messages must use this exact format:

```text
 ERROR - <description>
```

The leading space and spacing around the hyphen are required by existing log
handling.

## Scenario contribution requirements

The detailed requirements and examples for various types of workloads can be found here: 
- [UI-based scenarios](HOBL_UI_Scenario_Guide.md)
- [Command-based developer or benchmark scenarios](HOBL_Command_Scenario_Guide.md)

The following rules are especially important:

### Scenario design tenets
1. Be kind to users.
    - A scenario needs to "just work" without any manual set up.
    - Execution time is a big limiter, so maximize coverage in as little time as possible.  Merge scenarios where possible.
1. Re-use as much as possible.
	- Not only does it make building scenarios easier, but it's critical for maintenance.  
	- If an app changes an icon or accessibility tag, there should only be one place in the repository that needs to be updated.
1. Self-check
	- There can be many reasons why a scenario might not run correctly:  An unexpected popup, something accidentally left running, network glitches, devices freezes, etc.  Scenarios need to check that they ran correctly and completely, and FAIL otherwise.
	- This is important to prevent bad data from tainting conclusions.
1. Reliable
	- It needs to work, every time, on all kinds of devices.
	- Accommodate a wide range of screen resolutions and scaling factors.
	- Accommodate a wide variety of device performance.  Early silicon may have severe performance limitations.  Make sure that fixed delays are long enough to accommodate very slow devices.
	- Make sure that any first-run dialogs, tutorials, hints, etc. are all handled before measurement begins.
1. Maintain device and silicon impartiality
    - Scenarios must evaluate devices impartially and must not favor or disadvantage a particular manufacturer, processor, architecture, platform, or silicon implementation. 
    - Adapt behavior only when required by a documented capability or platform difference. Prefer capability detection over checks for vendor, model, or processor identity. 
1. Leave no trace
	- During the "teardown" phase, a scenario should clean up and close down everything that it launched.
	- It should also kill and clean up everything in the "kill" routine for the case when the user explicitly stops the scenario, or there is a failure of some sort.
	- Kill routine needs to have every action wrapped in try so that if one fails others can continue.  Kill routine itself must never get an exception.
1. Accommodate all ways of measurement.
	- Short run, targeting around 5 min, for DAQ measurements and heavy ETL tracing so that resulting files are not too unwieldy.  40 min max.
	- Ability to loop to support rundown measurements.  (Note this is different than scenario iterations.)
1. Reserve power-impacting changes to the annual HOBL release at the beginning of each calendar year.
	- To minimize users having to re-baseline.
1. Fast support.
    - Fast support is a core expectation for HOBL. The contributor or sponsoring team for a scenario is responsible for maintaining it, investigating user-reported failures, and answering questions.
    - Scenario owners are expected to acknowledge user reports and support requests same day, then provide status and drive the issue to resolution as quickly as practical. 


### Preserve the prep, setup, run, teardown, and kill lifecycle

- **Prep** installs dependencies and creates persistent scenario resources. It
  should be idempotent where practical.
- **Setup** performs procedures that are needed to set up the test for every iteration.
- **Run** performs the measured workload and must be repeatable across
  iterations.
- **Teardown** removes only outputs that the next run will recreate. It must not
  remove repositories, packages, environments, caches, or other prep-installed
  dependencies.
- **Kill** cleans up anything that may get left running when the test is terminated mid-run.  It should have try-except around every command to ensure it never fails.

### Maintain platform parity

When a scenario has Windows and macOS implementations, inspect both before
changing either. Equivalent implementations must time the same workload phases,
calculate shared metrics the same way, and use the same CSV keys.

## Testing and validation

HOBL contains varied workloads and does not have one command that validates every
possible change. Run the smallest meaningful validation for the files you
changed, then perform end-to-end scenario validation when behavior on a DUT is
affected.

As applicable:

- exercise setup, run, failure, cancellation, and teardown paths;
- verify repeat execution, including an iteration after the first successful
  run;
- test every affected architecture, or clearly state what was not available;
- confirm logs contain actionable errors and no sensitive data;
- verify output files, CSV shape, metric names, units, and values; and
- compare Windows and macOS results when changing a cross-platform scenario.

Do not validate destructive or configuration-changing behavior on a personal or
production machine. Use a dedicated DUT and preserve the repository rule that
testers must not disable normal operating-system services merely to improve a
measurement.

If full hardware validation is not available, describe exactly what you did
validate and what remains untested in the pull request. Maintainers may request
additional lab validation before merging.

## Documentation and dependencies

Update documentation in the same pull request when changing setup,
configuration, parameters, output, metrics, or user-visible behavior. Keep links
relative when referencing files in this repository.

Changes to files in `utilities/` require additional care:

- do not modify, reverse engineer, or redistribute Microsoft proprietary
  utilities outside the permissions stated in their directory;
- preserve upstream copyright and license text for third-party files;
- include only software whose license permits the intended use and
  redistribution;
- update NOTICE.md in the root folder, and applicable component notices when required;
  and
- identify the source, version, license, and reason for adding or updating a
  binary or third-party component in the pull request.

Prefer reproducible source or package-manager installation over committing new
binaries. Do not add generated artifacts unless the repository requires them.

## Submitting a pull request

Push your branch to your fork and open a pull request against `main`. Draft pull
requests are encouraged for substantial or cross-platform work when early
feedback would prevent rework.

A good pull request:

- links the related issue;
- explains the problem and why the change is needed;
- describes the implementation and important design choices;
- calls out user-visible behavior, compatibility, or measurement changes;
- lists exact validation performed, including operating systems,
  architectures, and hardware;
- identifies validation that was not performed;
- includes relevant logs or before-and-after results with sensitive data
  removed;
- updates tests and documentation where applicable; and
- contains no unrelated changes.

Before requesting review, confirm:

- [ ] The change is scoped to one issue or coherent objective.
- [ ] New and changed paths are discovered or derived, not assumed.
- [ ] Failure paths report actionable errors and command failures are checked.
- [ ] Scenario prep, run, and teardown responsibilities remain separated.
- [ ] Shared toolchains cannot be overwritten by the change.
- [ ] Windows and macOS behavior and metrics remain aligned where applicable.
- [ ] Relevant validation passed, or limitations are documented.
- [ ] Documentation and third-party notices are current.
- [ ] Logs, screenshots, commits, and generated files contain no secrets or
      confidential data.

Respond to review comments and automated checks. Keep the branch current when
requested, and resolve review conversations only after the concern has been
addressed or agreement has been reached.

## Contributor License Agreement

Most contributions require you to agree to a Contributor License Agreement
(CLA), declaring that you have the right to grant Microsoft the rights to use
your contribution. For details, visit
[https://cla.opensource.microsoft.com](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will determine whether you need to
provide a CLA and will add the appropriate status or instructions to the pull
request. Follow the bot's instructions. You generally need to complete this only
once for Microsoft repositories that use the same CLA.

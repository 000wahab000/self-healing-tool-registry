> Supplementary reading only. This file does not change scope. product.md, technical-approach.md and plan.md remain the source of truth; nothing here is a requirement.

Each entry's page was opened and title, authors and year checked on 2026-10-14. Entries marked "arXiv preprint" have no venue on their page and are not peer reviewed. Summaries are condensed from abstracts, not from full texts.

## 1. Breaking changes and evolution of web/REST APIs

### [How Many Web APIs Evolve Following Semantic Versioning?](https://link.springer.com/chapter/10.1007/978-3-031-62362-2_25)
Serbout and Pautasso, 2024. ICWE 2024 (Springer LNCS 14629).
- Shows: across 3,075 OpenAPI-described APIs (506,273 changes, 16,053 versions), in the best case only 517 APIs always bumped the major version on a breaking change, and 1,970 did not always warn clients.
- Relates: version numbers are not a reliable break signal, which supports detecting breaks at runtime (4xx, schema check) and diffing the actual specs.
- Tag: `useful-for-pitch`

### [Exploratory Analysis of the Structural Evolution of public REST APIs](https://conf.researchr.org/details/cibse-2023/cibse-2023-main-conference/12/Exploratory-Analysis-of-the-Structural-Evolution-of-public-REST-APIs)
Robles et al. (Robles, Potes, Garces, Canovas Izquierdo, Cabot), 2023. CIbSE 2023.
- Shows: a taxonomy of structural REST API changes grouped by their impact on client software, plus a mining process to detect them, applied to Azure APIs from APIsGuru.
- Relates: a ready vocabulary for our spec-diff classes; useful to check which client-breaking change types move/cast/header/route do and do not cover.
- Tag: `supports-current-design`

## 2. LLM tool use when APIs or their documentation change

### [Skill Drift Is Contract Violation: Proactive Maintenance for LLM Agent Skill Libraries](https://arxiv.org/abs/2605.10990)
Fan et al. (Fan, Tian, Li, Lu), 2026. arXiv preprint 2605.10990.
- Shows: extracts executable environment contracts from agent skill documents and checks only role-bearing assumptions; zero false alarms on 599 no-drift and hard-negative cases (contract-free CI probes: 40% false positives); violated contracts lift one-round repair success from 10% (without localization) to 78%. Also releases an 880-pair benchmark.
- Relates: same detect, localize, repair-once shape as ours; its false-alarm control parallels our need to avoid patching non-breaks. Its drift types (schema, auth, API migration) could seed our fault injector.
- Tag: `supports-current-design`

### [ToolRobustBench: Stage-Wise Perturbation Evaluation and Failure Diagnosis for Tool-Calling Agents](https://arxiv.org/abs/2608.23635)
Zheng, Wu and Chang, 2026. arXiv preprint 2608.23635.
- Shows: perturbs tool interface, user intent, tool output and runtime environment, and attributes failures to tool selection, schema grounding, argument binding or output handling (15,456 instances, 7 models); tool-output perturbation is the dominant bottleneck.
- Relates: its stage-wise failure labels are a template for reporting where the 422-loop baseline fails versus the healed path; its tool-interface perturbations resemble our rename, type and nesting breaks.
- Tag: `supports-current-design`

### [CodeUpdateArena: Benchmarking Knowledge Editing on API Updates](https://arxiv.org/abs/2407.06249)
Liu, Pandit, Ye, Choi and Durrett, 2024 (v3 2025). arXiv preprint 2407.06249 (page comment: "Under Review").
- Shows: 670 synthetic API-update plus program-synthesis examples (54 functions, 7 Python packages); prepending the update documentation did not let open-source code models (DeepSeek, CodeLlama) apply the change.
- Relates: motivation for not trusting an LLM to absorb an API change from docs alone and deriving the fix from the spec diff instead. Caveat: code generation, not runtime tool calls.
- Tag: `useful-for-pitch`

## 3. Automated API migration and adaptation

### [Reducing the Impact of Breaking Changes to Web Service Clients During Web API [Evolution]](https://conf.researchr.org/details/mobilesoft-2023/mobilesoft-2023-research-track/4/Reducing-the-Impact-of-Breaking-Changes-to-Web-Service-Clients-During-Web-API)
Schmiedmayer, Bauer and Bruegge, 2023. MOBILESoft 2023 (with ICSE). The page heading is cut off at "Web API"; the final word "Evolution" was not seen on the page.
- Shows: automated client adaptation from type-independent evolution patterns, with migration guides generated from OpenAPI specs; over 13 version increments (3,896 changes) it identified 86.1% of changes including 1,132 breaking ones, and 424 breaking changes could not be resolved automatically.
- Relates: closest prior art to spec diff then deterministic fix (but design-time Swift client generation, not a runtime patch); the 424 unresolved cases match our refuse-rather-than-invent safety gate.
- Tag: `supports-current-design`

### [Automated Program Repair Based on REST API Specifications Using Large Language Models](https://arxiv.org/abs/2510.25148)
Yamagishi, Yoshida, Makihara and Inoue, 2025. arXiv preprint 2510.25148.
- Shows: dcFix detects client code that violates a REST API spec and gives that fragment plus the spec to an LLM for corrected code; it beats a baseline that gives the LLM no pointer to the violating fragments.
- Relates: spec-grounded localization helps repair, which is the role our spec diff plays; we patch the request at runtime instead of regenerating client source with an LLM.
- Tag: `out-of-scope-idea`

## 4. Self-healing clients and test scripts

### [Semantic Test Repair for Web Applications](https://2023.esec-fse.org/details/fse-2023-research-papers/83/-Remote-Semantic-Test-Repair-for-Web-applications)
Qi, Qian and Li, 2023. ESEC/FSE 2023.
- Shows: Semter records semantic information from test runs on the original app version and finds moved UI elements by similarity; average repair ratio 84% on six web apps against three baselines.
- Relates: UI-locator healing is the analogue of our field-rename repair, and similarity ranking of candidates is loosely like our tie-break between candidate fixes. It targets DOM tests, so we would not build it.
- Tag: `out-of-scope-idea`

## 5. Evaluating agents under tool failures and noisy feedback

### [ToolMisuseBench: An Offline Deterministic Benchmark for Tool Misuse and Recovery in Agentic Systems](https://arxiv.org/abs/2604.01508)
Sigdel and Baral, 2026. arXiv preprint 2604.01508.
- Shows: 6,800 tasks over CRUD, retrieval, file and scheduling environments with replayable fault injection, scored under explicit step, call and retry budgets (success, invalid calls, policy violations, recovery quality, budgeted efficiency).
- Relates: nearest template for our evaluation: a budgeted retry loop is the 422-loop baseline, recovery quality maps to zero-touch rate, and budgeted efficiency to token overhead.
- Tag: `supports-current-design`

### [AgentNoiseBench: Benchmarking Robustness of Tool-Using LLM Agents Under Noisy Condition](https://arxiv.org/abs/2602.11348)
Wang et al. (12 authors), 2026. ICML 2026 poster (per the ICML page); arXiv 2602.11348.
- Shows: an automated pipeline injects controllable user noise and tool noise into existing agent benchmarks while keeping tasks solvable; models show consistent performance drops under noise.
- Relates: method to borrow for injecting breaks into an existing task set while keeping each task solvable, so failures are attributable to the agent or healer.
- Tag: `supports-current-design`

### [StableToolBench: Towards Stable Large-Scale Benchmarking on Tool Learning of Large Language Models](https://aclanthology.org/2024.findings-acl.664/)
Guo et al. (Guo, Cheng, Wang, Liang, Qin, Li, Liu, Sun, Liu), 2024. Findings of ACL 2024, pp. 11143-11156.
- Shows: real online APIs keep changing or going down, so it adds a virtual API server (caching plus simulators) and a GPT-4 judge with pass and win rates to stabilize scores.
- Relates: backs our use of an offline mock API with deterministic replay when measuring MTTR and comparing against the baseline.
- Tag: `supports-current-design`

## Possible pitch citations
Condensed from abstracts, numbers as reported; no verbatim quotes.
- In the best case only 517 of 3,075 studied web APIs consistently released major upgrades on breaking changes, and 1,970 did not always tell clients (Serbout and Pautasso, ICWE 2024).
- Tool-using agents often fail for operational reasons such as invalid arguments, interface drift, weak recovery and inefficient retries, even when language understanding is strong (Sigdel and Baral, ToolMisuseBench, arXiv 2604.01508, 2026).
- Violated environment contracts raised one-round repair success from 10% without localization to 78%, for agent skills rather than REST specifically (Fan et al., arXiv 2605.10990, 2026).

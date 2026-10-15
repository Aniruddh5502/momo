# User Memory Export — Aniruddho Biswas Badhon (Ani)

## Profile
- Ani (Aniruddho Biswas Badhon)
- Based in Bangladesh
- BUET Mechanical Engineering graduate (graduated June 2026, CGPA 2.85/4.0)
- Career strategy centers on international/remote roles, funded graduate programs abroad, and freelance USD-denominated work rather than local BD employment
- Decided against local BD industrial employment as a poor return on his skillset
- Self-taught across embedded firmware (ESP32/STM32, FreeRTOS, C/C++), scientific ML (PyTorch, surrogate modeling, FEM pipelines), agentic AI (LangGraph, FastAPI), and mechanical/thermal design (SolidWorks, ANSYS, OpenFOAM)
- Portfolio: aniruddh5502.github.io/Portfolio / github.com/Aniruddh5502

## Areas

### Cerberus (ESP32 + FreeRTOS fault-tolerant flight controller)
- ESP32 + FreeRTOS fault-tolerant flight controller
- Triple OTA partitioning with SHA-256 verification
- 3×3 TMR matrix with two-stage majority voting
- Hardware fault injection testing

### Grad School Applications (Erasmus Mundus, grad school)
- Actively pursuing fully funded graduate programs: Erasmus Mundus EU4M, IFROS, JEMARO
- Doing PhD outreach alongside program applications
- MEMS surrogate optimization framework is the primary research artifact supporting these applications
- Researching US stipend ranges, cost-of-living tiers, and multi-year savings projections under a minimal lifestyle
- Frames international employment/study as a prerequisite for his long-term financial trajectory, not an end in itself

### MEMS Surrogate Optimization Framework
- Repo: github.com/Aniruddh5502/mechanical-design-optimization-framework
- Primary research artifact for graduate program and PhD outreach
- Thesis work: 1,295 ANSYS runs, 20-model ensemble NN, PyTorch autograd Jacobian sensitivity, NSGA-II Pareto, UMAP diversity validation
- Has been engaging deeply with the limitations of current physics foundation models (FNO, MeshGraphNets) relative to his MEMS structural design domain

### Momobot
- LangGraph-based local agentic AI system running via Ollama (gemma4:31b)
- Current confirmed architecture: `USER_INPUT → REASONING → TOOL_NODE → COMPACT → REASONING` loop; no `security_gate_node`
- Memory is a persistent flat-file semantic store (`MEMORY.md`) with CRUD via `@tool`-decorated `save_memory` / `recall_memory` / `modify_memory` / `delete_memory` tools
- Memory parsing splits on `'\n\n---\n\n'` separator (not regex); each `## keyword` section self-contained for exact `.replace()` matching
- Memory tools located at `/mnt/user-data/outputs/`
- Compaction trigger is token-based, fires when `TOKEN_USAGE` (`prompt_eval_count`) exceeds 100,000 — no episodic FIFO or 20-loop trigger
- `TokenTracker` class manages counts without global state: `update_turn(response_metadata)`, `get_usage_percent()` (calculates CTX_WINDOW usage), `reset_turn()` per iteration
- Subagent uses standard context window only, no persistent memory cascade
- Tooling includes: persistent shell tool (Linux: bash sentinel-based; Windows: pwsh per-call), `edit`, `view` (Playwright-based), `web_search`/`web_fetch`, `list_directory`, `read`/`write`, OCR tool
- Built a system prompt crafting framework (thinking pattern / research-and-tool-use / autonomous-execution sections with worked examples) for Momobot's `SUB_SOUL.md`
- Packaged as a one-command Linux-installable CLI tool (`momobot_init.py` wizard, editable pip install, `/usr/local/bin` symlink via wrapper script)
- Memory-tiering work informed by investigation into MoE expert caching strategies (LFU/frequency-based hot-set in VRAM, full expert set in CPU RAM)

### Communication Style
- Communicates in a terse, direct, anti-sycophantic style
- Uses `:333` as an agreement/approval marker

### Finances
- Long-term financial philosophy: accumulate sufficient invested capital (~10 crore BDT) to generate passive income supporting his family indefinitely, after which work becomes directed toward genuine social impact
- Primary income strategies: Upwork (LangGraph/agentic AI positioning) and direct founder outreach
- Prefers freelance USD-denominated work over local BD employment
- Researching US stipend ranges, cost-of-living tiers, and multi-year savings projections under a minimal lifestyle

### Personal Interests
- Strong interest in philosophy
- Reads literature in both Bengali and English
- Interested in Shakta-Shaiva traditions

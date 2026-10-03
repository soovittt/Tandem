# Charlotte — Lead Architect Plan: Mac-Control Agent Harness + Native Command Bar

Grounded in the actual repo (`src/tandem/`): ReAct loop in `agent/agent.py`, OpenAI-compat backend in `llm/openai_compatible.py`, MCP adapter in `integrations/mcp.py`, AppleScript tools in `mac/`, vLLM launcher in `infra/aws/vllm-serve.sh`. The Next.js `web/` app is the browser console; the command bar is net-new Swift.

---

## 1. ADOPT — external drivers/harnesses to wire in (ranked)

**Rank 1 — `apple-mcp` (dhravya), MCP stdio. Wire TODAY.**
Deterministic Mail/Notes/Messages/Calendar/Reminders/Contacts via JXA. This directly overlaps and *outclasses* our hand-written `mac/apps/*.py` AppleScript tools for the same apps — more coverage, maintained upstream. Wire it through our existing `MCPIntegration.from_stdio` and demote our native AppleScript tools to a fallback.
`{"command":"bun","args":["run","/path/to/apple-mcp/index.ts"]}` (`brew install oven-sh/bun/bun` first).

**Rank 2 — `trycua/cua` + `cua-driver`, Python SDK (library, local host — NOT a VM). The hero capability.**
The only open stack that drives *any* app while the user's cursor stays put and focus isn't stolen (SkyLight `SLEventPostToPid`). This is Charlotte's headline demo: "it works alongside you." Do NOT route it through MCP — use the Python SDK directly so it shares our process, our screenshot cache, and our approval path.
`/bin/bash -c "$(curl -fsSL https://cua.ai/driver/install.sh)"` + `pip install "cua[agent]"`; grant Accessibility + Screen Recording to the Python host. Expose `cua_computer` as a small set of native Tools (`click_element`, `type_text`, `read_screen`, `run_steps`) wrapping `Computer`/`ComputerAgent`. **Pin a known-good driver release** and test your 2–3 demo apps early (background control is bleeding-edge: ~250ms focus flicker, cursor offset, Tk/canvas misses).

**Rank 3 — `QwenLM/open-computer-use`, MCP stdio. Generic AX fallback.**
Accessibility-first, background-friendly, trivial install. The middle rung for third-party apps with good AX trees that aren't Apple-native and aren't worth cua's complexity.
`npm i -g @qwen-code/open-computer-use` → `{"command":"open-computer-use","args":["mcp"]}`.

**Rank 4 — Hermes Agent patterns: BORROW, don't adopt the runtime.**
Our `agent/`, `memory/`, `skills/`, `guardrails/`, `approval.py` already are a Hermes-shaped harness. Do NOT re-platform onto Hermes/NemoClaw mid-hackathon — it's a rewrite with container/macOS friction. Instead lift two concrete ideas: (a) the **skill auto-generation loop** (synthesize a `Skill` from a completed multi-step trajectory into our `skills/file_store.py`), and (b) **terminal-backend-style command approval allowlists** feeding our `approval.py`.

**SKIP:** UI-TARS/Agent-S/self-operating-computer (foreground pyautogui — steals the machine, kills the "works alongside you" story and needs a second GPU-hosted VLM). NVIDIA OpenShell/NemoClaw Landlock/seccomp sandbox (Linux-only; on Mac it sandboxes a container we don't want in the loop). Keep one idea from OpenShell as a *narrative*: lock egress to the Nebius/vLLM endpoint only — but enforce it with a 20-line allowlist in our own guardrails, not the hardware stack.

**Routing policy (encode in a `Router` in `tools/`):** Apple first-party apps → `apple-mcp`. Generic AX apps → `open-computer-use`. Pixel-only / drag-heavy / must-run-in-background → `cua-driver`. Always prefer AX addressing; fall to pixels only when AX is empty.

---

## 2. EFFICIENCY — changes to harness + vLLM (ordered by impact)

**Harness**

1. **Fix prefix-cache hygiene — biggest win, and we're actively breaking it today.** `agent.py:124 _inject_relevant_memory` appends a `system` message *after* the first system prompt every `send()`, and `_loop_prompt` feeds tool results back as fresh `user` turns. Both mutate the middle of the prompt and reset KV reuse. Fix: (a) fold recalled memory into the **single leading system block** built once, or append it strictly at the tail; (b) keep history **append-only** — never reorder, never rewrite. Order the prompt: persona → operating rules → tool schemas (stable, byte-identical) → dynamic state last.

2. **Make MCP sessions persistent.** `integrations/mcp.py` calls `asyncio.run(stdio_client(...))` and re-spawns the server process on *every* `list_tools` and *every* tool call (lines 93-104). That re-launches bun/node per click and destroys any AX snapshot cache in the server. Hold one long-lived `ClientSession` per server on a background event loop; dispatch calls onto it. This alone cuts per-action latency massively since tool execution is ~half of E2E.

3. **Batch + parallelize actions per turn.** Native mode already iterates `result.tool_calls` (agent.py:94) but runs them serially. Run independent calls with `asyncio.gather` (~3/turn is the sweet spot). Add a `run_steps([...])` macro tool for dependent deterministic sequences (focus→type→tab→type) so one model turn performs a micro-plan — the single biggest step-count reducer.

4. **Perception ladder + screenshot discipline.** Default to AX (apple-mcp / open-computer-use / cua AX) → Set-of-Marks → raw pixels. Screenshot only on the pixel rung or for verification, never every step. Add a frame diff: skip byte-identical screenshots (also preserves vLLM's image KV hash). Crop to ROI; keep only last ~4 images full-detail, downscale older. Cache AX snapshots keyed on `(focused window id + title + top-node hash)`, invalidate **on action, not on a timer**.

5. **Reasoning OFF/ON routing on one Nemotron.** Add a cheap signal (known-control action? last action failed? low confidence?) → routine steps run reasoning-OFF + greedy + low `max_tokens`; planning/recovery/ambiguous grounding run reasoning-ON (temp 1.0/top_p 0.95). Route `reasoning_content` to logs, never back into context (keeps the prefix clean). Our `llm/openai_compatible.py` must pass `chat_template_kwargs={"enable_thinking": false}` for the OFF path.

6. **Add streaming to the backend.** `openai_compatible.py` is blocking (`max_tokens=1024`, temp 0.7). Add a `stream()` method yielding deltas so the harness parses/executes tool calls as they complete and the command bar shows tokens live; cap `max_tokens` aggressively for OFF steps (decode is linear, prefix-cache doesn't help it).

**vLLM (`infra/aws/vllm-serve.sh` — currently just `--max-model-len 4096 --enable-auto-tool-choice --tool-call-parser nemotron`)**

7. `--enable-prefix-caching` (verify V1 default; confirm `cached_tokens` rising in logs). The free lunch for a ReAct loop.
8. Hybrid-Mamba Nemotron prefix reuse: `--mamba-cache-mode align --enable-mamba-fine-grained-prefix-cache --prefix-match-unit 64`.
9. `--enable-chunked-prefill` with `--max-num-batched-tokens 2048` (latency-biased for a single live agent).
10. Guided JSON for tool calls (xgrammar) + **pre-warm tool schemas at startup** to pay the grammar compile once; use the model's documented reasoning parser (`--reasoning-parser`, e.g. `nemotron_v3`/`nano_v3`).
11. Raise `--max-model-len` well above 4096 (multi-step trajectories + AX text overflow it fast), `--kv-cache-dtype fp8`, `--async-scheduling`, FP8 weights, `--max-num-seqs 1–4`.
12. Speculative decoding (n-gram/suffix, or DFlash/DSpark if on Nemotron 3.5 Lightning) — tool-call JSON is highly predictable.

**Measure:** per-step prefix-cache hit rate, steps/task, tokens/step (vision vs text split), TTFT, tool-vs-decode latency, % frames skipped. Fly with instruments, not vibes.

---

## 3. NATIVE APP — command-bar architecture + structure

**Decision: native Swift, macOS-only.** SwiftUI/AppKit `LSUIElement` menu-bar app built with **SwiftPM (no `.xcodeproj`)**, ad-hoc signed. Reject Tauri — it reaches parity only by gluing `tauri-nspanel` + `global-shortcut`, and non-activating-panel-over-fullscreen + permission-free hotkey are exactly what judges feel. (Revisit only if a Windows demo becomes a hard requirement.)

**Four components:**
- **Menu bar:** `NSStatusItem` + `LSUIElement=true` in Info.plist → `.accessory` activation policy (no Dock icon, no focus theft).
- **Global hotkey:** Carbon `RegisterEventHotKey` only, v1 — permission-free, exclusive, pre-window. Avoid `NSEvent.addGlobalMonitor` (needs Accessibility, keylogger-scope). Pick a free combo (NOT ⌥⌘Space — that's Finder). Upgrade to NSEvent chords later *only after* Accessibility is granted for the cua driver anyway.
- **Command bar → cowork:** one `.nonactivatingPanel` `NSPanel` subclass hosting SwiftUI via `NSHostingView`; `isFloatingPanel`, `level=.floating`, `collectionBehavior=[.canJoinAllSpaces,.fullScreenAuxiliary]`, `becomesKeyOnlyIfNeeded`, `canBecomeKey=true`, traffic lights hidden. **One panel that resizes** (bar 680×72 → cowork 980×640), not two windows — preserves the "I started typing, now I'm in a workspace" continuity. Call `NSApp.activate` only when you actually need the keyboard.
- **Backend link:** `URLSession` to **`http://127.0.0.1:8000`** (loopback literal IP — ATS exempts it; `localhost` is flaky in a signed app). Consume the new SSE stream via `URLSession.bytes().lines`. App launches the Python backend as a child `Process` and health-checks `GET /health` before showing the bar. Crucially, the bar needs a **live approval surface**: render `requires_approval` tool calls as an inline approve/deny card — this is our new `ApprovalPolicy` implementation beyond `ConsoleApproval`, and it's the trust story for a background Mac-controlling agent.

**Project structure (new top-level `mac-app/`, sibling to `src/`, `web/`):**
```
mac-app/
├── Package.swift                 # swift-tools 6.0, .macOS(.v14), executableTarget "Charlotte"
├── build.sh                      # swift build -c release → assemble .app → codesign --sign -
├── Resources/Info.plist          # LSUIElement, ATS NSAllowsLocalNetworking, bundle id
└── Sources/Charlotte/
    ├── main.swift                # NSApplication + AppDelegate, setActivationPolicy(.accessory)
    ├── AppDelegate.swift         # NSStatusItem, wires HotKey + CommandBarController
    ├── HotKey.swift              # Carbon RegisterEventHotKey wrapper
    ├── FloatingPanel.swift       # nonactivating NSPanel subclass
    ├── CommandBarController.swift# toggle + bar⇄cowork morph
    ├── Views/{CommandBarView,CoworkView,ApprovalCard}.swift
    └── Net/Backend.swift         # 127.0.0.1:8000 SSE client + /approve POST
```
Backend side: add `chat/stream` (SSE) and an approval round-trip endpoint to `src/tandem/server.py`; `web/` stays as the richer debug/history console.

---

## 4. BUILD CHECKLIST — ordered path to a killer demo

**P0 — spine that must work on stage**
1. Add vLLM efficiency flags to `infra/aws/vllm-serve.sh` (prefix-caching, mamba fine-grained, chunked-prefill, guided JSON, bigger max-model-len, fp8). Confirm `cached_tokens` rising in logs.
2. Fix prefix-cache breakers in `agent/agent.py`: fold memory into the leading system block, keep history append-only, stable tool-schema ordering.
3. Make `integrations/mcp.py` sessions persistent (one long-lived `ClientSession` per server on a background loop) — kill the per-call respawn.
4. Wire **apple-mcp** via `MCPIntegration.from_stdio`; route Apple-app intents to it; demote `mac/apps/*` to fallback. End-to-end: "draft a Mail reply / add a reminder" from CLI.

**P1 — the hero capability + the surface**
5. Install cua-driver + SDK; grant Accessibility + Screen Recording; wrap `Computer` as native Tools (`click_element`, `type_text`, `read_screen`, `run_steps`). Smoke-test background control on your 2–3 target apps; pin the driver release.
6. Build the `Router` (apple-mcp → open-computer-use → cua) and the perception ladder (AX → SoM → pixels) with AX-snapshot caching + frame diff-skip.
7. Scaffold `mac-app/` (SwiftPM, build.sh, Info.plist); get the menu-bar `LSUIElement` app + Carbon hotkey + floating panel toggling.
8. Add `chat/stream` SSE + approval endpoint to `server.py`; add backend streaming + OFF/ON reasoning routing to `llm/openai_compatible.py`; wire `Backend.swift` to stream tokens into the bar.

**P2 — the trust + "grows with you" story**
9. Inline **approval card** in the bar (new `ApprovalPolicy` → web/panel) for `requires_approval` tools — the headline for a background Mac agent.
10. Egress allowlist in guardrails (outbound only to vLLM/Nebius) — "your R&D data can't exfiltrate."
11. Borrow Hermes' skill-synthesis: turn a successful multi-step trajectory into a saved `Skill` in `skills/file_store.py`; show it being reused.
12. Bar→cowork morph animation + live step/trace view.

**P3 — polish**
13. Parallel/batched tool execution (`asyncio.gather`, `run_steps` macro) + n-gram speculative tool execution.
14. Nebius cutover path (swap `base_url`/`api_key` in `config.py`; everything else unchanged).
15. Instrument the metrics dashboard; rehearse the demo on the exact apps with the pinned driver.

**Demo narrative to engineer toward:** hit the hotkey → bar drops over whatever you're doing → "File the three NVIDIA spec PDFs into a Notes summary and reply to Priya" → Charlotte reads Mail via apple-mcp, clicks through a third-party viewer via cua **without moving your cursor while you keep typing**, surfaces an approval card before sending, and saves the whole thing as a reusable skill — all reasoning on self-hosted Nemotron with the vLLM cache lit up.

**Load-bearing specifics:** backend must bind `127.0.0.1` (not `localhost`) for the signed app's ATS; `mac-app/` is a new sibling of `src/`; the two files most responsible for current inefficiency are `integrations/mcp.py` (per-call process respawn) and `agent/agent.py:124` (mid-prompt memory injection).
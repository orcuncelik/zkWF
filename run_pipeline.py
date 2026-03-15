#!/usr/bin/env python3
"""
zkWF End-to-End Pipeline Script (Python)

Usage:
    python3 run_pipeline.py [OPTIONS] [bpmn_file] [test_cases_file]
    python3 run_pipeline.py /Users/orcuncelik/MT/orcun/zkWF/models/unit_tests/t1_zkp.bpmn /Users/orcuncelik/MT/orcun/zkWF/models/unit_tests/t1_zkp.json
Options:
    --skip-tests    Skip ZK witness/proof test cases (compile+setup only)
    --skip-setup    Skip compile+setup (reuse existing proving.key)

Defaults:
    bpmn_file       bpmn/supply_chain.bpmn
    test_cases_file bpmn/supply_chain_testCases.json

Phases:
    1. Prerequisites check
    2. Build CLI jar (skip if up-to-date)
    3. ZoKrates circuits + trusted setup + ZK proof tests
    4. Export verifier.sol
    5. Compile contracts (EVM + zkVM)
    6. Deploy on Hardhat (local in-process network)
    6.5 On-chain execution benchmark (stepModel)
    7. zkSync L2 benchmarks (anvil-zksync) + gas comparison
    8. Summary
"""

import argparse
import json
import os
import platform
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# =============================================================================
# Logging helpers
# =============================================================================

class Logger:
    """Handles console output with formatting and log file mirroring."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._log_file = open(log_path, "a")

    def _write(self, text: str):
        print(text)
        self._log_file.write(text + "\n")
        self._log_file.flush()

    def bold(self, text: str):
        self._write(f"\033[1m{text}\033[0m")

    def info(self, text: str):
        self._write(f"  [INFO] {text}")

    def ok(self, text: str):
        self._write(f"  [ OK ] {text}")

    def warn(self, text: str):
        self._write(f"  [WARN] {text}")

    def fail(self, text: str):
        self._write(f"  [FAIL] {text}")
        sys.exit(1)

    def phase(self, number: str, title: str):
        self._write("")
        sep = "\u2501" * 60
        self._write(sep)
        self.bold(f"Phase {number}: {title}")
        self._write(sep)

    def blank(self):
        self._write("")

    def close(self):
        self._log_file.close()


# =============================================================================
# Metrics dataclass
# =============================================================================

@dataclass
class Metrics:
    """Stores all metrics collected throughout the pipeline."""
    compile_time: str = ""
    setup_time: str = ""
    test_count: str = ""
    test_fail: str = "0"
    avg_proof_time: str = ""
    l1_gas: str = ""
    l1_addr: str = ""
    l1_deploy_time: str = ""
    evm_bytecode_bytes: str = ""
    zk_bytecode_bytes: str = ""
    l2_gas: str = ""
    l2_addr: str = ""
    l2_deploy_time: str = ""
    circuit_artifact_sizes: dict = field(default_factory=dict)


@dataclass
class HardwareInfo:
    """Stores hardware and environment metadata."""
    cpu: str = "?"
    ram_gb: str = "?"
    os_info: str = "?"
    arch: str = "?"
    zokrates_version: str = "?"
    node_version: str = "?"


@dataclass
class BenchmarkState:
    """Stores temp file paths and JSON data for benchmark phases."""
    deploy_tmp: str = ""
    exec_tmp: str = ""
    zksync_deploy_tmp: str = ""
    zksync_exec_tmp: str = ""
    zk_tests_tmp: str = ""
    zk_tests_json: list = field(default_factory=list)
    deploy_json: dict = field(default_factory=dict)
    exec_json: dict = field(default_factory=lambda: {"skipped": True, "operations": []})
    zksync_deploy_json: dict = field(default_factory=dict)
    zksync_exec_json: dict = field(default_factory=lambda: {"skipped": True, "operations": []})
    l2_benchmark_ok: bool = False


# =============================================================================
# Config
# =============================================================================

@dataclass
class PipelineConfig:
    """Holds all pipeline paths and settings."""
    project_root: Path
    bpmn_file: Path
    test_cases_file: Path
    skip_tests: bool
    skip_setup: bool
    timestamp: str

    @property
    def zokrates_bin(self) -> Path:
        return self.project_root / ".zokrates" / "bin" / "zokrates"

    @property
    def zokrates_stdlib(self) -> Path:
        return self.project_root / ".zokrates" / "stdlib"

    @property
    def python_venv(self) -> Path:
        return self.project_root / "pycrypto" / "venv" / "bin" / "python3"

    @property
    def cli_jar(self) -> Path:
        return self.project_root / "generator" / "cli" / "build" / "libs" / "cli-1.0-SNAPSHOT-all.jar"

    @property
    def verifier_dir(self) -> Path:
        return self.project_root / "verifier"

    @property
    def generator_dir(self) -> Path:
        return self.project_root / "generator"

    @property
    def log_file(self) -> Path:
        return self.project_root / f"pipeline_{self.timestamp}.log"

    @property
    def benchmark_file(self) -> Path:
        return self.project_root / f"benchmark_{self.timestamp}.json"


# =============================================================================
# Utility functions
# =============================================================================

def run_cmd(cmd: list[str], cwd: Optional[Path] = None, env: Optional[dict] = None,
            capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command, optionally capturing output."""
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        cmd, cwd=cwd, env=merged_env,
        capture_output=capture, text=True,
        check=check,
    )


def run_cmd_capture(cmd: list[str], cwd: Optional[Path] = None,
                    env: Optional[dict] = None) -> tuple[str, int]:
    """Run a command, stream output live, capture it, and return (output, exit_code)."""
    merged_env = {**os.environ, **(env or {})}
    lines = []
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=merged_env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    for line in proc.stdout:
        print(line, end="")
        lines.append(line)
    proc.wait()
    return "".join(lines), proc.returncode


def check_command(log: Logger, name: str, cmd: str):
    """Verify a command exists on PATH."""
    path = shutil.which(cmd)
    if path is None:
        log.fail(f"{name} not found (command: {cmd}). Please install it and re-run.")
    log.ok(f"{name}: {path}")


def check_file(log: Logger, label: str, path: Path):
    """Verify a file exists."""
    if not path.is_file():
        log.fail(f"{label} not found at: {path}")
    log.ok(f"{label}: {path}")


def extract_json_field(data: dict, *keys, default="") -> str:
    """Safely extract a nested field from a dict."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return str(current) if current != default else default


def safe_load_json(path: str, default=None):
    """Load a JSON file, returning default on any error."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def compute_stats(vals: list[float]) -> dict:
    """Compute min/max/median/p95 for a list of values."""
    if not vals:
        return {"min": None, "max": None, "median": None, "p95": None}
    sv = sorted(vals)
    n = len(sv)
    return {
        "min": sv[0],
        "max": sv[-1],
        "median": round(statistics.median(sv), 4),
        "p95": round(sv[min(int(n * 0.95), n - 1)], 4),
    }


PROOF_SIZE_MEASUREMENT = (
    "On-disk byte size of the serialized ZoKrates proof JSON output "
    "(proofN.json)."
)


# =============================================================================
# Phase 1: Prerequisites
# =============================================================================

def phase_prerequisites(log: Logger, cfg: PipelineConfig, hw: HardwareInfo):
    """Check all required tools, files, and dependencies."""
    log.phase("1", "Prerequisites check")

    # Check required commands
    check_command(log, "java", "java")
    check_command(log, "node", "node")
    check_command(log, "npm", "npm")
    check_command(log, "python3", "python3")

    # Java version check (>= 11)
    result = run_cmd(["java", "-version"], capture=True, check=False)
    version_output = result.stderr or result.stdout
    match = re.search(r'"(\d+[\.\d]*)"', version_output)
    if match:
        ver_str = match.group(1)
        major = int(ver_str.split(".")[0])
        if major == 1:
            major = int(ver_str.split(".")[1])
        if major < 11:
            log.fail(f"Java 11+ required, found version {major}")
        log.ok(f"Java version: {major} (>= 11)")

    # Node version check
    node_ver = run_cmd(["node", "--version"], capture=True).stdout.strip()
    hw.node_version = node_ver
    node_major = node_ver.lstrip("v").split(".")[0]
    if node_major not in ("18", "20", "22"):
        log.warn(f"Node.js {node_ver} is not officially supported by Hardhat 2.x")
        log.warn("Recommended: Node.js 20 LTS")
        log.warn("Continuing anyway — unexpected behaviour may occur")
    else:
        log.ok(f"Node.js version: {node_ver} (supported)")

    # Check required files
    check_file(log, "ZoKrates binary", cfg.zokrates_bin)
    check_file(log, "ZoKrates stdlib", cfg.zokrates_stdlib / "field.zok")
    check_file(log, "Python venv", cfg.python_venv)
    check_file(log, "BPMN file", cfg.bpmn_file)
    check_file(log, "Test cases file", cfg.test_cases_file)

    # Ensure bitstring Python module
    result = run_cmd(
        [str(cfg.python_venv), "-c", "import bitstring"],
        capture=True, check=False,
    )
    if result.returncode != 0:
        log.info("bitstring not found — installing into venv...")
        run_cmd([str(cfg.python_venv), "-m", "pip", "install", "--quiet", "bitstring"])
    log.ok("Python bitstring module: available")

    # Ensure node_modules
    if not (cfg.verifier_dir / "node_modules").is_dir():
        log.info("node_modules missing — running npm install in verifier/...")
        run_cmd(["npm", "install", "--silent"], cwd=cfg.verifier_dir)
    log.ok("verifier/node_modules: present")

    # Collect hardware info
    hw.arch = platform.machine()
    hw.os_info = f"{platform.system()} {platform.release()}"
    try:
        hw.cpu = run_cmd(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture=True, check=False,
        ).stdout.strip() or hw.arch
    except Exception:
        hw.cpu = hw.arch
    try:
        import os as _os
        ram = _os.sysconf("SC_PAGE_SIZE") * _os.sysconf("SC_PHYS_PAGES") / (2**30)
        hw.ram_gb = str(round(ram, 1))
    except Exception:
        hw.ram_gb = "?"

    # ZoKrates version
    zok_out = run_cmd([str(cfg.zokrates_bin), "--version"], capture=True, check=False)
    match = re.search(r"(\d+\.\d+\.\d+)", zok_out.stdout + zok_out.stderr)
    hw.zokrates_version = match.group(1) if match else "?"

    log.info(f"Hardware : {hw.cpu} ({hw.arch}, {hw.ram_gb}GB RAM)")
    log.info(f"ZoKrates : v{hw.zokrates_version}")


# =============================================================================
# Phase 2: Build CLI jar
# =============================================================================

def phase_build_cli(log: Logger, cfg: PipelineConfig):
    """Build the CLI jar via Gradle if it doesn't already exist."""
    log.phase("2", "Build CLI jar")

    if cfg.cli_jar.is_file():
        log.ok(f"CLI jar already exists: {cfg.cli_jar}")
        log.info("Skipping build (delete jar to force rebuild)")
    else:
        log.info("Building CLI jar via Gradle...")
        run_cmd(["./gradlew", "cli:shadowJar", "--quiet"], cwd=cfg.generator_dir)
        check_file(log, "CLI jar", cfg.cli_jar)
        log.ok("CLI jar built successfully")


# =============================================================================
# Phase 3: ZoKrates circuits + trusted setup + ZK proof tests
# =============================================================================

def phase_zokrates(log: Logger, cfg: PipelineConfig, metrics: Metrics,
                   bench: BenchmarkState):
    """Run the generator CLI to produce circuits, perform setup, and run ZK tests."""
    log.phase("3", "ZoKrates circuits + trusted setup + ZK proof tests")

    # Build environment for the generator subprocess
    venv_dir = cfg.project_root / "pycrypto" / "venv"
    env = {
        "PYTHON": str(cfg.python_venv),
        "VIRTUAL_ENV": str(venv_dir),
        "PATH": f"{venv_dir / 'bin'}:{cfg.project_root / '.zokrates' / 'bin'}:{os.environ.get('PATH', '')}",
        "ZOKRATES_STDLIB": str(cfg.zokrates_stdlib),
    }

    # Build generator flags
    generator_flags = []
    flags_msg = ""
    if cfg.skip_tests:
        generator_flags.append("--skip-tests")
        flags_msg += " (--skip-tests)"
    if cfg.skip_setup:
        generator_flags.append("--skip-setup")
        flags_msg += " (--skip-setup)"

    if not cfg.skip_tests:
        removed = _cleanup_generator_test_artifacts(cfg.generator_dir)
        if removed:
            log.info(f"Removed {removed} stale proof artifact(s) from generator/")

    log.info(f"Running generator CLI{flags_msg}...")

    cmd = ["java", "-jar", str(cfg.cli_jar)] + generator_flags + [
        str(cfg.bpmn_file), str(cfg.test_cases_file),
    ]
    output, exit_code = run_cmd_capture(cmd, cwd=cfg.generator_dir, env=env)

    if exit_code != 0:
        fail_match = re.search(r"(\d+/\d+ tests failed)", output)
        if fail_match:
            log.fail(f"ZK proof tests failed: {fail_match.group(1)}")
        else:
            log.fail(f"Generator CLI exited with error (exit code {exit_code})")

    # Extract metrics from output
    _extract_generator_metrics(output, metrics)

    # Parse per-test ZK metrics from table output
    if not cfg.skip_tests:
        bench.zk_tests_json = _parse_zk_test_table(output, cfg.generator_dir)

    # Write ZK tests to temp file for benchmark report
    bench.zk_tests_tmp = tempfile.mktemp(prefix="zkwf-zktests-")
    with open(bench.zk_tests_tmp, "w") as f:
        json.dump(bench.zk_tests_json, f)

    # Verify output files
    check_file(log, "root.zok", cfg.generator_dir / "root.zok")
    check_file(log, "stateChange.zok", cfg.generator_dir / "stateChange.zok")
    if not cfg.skip_setup:
        check_file(log, "proving.key", cfg.generator_dir / "proving.key")
        check_file(log, "verification.key", cfg.generator_dir / "verification.key")

    log.ok("ZoKrates circuits generated")
    if metrics.compile_time:
        log.info(f"Compile time      : {metrics.compile_time}s")
    if metrics.setup_time:
        log.info(f"Setup time        : {metrics.setup_time}s")
    if not cfg.skip_tests:
        if metrics.test_count:
            log.info(f"Test cases run    : {metrics.test_count}")
        if metrics.avg_proof_time:
            log.info(f"Avg time (w+p)    : {metrics.avg_proof_time}s")

    # Log generated artifact sizes
    _log_circuit_artifact_sizes(log, cfg, metrics)


def _extract_generator_metrics(output: str, metrics: Metrics):
    """Extract timing and test metrics from generator CLI output."""
    m = re.search(r"Compile Time:: ([\d.]+)", output)
    if m:
        metrics.compile_time = m.group(1)

    m = re.search(r"Setup Time:: ([\d.]+)", output)
    if m:
        metrics.setup_time = m.group(1)

    m = re.search(r"(\d+) testcases loaded", output)
    if m:
        metrics.test_count = m.group(1)

    m = re.search(r"generated in ([\d.]+) s on average", output)
    if m:
        metrics.avg_proof_time = m.group(1)

    fail_match = re.search(r"(\d+)/\d+ tests failed", output)
    metrics.test_fail = fail_match.group(1) if fail_match else "0"


def _fmt_size(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024**3):.1f} GB"
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024**2):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


CIRCUIT_SUMMARY_ARTIFACTS = [
    ("out", "Flattened code (out)"),
    ("out.r1cs", "R1CS constraints (out.r1cs)"),
    ("proving.key", "Proving key (proving.key)"),
    ("verification.key", "Verification key (verification.key)"),
]


def _log_circuit_artifact_sizes(log: Logger, cfg: PipelineConfig, metrics: Metrics):
    """Log sizes of all generated artifacts in the generator directory."""
    # --- Single files ---
    single_files = CIRCUIT_SUMMARY_ARTIFACTS + [
        ("hash",             "Compiled hash circuit"),
        ("hash.zok",         "Hash ZoKrates source"),
        ("root.zok",         "Root ZoKrates source"),
        ("stateChange.zok",  "State change source"),
        ("abi.json",         "ABI definition"),
        ("verifier.sol",     "Verifier Solidity"),
        ("model.sol",        "Model Solidity"),
    ]
    log.blank()
    log.bold("  Generated Artifact Sizes")
    sizes = {}
    for filename, label in single_files:
        p = cfg.generator_dir / filename
        if p.is_file():
            sz = p.stat().st_size
            sizes[filename] = sz
            log.info(f"  {label:<34s} {_fmt_size(sz):>10s}")

    # --- Per-test file groups (glob patterns) ---
    file_groups = [
        ("hash*_curr",       "Hash witness curr"),
        ("hash*_curr.json",  "Hash witness curr JSON"),
        ("hash*_next",       "Hash witness next"),
        ("hash*_next.json",  "Hash witness next JSON"),
        ("out*.wtns",        "Witness files (out*.wtns)"),
        ("stateProof*.json", "State proof JSONs"),
        ("proof.json",       "ZK proof JSON"),
        ("test*.result",     "Test result files"),
        ("test*.json",       "Test JSON files"),
    ]
    for pattern, label in file_groups:
        files = sorted(cfg.generator_dir.glob(pattern))
        if not files:
            continue
        total = sum(f.stat().st_size for f in files)
        key = pattern.replace("*", "N")
        sizes[key] = total
        sizes[f"{key}_count"] = len(files)
        count_str = f" ({len(files)} files)" if len(files) > 1 else ""
        log.info(f"  {label + count_str:<34s} {_fmt_size(total):>10s}")

    metrics.circuit_artifact_sizes = sizes


def _parse_zk_test_table(output: str, proof_dir: Path) -> list[dict]:
    """Parse per-test ZK metrics from the generator's table output."""
    # Strip ANSI escape codes
    text = re.sub(r"\x1b\[[0-9;]*m", "", output)
    tests = []
    for line in text.splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|\s*([\d.]+)s\s*\|\s*([\d.]+)s\s*\|", line.strip())
        if m:
            test = {
                "test_id": int(m.group(1)),
                "witness_s": float(m.group(2)),
                "proof_s": float(m.group(3)),
            }
            # Measure proof size as the serialized JSON artifact written by ZoKrates.
            proof_file = proof_dir / f"proof{test['test_id']}.json"
            try:
                sz = proof_file.stat().st_size
                with open(proof_file) as f:
                    data = json.load(f)
                input_count = len(data.get("inputs", []))
                test["proof_size_bytes"] = sz
                test["public_inputs_count"] = input_count
                test["public_inputs_size_bytes"] = input_count * 32
            except Exception:
                pass
            tests.append(test)
    return tests


def _cleanup_generator_test_artifacts(generator_dir: Path) -> int:
    """Remove per-test proof artifacts so benchmarks only see the current run."""
    removed = 0
    for pattern in ("proof*.json", "stateProof*.json"):
        for path in generator_dir.glob(pattern):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed


# =============================================================================
# Phase 4: Export verifier.sol
# =============================================================================

def phase_export_verifier(log: Logger, cfg: PipelineConfig):
    """Export verifier.sol from ZoKrates and copy to verifier/contracts/."""
    log.phase("4", "Export verifier.sol")

    log.info("Exporting verifier contract...")
    run_cmd([str(cfg.zokrates_bin), "export-verifier"], cwd=cfg.generator_dir)

    verifier_sol = cfg.generator_dir / "verifier.sol"
    check_file(log, "verifier.sol (generator/)", verifier_sol)

    log.info("Copying verifier.sol to verifier/contracts/...")
    dest = cfg.verifier_dir / "contracts" / "verifier.sol"
    shutil.copy2(verifier_sol, dest)
    log.ok("verifier.sol deployed to verifier/contracts/")


# =============================================================================
# Phase 5: Compile contracts
# =============================================================================

def phase_compile_contracts(log: Logger, cfg: PipelineConfig, metrics: Metrics):
    """Compile contracts for both EVM (solc) and zkSync (zksolc)."""
    log.phase("5", "Compile contracts (EVM + zkVM)")

    # EVM compile
    log.info("Compiling for EVM (Hardhat/solc)...")
    run_cmd(["npx", "hardhat", "compile", "--quiet"], cwd=cfg.verifier_dir)
    log.ok("EVM compile complete")

    # zkSync compile
    log.info("Compiling for zkSync (zksolc)...")
    result = run_cmd(
        ["npx", "hardhat", "compile", "--network", "zkSyncTestnet"],
        cwd=cfg.verifier_dir, check=False,
    )
    if result.returncode == 0:
        log.ok("zkSync compile complete")
    else:
        log.warn("zkSync compile finished with warnings (non-fatal)")

    # Extract bytecode sizes
    _extract_bytecode_sizes(log, cfg, metrics)


def _extract_bytecode_sizes(log: Logger, cfg: PipelineConfig, metrics: Metrics):
    """Extract bytecode sizes from compiled artifact JSON files."""
    evm_artifact = cfg.verifier_dir / "artifacts-hardhat" / "contracts" / "model.sol" / "Model.json"
    zk_artifact = cfg.verifier_dir / "artifacts-hardhat-zk" / "contracts" / "model.sol" / "Model.json"

    if evm_artifact.is_file():
        data = json.loads(evm_artifact.read_text())
        bc = data.get("bytecode", "0x")
        metrics.evm_bytecode_bytes = str((len(bc) - 2) // 2)
        log.ok(f"EVM bytecode size: {metrics.evm_bytecode_bytes} bytes")
    else:
        log.warn("EVM artifact not found at expected path")

    if zk_artifact.is_file():
        data = json.loads(zk_artifact.read_text())
        bc = data.get("bytecode", "0x")
        metrics.zk_bytecode_bytes = str((len(bc) - 2) // 2)
        log.ok(f"zkVM bytecode size: {metrics.zk_bytecode_bytes} bytes")
    else:
        log.warn("zkVM artifact not found (zkSync compile may have used different output dir)")


# =============================================================================
# Phase 6: Deploy on Hardhat (L1 local)
# =============================================================================

def phase_deploy_hardhat(log: Logger, cfg: PipelineConfig, metrics: Metrics,
                         bench: BenchmarkState):
    """Deploy the Model contract on a local Hardhat network and collect metrics."""
    log.phase("6", "Deploy on Hardhat (local in-process network)")

    bench.deploy_tmp = tempfile.mktemp(prefix="zkwf-deploy-")
    Path(bench.deploy_tmp).write_text("{}")

    log.info("Deploying Model contract to Hardhat network (benchmark mode)...")
    env = {"BENCHMARK_DEPLOY_OUT": bench.deploy_tmp}
    run_cmd(
        ["npx", "hardhat", "run", "scripts/benchmark-deploy.js"],
        cwd=cfg.verifier_dir, env=env,
    )

    bench.deploy_json = safe_load_json(bench.deploy_tmp)
    dep = bench.deploy_json.get("deployment", {})
    metrics.l1_gas = str(dep.get("gas_used", ""))
    metrics.l1_addr = str(dep.get("contract_address", ""))
    metrics.l1_deploy_time = str(dep.get("deploy_time_s", ""))

    if metrics.l1_gas:
        log.ok(f"Gas used: {metrics.l1_gas}")
    if metrics.l1_addr:
        log.ok(f"Contract: {metrics.l1_addr}")
    if metrics.l1_deploy_time:
        log.ok(f"Deploy time: {metrics.l1_deploy_time}s")


# =============================================================================
# Phase 6.5: On-chain execution benchmark
# =============================================================================

def phase_execution_benchmark(log: Logger, cfg: PipelineConfig, bench: BenchmarkState):
    """Run on-chain execution benchmark (stepModel calls) on Hardhat."""
    log.phase("6.5", "On-chain execution benchmark (stepModel)")

    bench.exec_tmp = tempfile.mktemp(prefix="zkwf-exec-")
    Path(bench.exec_tmp).write_text(json.dumps({"skipped": True, "operations": []}))

    env = {
        "BENCHMARK_EXEC_OUT": bench.exec_tmp,
        "PROOF_DIR": str(cfg.generator_dir),
        "BENCHMARK_ZK_TESTS_FILE": bench.zk_tests_tmp,
    }

    if cfg.skip_tests:
        log.info("Skipping execution benchmark (--skip-tests)")
    else:
        log.info("Running on-chain execution benchmark (one deploy+call per stateProof)...")
        run_cmd(
            ["npx", "hardhat", "run", "scripts/benchmark-execution.js"],
            cwd=cfg.verifier_dir, env=env,
        )

    bench.exec_json = safe_load_json(
        bench.exec_tmp, {"skipped": True, "operations": []},
    )


# =============================================================================
# Phase 7: zkSync L2 benchmarks
# =============================================================================

def phase_zksync_benchmarks(log: Logger, cfg: PipelineConfig, metrics: Metrics,
                            bench: BenchmarkState):
    """Start anvil-zksync, deploy, run execution benchmarks, then stop the node."""
    log.phase("7", "zkSync L2 benchmarks (anvil-zksync)")

    bench.zksync_deploy_tmp = tempfile.mktemp(prefix="zkwf-zk-deploy-")
    bench.zksync_exec_tmp = tempfile.mktemp(prefix="zkwf-zk-exec-")
    Path(bench.zksync_deploy_tmp).write_text("{}")
    Path(bench.zksync_exec_tmp).write_text(json.dumps({"skipped": True, "operations": []}))

    anvil_proc = _start_anvil_zksync(log, cfg)
    if anvil_proc is None:
        return

    try:
        _run_l2_benchmarks(log, cfg, metrics, bench)
    finally:
        _stop_anvil_zksync(log, anvil_proc)

    # Read results
    bench.zksync_deploy_json = safe_load_json(bench.zksync_deploy_tmp)
    bench.zksync_exec_json = safe_load_json(
        bench.zksync_exec_tmp, {"skipped": True, "operations": []},
    )

    # Extract L2 metrics
    l2_dep = bench.zksync_deploy_json.get("deployment", {})
    metrics.l2_gas = str(l2_dep.get("gas_used", ""))
    metrics.l2_addr = str(l2_dep.get("contract_address", ""))
    metrics.l2_deploy_time = str(l2_dep.get("deploy_time_s", ""))

    if bench.l2_benchmark_ok:
        if metrics.l2_gas:
            log.ok(f"L2 Gas used: {metrics.l2_gas}")
        if metrics.l2_addr:
            log.ok(f"L2 Contract: {metrics.l2_addr}")
        if metrics.l2_deploy_time:
            log.ok(f"L2 Deploy time: {metrics.l2_deploy_time}s")

    # Gas comparison report
    _run_gas_comparison(log, cfg, bench)


def _start_anvil_zksync(log: Logger, cfg: PipelineConfig) -> Optional[subprocess.Popen]:
    """Locate and start the anvil-zksync node. Returns the process or None."""
    log.info("Starting anvil-zksync local node...")

    anvil_bin = _find_anvil_binary()
    anvil_log = open("/tmp/anvil-zksync.log", "w")

    if anvil_bin:
        log.info(f"Using cached binary: {anvil_bin}")
        proc = subprocess.Popen(
            [anvil_bin, "--port", "8011"],
            stdout=anvil_log, stderr=anvil_log,
            cwd=cfg.verifier_dir,
        )
    else:
        log.info("No cached binary found, trying 'npx hardhat node-zksync'...")
        proc = subprocess.Popen(
            ["npx", "hardhat", "node-zksync", "--port", "8011"],
            stdout=anvil_log, stderr=anvil_log,
            cwd=cfg.verifier_dir,
        )

    # Wait for node to be ready (up to 30s)
    ready = False
    for _ in range(30):
        try:
            result = subprocess.run(
                ["curl", "-s", "-X", "POST",
                 "-H", "Content-Type: application/json",
                 "-d", '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}',
                 "http://127.0.0.1:8011"],
                capture_output=True, text=True, timeout=2,
            )
            if "result" in result.stdout:
                ready = True
                break
        except Exception:
            pass
        time.sleep(1)

    if ready:
        log.ok(f"anvil-zksync node ready (PID {proc.pid})")
        return proc

    log.warn("anvil-zksync failed to start within 30s — skipping L2 benchmarks")
    log.warn("Check /tmp/anvil-zksync.log for details")
    _stop_anvil_zksync(log, proc)
    return None


def _find_anvil_binary() -> Optional[str]:
    """Find the newest cached anvil-zksync binary."""
    cache_dir = Path.home() / ".cache" / "hardhat-nodejs" / "zksync-memory-node"
    if not cache_dir.is_dir():
        return None
    binaries = [
        f for f in cache_dir.iterdir()
        if f.is_file() and os.access(f, os.X_OK)
    ]
    if not binaries:
        return None
    binaries.sort(key=lambda p: p.name)
    return str(binaries[-1])


def _run_l2_benchmarks(log: Logger, cfg: PipelineConfig, metrics: Metrics,
                       bench: BenchmarkState):
    """Run L2 deployment and execution benchmarks against anvil-zksync."""
    # Compile for zkSync
    log.info("Ensuring zkSync artifacts are up-to-date...")
    result = run_cmd(
        ["npx", "hardhat", "compile", "--network", "anvilZkSync"],
        cwd=cfg.verifier_dir, check=False,
    )
    if result.returncode != 0:
        log.warn("zkSync compile had warnings")

    # L2 deployment benchmark
    log.info("Deploying Model contract to anvil-zksync (benchmark mode)...")
    env = {"BENCHMARK_ZKSYNC_DEPLOY_OUT": bench.zksync_deploy_tmp}
    result = run_cmd(
        ["npx", "hardhat", "run", "scripts/benchmark-zksync-deploy.js",
         "--network", "anvilZkSync"],
        cwd=cfg.verifier_dir, env=env, check=False,
    )
    if result.returncode == 0:
        log.ok("L2 deployment benchmark complete")
    else:
        log.warn("L2 deployment benchmark failed")

    # L2 execution benchmark
    if cfg.skip_tests:
        log.info("Skipping L2 execution benchmark (--skip-tests)")
    else:
        log.info("Running L2 execution benchmark (one deploy+call per stateProof)...")
        env = {
            "BENCHMARK_ZKSYNC_EXEC_OUT": bench.zksync_exec_tmp,
            "PROOF_DIR": str(cfg.generator_dir),
            "BENCHMARK_ZK_TESTS_FILE": bench.zk_tests_tmp,
        }
        result = run_cmd(
            ["npx", "hardhat", "run", "scripts/benchmark-zksync-execution.js",
             "--network", "anvilZkSync"],
            cwd=cfg.verifier_dir, env=env, check=False,
        )
        if result.returncode == 0:
            log.ok("L2 execution benchmark complete")
        else:
            log.warn("L2 execution benchmark failed")

    bench.l2_benchmark_ok = True


def _stop_anvil_zksync(log: Logger, proc: subprocess.Popen):
    """Stop the anvil-zksync process."""
    try:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)
            log.ok("anvil-zksync node stopped")
    except Exception:
        proc.kill()


def _run_gas_comparison(log: Logger, cfg: PipelineConfig, bench: BenchmarkState):
    """Run the gas comparison report script."""
    log.info("Generating gas comparison report...")
    env = {
        "BENCHMARK_DEPLOY_OUT": bench.deploy_tmp or "",
        "BENCHMARK_EXEC_OUT": bench.exec_tmp or "",
        "BENCHMARK_ZKSYNC_DEPLOY_OUT": bench.zksync_deploy_tmp or "",
        "BENCHMARK_ZKSYNC_EXEC_OUT": bench.zksync_exec_tmp or "",
    }
    run_cmd(
        ["npx", "hardhat", "run", "scripts/estimate-gas.js"],
        cwd=cfg.verifier_dir, env=env,
    )


# =============================================================================
# Phase 8: Summary + Benchmark JSON
# =============================================================================

def phase_summary(log: Logger, cfg: PipelineConfig, metrics: Metrics,
                  bench: BenchmarkState, hw: HardwareInfo,
                  pipeline_duration: int):
    """Generate the benchmark JSON report and print a human-readable summary."""
    log.phase("8", "Benchmark report + summary")

    # Fetch mainnet gas prices once (used by both JSON and summary)
    log.info("Fetching live gas prices from mainnet RPCs...")
    l1_gas_price_gwei, l2_gas_price_gwei = _extract_gas_prices()
    if l1_gas_price_gwei is not None:
        log.ok(f"L1 (Ethereum) gas price: {l1_gas_price_gwei:.4f} gwei")
    else:
        log.warn("Could not fetch L1 gas price")
    if l2_gas_price_gwei is not None:
        log.ok(f"L2 (zkSync) gas price: {l2_gas_price_gwei:.4f} gwei")
    else:
        log.warn("Could not fetch L2 gas price")

    # Call zks_estimateFee on zkSync mainnet for real L2 fee estimates
    zk_deploy_est, zk_exec_est = _estimate_zksync_mainnet_fees(log, bench)

    _generate_benchmark_json(cfg, metrics, bench, hw, pipeline_duration,
                             l1_gas_price_gwei, l2_gas_price_gwei,
                             zk_deploy_est, zk_exec_est)

    if cfg.benchmark_file.is_file():
        log.ok(f"Benchmark JSON: {cfg.benchmark_file}")
    else:
        log.warn("Benchmark JSON generation failed")

    _print_summary(log, cfg, metrics, bench, pipeline_duration,
                   l1_gas_price_gwei, l2_gas_price_gwei,
                   zk_deploy_est, zk_exec_est)


def _generate_benchmark_json(cfg: PipelineConfig, metrics: Metrics,
                             bench: BenchmarkState, hw: HardwareInfo,
                             pipeline_duration: int,
                             l1_gas_price_gwei: Optional[float] = None,
                             l2_gas_price_gwei: Optional[float] = None,
                             zk_deploy_est: Optional['ZkSyncFeeEstimate'] = None,
                             zk_exec_est: Optional['ZkSyncFeeEstimate'] = None):
    """Build and write the full benchmark JSON report."""
    zk_tests = bench.zk_tests_json or []
    deploy_data = bench.deploy_json or {}
    exec_data = bench.exec_json or {"skipped": True, "operations": []}
    zksync_deploy_data = bench.zksync_deploy_json or {}
    zksync_exec_data = bench.zksync_exec_json or {"skipped": True, "operations": []}

    # Read package.json for tooling versions
    pkg = safe_load_json(str(cfg.verifier_dir / "package.json"))
    dev = pkg.get("devDependencies", {})
    deps = pkg.get("dependencies", {})

    def ver(name):
        v = dev.get(name) or deps.get(name) or "?"
        return v.lstrip("^~") if v != "?" else "?"

    dep = deploy_data.get("deployment", {})
    ops = exec_data.get("operations", [])
    l2_dep = zksync_deploy_data.get("deployment", {})
    l2_ops = zksync_exec_data.get("operations", [])

    # Compute aggregate stats
    witness_times = [t["witness_s"] for t in zk_tests if "witness_s" in t]
    proof_times = [t["proof_s"] for t in zk_tests if "proof_s" in t]
    total_times = [t.get("witness_s", 0) + t.get("proof_s", 0)
                   for t in zk_tests if "witness_s" in t]
    proof_sizes = [t["proof_size_bytes"] for t in zk_tests if "proof_size_bytes" in t]
    gas_vals = [op["gas_used"] for op in ops if not op.get("reverted")]
    calldata_vals = [op["calldata_bytes"] for op in ops if not op.get("reverted")]
    l2_gas_vals = [op["gas_used"] for op in l2_ops if not op.get("reverted")]
    l2_calldata_vals = [op["calldata_bytes"] for op in l2_ops if not op.get("reverted")]

    report = {
        "meta": {
            "timestamp": cfg.timestamp,
            "pipeline_duration_s": pipeline_duration,
            "bpmn_file": cfg.bpmn_file.name,
            "zokrates_version": hw.zokrates_version,
            "metric_definitions": {
                "zk_tests.proof_size_bytes": PROOF_SIZE_MEASUREMENT,
                "aggregates.zk_proof_sizes_bytes": (
                    "Aggregate statistics over zk_tests.proof_size_bytes."
                ),
            },
            "hardware": {
                "cpu": hw.cpu, "ram_gb": hw.ram_gb,
                "os": hw.os_info, "arch": hw.arch,
            },
            "tooling": {
                "node_version": hw.node_version,
                "hardhat_version": ver("hardhat"),
                "ethers_version": ver("ethers"),
                "hardhat_zksync_deploy_version": ver("@matterlabs/hardhat-zksync-deploy"),
                "hardhat_zksync_solc_version": ver("@matterlabs/hardhat-zksync-solc"),
            },
            "compiler_l1": {
                "solc_version": "0.8.0",
                "optimizer_enabled": True,
                "optimizer_runs": 200,
                "viaIR": False,
            },
            "compiler_l2": {
                "zksolc_version": "1.5.0",
                "optimizer_enabled": True,
                "optimizer_mode": "3",
            },
        },
        "l1": {
            "network": deploy_data.get("network", "hardhat"),
            "chain_id": deploy_data.get("chain_id", 31337),
            "deployment": {
                "contracts": dep.get("contracts", []),
                "contract_count": dep.get("contract_count", 1),
                "tx_count": dep.get("tx_count", 1),
                "contract_address": dep.get("contract_address", ""),
                "gas_used": dep.get("gas_used", 0),
                "effective_gas_price_wei": dep.get("effective_gas_price_wei", "0"),
                "fee_paid_wei": dep.get("fee_paid_wei", "0"),
                "block_number": dep.get("block_number", 0),
                "block_timestamp": dep.get("block_timestamp", 0),
                "deploy_time_s": dep.get("deploy_time_s", 0),
            },
            "execution": {
                "skipped": exec_data.get("skipped", False),
                "operations": ops,
            },
            "bytecode": {
                "evm_bytes": int(metrics.evm_bytecode_bytes or "0"),
                "zkvm_bytes": int(metrics.zk_bytecode_bytes or "0"),
            },
        },
        "l2_zksync": {
            "network": zksync_deploy_data.get("network", "anvilZkSync"),
            "chain_id": zksync_deploy_data.get("chain_id", 0),
            "measured": bool(l2_dep),
            "deployment": {
                "contracts": l2_dep.get("contracts", []),
                "contract_count": l2_dep.get("contract_count", 0),
                "tx_count": l2_dep.get("tx_count", 0),
                "contract_address": l2_dep.get("contract_address", ""),
                "gas_used": l2_dep.get("gas_used", 0),
                "effective_gas_price_wei": l2_dep.get("effective_gas_price_wei", "0"),
                "fee_paid_wei": l2_dep.get("fee_paid_wei", "0"),
                "block_number": l2_dep.get("block_number", 0),
                "block_timestamp": l2_dep.get("block_timestamp", 0),
                "deploy_time_s": l2_dep.get("deploy_time_s", 0),
            },
            "execution": {
                "skipped": zksync_exec_data.get("skipped", False),
                "operations": l2_ops,
            },
            "bytecode": {
                "zkvm_bytes": int(metrics.zk_bytecode_bytes or "0"),
            },
        },
        "zk_circuit": {
            "compile_time_s": float(metrics.compile_time or "0"),
            "setup_time_s": float(metrics.setup_time or "0"),
            "test_count": len(zk_tests) if zk_tests else int(metrics.test_count or "0"),
            "skip_tests": cfg.skip_tests,
            "artifact_sizes_bytes": metrics.circuit_artifact_sizes or {},
        },
        "zk_tests": zk_tests,
        "aggregates": {
            "zk_witness_times_s": compute_stats(witness_times),
            "zk_proof_times_s": compute_stats(proof_times),
            "zk_total_times_s": compute_stats(total_times),
            "zk_proof_sizes_bytes": compute_stats(proof_sizes),
            "l1_execution_gas": compute_stats(gas_vals),
            "l1_execution_calldata_bytes": compute_stats(calldata_vals),
            "l2_execution_gas": compute_stats(l2_gas_vals),
            "l2_execution_calldata_bytes": compute_stats(l2_calldata_vals),
        },
    }

    # Add mainnet gas prices and cost estimates
    mainnet_costs = {"l1_gas_price_gwei": l1_gas_price_gwei, "l2_gas_price_gwei": l2_gas_price_gwei}
    if l1_gas_price_gwei is not None:
        l1_deploy_gas = dep.get("gas_used", 0)
        if l1_deploy_gas:
            mainnet_costs["l1_deploy_fee_eth"] = l1_deploy_gas * l1_gas_price_gwei / 1e9
        if gas_vals:
            avg_l1_gas = sum(gas_vals) / len(gas_vals)
            mainnet_costs["l1_avg_exec_fee_eth"] = avg_l1_gas * l1_gas_price_gwei / 1e9

    # L2 fees: prefer zks_estimateFee results, fall back to gas_used × gasPrice
    zk_est_deploy = {}
    if zk_deploy_est:
        zk_est_deploy = {
            "gas_limit": zk_deploy_est.gas_limit,
            "max_fee_per_gas_wei": zk_deploy_est.max_fee_per_gas,
            "gas_per_pubdata_limit": zk_deploy_est.gas_per_pubdata_limit,
            "estimated_fee_eth": zk_deploy_est.estimated_fee_eth,
        }
        mainnet_costs["l2_deploy_fee_eth"] = zk_deploy_est.estimated_fee_eth
        mainnet_costs["l2_deploy_fee_source"] = "zks_estimateFee"
    elif l2_gas_price_gwei is not None:
        l2_deploy_gas = l2_dep.get("gas_used", 0)
        if l2_deploy_gas:
            mainnet_costs["l2_deploy_fee_eth"] = l2_deploy_gas * l2_gas_price_gwei / 1e9
            mainnet_costs["l2_deploy_fee_source"] = "gas_used × mainnet gasPrice (fallback)"

    zk_est_exec = {}
    if zk_exec_est:
        zk_est_exec = {
            "gas_limit": zk_exec_est.gas_limit,
            "max_fee_per_gas_wei": zk_exec_est.max_fee_per_gas,
            "gas_per_pubdata_limit": zk_exec_est.gas_per_pubdata_limit,
            "estimated_fee_eth": zk_exec_est.estimated_fee_eth,
        }
        mainnet_costs["l2_avg_exec_fee_eth"] = zk_exec_est.estimated_fee_eth
        mainnet_costs["l2_avg_exec_fee_source"] = "zks_estimateFee"
    elif l2_gas_price_gwei is not None and l2_gas_vals:
        avg_l2_gas = sum(l2_gas_vals) / len(l2_gas_vals)
        mainnet_costs["l2_avg_exec_fee_eth"] = avg_l2_gas * l2_gas_price_gwei / 1e9
        mainnet_costs["l2_avg_exec_fee_source"] = "gas_used × mainnet gasPrice (fallback)"

    mainnet_costs["zks_estimateFee_deploy"] = zk_est_deploy or None
    mainnet_costs["zks_estimateFee_exec"] = zk_est_exec or None
    report["mainnet_cost_estimate"] = mainnet_costs

    with open(cfg.benchmark_file, "w") as f:
        json.dump(report, f, indent=2)


def _json_rpc_post(url: str, method: str, params: list = None,
                   timeout: int = 15) -> Optional[dict]:
    """Send a JSON-RPC request using urllib (no curl dependency)."""
    import urllib.request
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params or [],
        "id": 1,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "zkWF-pipeline/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _extract_gas_prices():
    """Fetch live gas prices from Ethereum mainnet and zkSync mainnet RPC."""
    l1_gas_price_gwei = None
    l2_gas_price_gwei = None

    # L1 gas price from Ethereum mainnet
    resp = _json_rpc_post("https://eth.llamarpc.com", "eth_gasPrice")
    if resp and "result" in resp:
        l1_gas_price_gwei = _hex_to_int(resp["result"])
        if l1_gas_price_gwei is not None:
            l1_gas_price_gwei = l1_gas_price_gwei / 1e9  # wei → gwei

    # L2 gas price from zkSync mainnet
    resp = _json_rpc_post("https://mainnet.era.zksync.io", "eth_gasPrice")
    if resp and "result" in resp:
        l2_gas_price_gwei = _hex_to_int(resp["result"])
        if l2_gas_price_gwei is not None:
            l2_gas_price_gwei = l2_gas_price_gwei / 1e9  # wei → gwei

    return l1_gas_price_gwei, l2_gas_price_gwei


def _hex_to_int(hex_str: str) -> Optional[int]:
    """Convert a hex string (0x...) to int, or None on failure."""
    if not hex_str:
        return None
    hex_str = hex_str.lstrip("0x") if hex_str.startswith("0x") else hex_str
    if not hex_str:
        return None
    return int(hex_str, 16)


@dataclass
class ZkSyncFeeEstimate:
    """Result from zks_estimateFee on zkSync mainnet."""
    gas_limit: int = 0
    max_fee_per_gas: int = 0           # wei
    gas_per_pubdata_limit: int = 0
    max_priority_fee_per_gas: int = 0  # wei
    estimated_fee_wei: int = 0         # gas_limit * max_fee_per_gas

    @property
    def estimated_fee_eth(self) -> float:
        return self.estimated_fee_wei / 1e18


def _zksync_estimate_fee(tx_from: str, tx_to: Optional[str],
                         tx_data: str) -> Optional[ZkSyncFeeEstimate]:
    """Call zks_estimateFee on zkSync Era mainnet for a single transaction.

    Args:
        tx_from: sender address (any valid address works for estimation)
        tx_to:   destination address (None for contract creation)
        tx_data: hex-encoded calldata / deploy bytecode
    Returns:
        ZkSyncFeeEstimate or None if the RPC call fails.
    """
    tx_obj = {"from": tx_from, "data": tx_data}
    if tx_to:
        tx_obj["to"] = tx_to
    try:
        resp = _json_rpc_post(
            "https://mainnet.era.zksync.io", "zks_estimateFee",
            params=[tx_obj], timeout=20,
        )
        if not resp or "error" in resp:
            return None
        r = resp.get("result", {})
        gas_limit = _hex_to_int(r.get("gas_limit", "0x0")) or 0
        max_fee = _hex_to_int(r.get("max_fee_per_gas", "0x0")) or 0
        gas_per_pubdata = _hex_to_int(r.get("gas_per_pubdata_limit", "0x0")) or 0
        max_prio = _hex_to_int(r.get("max_priority_fee_per_gas", "0x0")) or 0
        return ZkSyncFeeEstimate(
            gas_limit=gas_limit,
            max_fee_per_gas=max_fee,
            gas_per_pubdata_limit=gas_per_pubdata,
            max_priority_fee_per_gas=max_prio,
            estimated_fee_wei=gas_limit * max_fee,
        )
    except Exception:
        return None


def _estimate_zksync_mainnet_fees(log: Logger, bench: BenchmarkState):
    """Use zks_estimateFee on zkSync Era mainnet to get real fee estimates.

    Estimates deployment fee using the captured deploy tx data, and
    execution fee using the calldata from the first successful stepModel test.

    Returns (deploy_estimate, exec_estimate) — each is ZkSyncFeeEstimate or None.
    """
    # Well-known funded address for estimation (doesn't need actual balance)
    ESTIMATOR_FROM = "0x0000000000000000000000000000000000000001"

    deploy_est = None
    exec_est = None

    # --- Deploy fee estimate ---
    l2_dep = (bench.zksync_deploy_json or {}).get("deployment", {})
    deploy_tx_data = l2_dep.get("deploy_tx_data")
    deploy_tx_to = l2_dep.get("deploy_tx_to")

    if deploy_tx_data:
        log.info("Calling zks_estimateFee for deployment on zkSync mainnet...")
        deploy_est = _zksync_estimate_fee(ESTIMATOR_FROM, deploy_tx_to, deploy_tx_data)
        if deploy_est:
            log.ok(f"Deploy estimate: gas_limit={deploy_est.gas_limit:,}, "
                   f"fee={deploy_est.estimated_fee_eth:.6f} ETH")
        else:
            log.warn("zks_estimateFee failed for deployment (mainnet may reject "
                     "simulated deploys)")
    else:
        log.warn("No deploy tx data captured — skipping zks_estimateFee for deploy")

    # --- Execution fee estimate (first successful stepModel) ---
    l2_ops = (bench.zksync_exec_json or {}).get("operations", [])
    first_ok = next(
        (op for op in l2_ops if not op.get("reverted") and op.get("calldata_hex")),
        None,
    )
    if first_ok:
        log.info("Calling zks_estimateFee for stepModel on zkSync mainnet...")
        # Use a dummy 'to' — the estimation will capture calldata/pubdata costs
        # even though execution will revert (contract not on mainnet).
        # Fall back to gas_used * gasPrice if this fails.
        exec_est = _zksync_estimate_fee(
            ESTIMATOR_FROM,
            first_ok.get("tx_to", ESTIMATOR_FROM),
            first_ok["calldata_hex"],
        )
        if exec_est:
            log.ok(f"Exec estimate: gas_limit={exec_est.gas_limit:,}, "
                   f"fee={exec_est.estimated_fee_eth:.6f} ETH")
        else:
            log.warn("zks_estimateFee failed for stepModel (contract not on mainnet) "
                     "— will use gas_used × mainnet gasPrice as fallback")
    else:
        log.warn("No execution calldata captured — skipping zks_estimateFee for exec")

    return deploy_est, exec_est


def _print_summary(log: Logger, cfg: PipelineConfig, metrics: Metrics,
                   bench: BenchmarkState, pipeline_duration: int,
                   l1_gas_price_gwei: Optional[float] = None,
                   l2_gas_price_gwei: Optional[float] = None,
                   zk_deploy_est: Optional['ZkSyncFeeEstimate'] = None,
                   zk_exec_est: Optional['ZkSyncFeeEstimate'] = None):
    """Print the human-readable pipeline summary."""
    log.blank()
    log.bold("\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
             "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
             "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
             "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
             "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510")
    log.bold("\u2502                   Pipeline Summary"
             "                      \u2502")
    log.bold("\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
             "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
             "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
             "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
             "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518")

    def row(label, value):
        log._write(f"  {label:<28s} {value}")

    row("BPMN model:", cfg.bpmn_file.name)
    row("Completed at:", time.strftime("%c"))
    row("Total pipeline time:", f"{pipeline_duration}s")
    log.blank()

    # --- Gas Price Info (from mainnet RPCs) ---
    log.bold("  Gas Prices (from mainnet RPCs)")
    if l1_gas_price_gwei is not None:
        row("L1 gas price:", f"{l1_gas_price_gwei:.4f} gwei")
    else:
        row("L1 gas price:", "(not fetched)")
    if l2_gas_price_gwei is not None:
        row("L2 (zkSync) gas price:", f"{l2_gas_price_gwei:.4f} gwei")
    else:
        row("L2 (zkSync) gas price:", "(not fetched)")
    log.blank()

    # --- Off-Chain Metrics ---
    log.bold("  Off-Chain Metrics")
    log.bold("  ZoKrates Circuit")
    row("Compile time:", f"{metrics.compile_time or '(not captured)'}s")
    row("Setup time:", f"{metrics.setup_time or '(not captured)'}s")
    # Circuit artifact sizes
    sizes = metrics.circuit_artifact_sizes
    if sizes:
        for key, label in CIRCUIT_SUMMARY_ARTIFACTS:
            if key in sizes:
                row(f"{label}:", _fmt_size(sizes[key]))
    log.blank()

    log.bold("  ZK Proof Tests")
    if cfg.skip_tests:
        row("Tests:", "skipped (--skip-tests)")
    else:
        row("Test cases run:", metrics.test_count or "(not captured)")
        row("Avg time (witness+proof):", f"{metrics.avg_proof_time or '(not captured)'}s")
        # Proof size from per-test data
        zk_tests = bench.zk_tests_json or []
        proof_sizes = [t["proof_size_bytes"] for t in zk_tests if "proof_size_bytes" in t]
        if proof_sizes:
            avg_proof_size = sum(proof_sizes) / len(proof_sizes)
            row("Avg proof size (JSON):", f"{avg_proof_size:,.0f} bytes")
            row("Proof size measures:", PROOF_SIZE_MEASUREMENT)
    log.blank()

    # --- On-Chain Metrics ---
    log.bold("  On-Chain Metrics")

    log.bold("  Ethereum L1 (Hardhat)")
    row("Gas used (deploy):", metrics.l1_gas or "(not captured)")
    row("Contract address:", metrics.l1_addr or "(not captured)")
    row("Deploy time:", f"{metrics.l1_deploy_time or '(not captured)'}s")
    # L1 deploy fee (gas_used × mainnet gas price)
    l1_dep = (bench.deploy_json or {}).get("deployment", {})
    if l1_gas_price_gwei is not None:
        try:
            l1_deploy_gas = int(l1_dep.get("gas_used", 0))
            if l1_deploy_gas > 0:
                l1_deploy_fee_eth = l1_deploy_gas * l1_gas_price_gwei / 1e9
                row("Deploy fee (mainnet):", f"{l1_deploy_fee_eth:.6f} ETH")
        except (ValueError, TypeError):
            pass
    # L1 execution stats
    l1_ops = (bench.exec_json or {}).get("operations", [])
    l1_valid_ops = [op for op in l1_ops if not op.get("reverted")]
    if l1_valid_ops:
        avg_exec_gas = sum(op["gas_used"] for op in l1_valid_ops) / len(l1_valid_ops)
        row("Avg execution gas:", f"{avg_exec_gas:,.0f}")
        # Fee estimate using mainnet gas price
        if l1_gas_price_gwei is not None:
            avg_fee_eth = avg_exec_gas * l1_gas_price_gwei / 1e9
            row("Avg exec fee (mainnet):", f"{avg_fee_eth:.6f} ETH")
        row("Calldata per tx:", f"{l1_valid_ops[0].get('calldata_bytes', 0)} bytes")
    log.blank()

    log.bold("  zkSync L2 (anvil-zksync)")
    if bench.l2_benchmark_ok and metrics.l2_gas:
        row("Gas used (deploy):", metrics.l2_gas)
        row("Contract address:", metrics.l2_addr or "(not captured)")
        row("Deploy time:", f"{metrics.l2_deploy_time or '(not captured)'}s")

        # L2 deploy fee — prefer zks_estimateFee, fall back to gas_used × gasPrice
        l2_dep = (bench.zksync_deploy_json or {}).get("deployment", {})
        if zk_deploy_est:
            row("Deploy fee (estimateFee):", f"{zk_deploy_est.estimated_fee_eth:.6f} ETH")
            row("  gas_limit:", f"{zk_deploy_est.gas_limit:,}")
            row("  max_fee_per_gas:", f"{zk_deploy_est.max_fee_per_gas / 1e9:.4f} gwei")
        elif l2_gas_price_gwei is not None:
            try:
                l2_deploy_gas = int(l2_dep.get("gas_used", 0))
                if l2_deploy_gas > 0:
                    l2_deploy_fee_eth = l2_deploy_gas * l2_gas_price_gwei / 1e9
                    row("Deploy fee (fallback):", f"{l2_deploy_fee_eth:.6f} ETH")
            except (ValueError, TypeError):
                pass

        # L2 execution stats
        l2_ops = (bench.zksync_exec_json or {}).get("operations", [])
        l2_valid_ops = [op for op in l2_ops if not op.get("reverted")]
        if l2_valid_ops:
            avg_l2_exec_gas = sum(op["gas_used"] for op in l2_valid_ops) / len(l2_valid_ops)
            row("Avg execution gas:", f"{avg_l2_exec_gas:,.0f}")
            # Prefer zks_estimateFee, fall back to gas_used × gasPrice
            if zk_exec_est:
                row("Avg exec fee (estimateFee):", f"{zk_exec_est.estimated_fee_eth:.6f} ETH")
                row("  gas_limit:", f"{zk_exec_est.gas_limit:,}")
                row("  max_fee_per_gas:", f"{zk_exec_est.max_fee_per_gas / 1e9:.4f} gwei")
            elif l2_gas_price_gwei is not None:
                avg_l2_fee_eth = avg_l2_exec_gas * l2_gas_price_gwei / 1e9
                row("Avg exec fee (fallback):", f"{avg_l2_fee_eth:.6f} ETH")
            row("Calldata per tx:", f"{l2_valid_ops[0].get('calldata_bytes', 0)} bytes")

        # Fee savings (deployment) — L1 mainnet vs L2 estimateFee/gasPrice
        l1_deploy_fee_eth = None
        if l1_gas_price_gwei is not None:
            try:
                l1_dep_data = (bench.deploy_json or {}).get("deployment", {})
                l1_dg = int(l1_dep_data.get("gas_used", 0))
                if l1_dg > 0:
                    l1_deploy_fee_eth = l1_dg * l1_gas_price_gwei / 1e9
            except (ValueError, TypeError):
                pass
        l2_deploy_fee_eth = None
        if zk_deploy_est:
            l2_deploy_fee_eth = zk_deploy_est.estimated_fee_eth
        elif l2_gas_price_gwei is not None:
            try:
                l2_dg = int(l2_dep.get("gas_used", 0))
                if l2_dg > 0:
                    l2_deploy_fee_eth = l2_dg * l2_gas_price_gwei / 1e9
            except (ValueError, TypeError):
                pass
        if l1_deploy_fee_eth and l2_deploy_fee_eth and l1_deploy_fee_eth > 0:
            fee_savings = (1 - l2_deploy_fee_eth / l1_deploy_fee_eth) * 100
            row("Deploy fee savings:", f"{fee_savings:.1f}%")
    else:
        row("Status:", "skipped (anvil-zksync not available)")
    log.blank()

    log.bold("  Bytecode Sizes")
    row("EVM (solc):", f"{metrics.evm_bytecode_bytes or '(not captured)'} bytes")
    row("zkVM (zksolc):", f"{metrics.zk_bytecode_bytes or '(not captured)'} bytes")
    log.blank()

    log.info(f"Full log saved to:     {cfg.log_file}")
    if cfg.benchmark_file.is_file():
        log.info(f"Benchmark JSON saved: {cfg.benchmark_file}")
    log.blank()
    log.bold("Pipeline completed successfully.")


# =============================================================================
# Temp file cleanup
# =============================================================================

def cleanup_temp_files(bench: BenchmarkState):
    """Remove all temporary files created during the pipeline."""
    for path in (bench.deploy_tmp, bench.exec_tmp, bench.zksync_deploy_tmp,
                 bench.zksync_exec_tmp, bench.zk_tests_tmp):
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


# =============================================================================
# Main entry point
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="zkWF End-to-End Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--skip-tests", action="store_true",
                        help="Skip ZK witness/proof test cases (compile+setup only)")
    parser.add_argument("--skip-setup", action="store_true",
                        help="Skip compile+setup (reuse existing proving.key)")
    parser.add_argument("bpmn_file", nargs="?", default="bpmn/supply_chain.bpmn",
                        help="Path to the BPMN file (default: bpmn/supply_chain.bpmn)")
    parser.add_argument("test_cases_file", nargs="?",
                        default="bpmn/supply_chain_testCases.json",
                        help="Path to the test cases JSON (default: bpmn/supply_chain_testCases.json)")
    return parser.parse_args()


def main():
    args = parse_args()
    project_root = Path(__file__).resolve().parent
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    # Resolve paths
    bpmn = Path(args.bpmn_file)
    if not bpmn.is_absolute():
        bpmn = project_root / bpmn
    test_cases = Path(args.test_cases_file)
    if not test_cases.is_absolute():
        test_cases = project_root / test_cases

    cfg = PipelineConfig(
        project_root=project_root,
        bpmn_file=bpmn,
        test_cases_file=test_cases,
        skip_tests=args.skip_tests,
        skip_setup=args.skip_setup,
        timestamp=timestamp,
    )

    log = Logger(cfg.log_file)
    metrics = Metrics()
    bench = BenchmarkState()
    hw = HardwareInfo()
    pipeline_start = int(time.time())

    # Banner
    log.blank()
    log.bold("\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"
             "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"
             "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"
             "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"
             "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"
             "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557")
    log.bold("\u2551              zkWF End-to-End Pipeline"
             "                       \u2551")
    log.bold("\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"
             "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"
             "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"
             "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"
             "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"
             "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d")
    log.blank()
    log.info(f"BPMN file  : {cfg.bpmn_file}")
    log.info(f"Test cases : {cfg.test_cases_file}")
    log.info(f"Log file   : {cfg.log_file}")
    log.info(f"Started at : {time.strftime('%c')}")
    if cfg.skip_tests:
        log.info("Mode       : compile+setup only (--skip-tests)")

    try:
        phase_prerequisites(log, cfg, hw)
        phase_build_cli(log, cfg)
        phase_zokrates(log, cfg, metrics, bench)
        phase_export_verifier(log, cfg)
        phase_compile_contracts(log, cfg, metrics)
        phase_deploy_hardhat(log, cfg, metrics, bench)
        phase_execution_benchmark(log, cfg, bench)
        phase_zksync_benchmarks(log, cfg, metrics, bench)

        pipeline_duration = int(time.time()) - pipeline_start
        phase_summary(log, cfg, metrics, bench, hw, pipeline_duration)
    finally:
        cleanup_temp_files(bench)
        log.close()


if __name__ == "__main__":
    main()

/**
 * Gas Comparison Report — L1 (Hardhat) vs L2 (anvil-zksync)
 *
 * Reads measured benchmark data from:
 *   $BENCHMARK_DEPLOY_OUT          — L1 deployment metrics
 *   $BENCHMARK_EXEC_OUT            — L1 execution metrics
 *   $BENCHMARK_ZKSYNC_DEPLOY_OUT   — L2 deployment metrics
 *   $BENCHMARK_ZKSYNC_EXEC_OUT     — L2 execution metrics
 *
 * Prints a human-readable comparison table. Fee deltas are comparable across
 * layers; raw gas units are shown only as measured values.
 *
 * Usage (pipeline):
 *   npx hardhat run scripts/estimate-gas.js
 */

const fs = require("fs");

function safeLoad(envVar) {
  const p = process.env[envVar];
  if (!p) return null;
  try {
    return JSON.parse(fs.readFileSync(p, "utf8"));
  } catch {
    return null;
  }
}

function pct(a, b) {
  if (!a || !b) return "N/A";
  return ((1 - b / a) * 100).toFixed(1) + "%";
}

function padR(s, n) {
  return String(s).padEnd(n);
}
function padL(s, n) {
  return String(s).padStart(n);
}

function fmtGas(n) {
  if (n == null) return "N/A";
  return Number(n).toLocaleString();
}

function fmtFee(wei) {
  if (wei == null || wei === "0" || wei === 0) return "N/A";
  const eth = Number(BigInt(wei)) / 1e18;
  if (eth < 0.000001) return (eth * 1e9).toFixed(4) + " Gwei";
  return eth.toFixed(6) + " ETH";
}

function fmtWei(wei) {
  if (wei == null || wei === "0" || wei === 0) return "N/A";
  return Number(BigInt(wei)).toLocaleString();
}

function pctBigInt(a, b) {
  if (!a || !b || a === "0" || b === "0") return "N/A";
  const ratio = Number(BigInt(b)) / Number(BigInt(a));
  return ((1 - ratio) * 100).toFixed(1) + "%";
}

async function main() {
  const l1Deploy = safeLoad("BENCHMARK_DEPLOY_OUT");
  const l1Exec = safeLoad("BENCHMARK_EXEC_OUT");
  const l2Deploy = safeLoad("BENCHMARK_ZKSYNC_DEPLOY_OUT");
  const l2Exec = safeLoad("BENCHMARK_ZKSYNC_EXEC_OUT");

  const SEP = "=".repeat(64);
  const DASH = "-".repeat(64);

  console.log(SEP);
  console.log("  L1 vs L2 Cost Report (Measured)");
  console.log(SEP);

  // ── Deployment comparison ──────────────────────────────────────
  console.log("\n  Deployment Metrics");
  console.log(DASH);

  const l1Gas = l1Deploy?.deployment?.gas_used;
  const l2Gas = l2Deploy?.deployment?.gas_used;
  const l1Fee = l1Deploy?.deployment?.fee_paid_wei;
  const l2Fee = l2Deploy?.deployment?.fee_paid_wei;
  const l1Time = l1Deploy?.deployment?.deploy_time_s;
  const l2Time = l2Deploy?.deployment?.deploy_time_s;

  console.log(
    `  ${padR("", 24)} ${padL("L1 (Hardhat)", 16)} ${padL("L2 (anvil-zksync)", 20)} ${padL("Fee Savings", 12)}`
  );
  console.log(
    `  ${padR("Gas used (raw units)", 24)} ${padL(fmtGas(l1Gas), 16)} ${padL(fmtGas(l2Gas), 20)} ${padL("N/A", 12)}`
  );
  console.log(
    `  ${padR("Fee (wei)", 24)} ${padL(fmtWei(l1Fee), 16)} ${padL(fmtWei(l2Fee), 20)} ${padL(pctBigInt(l1Fee, l2Fee), 12)}`
  );
  console.log(
    `  ${padR("Fee (ETH)", 24)} ${padL(fmtFee(l1Fee), 16)} ${padL(fmtFee(l2Fee), 20)}`
  );
  console.log(
    `  ${padR("Deploy time (s)", 24)} ${padL(l1Time ?? "N/A", 16)} ${padL(l2Time ?? "N/A", 20)}`
  );

  // ── Execution comparison ───────────────────────────────────────
  const l1Ops = l1Exec?.operations || [];
  const l2Ops = l2Exec?.operations || [];

  if (l1Ops.length > 0 || l2Ops.length > 0) {
    console.log("\n  Execution Metrics (stepModel per test case)");
    console.log(DASH);
    console.log(
      `  ${padR("Test", 8)} ${padL("L1 gas", 14)} ${padL("L2 gas", 14)} ${padL("L1 fee (wei)", 22)} ${padL("L2 fee (wei)", 22)} ${padL("Fee Δ", 10)}`
    );

    // Build lookup by test_id
    const l2ByTest = {};
    for (const op of l2Ops) l2ByTest[op.test_id] = op;

    const allTestIds = [
      ...new Set([
        ...l1Ops.map((o) => o.test_id),
        ...l2Ops.map((o) => o.test_id),
      ]),
    ].sort((a, b) => a - b);

    let totalL1Gas = 0,
      totalL2Gas = 0,
      totalL1Fee = 0n,
      totalL2Fee = 0n,
      matchCount = 0;

    for (const tid of allTestIds) {
      const l1Op = l1Ops.find((o) => o.test_id === tid);
      const l2Op = l2ByTest[tid];

      const l1g = l1Op && !l1Op.reverted ? l1Op.gas_used : null;
      const l2g = l2Op && !l2Op.reverted ? l2Op.gas_used : null;
      const l1f = l1Op && !l1Op.reverted ? l1Op.fee_paid_wei : null;
      const l2f = l2Op && !l2Op.reverted ? l2Op.fee_paid_wei : null;

      if (l1g && l2g) {
        totalL1Gas += l1g;
        totalL2Gas += l2g;
        totalL1Fee += BigInt(l1f || 0);
        totalL2Fee += BigInt(l2f || 0);
        matchCount++;
      }

      const status =
        (l1Op?.reverted ? " (L1 rev)" : "") +
        (l2Op?.reverted ? " (L2 rev)" : "");

      console.log(
        `  ${padR(tid, 8)} ${padL(fmtGas(l1g), 14)} ${padL(fmtGas(l2g), 14)} ${padL(fmtWei(l1f), 22)} ${padL(fmtWei(l2f), 22)} ${padL(pctBigInt(l1f, l2f), 10)}${status}`
      );
    }

    if (matchCount > 0) {
      console.log(DASH);
      const avgL1 = Math.round(totalL1Gas / matchCount);
      const avgL2 = Math.round(totalL2Gas / matchCount);
      const avgL1Fee = (totalL1Fee / BigInt(matchCount)).toString();
      const avgL2Fee = (totalL2Fee / BigInt(matchCount)).toString();
      console.log(
        `  ${padR("Average", 8)} ${padL(fmtGas(avgL1), 14)} ${padL(fmtGas(avgL2), 14)} ${padL(fmtWei(avgL1Fee), 22)} ${padL(fmtWei(avgL2Fee), 22)} ${padL(pctBigInt(avgL1Fee, avgL2Fee), 10)}`
      );
      console.log(
        `  ${padR("Total", 8)} ${padL(fmtGas(totalL1Gas), 14)} ${padL(fmtGas(totalL2Gas), 14)} ${padL(fmtWei(totalL1Fee.toString()), 22)} ${padL(fmtWei(totalL2Fee.toString()), 22)} ${padL(pctBigInt(totalL1Fee.toString(), totalL2Fee.toString()), 10)}`
      );
    }
  }

  // ── Summary ────────────────────────────────────────────────────
  console.log("\n" + SEP);
  console.log("  Notes");
  console.log(SEP);
  if (l2Deploy) {
    console.log("  - L2 gas values are real measurements from anvil-zksync");
  } else {
    console.log("  - L2 deployment data not available (anvil-zksync may not have run)");
  }
  if (l2Exec && l2Ops.length > 0) {
    console.log("  - L2 execution gas is measured per-transaction on local zkSync node");
  }
  console.log("  - Raw gas units are shown for reference only and are not comparable across L1/L2");
  console.log("  - Fee Δ is the meaningful cross-layer comparison in this report");
  console.log("");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });

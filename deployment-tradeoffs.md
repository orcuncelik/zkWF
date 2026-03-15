# zkWF Deployment Tradeoffs: L1 vs zkSync Era

This document analyzes the cost tradeoffs between deploying zkWF on Ethereum L1 versus zkSync Era, with particular focus on ZK proof verification costs.

---

## Summary

| Factor | Ethereum L1 | zkSync Era | Winner |
|--------|-------------|------------|--------|
| Deployment cost | High (~$147) | Low (~$0.12) | zkSync |
| Verification cost (per step) | Lower | 2-3x higher | L1 |
| Best for short workflows | - | ✅ | zkSync |
| Best for long workflows | ✅ | - | L1 |

---

## The Apparent Contradiction

### What the Documentation Claims

From `ZKSYNC.md`:

| Metric | Ethereum Mainnet | zkSync Era | Savings |
|--------|------------------|------------|---------|
| Deployment Gas | 1,962,382 | ~196,238 | 90% |
| Deployment Cost | ~$147 | ~$0.12 | **99.9%** |

### What Actually Happens with ZK Verification

zkSync Era's BN254 precompiles (ecAdd, ecMul, ecPairing) run as **system contracts**, not native precompiles. This makes pairing operations **2-3x more expensive** in L1 gas-equivalent terms.

| Operation | Ethereum L1 | zkSync Era |
|-----------|-------------|------------|
| ecAdd | 150 gas (precompile) | ~300-500 gas (system contract) |
| ecMul | 6,000 gas (precompile) | ~12,000-18,000 gas (system contract) |
| ecPairing | 45,000 + 34,000×pairs | 2-3x higher |

**Both statements are true** - they measure different operations:
- Deployment and simple operations are cheaper on zkSync
- Pairing-heavy ZK verification is more expensive on zkSync

---

## Why zkSync Verification is More Expensive

### Ethereum L1 Architecture

```
Contract calls ecPairing (0x08)
        ↓
Native precompile executes in ~1ms
        ↓
Result returned (cheap)
```

### zkSync Era Architecture

```
Contract calls ecPairing
        ↓
System contract (Solidity) executes
        ↓
zkSync must prove correctness inside its own ZK circuit
        ↓
Result returned (expensive)
```

zkSync must prove that the pairing operation was computed correctly inside its rollup proof, adding significant overhead.

---

## Cost Breakdown for zkWF

### One-Time vs Recurring Costs

| Cost Type | Frequency | L1 Cost | zkSync Cost |
|-----------|-----------|---------|-------------|
| Contract deployment | **Once** | ~$147 | ~$0.12 |
| `stepModel()` verification | **Per workflow step** | ~$5-15 | ~$10-45 (2-3x) |
| Calldata (proof storage) | **Per step** | Similar | Similar |

### Break-Even Analysis

Assuming:
- Deployment savings: $147 - $0.12 ≈ **$147**
- Extra verification cost per step: $25 - $10 = **$15**

```
Break-even point = $147 / $15 ≈ 10 workflow steps
```

**After ~10 workflow steps, Ethereum L1 becomes cheaper overall.**

---

## Scenario Comparisons

### Scenario 1: Many Short Workflows (zkSync Wins)

Deploy many workflow contracts, each with few steps.

```
Example: 10 workflow instances, 5 steps each

L1:     10 × $147 (deploy) + 50 × $10 (verify) = $1,970
zkSync: 10 × $0.12 (deploy) + 50 × $25 (verify) = $1,251

Winner: zkSync ✅ (saves $719)
```

### Scenario 2: Few Long Workflows (L1 Wins)

Deploy once, use extensively.

```
Example: 1 workflow instance, 200 steps

L1:     1 × $147 (deploy) + 200 × $10 (verify) = $2,147
zkSync: 1 × $0.12 (deploy) + 200 × $25 (verify) = $5,000

Winner: Ethereum L1 ✅ (saves $2,853)
```

### Decision Matrix

| Workflow Pattern | Expected Steps | Recommendation |
|------------------|----------------|----------------|
| Many short processes | < 10 per contract | zkSync Era |
| Few long processes | > 10 per contract | Ethereum L1 |
| Mixed / Unknown | Variable | Measure first |

---

## Reducing Verification Costs

### The Root Problem

Groth16 (used by ZoKrates) requires **pairing operations**:

```
Groth16 verification = 3 pairings + multi-scalar multiplication
                     = Expensive on zkSync
```

### Alternative Proving Systems

| Scheme | Commitment | Pairings Required? | Proof Size | zkSync Fit |
|--------|------------|-------------------|------------|------------|
| **Groth16** | - | Yes (3) | ~200 bytes | Poor |
| PLONK + KZG | KZG | Yes (2) | ~400 bytes | Still poor |
| **PLONK + IPA** | IPA | **No** | ~1-2 KB | Better |
| **PLONK + FRI** | FRI | **No** | ~10-50 KB | Better |
| **STARKs** | FRI | **No** | ~50-200 KB | Best compute |

**Key insight:** KZG-based PLONK won't help - it still uses pairings. You need a **pairing-free** scheme.

### Option 1: Noir + UltraPLONK

Noir is a modern ZK DSL with multiple backend support:

```bash
# Install
curl -L https://raw.githubusercontent.com/noir-lang/noirup/main/install | bash
noirup

# Verification uses fewer/no pairings depending on backend
```

**Pros:** Active development, good tooling, zkSync-aware
**Cons:** Requires rewriting circuits from ZoKrates

### Option 2: STARK-based Systems (Risc0, SP1)

Write verification logic in Rust, no circuits needed:

```rust
// Risc0 example - verification uses only hash operations
fn verify_workflow_step(current_hash: [u8; 32], next_hash: [u8; 32]) -> bool {
    // Plain Rust logic, proven in zkVM
}
```

**Pros:** No pairings, developer-friendly (plain Rust)
**Cons:** Larger proofs (more calldata cost)

### Option 3: Proof Aggregation

Batch multiple workflow steps into one proof:

```
Without aggregation:
  10 steps → 10 proofs → 10 verifications → 10 × pairing cost

With aggregation:
  10 steps → 10 proofs → 1 aggregated proof → 1 verification
```

Tools: SnarkPack, Nebra UPA, custom recursion

**Pros:** Works with existing Groth16 setup
**Cons:** Added complexity, latency for batching

### Tradeoff Summary

| Approach | Verification Cost | Calldata Cost | Implementation Effort |
|----------|------------------|---------------|----------------------|
| Groth16 (current) | High | Low | None |
| FRI/STARK | Low | High | High (rewrite) |
| Aggregation | Low (amortized) | Low | Medium |

---

## Recommendations

### Short-Term

1. **Deploy on ERA Sepolia testnet** with current Groth16 setup
2. **Measure actual costs** for the three main operations:
   - Contract deployment
   - Single `stepModel()` call with real proof
   - Calldata costs
3. **Document findings** with real numbers

### Medium-Term

Consider **proof aggregation** if:
- Workflows have many steps
- Batch latency is acceptable
- Want to keep existing ZoKrates setup

### Long-Term

Evaluate migration to **pairing-free proving systems**:

| System | Best For | Migration Effort |
|--------|----------|------------------|
| Noir | Circuit-based ZK, similar to ZoKrates | Medium |
| Risc0/SP1 | General computation, complex logic | High |
| Halo2 | Custom circuits, no trusted setup | High |

---

## Migration Effort & Cost Estimates

Based on the current zkWF codebase analysis:

### Current Codebase Scope

| Component | Size | Description |
|-----------|------|-------------|
| ZoKrates circuits | ~4 files | `root.zok`, `stateChange.zok`, `hash.zok`, signature verification |
| Java generator | ~672 LOC | BPMN → ZoKrates code generation |
| Solidity contracts | ~3 files | Verifier, Model, Migrations |
| Python crypto | ~5 files | EdDSA signing, hashing utilities |

### Circuit Complexity

The `root.zok` circuit includes:
- **SHA256 hashing** - state commitment
- **EdDSA signature verification** - BabyJubJub curve
- **State transition logic** - workflow validation
- **50 public keys** - participant verification

---

## Approach Comparison Matrix

| Approach | Dev Effort | Runtime Cost (zkSync) | Proof Size | Trusted Setup |
|----------|------------|----------------------|------------|---------------|
| **1. Groth16 (current)** | None | High (pairings) | ~200 B | Yes |
| **2. Proof Aggregation** | Medium | Low (amortized) | ~200 B | Yes |
| **3. Noir Migration** | Medium-High | Medium | ~1-2 KB | No (UltraPlonk) |
| **4. STARK Migration** | Very High | Low | ~50-200 KB | No |

---

## Approach 1: Stay on Groth16 (Baseline)

**Effort: None**

| Item | Cost | Notes |
|------|------|-------|
| Development | $0 | No changes needed |
| Deployment (zkSync) | ~$0.12 | One-time |
| Per verification | ~$10-45 | 2-3x L1 cost |

**When to choose:** Short workflows (< 10 steps), quick deployment needed

---

## Approach 2: Proof Aggregation

**Effort: 2-4 weeks**

Batch multiple Groth16 proofs into one verification call using SnarkPack or Nebra UPA.

### Components to Build

| Component | Effort | Description |
|-----------|--------|-------------|
| Aggregator service | 1-2 weeks | Off-chain service to collect and batch proofs |
| Smart contract updates | 3-5 days | Batch verification logic |
| Client SDK updates | 3-5 days | Submit proofs to aggregator |
| Testing & integration | 1 week | End-to-end testing |

### Cost Estimate

| Item | Cost |
|------|------|
| Development (if outsourced) | $8,000 - $15,000 |
| Development (in-house) | 2-4 weeks engineer time |
| Deployment | ~$0.12 |
| Per verification (batched) | ~$2-5 (amortized over batch) |

### Tradeoffs

| Pros | Cons |
|------|------|
| Keeps existing ZoKrates circuits | Adds latency (wait for batch) |
| Minimal code changes | New infrastructure to maintain |
| Works with current tooling | Batch size optimization needed |

**When to choose:** Many workflow steps, can tolerate batching latency

---

## Approach 3: Noir Migration

**Effort: 6-10 weeks**

Rewrite ZoKrates circuits in Noir, which supports UltraPlonk (no pairings for verification).

### Components to Rewrite

| Component | Effort | Complexity |
|-----------|--------|------------|
| Core circuit (`root.zok` → `main.nr`) | 2-3 weeks | High - EdDSA + SHA256 + state logic |
| State transition logic | 1 week | Medium |
| Java generator updates | 2-3 weeks | Output Noir instead of ZoKrates |
| Solidity verifier | 1 week | Use Noir's generated verifier |
| Python crypto updates | 3-5 days | Noir-compatible serialization |
| Testing & debugging | 2 weeks | Circuit debugging is slow |

### Circuit Translation Example

**ZoKrates (current):**
```zokrates
import "signatures/verifyEddsa.zok" as verifyEddsa;
def main(public u32[8] h_s_curr, ...) -> u32[8] {
    bool isVerified = verifyEddsa(R, S, A, h_curr, result, context);
    assert(isVerified);
    return result;
}
```

**Noir (target):**
```rust
use dep::std::eddsa::eddsa_poseidon_verify;
fn main(h_s_curr: pub [u32; 8], ...) -> [u32; 8] {
    let is_verified = eddsa_poseidon_verify(pub_key, signature, message);
    assert(is_verified);
    result
}
```

### Cost Estimate

| Item | Cost |
|------|------|
| Development (if outsourced) | $25,000 - $45,000 |
| Development (in-house) | 6-10 weeks engineer time |
| Audit (recommended) | $10,000 - $30,000 |
| Deployment | ~$0.15-0.30 (larger verifier) |
| Per verification | ~$5-15 (no pairings) |

### Tradeoffs

| Pros | Cons |
|------|------|
| No pairing operations | Significant rewrite |
| Active ecosystem & tooling | Different constraint system |
| No trusted setup | Larger proof size (~5-10x) |
| Better zkSync compatibility | Learning curve for Noir |

### Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| EdDSA stdlib differences | Medium | Test thoroughly, may need custom impl |
| SHA256 constraint count | Low | Noir has optimized SHA256 |
| Generator complexity | Medium | Incremental migration |

**When to choose:** Long-term project, need zkSync optimization, have development resources

---

## Approach 4: STARK Migration (Risc0/SP1)

**Effort: 12-20 weeks**

Complete rewrite using a zkVM - write verification logic in Rust instead of circuits.

### Why This is a Major Change

STARKs use a fundamentally different proof system:
- **Field**: Different prime field (not BN254)
- **Signatures**: Need to reimplement EdDSA for STARK field
- **Hashing**: Poseidon preferred over SHA256 (10-100x faster in STARK)
- **Architecture**: zkVM vs circuit DSL

### Components to Rewrite

| Component | Effort | Notes |
|-----------|--------|-------|
| Core verification (Rust) | 3-4 weeks | Rewrite all logic in Rust |
| EdDSA implementation | 2-3 weeks | Custom impl for STARK field |
| Hash migration (SHA256→Poseidon) | 2 weeks | Or pay 100x cost for SHA256 |
| Java generator | 4-6 weeks | Output Rust instead of ZoKrates |
| Smart contract integration | 2 weeks | STARK verifier is different |
| Python crypto updates | 1-2 weeks | New signature scheme |
| Testing & debugging | 3-4 weeks | New tooling to learn |

### Cost Estimate

| Item | Cost |
|------|------|
| Development (if outsourced) | $60,000 - $120,000 |
| Development (in-house) | 12-20 weeks engineer time |
| Audit (strongly recommended) | $20,000 - $50,000 |
| Deployment | ~$0.50-2.00 (larger contract) |
| Per verification | ~$3-10 (hash-based) |
| Calldata per proof | ~$5-20 (50-200 KB proofs) |

### Tradeoffs

| Pros | Cons |
|------|------|
| No pairings at all | Complete rewrite required |
| Write Rust, not circuits | ~100x larger proofs |
| Post-quantum potential | Higher calldata costs |
| No trusted setup | Different crypto primitives |

**When to choose:** Greenfield project, post-quantum requirements, have significant resources

---

## Cost Summary Table

| Approach | Dev Cost | Time | Deploy Cost | Per-Step Cost | Best For |
|----------|----------|------|-------------|---------------|----------|
| **Groth16** | $0 | 0 | $0.12 | $10-45 | Quick deploy, short workflows |
| **Aggregation** | $8-15K | 2-4 wks | $0.12 | $2-5 | Many steps, batch OK |
| **Noir** | $25-45K | 6-10 wks | $0.15-0.30 | $5-15 | Long-term, zkSync focus |
| **STARK** | $60-120K | 12-20 wks | $0.50-2 | $3-10 + calldata | Greenfield, post-quantum |

---

## Recommendation Summary

```
                    ┌─────────────────────────────────────┐
                    │     What's your primary goal?       │
                    └─────────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
            ▼                       ▼                       ▼
    ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
    │ Ship quickly  │      │ Optimize for  │      │ Future-proof  │
    │ (< 10 steps)  │      │ many steps    │      │ (post-quantum)│
    └───────────────┘      └───────────────┘      └───────────────┘
            │                       │                       │
            ▼                       ▼                       ▼
    ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
    │   Groth16     │      │  Aggregation  │      │    STARK      │
    │   (current)   │      │   or Noir     │      │  (Risc0/SP1)  │
    └───────────────┘      └───────────────┘      └───────────────┘
```

**My recommendation:** Start with **Approach 2 (Proof Aggregation)** if you need zkSync optimization now. It provides the best ROI - keeps existing code, reduces per-step costs significantly, and can be implemented incrementally.

---

## Action Items

- [ ] Deploy to ERA Sepolia and measure real verification costs
- [ ] Compare measured costs with L1 Sepolia deployment
- [ ] Calculate break-even point with actual numbers
- [ ] Evaluate proof aggregation feasibility (SnarkPack vs Nebra UPA)
- [ ] Prototype Noir circuit for one simple workflow (if considering long-term migration)

---

## References

- [zkSync Era Documentation](https://docs.zksync.io)
- [EIP-196: Precompiled contracts for elliptic curve operations](https://eips.ethereum.org/EIPS/eip-196)
- [EIP-197: Precompiled contracts for pairing checks](https://eips.ethereum.org/EIPS/eip-197)
- [Noir Language](https://noir-lang.org/)
- [Risc0](https://www.risczero.com/)
- [ZoKrates Documentation](https://zokrates.github.io/)

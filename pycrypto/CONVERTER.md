# BPMN to zkWF Converter

A Python tool that converts standard BPMN 2.0 files into zkWF-compatible format by automatically adding zero-knowledge proof extensions.

## Overview

zkWF (Zero-Knowledge Workflow) requires BPMN files to include custom `zkp:` namespace attributes for cryptographic operations. This converter automates the process of:

1. Adding the `xmlns:zkp` namespace declaration
2. Generating EdDSA public keys for each participant
3. Validating BPMN structure for zkWF compatibility

## Requirements

- Python 3.8+
- Optional: `zokrates-pycrypto` for cryptographic key generation

```bash
# Optional: Install for unique key generation
pip install zokrates-pycrypto
```

Without `zokrates-pycrypto`, the converter uses predefined test keys (sufficient for development/testing).

## Installation

The converter is located at `pycrypto/bpmn_to_zkwf.py`. No installation required - run directly with Python.

```bash
cd pycrypto
python3 bpmn_to_zkwf.py --help
```

## Usage

### Basic Conversion

```bash
# Convert file (creates input_zkwf.bpmn)
python3 bpmn_to_zkwf.py ../diagram.bpmn

# Convert with custom output path
python3 bpmn_to_zkwf.py ../diagram.bpmn ../output.bpmn
```

### Validation Only

```bash
# Check if BPMN is zkWF-compatible without converting
python3 bpmn_to_zkwf.py --validate-only ../diagram.bpmn
```

### Skip Validation

```bash
# Convert without validation checks
python3 bpmn_to_zkwf.py --no-validate ../diagram.bpmn
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `--validate-only` | Only validate the BPMN file, don't convert |
| `--no-validate` | Skip validation and convert directly |

## What Gets Added

### 1. zkp Namespace

The converter adds the zkp namespace to the root `<definitions>` element:

```xml
<!-- Before -->
<bpmn2:definitions xmlns:bpmn2="http://www.omg.org/spec/BPMN/20100524/MODEL" ...>

<!-- After -->
<bpmn2:definitions xmlns:bpmn2="http://www.omg.org/spec/BPMN/20100524/MODEL"
                   xmlns:zkp="http://zkp.toldi.eu" ...>
```

### 2. Public Keys for Participants

Each `<participant>` element receives a unique EdDSA public key:

```xml
<!-- Before -->
<bpmn2:participant id="Participant_1" name="Client" processRef="Process_1" />

<!-- After -->
<bpmn2:participant id="Participant_1" name="Client" processRef="Process_1"
    zkp:publicKey="7350854827252829541674033642803854801334834402587808031858165572750984534676, 21854189621934227298279236061289964015847784208108325958639815905934377828601" />
```

### 3. Public Keys for Lanes (if present)

If your BPMN uses lanes within pools, each lane also receives a public key:

```xml
<bpmn2:lane id="Lane_1" name="Approver"
    zkp:publicKey="14897476871502190904409029696666322856887678969656209656241038339251270171395, 16668832459046858928951622951481252834155254151733002984053501254009901876174">
```

## Validation Checks

The converter validates your BPMN for zkWF compatibility:

### Errors (Must Fix)

| Check | Description |
|-------|-------------|
| No collaboration | zkWF requires a collaboration diagram with participants |
| No participants | At least one participant (pool) is required |
| Unsupported elements | Elements like subProcess, serviceTask, etc. are not supported |
| Invalid XML | File must be valid XML |

### Warnings (Should Fix)

| Check | Description |
|-------|-------------|
| Missing endEvent | Each process should have an end event |
| Dangling flows | Elements without incoming/outgoing connections |
| Missing startEvent | Each process should have a start event |
| Orphan message events | Intermediate events without outgoing flows |

### Info (Informational)

| Check | Description |
|-------|-------------|
| Participant count | Number of participants found |
| Process count | Number of processes found |
| Task count | Number of tasks per process |
| Existing keys | Whether zkp:publicKey already exists |

## Supported BPMN Elements

zkWF supports a subset of BPMN 2.0 elements:

### Supported

| Element | Description |
|---------|-------------|
| `startEvent` | Process start |
| `endEvent` | Process end |
| `task` | Generic task |
| `parallelGateway` | Parallel split/join |
| `exclusiveGateway` | XOR decision/merge |
| `sequenceFlow` | Flow between elements |
| `messageFlow` | Flow between participants |
| `intermediateCatchEvent` | Receive message |
| `intermediateThrowEvent` | Send message |
| `participant` | Pool |
| `lane` | Lane within pool |
| `collaboration` | Multi-participant diagram |
| `message` | Message definition |

### NOT Supported

| Element | Reason |
|---------|--------|
| `subProcess` | Nested processes not supported |
| `serviceTask`, `userTask`, etc. | Only generic `task` supported |
| `boundaryEvent` | Boundary events not supported |
| `timerEventDefinition` | Timer events not supported |
| `eventBasedGateway` | Only parallel/exclusive gateways |
| `dataObject`, `dataStore` | Data elements not supported |

## Example Output

### Validation Report

```
============================================================
Validating: ../diagram.bpmn
============================================================

⚠️  WARNINGS (should fix):
   • Process 'Process_1' has no endEvent - workflow may not terminate properly
   • IntermediateEvent 'Event_0hmwt4r' has no outgoing flow

ℹ️  INFO:
   • Found 1 collaboration(s)
   • Found 2 participant(s)
   • Participant 'Client' will get auto-generated publicKey
   • Participant 'Server' will get auto-generated publicKey
   • Found 2 process(es)
   • Process 'Process_1' has 3 task(s)

⚠️  BPMN is usable but has warnings
============================================================
```

### Successful Conversion

```
============================================================
Validating: ../diagram.bpmn
============================================================

ℹ️  INFO:
   • Found 1 collaboration(s)
   • Found 2 participant(s)
   • zkp namespace will be added

✅ BPMN structure is valid for zkWF
============================================================
Converted: ../diagram.bpmn -> ../diagram_zkwf.bpmn
  - Added zkp namespace
  - Added 2 participant public key(s)
```

## Public Key Format

Public keys are EdDSA keys on the BabyJubJub curve, represented as two field elements (x, y coordinates):

```
zkp:publicKey="X_COORDINATE, Y_COORDINATE"
```

Example:
```
zkp:publicKey="7350854827252829541674033642803854801334834402587808031858165572750984534676, 21854189621934227298279236061289964015847784208108325958639815905934377828601"
```

These keys are used for:
- Signing state transitions in the zero-knowledge proof
- Verifying participant authorization on-chain

## Workflow

```
┌─────────────────┐
│  Standard BPMN  │
│   (any tool)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Converter     │
│ bpmn_to_zkwf.py │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  zkWF-ready     │
│     BPMN        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  zkWF Generator │
│  (CLI or GUI)   │
└─────────────────┘
```

## Troubleshooting

### "No collaboration element found"

Your BPMN file doesn't have participants (pools). zkWF requires a collaboration diagram.

**Fix:** Add at least one participant/pool to your diagram in your BPMN editor.

### "Unsupported element found"

You're using BPMN elements that zkWF doesn't support.

**Fix:** Replace unsupported elements with supported alternatives:
- `serviceTask` → `task`
- `subProcess` → flatten into main process
- `eventBasedGateway` → `exclusiveGateway`

### "Process has no endEvent"

Workflows need proper termination points.

**Fix:** Add an `endEvent` after the last activity in each process.

### "IntermediateEvent has no outgoing flow"

Message events need to connect to subsequent activities.

**Fix:** Add a sequence flow from the intermediate event to the next activity or end event.

### Predefined test keys warning

```
Warning: zokrates-pycrypto not installed. Using predefined test keys.
```

This is fine for development/testing. For production, install `zokrates-pycrypto`:

```bash
pip install zokrates-pycrypto
```

## Integration with zkWF

After conversion, use the zkWF tools:

```bash
# Using CLI
cd generator
./gradlew cli:shadowjar
java -jar cli/build/libs/cli-1.0-SNAPSHOT-all.jar your_diagram_zkwf.bpmn test_cases.json

# Using GUI
./gradlew gui:shadowjar
java -jar gui/build/libs/WFGUI.jar
```

## See Also

- [zkWF README](../README.md) - Main project documentation
- [zkWF Editor](../editor/) - Visual BPMN editor with zkp properties panel
- [Leasing Payment Example](../models/leasing-payment/) - Complex multi-participant example

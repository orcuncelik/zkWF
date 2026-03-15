#!/usr/bin/env python3
"""
BPMN to zkWF Converter

Automatically adds zkp extensions to standard BPMN files:
- Adds xmlns:zkp namespace
- Generates unique EdDSA public keys for each participant
- Adds zkp:publicKey attributes
- Validates BPMN structure for zkWF compatibility

Usage:
    python bpmn_to_zkwf.py input.bpmn [output.bpmn]
    python bpmn_to_zkwf.py --validate-only input.bpmn

If output is not specified, creates input_zkwf.bpmn
"""

import sys
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional

try:
    from zokrates_pycrypto.eddsa import PrivateKey, PublicKey
    from zokrates_pycrypto.field import FQ
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("Warning: zokrates-pycrypto not installed. Using predefined test keys.")
    print("Install with: pip install zokrates-pycrypto")


# Predefined test keys (used if zokrates-pycrypto not available)
TEST_KEYS = [
    ("7350854827252829541674033642803854801334834402587808031858165572750984534676",
     "21854189621934227298279236061289964015847784208108325958639815905934377828601"),
    ("21715273850596312954904974472147290906491269550500570193604680361889132220377",
     "3161870534391964258194010589089177316887486533167236663570547206873941016760"),
    ("14897476871502190904409029696666322856887678969656209656241038339251270171395",
     "16668832459046858928951622951481252834155254151733002984053501254009901876174"),
    ("9042369582473258640608156702000501292772581947454267167560366333613005574515",
     "4249323117433249059780096680642725049854712516559612996154758631746161341441"),
    ("18610151028517609696489385127228923809234283712216547596137063984002264807980",
     "15706728402907829034895394391498523697498210869052613667799615424387676440728"),
    ("2859103679630024059498494767933824972678677917624041308920234488268354265938",
     "19847785579733549885819811528440650702764392175164332980466249872115156558645"),
    ("8718960941578218548606622536728536434189594824475126540690250819958498694116",
     "6150630056559750708017966060387808947003323111181810120700602902469852009722"),
    ("5631859175651476201659386188924615998255422851660033084387884034976949594983",
     "19845904236827347317737904564839975479623648674478734839379998803712733353376"),
]

# Base seeds for generating keys
KEY_SEEDS = [
    1997011358982923168928344992199991480689546837621580239342656433234255379027,
    1997011358982923168928344992199991480689546837621580239342656433234255379026,
    1997011358982923168928344992199991480689546837621580239342656433234255379025,
    1997011358982923168928344992199991480689546837621580239342656433234255379024,
    1997011358982923168928344992199991480689546837621580239342656433234255379023,
    1997011358982923168928344992199991480689546837621580239342656433234255379022,
    1997011358982923168928344992199991480689546837621580239342656433234255379021,
    1997011358982923168928344992199991480689546837621580239342656433234255379020,
]


def generate_public_key(index: int) -> tuple[str, str]:
    """Generate a public key for a participant."""
    if HAS_CRYPTO:
        seed = KEY_SEEDS[index % len(KEY_SEEDS)]
        # Add index offset to create unique keys
        seed = seed - index
        sk = PrivateKey(FQ(seed))
        pk = PublicKey.from_private(sk)
        return str(pk.p.x.n), str(pk.p.y.n)
    else:
        # Use predefined test keys
        return TEST_KEYS[index % len(TEST_KEYS)]


@dataclass
class ValidationResult:
    """Result of BPMN validation."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_info(self, msg: str):
        self.info.append(msg)

    def print_report(self):
        if self.errors:
            print("\n❌ ERRORS (must fix):")
            for e in self.errors:
                print(f"   • {e}")
        if self.warnings:
            print("\n⚠️  WARNINGS (should fix):")
            for w in self.warnings:
                print(f"   • {w}")
        if self.info:
            print("\nℹ️  INFO:")
            for i in self.info:
                print(f"   • {i}")
        if self.is_valid and not self.warnings:
            print("\n✅ BPMN structure is valid for zkWF")
        elif self.is_valid:
            print("\n⚠️  BPMN is usable but has warnings")
        else:
            print("\n❌ BPMN has errors that must be fixed")


# Supported BPMN elements in zkWF
SUPPORTED_ELEMENTS = {
    'startEvent', 'endEvent', 'task', 'sendTask', 'receiveTask', 'parallelGateway', 'exclusiveGateway',
    'sequenceFlow', 'messageFlow', 'intermediateCatchEvent', 'intermediateThrowEvent',
    'participant', 'collaboration', 'process', 'lane', 'laneSet', 'message',
    'messageEventDefinition', 'incoming', 'outgoing'
}

# Elements that are NOT supported
UNSUPPORTED_ELEMENTS = {
    'subProcess', 'callActivity', 'serviceTask', 'userTask', 'scriptTask',
    'businessRuleTask', 'manualTask',
    'boundaryEvent', 'timerEventDefinition', 'errorEventDefinition',
    'signalEventDefinition', 'conditionalEventDefinition', 'escalationEventDefinition',
    'compensateEventDefinition', 'linkEventDefinition', 'terminateEventDefinition',
    'dataObject', 'dataStore', 'dataInput', 'dataOutput',
    'eventBasedGateway', 'complexGateway', 'inclusiveGateway',
    'transaction', 'adHocSubProcess', 'choreography', 'conversation'
}


def validate_bpmn(input_path: str) -> ValidationResult:
    """
    Validate a BPMN file for zkWF compatibility.

    Checks:
    - Has collaboration element (required)
    - All participants have or will get public keys
    - No unsupported elements
    - Processes have proper start and end events
    - All flows are connected
    - Message events have corresponding message flows
    """
    result = ValidationResult()

    try:
        tree = ET.parse(input_path)
        root = tree.getroot()
    except ET.ParseError as e:
        result.add_error(f"Invalid XML: {e}")
        return result

    # Extract namespace
    ns = {}
    if root.tag.startswith('{'):
        default_ns = root.tag[1:root.tag.index('}')]
        ns['bpmn'] = default_ns
        ns['bpmn2'] = default_ns
    else:
        ns['bpmn'] = 'http://www.omg.org/spec/BPMN/20100524/MODEL'
        ns['bpmn2'] = 'http://www.omg.org/spec/BPMN/20100524/MODEL'

    # Check for collaboration
    collaborations = root.findall('.//{%s}collaboration' % ns['bpmn'])
    if not collaborations:
        result.add_error("No <collaboration> element found. zkWF requires a collaboration diagram with participants.")
        result.add_info("Tip: Add participants (pools) to your diagram")
    else:
        result.add_info(f"Found {len(collaborations)} collaboration(s)")

    # Check participants
    participants = root.findall('.//{%s}participant' % ns['bpmn'])
    if not participants:
        result.add_error("No participants found. zkWF requires at least one participant.")
    else:
        result.add_info(f"Found {len(participants)} participant(s)")
        for p in participants:
            name = p.get('name', p.get('id', 'unknown'))
            # Check if already has public key
            has_key = False
            for attr in p.attrib:
                if 'publicKey' in attr:
                    has_key = True
                    break
            if has_key:
                result.add_info(f"Participant '{name}' already has publicKey")
            else:
                result.add_info(f"Participant '{name}' will get auto-generated publicKey")

    # Check for unsupported elements
    for elem in root.iter():
        tag = elem.tag
        if '}' in tag:
            tag = tag.split('}')[1]
        if tag in UNSUPPORTED_ELEMENTS:
            result.add_error(f"Unsupported element <{tag}> found. zkWF does not support this element type.")

    # Check processes
    processes = root.findall('.//{%s}process' % ns['bpmn'])
    result.add_info(f"Found {len(processes)} process(es)")

    for process in processes:
        proc_id = process.get('id', 'unknown')

        # Find start events
        start_events = process.findall('.//{%s}startEvent' % ns['bpmn'])
        if not start_events:
            result.add_warning(f"Process '{proc_id}' has no startEvent")

        # Find end events
        end_events = process.findall('.//{%s}endEvent' % ns['bpmn'])
        if not end_events:
            result.add_warning(f"Process '{proc_id}' has no endEvent - workflow may not terminate properly")

        # Check tasks (including sendTask and receiveTask)
        tasks = process.findall('.//{%s}task' % ns['bpmn'])
        send_tasks = process.findall('.//{%s}sendTask' % ns['bpmn'])
        receive_tasks = process.findall('.//{%s}receiveTask' % ns['bpmn'])
        total_tasks = len(tasks) + len(send_tasks) + len(receive_tasks)
        result.add_info(f"Process '{proc_id}' has {total_tasks} task(s)")

        # Check for dangling elements (no incoming or outgoing)
        all_elements = {}
        incoming_flows: Dict[str, List[str]] = {}
        outgoing_flows: Dict[str, List[str]] = {}

        # Build flow map
        for seq_flow in process.findall('.//{%s}sequenceFlow' % ns['bpmn']):
            flow_id = seq_flow.get('id')
            source = seq_flow.get('sourceRef')
            target = seq_flow.get('targetRef')
            if source:
                outgoing_flows.setdefault(source, []).append(flow_id)
            if target:
                incoming_flows.setdefault(target, []).append(flow_id)

        # Check each element for connections
        for elem in process:
            tag = elem.tag
            if '}' in tag:
                tag = tag.split('}')[1]
            elem_id = elem.get('id')

            if tag in ['task', 'sendTask', 'receiveTask', 'parallelGateway', 'exclusiveGateway']:
                if elem_id not in incoming_flows:
                    result.add_warning(f"Element '{elem_id}' ({tag}) has no incoming flow")
                if elem_id not in outgoing_flows:
                    result.add_warning(f"Element '{elem_id}' ({tag}) has no outgoing flow")

            elif tag == 'startEvent':
                if elem_id not in outgoing_flows:
                    result.add_warning(f"StartEvent '{elem_id}' has no outgoing flow")

            elif tag == 'endEvent':
                if elem_id not in incoming_flows:
                    result.add_warning(f"EndEvent '{elem_id}' has no incoming flow")

            elif tag in ['intermediateCatchEvent', 'intermediateThrowEvent']:
                if elem_id not in incoming_flows:
                    result.add_warning(f"IntermediateEvent '{elem_id}' has no incoming flow")
                if elem_id not in outgoing_flows:
                    result.add_warning(f"IntermediateEvent '{elem_id}' has no outgoing flow - needs connection to continue workflow")

    # Check message flows
    message_flows = root.findall('.//{%s}messageFlow' % ns['bpmn'])
    throw_events = root.findall('.//{%s}intermediateThrowEvent' % ns['bpmn'])
    catch_events = root.findall('.//{%s}intermediateCatchEvent' % ns['bpmn'])

    if throw_events or catch_events:
        result.add_info(f"Found {len(throw_events)} throw event(s) and {len(catch_events)} catch event(s)")
        if not message_flows:
            result.add_warning("Message events exist but no messageFlow elements found")

    # Check zkp namespace
    zkp_ns = None
    for attr, value in root.attrib.items():
        if 'zkp' in attr.lower() or 'zkp.toldi.eu' in value:
            zkp_ns = True
            break

    if zkp_ns:
        result.add_info("zkp namespace already present")
    else:
        result.add_info("zkp namespace will be added")

    return result


def convert_bpmn_to_zkwf(input_path: str, output_path: str = None, validate: bool = True) -> str:
    """
    Convert a standard BPMN file to zkWF format.

    Args:
        input_path: Path to input BPMN file
        output_path: Path for output file (optional)
        validate: Whether to validate the BPMN structure

    Returns:
        Path to the output file
    """
    # Run validation first
    if validate:
        print(f"\n{'='*60}")
        print(f"Validating: {input_path}")
        print('='*60)
        result = validate_bpmn(input_path)
        result.print_report()
        print('='*60)

        if not result.is_valid:
            print("\n⛔ Conversion aborted due to errors.")
            print("Fix the errors above and try again.")
            return None

    if output_path is None:
        base = Path(input_path).stem
        output_path = str(Path(input_path).parent / f"{base}_zkwf.bpmn")

    # Read the file content
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if already has zkp namespace
    if 'xmlns:zkp=' in content:
        print(f"Warning: {input_path} already contains zkp namespace")

    # Check if using default namespace (unprefixed elements) - needs conversion to bpmn2: prefix
    uses_default_ns = 'xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"' in content
    if uses_default_ns:
        print("  - Converting default namespace to bpmn2: prefix")
        # Convert default namespace to bpmn2 prefix
        content = content.replace(
            'xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"',
            'xmlns:bpmn2="http://www.omg.org/spec/BPMN/20100524/MODEL"'
        )
        # List of BPMN elements that need prefixing
        bpmn_elements = [
            'definitions', 'collaboration', 'participant', 'messageFlow', 'message',
            'process', 'startEvent', 'endEvent', 'task', 'sendTask', 'receiveTask',
            'sequenceFlow', 'exclusiveGateway', 'parallelGateway', 'inclusiveGateway',
            'intermediateCatchEvent', 'intermediateThrowEvent', 'messageEventDefinition',
            'incoming', 'outgoing', 'lane', 'laneSet', 'flowNodeRef',
            'conditionExpression', 'extensionElements', 'documentation'
        ]
        for elem in bpmn_elements:
            # Replace opening tags (with attributes)
            content = re.sub(rf'<{elem}(\s|>|/>)', rf'<bpmn2:{elem}\1', content)
            # Replace closing tags
            content = re.sub(rf'</{elem}>', rf'</bpmn2:{elem}>', content)

    # Add zkp namespace to definitions tag if not present
    # Handles both prefixed (bpmn:, bpmn2:) and unprefixed (default namespace) definitions
    if 'xmlns:zkp=' not in content:
        # Find the definitions tag and add zkp namespace
        content = re.sub(
            r'(<(?:bpmn2?:)?definitions[^>]*)(>)',
            r'\1 xmlns:zkp="http://zkp.toldi.eu"\2',
            content,
            count=1
        )

    # Parse XML to find participants and lanes
    # We need to handle namespaces carefully

    # Register namespaces to preserve them
    namespaces = {
        'bpmn2': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
        'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
        'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
        'dc': 'http://www.omg.org/spec/DD/20100524/DC',
        'di': 'http://www.omg.org/spec/DD/20100524/DI',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'zkp': 'http://zkp.toldi.eu',
    }

    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)

    # Find all participants and add public keys using regex
    # This preserves the original formatting better than ET

    participant_index = 0

    def add_public_key(match):
        nonlocal participant_index
        tag = match.group(0)

        # Check if already has publicKey
        if 'zkp:publicKey=' in tag:
            participant_index += 1
            return tag

        # Generate key for this participant
        x, y = generate_public_key(participant_index)
        public_key = f"{x}, {y}"
        participant_index += 1

        # Add publicKey attribute before the closing
        if tag.endswith('/>'):
            return tag[:-2] + f' zkp:publicKey="{public_key}" />'
        else:
            return tag[:-1] + f' zkp:publicKey="{public_key}">'

    # Match participant tags (both self-closing and with content)
    # Handles both prefixed (bpmn:, bpmn2:) and unprefixed (default namespace) elements
    content = re.sub(
        r'<(?:bpmn2?:)?participant[^>]*(?:/>|>)',
        add_public_key,
        content
    )

    # Also handle lanes if present
    lane_index = 0

    def add_lane_public_key(match):
        nonlocal lane_index
        tag = match.group(0)

        if 'zkp:publicKey=' in tag:
            lane_index += 1
            return tag

        # Use different key range for lanes
        x, y = generate_public_key(lane_index + 100)
        public_key = f"{x}, {y}"
        lane_index += 1

        if tag.endswith('/>'):
            return tag[:-2] + f' zkp:publicKey="{public_key}" />'
        else:
            return tag[:-1] + f' zkp:publicKey="{public_key}">'

    # Handles both prefixed (bpmn:, bpmn2:) and unprefixed (default namespace) elements
    content = re.sub(
        r'<(?:bpmn2?:)?lane[^>]*(?:/>|>)',
        add_lane_public_key,
        content
    )

    # =========================================================================
    # Handle exclusive gateway conditions
    # =========================================================================
    # This section:
    # 1. Finds exclusive gateways with multiple outgoing flows (decision gateways)
    # 2. Finds the task that precedes each gateway
    # 3. Adds zkp:variables="u32 canHandle" to that task
    # 4. Converts sequence flow names to valid variable expressions
    # =========================================================================

    # Parse the content to find gateway structure
    # We need to find:
    # - exclusiveGateway elements with multiple outgoing flows
    # - The sequenceFlow that leads into the gateway (to find preceding task)
    # - The sequenceFlows that lead out of the gateway (to fix their names)

    gateway_var_counter = 0

    # Find all exclusive gateways with their IDs
    gateway_pattern = r'<(?:bpmn2?:)?exclusiveGateway[^>]*id="([^"]+)"[^>]*>'
    gateways = re.findall(gateway_pattern, content)

    # For each gateway, find incoming and outgoing flows
    for gateway_id in gateways:
        # Find outgoing flows from this gateway
        outgoing_pattern = rf'<(?:bpmn2?:)?sequenceFlow[^>]*sourceRef="{gateway_id}"[^>]*>'
        outgoing_flows = re.findall(outgoing_pattern, content)

        # Only process decision gateways (multiple outgoing flows)
        if len(outgoing_flows) <= 1:
            continue

        # Find the incoming flow to this gateway
        incoming_pattern = rf'<(?:bpmn2?:)?sequenceFlow[^>]*targetRef="{gateway_id}"[^>]*sourceRef="([^"]+)"[^>]*>'
        incoming_match = re.search(incoming_pattern, content)
        if not incoming_match:
            # Try alternative order of attributes
            incoming_pattern = rf'<(?:bpmn2?:)?sequenceFlow[^>]*sourceRef="([^"]+)"[^>]*targetRef="{gateway_id}"[^>]*>'
            incoming_match = re.search(incoming_pattern, content)

        if incoming_match:
            preceding_task_id = incoming_match.group(1)
            var_name = f"canHandle{gateway_var_counter}" if gateway_var_counter > 0 else "canHandle"
            gateway_var_counter += 1

            # Add zkp:variables to the preceding task if it doesn't have one
            # Match the task element
            task_patterns = [
                rf'(<(?:bpmn2?:)?(?:task|sendTask|receiveTask)[^>]*id="{preceding_task_id}"[^>]*)(>)',
                rf'(<(?:bpmn2?:)?(?:task|sendTask|receiveTask)[^>]*id="{preceding_task_id}"[^>]*)(/\s*>)',
            ]

            for task_pattern in task_patterns:
                task_match = re.search(task_pattern, content)
                if task_match:
                    task_tag = task_match.group(0)
                    if 'zkp:variables=' not in task_tag:
                        # Add zkp:variables attribute
                        new_task_tag = task_match.group(1) + f' zkp:variables="u32 {var_name}"' + task_match.group(2)
                        content = content.replace(task_tag, new_task_tag)
                        print(f"  - Added zkp:variables to task '{preceding_task_id}' for gateway '{gateway_id}'")
                    break

            # Now fix the sequence flow names for this gateway's outgoing flows
            # Find all outgoing flows and their names
            flow_pattern = rf'<(?:bpmn2?:)?sequenceFlow[^>]*sourceRef="{gateway_id}"[^>]*>'

            condition_counter = 0
            for flow_match in re.finditer(flow_pattern, content):
                flow_tag = flow_match.group(0)

                # Extract the flow name if present
                name_match = re.search(r'name="([^"]*)"', flow_tag)
                if name_match:
                    old_name = name_match.group(1)
                    # Check if it's already a valid expression
                    if '==' in old_name or old_name.replace(' ', '').isidentifier():
                        continue

                    # Convert label to variable expression
                    new_name = f"{var_name} == {condition_counter}"
                    new_flow_tag = flow_tag.replace(f'name="{old_name}"', f'name="{new_name}"')
                    content = content.replace(flow_tag, new_flow_tag)
                    print(f"  - Converted condition '{old_name}' -> '{new_name}'")
                    condition_counter += 1

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Converted: {input_path} -> {output_path}")
    print(f"  - Added zkp namespace")
    print(f"  - Added {participant_index} participant public key(s)")
    if lane_index > 0:
        print(f"  - Added {lane_index} lane public key(s)")

    return output_path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nExamples:")
        print("  python bpmn_to_zkwf.py ../diagram.bpmn")
        print("  python bpmn_to_zkwf.py ../diagram.bpmn ../diagram_zkwf.bpmn")
        print("  python bpmn_to_zkwf.py --validate-only ../diagram.bpmn")
        print("  python bpmn_to_zkwf.py --no-validate ../diagram.bpmn")
        sys.exit(1)

    # Parse arguments
    validate_only = False
    skip_validate = False
    input_path = None
    output_path = None

    args = sys.argv[1:]
    for arg in args:
        if arg == '--validate-only':
            validate_only = True
        elif arg == '--no-validate':
            skip_validate = True
        elif input_path is None:
            input_path = arg
        else:
            output_path = arg

    if not input_path:
        print("Error: No input file specified")
        sys.exit(1)

    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    if validate_only:
        print(f"\n{'='*60}")
        print(f"Validating: {input_path}")
        print('='*60)
        result = validate_bpmn(input_path)
        result.print_report()
        print('='*60)
        sys.exit(0 if result.is_valid else 1)
    else:
        result = convert_bpmn_to_zkwf(input_path, output_path, validate=not skip_validate)
        if result is None:
            sys.exit(1)


if __name__ == "__main__":
    main()

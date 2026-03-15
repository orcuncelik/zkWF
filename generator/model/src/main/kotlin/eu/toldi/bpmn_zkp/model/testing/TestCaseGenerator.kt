/*
 * Copyright 2023 Contributors of the zkWF project
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

package eu.toldi.bpmn_zkp.model.testing

import eu.toldi.bpmn_zkp.model.Model
import eu.toldi.bpmn_zkp.model.bpmn.*
import eu.toldi.bpmn_zkp.model.state.StateVectorElement
import eu.toldi.bpmn_zkp.model.state.Variable
import eu.toldi.bpmn_zkp.model.state.VariableType
import java.io.File

/**
 * Generates test cases from a BPMN model by traversing the workflow graph.
 *
 * Usage:
 *   val model = Model(File("path/to/model.bpmn"))
 *   val generator = TestCaseGenerator(model)
 *   val testCases = generator.generateTestCases()
 *   File("testcases.json").writeText(testCases.toJson())
 */
class TestCaseGenerator(private val model: Model) {

    private data class GeneratorState(
        val stateVector: List<Int>,
        val randomness: Long,
        val variables: List<String>,
        val messages: List<List<String>>
    ) {
        fun signature(): String {
            val messagesSignature = messages.joinToString(";") { it.joinToString(",") }
            return "${stateVector.joinToString(",")}|${variables.joinToString(",")}|$messagesSignature"
        }
    }

    private data class FiredTransition(
        val keyIndex: Int,
        val nextState: GeneratorState
    )

    private data class ExpressionConstraint(
        val expression: String,
        val expected: Boolean
    )

    private data class Token(val type: TokenType, val text: String)

    private enum class TokenType {
        IDENTIFIER,
        NUMBER,
        TRUE,
        FALSE,
        LPAREN,
        RPAREN,
        AND,
        OR,
        NOT,
        EQ,
        NEQ,
        LT,
        LTE,
        GT,
        GTE,
        END
    }

    private sealed class Value {
        data class BoolValue(val value: Boolean) : Value()
        data class NumberValue(val value: Long) : Value()
    }

    private val stateVectorElements: List<StateVectorElement>
    private val stateVectorElementIndex: Map<StateVectorElement, Int>
    private val stateVectorEvents: List<Event>
    private val variableList: List<Variable>
    private val variableIndexByName: Map<String, Int>
    private val variableTypeByName: Map<String, VariableType>
    private val messageCount: Int
    private val messageIndexById: Map<String, Int>
    private val throwStateIndexByMessageId: Map<String, Int>

    init {
        @Suppress("UNCHECKED_CAST")
        stateVectorElements = model.events.filter { it is StateVectorElement } as List<StateVectorElement>
        stateVectorElementIndex = stateVectorElements.withIndex().associate { it.value to it.index }
        stateVectorEvents = stateVectorElements.map { it as Event }
        variableList = model.variables.values.toList()
        variableIndexByName = variableList.withIndex().associate { it.value.name to it.index }
        variableTypeByName = variableList.associate { it.name to it.type }
        messageCount = model.messages.size
        messageIndexById = model.messages.withIndex().associate { it.value.id to it.index }
        throwStateIndexByMessageId = stateVectorElements.withIndex()
            .mapNotNull { (index, element) ->
                (element as? MessageThrowEvent)?.message?.id?.let { messageId -> messageId to index }
            }
            .toMap()
    }

    /**
     * Generates all test cases for the workflow by traversing from start to end.
     * For exclusive gateways, generates test cases for each possible branch.
     * For parallel gateways, generates test cases that execute all branches.
     */
    fun generateTestCases(
        maxDepth: Int = 256,
        maxVisitsPerState: Int = 1,
        maxChains: Int = 5000,
        initialRandomness: Long = 1675454832L
    ): TestCases {
        val initialState = getInitialState(initialRandomness)
        val chains = mutableListOf<List<TestCase>>()
        collectAllChains(
            state = initialState,
            depth = 0,
            maxDepth = maxDepth,
            maxVisitsPerState = maxVisitsPerState,
            maxChains = maxChains,
            path = mutableListOf(),
            seenInPath = mutableMapOf(),
            chains = chains
        )
        return flattenChains(chains)
    }

    /**
     * Generates a single execution path through the workflow.
     * For exclusive gateways, takes the first (or default) branch.
     * Useful for simple linear testing.
     */
    fun generateLinearTestCases(
        maxDepth: Int = 256,
        initialRandomness: Long = 1675454832L
    ): TestCases {
        val testCases = mutableListOf<TestCase>()
        var current = getInitialState(initialRandomness)

        for (depth in 0 until maxDepth) {
            if (isTerminal(current)) break

            val active = current.stateVector.indices.filter { current.stateVector[it] == 1 }.sorted()
            if (active.isEmpty()) break

            val selected = active.asSequence()
                .map { activeIndex -> activeIndex to fireActiveElement(current, activeIndex) }
                .firstOrNull { (_, transitions) -> transitions.isNotEmpty() }
                ?: break

            val picked = selected.second.first()
            testCases.add(
                TestCase(
                    initialState = current.toState(),
                    newState = picked.nextState.toState(),
                    keyIndex = picked.keyIndex
                )
            )
            current = picked.nextState
        }

        return TestCases(testCases)
    }

    /**
     * Gets the initial state based on start events.
     */
    private fun getInitialState(initialRandomness: Long): GeneratorState {
        val stateVector = MutableList(stateVectorElements.size) { 0 }
        val startEvents = model.events.filterIsInstance<StartEvent>()

        for (start in startEvents) {
            val states = propagateFromStart(start.outGoingTransition.end, stateVector.toList())
            if (states.isNotEmpty()) {
                states.first().forEachIndexed { index, value ->
                    stateVector[index] = maxOf(stateVector[index], value)
                }
            }
        }

        return GeneratorState(
            stateVector = stateVector.toList(),
            randomness = initialRandomness,
            variables = List(variableList.size) { "0" },
            messages = List(messageCount) { List(8) { "0" } }
        )
    }

    /**
     * Collects all complete chains (from an initial state to terminal state).
     */
    private fun collectAllChains(
        state: GeneratorState,
        depth: Int,
        maxDepth: Int,
        maxVisitsPerState: Int,
        maxChains: Int,
        path: MutableList<TestCase>,
        seenInPath: MutableMap<String, Int>,
        chains: MutableList<List<TestCase>>
    ) {
        if (chains.size >= maxChains) return
        if (isTerminal(state)) {
            chains.add(path.toList())
            return
        }
        if (depth >= maxDepth) return

        val signature = state.signature()
        val seenCount = seenInPath.getOrDefault(signature, 0)
        if (seenCount >= maxVisitsPerState) return
        seenInPath[signature] = seenCount + 1

        val activeIndexes = state.stateVector.indices.filter { state.stateVector[it] == 1 }.sorted()
        for (activeIndex in activeIndexes) {
            val transitions = fireActiveElement(state, activeIndex)
            for (transition in transitions) {
                if (chains.size >= maxChains) break
                val testCase = TestCase(
                    initialState = state.toState(),
                    newState = transition.nextState.toState(),
                    keyIndex = transition.keyIndex
                )
                path.add(testCase)
                collectAllChains(
                    state = transition.nextState,
                    depth = depth + 1,
                    maxDepth = maxDepth,
                    maxVisitsPerState = maxVisitsPerState,
                    maxChains = maxChains,
                    path = path,
                    seenInPath = seenInPath,
                    chains = chains
                )
                path.removeAt(path.lastIndex)
            }
            if (chains.size >= maxChains) break
        }

        if (seenCount == 0) {
            seenInPath.remove(signature)
        } else {
            seenInPath[signature] = seenCount
        }
    }

    /**
     * Fires an active state-vector element and returns all possible successor states.
     */
    private fun fireActiveElement(state: GeneratorState, activeIndex: Int): List<FiredTransition> {
        if (activeIndex < 0 || activeIndex >= stateVectorEvents.size) return emptyList()
        if (state.stateVector[activeIndex] != 1) return emptyList()

        val activeElement = stateVectorEvents[activeIndex]
        if (activeElement !is SingleOutput) return emptyList()
        if (activeElement is MessageCatchEvent && !canFireMessageCatch(state, activeElement)) return emptyList()

        val nextVector = state.stateVector.toMutableList()
        nextVector[activeIndex] = 2

        var nextMessages = state.messages.map { it.toMutableList() }.toList()
        if (activeElement is MessageThrowEvent) {
            nextMessages = updateMessagesForThrow(nextMessages, activeElement)
        }

        val advanced = advanceToNextStateElements(
            state = GeneratorState(
                stateVector = nextVector.toList(),
                randomness = state.randomness + 1,
                variables = state.variables.toList(),
                messages = nextMessages.map { it.toList() }
            ),
            element = activeElement.outGoingTransition.end,
            activeIndex = activeIndex
        )

        return advanced.map { FiredTransition(getKeyIndexForTask(activeIndex), it) }
    }

    private fun canFireMessageCatch(state: GeneratorState, catchEvent: MessageCatchEvent): Boolean {
        val throwIndex = throwStateIndexByMessageId[catchEvent.message.id] ?: return false
        return throwIndex in state.stateVector.indices && state.stateVector[throwIndex] == 2
    }

    private fun advanceToNextStateElements(
        state: GeneratorState,
        element: Event,
        activeIndex: Int
    ): List<GeneratorState> {
        return when (element) {
            is FinalEvent -> listOf(state)
            is StateVectorElement -> {
                val idx = stateVectorElementIndex[element] ?: return listOf(state)
                if (state.stateVector[idx] != 0) return listOf(state)
                val updated = state.stateVector.toMutableList()
                updated[idx] = 1
                listOf(state.copy(stateVector = updated.toList()))
            }
            is ParallelGatewayStart -> {
                var states = listOf(state)
                for (transition in element.outGoingTransitions) {
                    states = states.flatMap { current ->
                        advanceToNextStateElements(current, transition.end, activeIndex)
                    }
                }
                states
            }
            is ParallelGatewayEnd -> {
                val allIncomingCompleted = element.incomingTransitions.all { transition ->
                    val incomingElement = transition.start
                    if (incomingElement !is StateVectorElement) {
                        true
                    } else {
                        val idx = stateVectorElementIndex[incomingElement]
                        idx != null && state.stateVector[idx] == 2
                    }
                }
                if (!allIncomingCompleted) listOf(state)
                else advanceToNextStateElements(state, element.outGoingTransition.end, activeIndex)
            }
            is ExclusiveGatewayEnd -> {
                advanceToNextStateElements(state, element.outGoingTransition.end, activeIndex)
            }
            is ExclusiveGatewayStart -> {
                element.outGoingTransitions.flatMap { transition ->
                    val withVariables = applyGatewayVariableAssignments(
                        state = state,
                        gateway = element,
                        selectedTransition = transition,
                        activeIndex = activeIndex
                    )
                    advanceToNextStateElements(withVariables, transition.end, activeIndex)
                }
            }
            else -> listOf(state)
        }
    }

    /**
     * Initializes active places from start events.
     */
    private fun propagateFromStart(element: Event, vector: List<Int>): List<List<Int>> {
        return when (element) {
            is StateVectorElement -> {
                val index = stateVectorElementIndex[element] ?: return listOf(vector)
                val updated = vector.toMutableList()
                if (updated[index] == 0) {
                    updated[index] = 1
                }
                listOf(updated.toList())
            }
            is ParallelGatewayStart -> {
                var states = listOf(vector)
                for (transition in element.outGoingTransitions) {
                    states = states.flatMap { state -> propagateFromStart(transition.end, state) }
                }
                states
            }
            is ExclusiveGatewayStart -> {
                val preferred = element.default ?: element.outGoingTransitions.firstOrNull()
                if (preferred == null) listOf(vector) else propagateFromStart(preferred.end, vector)
            }
            is ParallelGatewayEnd -> propagateFromStart(element.outGoingTransition.end, vector)
            is ExclusiveGatewayEnd -> propagateFromStart(element.outGoingTransition.end, vector)
            else -> listOf(vector)
        }
    }

    private fun updateMessagesForThrow(
        messages: List<MutableList<String>>,
        throwEvent: MessageThrowEvent
    ): List<MutableList<String>> {
        val messageIndex = messageIndexById[throwEvent.message.id] ?: return messages
        if (messageIndex < 0 || messageIndex >= messages.size) return messages

        val updated = messages.map { it.toMutableList() }.toMutableList()
        val row = updated[messageIndex]
        if (row.isNotEmpty()) {
            val currentValue = row[0].toLongOrNull() ?: 0L
            row[0] = (currentValue + 1L).toString()
            updated[messageIndex] = row
        }
        return updated
    }

    private fun applyGatewayVariableAssignments(
        state: GeneratorState,
        gateway: ExclusiveGatewayStart,
        selectedTransition: Transition,
        activeIndex: Int
    ): GeneratorState {
        val constraints = buildGatewayConstraints(gateway, selectedTransition)
        if (constraints.isEmpty()) return state

        val writableVariables = model.variableWritePermission[activeIndex]
            ?.map { it.name }
            ?.toSet()
            ?: emptySet()

        val initialValues = variableList
            .mapIndexed { index, variable -> variable.name to state.variables.getOrElse(index) { "0" } }
            .toMap()
            .toMutableMap()

        val referencedVariables = constraints
            .flatMap { extractVariableNames(it.expression) }
            .filter { variableIndexByName.containsKey(it) }
            .distinct()

        if (referencedVariables.isEmpty()) return state

        val numericConstants = constraints.flatMap { extractNumericConstants(it.expression) }
        val domains = referencedVariables.associateWith { variableName ->
            val current = initialValues[variableName] ?: "0"
            val type = variableTypeByName[variableName] ?: VariableType.U32
            if (!writableVariables.contains(variableName)) {
                listOf(current)
            } else {
                when (type) {
                    VariableType.BOOL -> listOf(current, "false", "true", "0", "1").distinct()
                    VariableType.U32, VariableType.FIELD -> buildNumericDomain(current, numericConstants)
                }
            }
        }

        val solved = solveVariableConstraints(
            referencedVariables = referencedVariables,
            domains = domains,
            currentValues = initialValues,
            constraints = constraints
        ) ?: return state

        val updatedVariables = state.variables.toMutableList()
        solved.forEach { (name, value) ->
            val index = variableIndexByName[name] ?: return@forEach
            if (index in updatedVariables.indices) {
                updatedVariables[index] = value
            }
        }

        return state.copy(variables = updatedVariables.toList())
    }

    private fun buildGatewayConstraints(
        gateway: ExclusiveGatewayStart,
        selectedTransition: Transition
    ): List<ExpressionConstraint> {
        val constraints = mutableListOf<ExpressionConstraint>()
        val selectedExpression = selectedTransition.name?.trim().orEmpty()
        if (selectedExpression.isNotBlank()) {
            constraints.add(ExpressionConstraint(selectedExpression, true))
        }

        if (gateway.default != null && gateway.default.id == selectedTransition.id) {
            gateway.outGoingTransitions
                .filter { it.id != selectedTransition.id }
                .mapNotNull { transition ->
                    transition.name?.trim()?.takeIf { it.isNotBlank() }
                }
                .forEach { expression ->
                    constraints.add(ExpressionConstraint(expression, false))
                }
        }
        return constraints
    }

    private fun solveVariableConstraints(
        referencedVariables: List<String>,
        domains: Map<String, List<String>>,
        currentValues: MutableMap<String, String>,
        constraints: List<ExpressionConstraint>
    ): Map<String, String>? {
        fun isSatisfied(values: Map<String, String>): Boolean {
            return constraints.all { constraint ->
                val result = evaluateExpression(constraint.expression, values)
                result == constraint.expected
            }
        }

        fun backtrack(index: Int): Map<String, String>? {
            if (index >= referencedVariables.size) {
                return if (isSatisfied(currentValues)) currentValues.toMap() else null
            }

            val variableName = referencedVariables[index]
            val candidates = domains[variableName].orEmpty().ifEmpty { listOf(currentValues[variableName] ?: "0") }
            val original = currentValues[variableName]
            for (candidate in candidates) {
                currentValues[variableName] = candidate
                val solved = backtrack(index + 1)
                if (solved != null) return solved
            }
            if (original == null) currentValues.remove(variableName) else currentValues[variableName] = original
            return null
        }

        return backtrack(0)
    }

    private fun buildNumericDomain(current: String, numericConstants: List<Long>): List<String> {
        val values = mutableSetOf<Long>()
        values.add(current.toLongOrNull() ?: 0L)
        values.addAll(numericConstants)
        values.add(0L)
        values.add(1L)
        values.add(2L)
        values.add(3L)
        if (numericConstants.isNotEmpty()) {
            val max = numericConstants.maxOrNull() ?: 0L
            val min = numericConstants.minOrNull() ?: 0L
            values.add(max + 1)
            if (min > 0) values.add(min - 1)
        }
        return values
            .filter { it >= 0 }
            .sorted()
            .map { it.toString() }
    }

    private fun evaluateExpression(expression: String, variables: Map<String, String>): Boolean {
        return runCatching {
            val tokens = tokenizeExpression(expression)
            val parser = ExpressionParser(tokens, variables, variableTypeByName)
            parser.parse()
        }.getOrDefault(false)
    }

    private fun tokenizeExpression(expression: String): List<Token> {
        val tokens = mutableListOf<Token>()
        var i = 0
        while (i < expression.length) {
            val c = expression[i]
            when {
                c.isWhitespace() -> i++
                i + 1 < expression.length && expression.substring(i, i + 2) == "&&" -> {
                    tokens.add(Token(TokenType.AND, "&&"))
                    i += 2
                }
                i + 1 < expression.length && expression.substring(i, i + 2) == "||" -> {
                    tokens.add(Token(TokenType.OR, "||"))
                    i += 2
                }
                i + 1 < expression.length && expression.substring(i, i + 2) == "==" -> {
                    tokens.add(Token(TokenType.EQ, "=="))
                    i += 2
                }
                i + 1 < expression.length && expression.substring(i, i + 2) == "!=" -> {
                    tokens.add(Token(TokenType.NEQ, "!="))
                    i += 2
                }
                i + 1 < expression.length && expression.substring(i, i + 2) == "<=" -> {
                    tokens.add(Token(TokenType.LTE, "<="))
                    i += 2
                }
                i + 1 < expression.length && expression.substring(i, i + 2) == ">=" -> {
                    tokens.add(Token(TokenType.GTE, ">="))
                    i += 2
                }
                c == '!' -> {
                    tokens.add(Token(TokenType.NOT, "!"))
                    i++
                }
                c == '<' -> {
                    tokens.add(Token(TokenType.LT, "<"))
                    i++
                }
                c == '>' -> {
                    tokens.add(Token(TokenType.GT, ">"))
                    i++
                }
                c == '(' -> {
                    tokens.add(Token(TokenType.LPAREN, "("))
                    i++
                }
                c == ')' -> {
                    tokens.add(Token(TokenType.RPAREN, ")"))
                    i++
                }
                c.isDigit() -> {
                    val start = i
                    while (i < expression.length && expression[i].isDigit()) i++
                    tokens.add(Token(TokenType.NUMBER, expression.substring(start, i)))
                }
                c.isLetter() || c == '_' -> {
                    val start = i
                    while (i < expression.length && (expression[i].isLetterOrDigit() || expression[i] == '_')) i++
                    val text = expression.substring(start, i)
                    val type = when (text) {
                        "true" -> TokenType.TRUE
                        "false" -> TokenType.FALSE
                        else -> TokenType.IDENTIFIER
                    }
                    tokens.add(Token(type, text))
                }
                else -> i++
            }
        }
        tokens.add(Token(TokenType.END, ""))
        return tokens
    }

    private fun extractVariableNames(expression: String): List<String> {
        val regex = Regex("\\b[A-Za-z_][A-Za-z0-9_]*\\b")
        return regex.findAll(expression)
            .map { it.value }
            .filter { it != "true" && it != "false" }
            .toList()
    }

    private fun extractNumericConstants(expression: String): List<Long> {
        val regex = Regex("\\b\\d+\\b")
        return regex.findAll(expression)
            .mapNotNull { it.value.toLongOrNull() }
            .toList()
    }

    private fun flattenChains(chains: List<List<TestCase>>): TestCases {
        val nonEmptyChains = chains.filter { it.isNotEmpty() }
        if (nonEmptyChains.isEmpty()) return TestCases(emptyList())

        val flattened = mutableListOf<TestCase>()
        nonEmptyChains.forEachIndexed { chainIndex, chain ->
            chain.forEachIndexed { stepIndex, step ->
                val shouldRedeploy = chainIndex > 0 && stepIndex == 0
                flattened.add(
                    if (shouldRedeploy) step.copy(requireRedeploy = true) else step
                )
            }
        }
        return TestCases(flattened)
    }

    private fun isTerminal(state: GeneratorState): Boolean = state.stateVector.none { it == 1 }

    private fun GeneratorState.toState(): State {
        return State(
            stateVector = stateVector.map { it.toString() },
            randomness = randomness.toString(),
            variables = variables.toList(),
            messages = messages.map { it.toList() }
        )
    }

    /**
     * Gets the key index (participant index) for a task.
     */
    private fun getKeyIndexForTask(taskIndex: Int): Int {
        if (taskIndex >= 0 && taskIndex < model.publicKeys.size) {
            val taskKey = model.publicKeys[taskIndex]
            // Find which participant has this key
            for ((index, participant) in model.participants.withIndex()) {
                if (participant.publicKey == taskKey) {
                    return index
                }
            }
            // Check lane keys
            for ((_, key) in model.publicKeys.withIndex()) {
                if (key == taskKey) {
                    // Return the index in the unique keys list
                    val uniqueKeys = model.publicKeys.distinct()
                    return uniqueKeys.indexOf(taskKey)
                }
            }
        }
        return 0 // Default to first participant
    }

    companion object {
        /**
         * Convenience method to generate test cases from a BPMN file.
         */
        fun fromFile(bpmnFile: File): TestCases {
            val model = Model(bpmnFile)
            val generator = TestCaseGenerator(model)
            return generator.generateTestCases()
        }

        /**
         * Convenience method to generate linear test cases from a BPMN file.
         */
        fun linearFromFile(bpmnFile: File): TestCases {
            val model = Model(bpmnFile)
            val generator = TestCaseGenerator(model)
            return generator.generateLinearTestCases()
        }
    }

    private class ExpressionParser(
        private val tokens: List<Token>,
        private val variableValues: Map<String, String>,
        private val variableTypes: Map<String, VariableType>
    ) {
        private var position = 0

        fun parse(): Boolean {
            val value = parseOr()
            expect(TokenType.END)
            return value
        }

        private fun parseOr(): Boolean {
            var result = parseAnd()
            while (match(TokenType.OR)) {
                result = result || parseAnd()
            }
            return result
        }

        private fun parseAnd(): Boolean {
            var result = parseUnary()
            while (match(TokenType.AND)) {
                result = result && parseUnary()
            }
            return result
        }

        private fun parseUnary(): Boolean {
            return if (match(TokenType.NOT)) {
                !parseUnary()
            } else {
                parseComparison()
            }
        }

        private fun parseComparison(): Boolean {
            val left = parseValue()
            val operator = when {
                match(TokenType.EQ) -> TokenType.EQ
                match(TokenType.NEQ) -> TokenType.NEQ
                match(TokenType.LT) -> TokenType.LT
                match(TokenType.LTE) -> TokenType.LTE
                match(TokenType.GT) -> TokenType.GT
                match(TokenType.GTE) -> TokenType.GTE
                else -> null
            }

            if (operator == null) {
                return toBoolean(left)
            }

            val right = parseValue()
            return compare(left, right, operator)
        }

        private fun parseValue(): Value {
            val token = current()
            return when (token.type) {
                TokenType.NUMBER -> {
                    advance()
                    Value.NumberValue(token.text.toLongOrNull() ?: 0L)
                }
                TokenType.TRUE -> {
                    advance()
                    Value.BoolValue(true)
                }
                TokenType.FALSE -> {
                    advance()
                    Value.BoolValue(false)
                }
                TokenType.IDENTIFIER -> {
                    advance()
                    variableValue(token.text)
                }
                TokenType.LPAREN -> {
                    advance()
                    val inner = parseOr()
                    expect(TokenType.RPAREN)
                    Value.BoolValue(inner)
                }
                else -> {
                    advance()
                    Value.BoolValue(false)
                }
            }
        }

        private fun variableValue(name: String): Value {
            val raw = variableValues[name] ?: "0"
            return when (variableTypes[name]) {
                VariableType.BOOL -> Value.BoolValue(raw == "true" || raw == "1")
                VariableType.U32, VariableType.FIELD -> Value.NumberValue(raw.toLongOrNull() ?: 0L)
                null -> {
                    when (raw) {
                        "true" -> Value.BoolValue(true)
                        "false" -> Value.BoolValue(false)
                        else -> Value.NumberValue(raw.toLongOrNull() ?: 0L)
                    }
                }
            }
        }

        private fun compare(left: Value, right: Value, operator: TokenType): Boolean {
            return if (left is Value.BoolValue || right is Value.BoolValue) {
                val lv = toBoolean(left)
                val rv = toBoolean(right)
                when (operator) {
                    TokenType.EQ -> lv == rv
                    TokenType.NEQ -> lv != rv
                    else -> false
                }
            } else {
                val lv = (left as Value.NumberValue).value
                val rv = (right as Value.NumberValue).value
                when (operator) {
                    TokenType.EQ -> lv == rv
                    TokenType.NEQ -> lv != rv
                    TokenType.LT -> lv < rv
                    TokenType.LTE -> lv <= rv
                    TokenType.GT -> lv > rv
                    TokenType.GTE -> lv >= rv
                    else -> false
                }
            }
        }

        private fun toBoolean(value: Value): Boolean {
            return when (value) {
                is Value.BoolValue -> value.value
                is Value.NumberValue -> value.value != 0L
            }
        }

        private fun current(): Token = tokens.getOrElse(position) { Token(TokenType.END, "") }

        private fun advance() {
            if (position < tokens.size) position++
        }

        private fun match(type: TokenType): Boolean {
            if (current().type != type) return false
            advance()
            return true
        }

        private fun expect(type: TokenType) {
            if (!match(type)) {
                throw IllegalArgumentException("Expected token $type at position $position")
            }
        }
    }
}

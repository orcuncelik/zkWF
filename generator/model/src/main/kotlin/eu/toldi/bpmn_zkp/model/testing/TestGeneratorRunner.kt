package eu.toldi.bpmn_zkp.model.testing

import eu.toldi.bpmn_zkp.model.Model
import java.io.File

fun main(args: Array<String>) {
    val parsed = parseArgs(args)
    if (parsed.showHelp) {
        printHelp()
        return
    }

    val bpmnPath = parsed.bpmnPath ?: "../models/unit_tests/t2_zkp.bpmn"
    val bpmnFile = File(bpmnPath)

    if (!bpmnFile.exists()) {
        println("Error: File not found: ${bpmnFile.absolutePath}")
        return
    }

    println("=== Test Case Generator ===")
    println("Input: ${bpmnFile.name}")
    println()

    try {
        val model = Model(bpmnFile)
        val generator = TestCaseGenerator(model)

        println("Model Info:")
        println("  - Participants: ${model.participants.map { it.name }}")
        println("  - Variables: ${model.variables.keys}")
        println("  - Messages: ${model.messages.size}")
        println()

        val testCases = if (parsed.linearMode) {
            generator.generateLinearTestCases(
                maxDepth = parsed.maxDepth,
                initialRandomness = parsed.initialRandomness
            )
        } else {
            generator.generateTestCases(
                maxDepth = parsed.maxDepth,
                maxVisitsPerState = parsed.maxVisitsPerState,
                maxChains = parsed.maxChains,
                initialRandomness = parsed.initialRandomness
            )
        }

        println("Mode: ${if (parsed.linearMode) "linear" else "all-paths"}")
        println("Generated ${testCases.size} test cases:")
        println()

        if (parsed.verbose) {
            testCases.forEachIndexed { index, tc ->
                println("Test Case ${index + 1}:")
                println("  Initial State:")
                println("    stateVector: ${tc.initialState.stateVector}")
                println("    randomness: ${tc.initialState.randomness}")
                println("    variables: ${tc.initialState.variables}")
                println("    messages: ${tc.initialState.messages}")
                println("  New State:")
                println("    stateVector: ${tc.newState.stateVector}")
                println("    randomness: ${tc.newState.randomness}")
                println("    variables: ${tc.newState.variables}")
                println("    messages: ${tc.newState.messages}")
                println("  keyIndex: ${tc.keyIndex}")
                println("  requireRedeploy: ${tc.requireRedeploy}")
                println()
            }
        }

        val json = testCases.toJson()
        parsed.outputPath?.let { output ->
            File(output).writeText(json)
            println("Saved JSON to: ${File(output).absolutePath}")
        }
        if (parsed.outputPath == null || parsed.verbose) {
            println("=== JSON Output ===")
            println(json)
        } else {
            println("JSON output omitted from stdout (use --verbose to print it).")
        }

    } catch (e: Exception) {
        println("Error: ${e.message}")
        e.printStackTrace()
    }
}

private data class RunnerArgs(
    val bpmnPath: String?,
    val outputPath: String?,
    val linearMode: Boolean,
    val maxDepth: Int,
    val maxVisitsPerState: Int,
    val maxChains: Int,
    val initialRandomness: Long,
    val verbose: Boolean,
    val showHelp: Boolean
)

private fun parseArgs(args: Array<String>): RunnerArgs {
    var bpmnPath: String? = null
    var outputPath: String? = null
    var linearMode = false
    var maxDepth = 256
    var maxVisitsPerState = 1
    var maxChains = 5000
    var initialRandomness = 1675454832L
    var verbose = false
    var showHelp = false

    var i = 0
    while (i < args.size) {
        when (val arg = args[i]) {
            "-h", "--help" -> showHelp = true
            "--linear" -> linearMode = true
            "--verbose" -> verbose = true
            "--output" -> {
                outputPath = args.getOrNull(i + 1)
                i++
            }
            "--max-depth" -> {
                maxDepth = args.getOrNull(i + 1)?.toIntOrNull() ?: maxDepth
                i++
            }
            "--max-visits" -> {
                maxVisitsPerState = args.getOrNull(i + 1)?.toIntOrNull() ?: maxVisitsPerState
                i++
            }
            "--max-chains" -> {
                maxChains = args.getOrNull(i + 1)?.toIntOrNull() ?: maxChains
                i++
            }
            "--initial-randomness" -> {
                initialRandomness = args.getOrNull(i + 1)?.toLongOrNull() ?: initialRandomness
                i++
            }
            else -> {
                if (!arg.startsWith("--") && bpmnPath == null) {
                    bpmnPath = arg
                }
            }
        }
        i++
    }

    return RunnerArgs(
        bpmnPath = bpmnPath,
        outputPath = outputPath,
        linearMode = linearMode,
        maxDepth = maxDepth,
        maxVisitsPerState = maxVisitsPerState,
        maxChains = maxChains,
        initialRandomness = initialRandomness,
        verbose = verbose,
        showHelp = showHelp
    )
}

private fun printHelp() {
    println("Usage:")
    println("  TestGeneratorRunnerKt [bpmnFile] [OPTIONS]")
    println()
    println("Options:")
    println("  --linear                    Generate a single linear path")
    println("  --output <path>             Write JSON output to file")
    println("  --max-depth <n>             Max steps explored per chain (default: 256)")
    println("  --max-visits <n>            Max repeated visits per state in one chain (default: 1)")
    println("  --max-chains <n>            Max number of chains to generate (default: 5000)")
    println("  --initial-randomness <n>    Starting randomness value (default: 1675454832)")
    println("  --verbose                   Print every generated test case details")
    println("  -h, --help                  Show this help")
}

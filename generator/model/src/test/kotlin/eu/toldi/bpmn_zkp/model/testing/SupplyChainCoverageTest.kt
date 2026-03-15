package eu.toldi.bpmn_zkp.model.testing

import eu.toldi.bpmn_zkp.model.Model
import eu.toldi.bpmn_zkp.model.state.StateVectorElement
import java.io.File
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertContains
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class SupplyChainCoverageTest {

    @BeforeTest
    fun resetTestCaseCounter() {
        TestCase.testCaseCount = 0
    }

    @Test
    fun parsesSupplyChainParticipantsPublicKeysAndInitialState() {
        val model = Model(repoFile("bpmn", "supply_chain.bpmn"))
        val trace = TestCaseGenerator(model).generateLinearTestCases()
        val firstState = trace.first().initialState

        assertEquals(
            listOf("Bulk Buyer", "Manufacturer", "Middleman", "Supplier", "Special Carrier"),
            model.participants.map { it.name }
        )
        assertEquals(
            mapOf(
                "Bulk Buyer" to "7350854827252829541674033642803854801334834402587808031858165572750984534676, 21854189621934227298279236061289964015847784208108325958639815905934377828601",
                "Manufacturer" to "21715273850596312954904974472147290906491269550500570193604680361889132220377, 3161870534391964258194010589089177316887486533167236663570547206873941016760",
                "Middleman" to "14897476871502190904409029696666322856887678969656209656241038339251270171395, 16668832459046858928951622951481252834155254151733002984053501254009901876174",
                "Supplier" to "9042369582473258640608156702000501292772581947454267167560366333613005574515, 4249323117433249059780096680642725049854712516559612996154758631746161341441",
                "Special Carrier" to "7350854827252829541674033642803854801334834402587808031858165572750984534676, 21854189621934227298279236061289964015847784208108325958639815905934377828601"
            ),
            model.participants.associate { it.name to it.publicKey }
        )
        assertEquals(
            model.events.filterIsInstance<StateVectorElement>().size,
            model.publicKeys.size
        )
        assertEquals("1675454832", firstState.randomness)
        assertEquals(
            setOf(
                "Activity_1mmg8os",
                "Event_1c9dw6k",
                "Event_17syoh1",
                "Event_169zxl0",
                "Event_07evuve"
            ),
            activeStateIds(model, firstState)
        )
    }

    @Test
    fun generatesCommittedSupplyChainTraceAndTerminates() {
        val bpmnFile = repoFile("bpmn", "supply_chain.bpmn")
        val expectedTrace = TestCases.fromJson(repoFile("bpmn", "supply_chain_testCases.json").readText())
        val model = Model(bpmnFile)
        val actualTrace = TestCaseGenerator(model).generateLinearTestCases()
        val splitState = actualTrace[7].newState
        val finalState = actualTrace.last().newState

        assertEquals(40, actualTrace.size)
        assertEquals(expectedTrace, actualTrace)
        assertContains(activeStateIds(model, splitState), "Activity_122n7a0")
        assertContains(activeStateIds(model, splitState), "Activity_1ez2o8n")
        assertTrue(
            finalState.stateVector.none { it == "1" },
            "Final state should be terminal with no active state-vector elements."
        )
    }

    private fun activeStateIds(model: Model, state: State): Set<String> {
        val stateVectorElements = model.events.filterIsInstance<StateVectorElement>()
        return state.stateVector.mapIndexedNotNull { index, value ->
            if (value == "1") stateVectorElements[index].id else null
        }.toSet()
    }

    private fun repoFile(vararg parts: String): File {
        var current = File(System.getProperty("user.dir")).absoluteFile
        while (true) {
            val candidate = parts.fold(current) { base, part -> File(base, part) }
            if (candidate.exists()) return candidate
            current = current.parentFile ?: break
        }
        error("Could not locate repository file: ${parts.joinToString("/")}")
    }
}

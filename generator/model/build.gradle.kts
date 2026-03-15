plugins {
    kotlin("jvm")
    application
}

group = "eu.toldi"
version = "1.0-SNAPSHOT"

repositories {
    mavenCentral()
}

dependencies {
    implementation(kotlin("stdlib"))
    implementation("com.beust:klaxon:5.6")
    implementation("org.web3j:core:4.9.1")
}

application {
    mainClass.set("eu.toldi.bpmn_zkp.model.testing.TestGeneratorRunnerKt")
}

tasks.register<JavaExec>("generateTests") {
    group = "application"
    description = "Generate test cases from a BPMN file"
    classpath = sourceSets["main"].runtimeClasspath
    mainClass.set("eu.toldi.bpmn_zkp.model.testing.TestGeneratorRunnerKt")
}

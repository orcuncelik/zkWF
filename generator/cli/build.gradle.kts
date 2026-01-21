plugins {
    id("com.github.johnrengelman.shadow") version "8.1.1"
    java
    kotlin("jvm")
}

group = "eu.toldi"
version = "1.0-SNAPSHOT"

repositories {
    mavenCentral()
}

dependencies {
    implementation(kotlin("stdlib"))
    implementation(project(":model"))
    implementation(project(":zokrates-wrapper"))
    val coroutines_version = "1.6.4"
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:$coroutines_version")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-javafx:$coroutines_version")
    implementation("com.beust:klaxon:5.6")
    implementation("org.web3j:core:4.9.1")
    testImplementation("org.junit.jupiter:junit-jupiter-api:5.9.0")
    testRuntimeOnly("org.junit.jupiter:junit-jupiter-engine:5.9.0")
}

tasks {
    shadowJar {
        archiveBaseName.set("cli")
        archiveClassifier.set("all")
        archiveVersion.set("1.0-SNAPSHOT")
        manifest {
            attributes["Main-Class"] = "eu.toldi.bpmn_zkp.CLIMainKt"
        }
        mergeServiceFiles()
    }
}

tasks.getByName<Test>("test") {
    useJUnitPlatform()
}

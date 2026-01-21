plugins {
    id("com.github.johnrengelman.shadow") version "8.1.1"
    id("org.openjfx.javafxplugin") version "0.1.0"
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
    implementation("no.tornado:tornadofx:1.7.20")
    implementation("org.web3j:core:4.9.1")
}

javafx {
    modules("javafx.controls", "javafx.fxml", "javafx.web")
    version = "21"
}

tasks {
    shadowJar {
        archiveBaseName.set("bpmn_zkp")
        archiveClassifier.set("")
        archiveVersion.set("")
        manifest {
            attributes["Main-Class"] = "eu.toldi.bpmn_zkp.GUIKt"
        }
        mergeServiceFiles()
    }
}


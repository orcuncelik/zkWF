plugins {
    kotlin("jvm") version "1.9.22"
}

repositories {
    mavenCentral()
}

subprojects {

    apply {
        plugin("kotlin")
    }

    repositories {
        mavenCentral()
    }

    // Configure all Kotlin and Java tasks to target Java 21 bytecode
    // (Kotlin 1.9.x doesn't support Java 22 target yet)
    tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
        kotlinOptions {
            jvmTarget = "21"
        }
    }

    tasks.withType<JavaCompile>().configureEach {
        sourceCompatibility = "21"
        targetCompatibility = "21"
    }
}

# Repository Guidelines

## Project Structure & Module Organization
- `generator/`: Gradle/Kotlin multi-module for the zkWF GUI and CLI, plus ZoKrates templates in `generator/*.zok.template` and Solidity in `generator/gui/src/main/solidity/`.
- `editor/`: Web-based BPMN modeler extension (webpack/LESS).
- `verifier/`: Truffle smart-contract project for the state manager.
- `verifier_fabric/`: Hyperledger Fabric chaincode (Kotlin/Java).
- `pycrypto/`: Python crypto helpers and CLI.
- `models/`: Example BPMN workflows and JSON test cases (e.g., `models/unit tests/*.bpmn`).

## Build, Test, and Development Commands
- `cd generator && ./gradlew gui:shadowjar`: build the GUI jar, then run `java -jar generator/gui/build/libs/WFGUI.jar`.
- `cd generator && ./gradlew cli:shadowjar`: build the CLI jar (`cli-1.0-SNAPSHOT-all.jar`).
- `cd editor && npm install && npm run dev`: build and serve the BPMN editor; use `npm run build` for a production bundle.
- `cd verifier_fabric && ./gradlew shadowJar`: build the chaincode jar; `./gradlew test` runs JUnit tests.
- `cd pycrypto && pip install -r requirements.txt`: `source venv/bin/activate`  install runtime deps; `pip install -r requirements-dev.txt` for linting tools.

## Coding Style & Naming Conventions
- JavaScript (editor): 2-space indentation, semicolons, camelCase for functions and variables.
- Kotlin/Java (generator, verifier_fabric): 4-space indentation, PascalCase for types, camelCase for methods/fields.
- Python (pycrypto): 4-space indentation, `snake_case`, tests named `*_test.py`.
- `pycrypto` uses `black`, `flake8`, and `isort` via `pre-commit` (see `pycrypto/README.md`).

## Testing Guidelines
- Python unit tests: `cd pycrypto && python -m unittest discover -s tests`.
- Fabric chaincode: `cd verifier_fabric && ./gradlew test` (JUnit 5).
- BPMN/JSON cases in `models/` are used by the CLI during batch runs.

## Commit & Pull Request Guidelines
- Recent history shows simple, short messages (e.g., "Update README.md"); use concise, imperative summaries.
- PRs should explain the module touched, include steps to verify, and link related issues.
- Include screenshots or short clips for changes in `editor/` or `generator/gui/`.

## Run tips
- To run tests: `PYTHON=../pycrypto/venv/bin/python \
     java -jar cli/build/libs/cli-1.0-SNAPSHOT-all.jar \
       ../models/leasing-payment/leasing-payment.bpmn \
       ../models/leasing-payment/testCases.json`
- 

# TODO

## 1 gate_runner quiet crashes with UnicodeEncodeError on cp1250 consoles

status: open
class: bug

Crepidoma scripts/gate_runner.py:77 print(line) raises UnicodeEncodeError for U+25CF under a Windows cp1250 console. QC2C works around it with PYTHONIOENCODING=utf-8 in tasks/local.yml; fix upstream with sys.stdout.reconfigure(errors='replace').

## 2 Host jest cannot resolve jest-circus runner on Windows

status: open
class: bug

node packages/typescript/node_modules/jest/bin/jest.js run from packages/typescript reports 'Module ...jest-circus/build/runner.js in the testRunner option was not found' although the file exists; npm test also lacks .cmd shims after the Docker install. Blocks a host local:node task; TypeScript tests stay on workflow:test-node.

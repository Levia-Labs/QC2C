# Packages

Client libraries for QC2C. They share the same sector data and lookup algorithm; only the code that reads the manifest and sector files differs per language.

| Package                            | Registry                                  | Install            |
| ---------------------------------- | ----------------------------------------- | ------------------ |
| [python](python/README.md)         | [PyPI](https://pypi.org/project/qc2c/)    | `pip install qc2c` |
| [typescript](typescript/README.md) | [npm](https://www.npmjs.com/package/qc2c) | `npm install qc2c` |

Ports to other languages are welcome. Read the manifest, pick the sector whose bounding box contains the point, then run a point-in-polygon test over that sector's countries.

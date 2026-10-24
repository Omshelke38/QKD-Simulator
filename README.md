# Quantum Key Distribution Protocol Simulator with Eavesdropper Detection

An educational Python/Streamlit project that demonstrates the main ideas of BB84 quantum key distribution (QKD), basis sifting, sample Quantum Bit Error Rate (QBER), and an optional intercept-resend eavesdropper.

## Features

- Configurable number of simulated bits
- Optional Eve intercept-resend simulation
- Basis matching and sifted-bit preview
- Sample QBER calculation and configurable threshold
- QBER and matching/discarded-bit charts
- Simulation history and CSV exports
- Custom message input and AES-GCM authenticated-encryption demonstration
- Educational explanation and explicit limitations

## Requirements

- Python 3.9 or newer
- pip

## Run locally

Open Terminal in this project folder and run:

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

Streamlit will print a local URL, usually `http://localhost:8501`. Open that URL in your browser.

To stop the app, return to the Terminal and press `Control + C`.

## Files

- `app.py` — application and simulation logic
- `requirements.txt` — Python dependencies
- `.gitignore` — excludes local environment and temporary files

## How the simulation works

1. Alice generates random bits and preparation bases.
2. Bob chooses random measurement bases.
3. If Eve is enabled, she measures and resends signals using random bases.
4. Alice and Bob keep positions where their bases match (basis sifting).
5. A random sample of sifted bits is compared to estimate QBER.
6. The sample QBER is compared with the configured threshold.
7. The separate message demo attempts AES-GCM encryption/decryption when the fresh sample passes.

## Important limitations

This is a classical educational simulation, not a physical quantum channel and not a production-ready QKD implementation. It does not implement a complete security proof, authenticated classical communication, error correction, or privacy amplification. A low sample QBER does not prove that eavesdropping is absent. Do not use this project to protect real-world secrets.

## Suggested academic citation

Bennett, C. H., and Brassard, G. “Quantum cryptography: Public key distribution and coin tossing.” Proceedings of the IEEE International Conference on Computers, Systems and Signal Processing, Bangalore, India, 1984, pp. 175–179.

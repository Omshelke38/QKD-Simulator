import hashlib
import secrets
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

st.set_page_config(page_title="BB84 QKD Simulator", page_icon="", layout="wide")

# ---------------- BB84 protocol model ----------------
def measure(bit, prepared_basis, measured_basis, rng):
    """Ideal BB84 measurement: same basis is deterministic; different basis is 50/50."""
    return int(bit) if prepared_basis == measured_basis else int(rng.integers(0, 2))


def run_bb84(n, eve_on, noise_pct, sample_pct, qber_limit, seed=None):
    rng = np.random.default_rng(seed)

    # Alice prepares random bit values and random bases.
    a_bits = rng.integers(0, 2, n, dtype=np.int8)
    a_basis = rng.integers(0, 2, n, dtype=np.int8)

    # Eve intercepts each signal, measures in a random basis, then resends.
    e_basis = np.full(n, -1, dtype=np.int8)
    e_bits = np.full(n, -1, dtype=np.int8)
    sent_bits, sent_basis = a_bits.copy(), a_basis.copy()
    if eve_on:
        e_basis = rng.integers(0, 2, n, dtype=np.int8)
        for i in range(n):
            e_bits[i] = measure(int(a_bits[i]), int(a_basis[i]), int(e_basis[i]), rng)
        sent_bits, sent_basis = e_bits.copy(), e_basis.copy()

    # Bob measures each received signal using an independent random basis.
    b_basis = rng.integers(0, 2, n, dtype=np.int8)
    b_bits = np.array(
        [measure(int(sent_bits[i]), int(sent_basis[i]), int(b_basis[i]), rng) for i in range(n)],
        dtype=np.int8,
    )

    # Model independent bit-flip noise in the channel.
    flips = rng.random(n) < noise_pct / 100
    b_bits = np.bitwise_xor(b_bits, flips.astype(np.int8))

    # Public basis comparison; only matching positions survive sifting.
    matched = a_basis == b_basis
    sift_idx = np.flatnonzero(matched)
    sift_a, sift_b = a_bits[sift_idx], b_bits[sift_idx]

    # Reveal a random sample to estimate QBER; remove those bits from candidate key.
    if len(sift_idx):
        sample_n = min(len(sift_idx), max(1, round(len(sift_idx) * sample_pct / 100)))
        sample_pos = rng.choice(len(sift_idx), sample_n, replace=False)
    else:
        sample_pos = np.array([], dtype=int)
    errors = int(np.count_nonzero(sift_a[sample_pos] != sift_b[sample_pos]))
    qber = errors / len(sample_pos) * 100 if len(sample_pos) else 0.0
    passed = bool(len(sample_pos) and qber <= qber_limit)

    keep = np.ones(len(sift_idx), dtype=bool)
    keep[sample_pos] = False
    candidate_a, candidate_b = sift_a[keep], sift_b[keep]
    strings_match = bool(len(candidate_a) and np.array_equal(candidate_a, candidate_b))

    # Educational hash-based key demonstration, not a full privacy-amplification proof.
    key_a = key_b = None
    if passed and strings_match and len(candidate_a) >= 256:
        raw_a = "".join(map(str, candidate_a.tolist())).encode()
        raw_b = "".join(map(str, candidate_b.tolist())).encode()
        key_a = hashlib.sha256(b"BB84-EDU|" + raw_a).digest()
        key_b = hashlib.sha256(b"BB84-EDU|" + raw_b).digest()

    sift_lookup = {int(original): j for j, original in enumerate(sift_idx)}
    sample_set = set(sample_pos.tolist())
    rows = []
    for i in range(n):
        j = sift_lookup.get(i)
        is_match = bool(matched[i])
        rows.append({
            "Signal": i + 1,
            "Alice bit": int(a_bits[i]),
            "Alice basis": "+" if a_basis[i] == 0 else "×",
            "Eve basis": ("+" if e_basis[i] == 0 else "×") if eve_on else "—",
            "Eve result": int(e_bits[i]) if eve_on else "—",
            "Bob basis": "+" if b_basis[i] == 0 else "×",
            "Bob result": int(b_bits[i]),
            "Basis match": is_match,
            "QBER sample": bool(is_match and j in sample_set),
            "Error": bool(is_match and a_bits[i] != b_bits[i]),
            "Channel flip": bool(flips[i]),
        })

    return {
        "n": n, "eve": eve_on, "noise": noise_pct, "matched": int(matched.sum()),
        "discarded": int((~matched).sum()), "sample_n": len(sample_pos),
        "errors": errors, "qber": qber, "limit": qber_limit, "passed": passed,
        "candidate_n": len(candidate_a), "strings_match": strings_match,
        "key_a": key_a, "key_b": key_b, "rows": pd.DataFrame(rows),
        "sift_a": sift_a, "sift_b": sift_b, "sample_pos": sample_pos,
    }


def fingerprint(key):
    return hashlib.sha256(key).hexdigest()[:16].upper()


# ---------------- Streamlit interface ----------------
st.title("🔐 BB84 Quantum Key Distribution Simulator")
st.caption("Alice · Quantum channel · Optional Eve · Bob · Basis sifting · QBER estimation")

with st.expander("About this simulation and its limitations"):
    st.write(
        "This is a classical software simulation of the BB84 protocol. It models ideal "
        "BB84 measurement probabilities, intercept-resend eavesdropping, optional channel "
        "bit-flip noise, basis reconciliation and sample quantum bit error rate (QBER). "
        "It does not transmit physical photons or use quantum hardware."
    )
    st.warning(
        "Educational model only: no authenticated classical channel, full error-correction "
        "protocol, finite-key analysis or composable security proof is implemented. "
        "A passing sample QBER does not prove that no eavesdropper is present."
    )

with st.sidebar:
    st.header("Experiment configuration")
    n = st.select_slider("Number of signals", [100, 250, 500, 1000, 2000, 5000, 10000], value=1000)
    eve = st.toggle("Enable Eve (intercept-resend)", value=False)
    noise = st.slider("Channel bit-flip noise", 0.0, 10.0, 0.0, 0.5)
    sample_pct = st.slider("QBER sample size (% of sifted bits)", 5, 50, 25)
    limit = st.slider("QBER abort threshold (%)", 0.0, 25.0, 11.0, 0.5)
    seed_input = st.text_input("Random seed (optional)", placeholder="e.g. 42")
    execute = st.button("▶ Run BB84 simulation", type="primary", use_container_width=True)
    st.caption("Use the same seed to reproduce an experiment.")

if "result" not in st.session_state:
    st.session_state.result = None
if "history" not in st.session_state:
    st.session_state.history = []
if "aes_result" not in st.session_state:
    st.session_state.aes_result = None

if execute:
    if seed_input.strip() and not seed_input.strip().lstrip("-").isdigit():
        st.error("Seed must be an integer.")
        st.stop()
    seed = int(seed_input) if seed_input.strip() else None
    progress = st.progress(0, text="Initializing protocol...")
    status = st.status("Running BB84 protocol", expanded=True)
    stages = [
        ("1/5 · Alice prepares random bits and bases", 15),
        ("2/5 · Quantum channel applies Eve/no-Eve model", 35),
        ("3/5 · Bob measures signals in random bases", 60),
        ("4/5 · Alice and Bob reconcile measurement bases", 80),
    ]
    for label, pct in stages:
        status.write(label)
        progress.progress(pct, text=label)
    result = run_bb84(n, eve, noise, sample_pct, limit, seed)
    status.write("5/5 · Random sample revealed; QBER calculated; candidate key checked.")
    progress.progress(100, text="Simulation complete")
    status.update(label="BB84 experiment completed", state="complete", expanded=False)
    st.session_state.result = result
    st.session_state.aes_result = None
    st.session_state.history.append({
        "Run time": datetime.now().strftime("%H:%M:%S"),
        "Eve": "ON" if eve else "OFF",
        "Signals": n,
        "Sifted": result["matched"],
        "QBER (%)": round(result["qber"], 2),
        "Decision": "PASS" if result["passed"] else "ABORT",
    })

r = st.session_state.result
if r is None:
    st.info("Choose experiment settings in the sidebar and click **Run BB84 simulation**.")
    st.markdown("### Protocol workflow")
    st.code("ALICE PREPARES → QUANTUM CHANNEL → BOB MEASURES → BASIS SIFTING → QBER TEST → KEY CHECK")
    st.markdown(
        "- Alice creates random bits and chooses a random basis for every signal.\n"
        "- Eve, if enabled, intercepts, measures and resends every signal.\n"
        "- Bob independently chooses measurement bases.\n"
        "- Alice and Bob publicly compare bases, not bit values, and discard mismatches.\n"
        "- A random subset of sifted bits is revealed to estimate QBER."
    )
    st.stop()

st.subheader("Experiment summary")
cols = st.columns(5)
cols[0].metric("Signals sent", f'{r["n"]:,}')
cols[1].metric("Sifted bits", f'{r["matched"]:,}')
cols[2].metric("Discarded", f'{r["discarded"]:,}')
cols[3].metric("Sample QBER", f'{r["qber"]:.2f}%')
cols[4].metric("Sample errors", f'{r["errors"]}/{r["sample_n"]}')

if r["passed"]:
    st.success(f'SAMPLE TEST PASSED: QBER {r["qber"]:.2f}% ≤ threshold {r["limit"]:.2f}%. This is not a proof of security.')
else:
    st.error(f'PROTOCOL ABORT: QBER {r["qber"]:.2f}% > threshold {r["limit"]:.2f}%, or no sample was available.')

st.subheader("1 · Protocol processing log")
log = [
    ("Alice — state preparation", f'{r["n"]:,} random bit values and preparation bases generated.'),
    ("Quantum channel", "Eve intercept-resend is active." if r["eve"] else "No eavesdropper configured."),
    ("Bob — measurement", f'{r["n"]:,} signals measured using independent random bases.'),
    ("Basis reconciliation", f'{r["matched"]:,} matching positions retained; {r["discarded"]:,} discarded.'),
    ("Parameter estimation", f'{r["sample_n"]:,} sifted bits sampled; {r["errors"]:,} errors found.'),
]
for title, detail in log:
    st.markdown(f"**{title}:** {detail}")

st.subheader("2 · Signal-by-signal transmission table")
st.caption("First 200 signals shown. Download the complete experiment record for all signals.")
st.dataframe(r["rows"].head(200), use_container_width=True, hide_index=True)
st.download_button(
    "Download complete signal record (CSV)",
    r["rows"].to_csv(index=False).encode("utf-8"),
    "bb84_signal_record.csv",
    "text/csv",
)

st.subheader("3 · Sifting and error analysis")
left, right = st.columns(2)
with left:
    st.markdown("**Basis comparison**")
    st.bar_chart(pd.DataFrame(
        {"Signals": [r["matched"], r["discarded"]]},
        index=["Same basis · kept", "Different basis · discarded"],
    ))
with right:
    st.markdown("**Sample QBER and abort threshold**")
    st.bar_chart(pd.DataFrame(
        {"Percent": [r["qber"], r["limit"]]},
        index=["Measured QBER", "Abort threshold"],
    ))

st.write(
    f'{r["sample_n"]:,} sifted bits were publicly revealed for the error estimate and excluded '
    f'from the candidate key. {r["candidate_n"]:,} unrevealed candidate bits remain.'
)

st.subheader("4 · Shared-key consistency check")
a, b, c = st.columns(3)
a.metric("Candidate bits remaining", f'{r["candidate_n"]:,}')
b.metric("Alice/Bob strings", "Identical" if r["strings_match"] else "Different / unavailable")
ready = r["key_a"] is not None and r["key_b"] is not None and r["key_a"] == r["key_b"]
c.metric("256-bit demo key", "Ready" if ready else "Not generated")

if not r["strings_match"]:
    st.warning("The candidate strings differ. This simplified simulator does not implement error correction, so it will not claim Alice and Bob share a key.")
elif not r["passed"]:
    st.warning("The QBER sample failed. Key generation is disabled.")
elif not ready:
    st.warning("At least 256 identical candidate bits are required for this demonstration. Increase signal count or reduce the sample percentage.")
else:
    st.success("Both simulated endpoints derive the same 256-bit demonstration key.")
    st.code("SHA-256 fingerprint: " + fingerprint(r["key_a"]))

st.subheader("5 · Classical AES-GCM message test")
st.caption("This demonstrates classical authenticated encryption using the simulated shared key. The message is not transmitted as a quantum signal.")
message = st.text_area("Alice's test message", placeholder="Type a message to encrypt...")
if st.button("Encrypt at Alice and decrypt at Bob", disabled=not ready):
    nonce = secrets.token_bytes(12)
    cipher = AESGCM(r["key_a"])
    encrypted = cipher.encrypt(nonce, message.encode("utf-8"), None)
    recovered = AESGCM(r["key_b"]).decrypt(nonce, encrypted, None).decode("utf-8")
    st.session_state.aes_result = {
        "nonce": nonce.hex(), "ciphertext": encrypted.hex(), "recovered": recovered,
        "verified": recovered == message,
    }

if st.session_state.aes_result:
    x = st.session_state.aes_result
    st.success("AES-GCM authentication and decryption verified." if x["verified"] else "Verification failed.")
    st.text_input("Nonce (hex)", x["nonce"], disabled=True)
    st.text_area("Ciphertext and authentication tag (hex)", x["ciphertext"], disabled=True)
    st.text_area("Bob's decrypted message", x["recovered"], disabled=True)

st.subheader("6 · Experiment history")
if st.session_state.history:
    history = pd.DataFrame(st.session_state.history)
    st.dataframe(history, use_container_width=True, hide_index=True)
    st.line_chart(history.set_index("Run time")[["QBER (%)"]])
    st.download_button("Download history (CSV)", history.to_csv(index=False).encode(), "bb84_history.csv", "text/csv")
    if st.button("Clear history"):
        st.session_state.history = []
        st.rerun()
else:
    st.caption("Run another experiment to build a comparison history.")

with st.expander("Expected validation behaviour"):
    st.markdown(
        "- **Eve OFF, noise 0%:** QBER should be 0% in the ideal model; around half of all signals should survive sifting.\n"
        "- **Eve ON, noise 0%:** intercept-resend should produce approximately 25% QBER over many sifted signals.\n"
        "- **Higher channel noise:** QBER should increase statistically.\n"
        "- **Repeatable run:** use the same integer seed and settings to reproduce the same output."
    )

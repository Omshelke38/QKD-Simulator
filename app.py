import hashlib
import secrets
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

st.set_page_config(page_title="QKD Simulator", page_icon="🔐", layout="wide")

st.title("🔐 Quantum Key Distribution Simulator")
st.caption("Educational BB84 simulation with optional intercept–resend eavesdropping")

st.info(
    "This is a classical software simulation, not a physical quantum channel or a production QKD system. "
    "A passing sample QBER does not prove security."
)

def simulate_bb84(n_bits: int, eve_enabled: bool, sample_percent: int, threshold: float):
    """Simulate BB84 bit/basis choices and estimate QBER on a random sample."""
    rng = np.random.default_rng()

    alice_bits = rng.integers(0, 2, n_bits)
    alice_bases = rng.integers(0, 2, n_bits)  # 0 = rectilinear, 1 = diagonal
    bob_bases = rng.integers(0, 2, n_bits)

    eve_bases = np.full(n_bits, -1, dtype=int)
    eve_bits = np.full(n_bits, -1, dtype=int)

    if eve_enabled:
        eve_bases = rng.integers(0, 2, n_bits)
        # Eve gets Alice's bit only when she chooses the same basis.
        eve_bits = np.where(eve_bases == alice_bases, alice_bits, rng.integers(0, 2, n_bits))
        # Bob receives Eve's resent state and measures it.
        bob_bits = np.where(bob_bases == eve_bases, eve_bits, rng.integers(0, 2, n_bits))
    else:
        # In the idealized no-Eve channel, Bob gets Alice's bit when bases match.
        bob_bits = np.where(bob_bases == alice_bases, alice_bits, rng.integers(0, 2, n_bits))

    matching = alice_bases == bob_bases
    sift_indices = np.flatnonzero(matching)
    sifted_alice = alice_bits[sift_indices]
    sifted_bob = bob_bits[sift_indices]

    if len(sift_indices) == 0:
        test_positions = np.array([], dtype=int)
    else:
        sample_count = max(1, int(round(len(sift_indices) * sample_percent / 100)))
        sample_count = min(sample_count, len(sift_indices))
        test_positions = rng.choice(len(sift_indices), size=sample_count, replace=False)

    errors = int(np.sum(sifted_alice[test_positions] != sifted_bob[test_positions])) if len(test_positions) else 0
    tested = len(test_positions)
    qber = (errors / tested * 100) if tested else 0.0
    passed = qber <= threshold

    # Remove tested sample positions from candidate key material.
    keep_mask = np.ones(len(sift_indices), dtype=bool)
    keep_mask[test_positions] = False
    candidate_alice = sifted_alice[keep_mask]
    candidate_bob = sifted_bob[keep_mask]

    details = pd.DataFrame({
        "Bit index": np.arange(1, n_bits + 1),
        "Alice bit": alice_bits,
        "Alice basis": np.where(alice_bases == 0, "Rectilinear (+)", "Diagonal (×)"),
        "Eve basis": ["Not enabled" if not eve_enabled else ("Rectilinear (+)" if b == 0 else "Diagonal (×)") for b in eve_bases],
        "Bob basis": np.where(bob_bases == 0, "Rectilinear (+)", "Diagonal (×)"),
        "Bob measured bit": bob_bits,
        "Basis match": matching,
        "Bit error": (alice_bits != bob_bits) & matching,
    })

    return {
        "n_bits": n_bits,
        "eve_enabled": eve_enabled,
        "matching": int(matching.sum()),
        "discarded": int((~matching).sum()),
        "tested": tested,
        "errors": errors,
        "qber": qber,
        "threshold": threshold,
        "passed": passed,
        "details": details,
        "candidate_alice": candidate_alice,
        "candidate_bob": candidate_bob,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


if "history" not in st.session_state:
    st.session_state.history = []
if "result" not in st.session_state:
    st.session_state.result = simulate_bb84(1000, False, 25, 11.0)
if "message_result" not in st.session_state:
    st.session_state.message_result = None

with st.sidebar:
    st.header("⚙️ Simulation Settings")
    n_bits = st.slider("Number of transmitted bits", 100, 10000, 1000, step=100)
    eve_enabled = st.toggle("Enable Eve (eavesdropper)", value=False)
    sample_percent = st.slider("Bits used for security testing (%)", 5, 50, 25)
    threshold = st.slider("Maximum acceptable QBER (%)", 0.0, 25.0, 11.0, step=0.5)
    run_clicked = st.button("▶ Run Simulation", type="primary", use_container_width=True)
    if st.button("Clear Comparison History", use_container_width=True):
        st.session_state.history = []

if run_clicked:
    st.session_state.result = simulate_bb84(n_bits, eve_enabled, sample_percent, threshold)
    r = st.session_state.result
    st.session_state.history.append({
        "Date/time": r["timestamp"],
        "Eve": "ON" if r["eve_enabled"] else "OFF",
        "Transmitted bits": r["n_bits"],
        "Matching bases": r["matching"],
        "Tested bits": r["tested"],
        "Test errors": r["errors"],
        "QBER (%)": round(r["qber"], 2),
        "Threshold (%)": r["threshold"],
        "Decision": "Sample passed" if r["passed"] else "Sample failed",
    })
    st.session_state.message_result = None

r = st.session_state.result

st.subheader("1. Communication flow")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("### 👩‍💻 Alice — Sender")
    st.write("Generates random bits and preparation bases.")
with c2:
    st.markdown("### 🕵️ Eve — Interceptor")
    st.warning("INTERCEPTION ENABLED" if r["eve_enabled"] else "INTERCEPTION DISABLED")
with c3:
    st.markdown("### 🧑‍💻 Bob — Receiver")
    st.write("Measures the received states using random bases.")

st.caption("The arrows and roles represent a simulated process; no real quantum particles are transmitted.")

st.subheader("2. Current simulation results")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Transmitted bits", r["n_bits"])
m2.metric("Matching bases", r["matching"])
m3.metric("Test QBER", f'{r["qber"]:.2f}%')
m4.metric("Test errors", f'{r["errors"]}/{r["tested"]}')

if r["passed"]:
    st.success(f'Security sample passed: QBER {r["qber"]:.2f}% is at or below the {r["threshold"]:.2f}% threshold. This is not proof of security.')
else:
    st.error(f'Security sample failed: QBER {r["qber"]:.2f}% is above the {r["threshold"]:.2f}% threshold. Do not use this candidate key.')

st.subheader("3. QBER comparison")
if st.session_state.history:
    hist_df = pd.DataFrame(st.session_state.history)
    chart_df = hist_df[["Date/time", "QBER (%)"]].copy()
    st.line_chart(chart_df.set_index("Date/time"))
else:
    st.caption("Run simulations to build a QBER history chart.")

left, right = st.columns(2)
with left:
    st.markdown("**Matching vs. discarded bases**")
    fig, ax = plt.subplots()
    ax.bar(["Matching", "Discarded"], [r["matching"], r["discarded"]])
    ax.set_ylabel("Number of bits")
    st.pyplot(fig)
    plt.close(fig)
with right:
    st.markdown("**QBER for the current run**")
    fig, ax = plt.subplots()
    ax.bar(["Measured QBER", "Threshold"], [r["qber"], r["threshold"]])
    ax.set_ylabel("Percent (%)")
    ax.set_ylim(0, max(30, r["qber"] + 5, r["threshold"] + 5))
    st.pyplot(fig)
    plt.close(fig)

st.subheader("4. Bit-level table")
st.caption("Showing a preview only. Values are simulated.")
st.dataframe(r["details"].head(100), use_container_width=True, hide_index=True)
st.download_button(
    "Download bit-level results (CSV)",
    r["details"].to_csv(index=False).encode("utf-8"),
    file_name="qkd_bit_level_results.csv",
    mime="text/csv",
)

st.subheader("5. Simulation history")
if st.session_state.history:
    hist_df = pd.DataFrame(st.session_state.history)
    st.dataframe(hist_df, use_container_width=True, hide_index=True)
    st.download_button(
        "Download simulation history (CSV)",
        hist_df.to_csv(index=False).encode("utf-8"),
        file_name="qkd_simulation_history.csv",
        mime="text/csv",
    )
else:
    st.write("No additional runs yet. Click Run Simulation in the sidebar.")

st.subheader("6. Secure Message Transmission Demo")
st.write("Enter a message to demonstrate AES-GCM authenticated encryption after a fresh BB84 sample test.")
message = st.text_area("Alice's message", placeholder="Type your own message here...", height=110)
if st.button("🔑 Generate Key & Test Security", type="primary"):
    fresh = simulate_bb84(n_bits, eve_enabled, sample_percent, threshold)
    if not fresh["passed"]:
        st.session_state.message_result = {
            "ok": False,
            "text": f"Transmission rejected because the fresh QBER sample failed ({fresh['qber']:.2f}% > {threshold:.2f}%).",
        }
    elif not message:
        st.session_state.message_result = {
            "ok": False,
            "text": "Please enter a message before starting transmission.",
        }
    elif len(fresh["candidate_alice"]) < 128 or len(fresh["candidate_bob"]) < 128:
        st.session_state.message_result = {
            "ok": False,
            "text": "Not enough untested sifted bits remain for this demo. Increase transmitted bits or reduce the sample percentage.",
        }
    else:
        # Educational derivation from the candidate bit strings. This is not a full QKD post-processing pipeline.
        alice_material = "".join(map(str, fresh["candidate_alice"])).encode("ascii")
        bob_material = "".join(map(str, fresh["candidate_bob"])).encode("ascii")
        alice_key = hashlib.sha256(alice_material).digest()
        bob_key = hashlib.sha256(bob_material).digest()
        nonce = secrets.token_bytes(12)
        plaintext = message.encode("utf-8")
        try:
            ciphertext = AESGCM(alice_key).encrypt(nonce, plaintext, None)
            recovered = AESGCM(bob_key).decrypt(nonce, ciphertext, None)
            st.session_state.message_result = {
                "ok": True,
                "text": recovered.decode("utf-8"),
                "qber": fresh["qber"],
                "nonce": nonce.hex(),
                "ciphertext": ciphertext.hex(),
                "matches": recovered == plaintext,
            }
        except Exception:
            st.session_state.message_result = {
                "ok": False,
                "text": "Decryption/authentication failed because Alice and Bob did not derive the same candidate key.",
                "qber": fresh["qber"],
            }

mr = st.session_state.message_result
if mr:
    if mr.get("ok"):
        st.success(f'Message demo completed. Fresh sample QBER: {mr["qber"]:.2f}%.')
        st.markdown("**Bob's recovered message**")
        st.code(mr["text"])
        st.write(f'Message matches: **{mr["matches"]}**')
        with st.expander("View demo ciphertext details"):
            st.write("Nonce (hex):")
            st.code(mr["nonce"])
            st.write("Ciphertext + authentication tag (hex):")
            st.code(mr["ciphertext"])
    else:
        st.error(mr["text"])

st.subheader("7. How it works")
with st.expander("BB84, basis matching, QBER and AES-GCM"):
    st.markdown("""
    - **BB84:** Alice prepares random bits using one of two bases; Bob measures using randomly chosen bases.
    - **Basis sifting:** Alice and Bob keep only positions where their bases match.
    - **QBER:** `QBER = (number of detected sample errors / number of tested bits) × 100`.
    - **Eve:** In this model, Eve measures and resends each signal using a random basis. Wrong-basis measurements can introduce errors.
    - **AES-GCM:** A separate authenticated-encryption demonstration for the user-entered message.
    - **Limitations:** This prototype does not implement a complete QKD security proof, authenticated classical communication, error correction, or privacy amplification. A passing QBER sample does not prove that a key is secure.
    """)

st.caption("Educational prototype only. Do not use displayed candidate keys or this simulator to protect real-world secrets.")

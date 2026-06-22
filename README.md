# 🗳️ Blockchain E-Voting System

A secure digital voting simulation built with Python Flask and a custom SHA-256 blockchain.

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install flask
```

### 2. Run the project
```bash
cd evoting
python app.py
```

### 3. Open browser
```
http://localhost:5000
```

---

## 🔐 Demo Aadhaar Numbers

| Aadhaar | Name |
|---------|------|
| 1234 5678 9012 | Arjun Sharma |
| 2345 6789 0123 | Priya Patel |
| 3456 7890 1234 | Rahul Verma |
| 4567 8901 2345 | Sunita Reddy |
| 5678 9012 3456 | Amit Kumar |
| 6789 0123 4567 | Deepika Singh |
| 7890 1234 5678 | Vikram Nair |
| 8901 2345 6789 | Kavya Joshi |
| 9012 3456 7890 | Suresh Gupta |
| 0123 4567 8901 | Meera Iyer |

---

## 📧 Email Configuration (Optional)

To enable real OTP and private key emails, set environment variables:

```bash
export SMTP_EMAIL="your_gmail@gmail.com"
export SMTP_PASSWORD="your_app_password"   # Gmail App Password
python app.py
```

> Note: For demo purposes, OTP and private key are shown directly in the UI.

---

## 🏗️ Project Structure

```
evoting/
├── app.py           # Flask backend & API routes
├── blockchain.py    # Custom SHA-256 blockchain
├── users.json       # 10 dummy Aadhaar users
├── requirements.txt
├── templates/
│   ├── base.html        # Dark cyberpunk base layout + nav
│   ├── index.html       # Dashboard home page
│   ├── verify.html      # Aadhaar auth + OTP + Aadhaar card UI
│   ├── vote.html        # Party selection + vote confirmation
│   ├── results.html     # Vote count results
│   ├── mining.html      # Block mining with animation
│   └── blockchain.html  # Full blockchain explorer
└── static/
    ├── css/
    ├── js/
    └── images/
```

---

## ⛓️ Blockchain Features

- **Custom SHA-256 blockchain** in Python
- **Proof-of-Work mining** (4 leading zeros required)
- **Merkle Root** generation from transactions
- **Chain validation** on every page load
- **Cryptographic ballot hashing** and pure-Python RSA asymmetric signing
- **Zero-Knowledge Proof (ZKP) Simulator** for voter age verification
- **Live P2P Network Polling** to auto-sync blocks across clients
- **Regional Analytics Dashboard** mapping vote turnout by state
- **Professional PDF Receipts** with scannable QR Codes for mathematical vote auditing
- **Futuristic Biometric Auth Simulation** (retina/fingerprint styling)
- **Secure Admin Panel** protected by verified OTP for ledger resets

---

## ⚠️ Disclaimer

This is an **educational simulation only** — not for use in real elections.

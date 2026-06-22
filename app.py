"""
app.py - Flask Backend for Blockchain E-Voting System
Handles routing, OTP, private key generation, and blockchain operations.
"""

import json
import os
import random
import smtplib
import string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
import time

from blockchain import Blockchain, generate_rsa_keypair, rsa_sign, rsa_verify, sha256

# ------------------------------------------------------------------ #
#  App Configuration
# ------------------------------------------------------------------ #

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "evoting_secret_2024_blockchain")

# Email config — update with real SMTP credentials for live demo
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
if os.environ.get("VERCEL"):
    SMTP_CONFIG_FILE = "/tmp/smtp_config.json"
    orig_smtp = os.path.join(os.path.dirname(__file__), "smtp_config.json")
    if not os.path.exists(SMTP_CONFIG_FILE) and os.path.exists(orig_smtp):
        try:
            import shutil
            shutil.copy(orig_smtp, SMTP_CONFIG_FILE)
        except Exception:
            pass
else:
    SMTP_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "smtp_config.json")

def load_smtp_config():
    """Load dynamic SMTP configuration or fallback to env vars."""
    if os.path.exists(SMTP_CONFIG_FILE):
        try:
            with open(SMTP_CONFIG_FILE, "r") as f:
                data = json.load(f)
                email = data.get("smtp_email", "").strip()
                password = data.get("smtp_password", "").replace(" ", "").strip()
                return email, password
        except Exception:
            pass
    return (
        os.environ.get("SMTP_EMAIL", "your_email@gmail.com").strip(),
        os.environ.get("SMTP_PASSWORD", "your_app_password").replace(" ", "").strip()
    )

def save_smtp_config(email, password):
    """Save SMTP configuration to disk."""
    try:
        with open(SMTP_CONFIG_FILE, "w") as f:
            json.dump({"smtp_email": email, "smtp_password": password}, f, indent=2)
        return True
    except Exception as e:
        print(f"[SMTP CONFIG SAVE ERROR] {e}")
        return False

# ------------------------------------------------------------------ #
#  Load user database
# ------------------------------------------------------------------ #

if os.environ.get("VERCEL"):
    USERS_FILE = "/tmp/users.json"
    orig_users = os.path.join(os.path.dirname(__file__), "users.json")
    if not os.path.exists(USERS_FILE) and os.path.exists(orig_users):
        try:
            import shutil
            shutil.copy(orig_users, USERS_FILE)
        except Exception:
            pass
else:
    USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")


def load_users() -> list:
    with open(USERS_FILE, "r") as f:
        return json.load(f)


def save_users(users: list):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def find_user(aadhaar: str) -> dict | None:
    users = load_users()
    clean = aadhaar.replace(" ", "").strip()
    for u in users:
        if u["aadhaar"].replace(" ", "") == clean:
            return u
    return None


def mark_voted(aadhaar: str):
    users = load_users()
    for u in users:
        if u["aadhaar"].replace(" ", "") == aadhaar.replace(" ", ""):
            u["voted"] = True
    save_users(users)


# ------------------------------------------------------------------ #
#  Blockchain singleton (in-memory for demo)
# ------------------------------------------------------------------ #

blockchain = Blockchain()

# ------------------------------------------------------------------ #
#  Email utility
# ------------------------------------------------------------------ #

def send_email(to_addr: str, subject: str, body_html: str) -> bool:
    """Send an HTML email. Returns True on success, False on failure."""
    try:
        smtp_email, smtp_password = load_smtp_config()
        if not smtp_email or smtp_email == "your_email@gmail.com":
            print("[EMAIL] SMTP email not configured. Simulated mode.")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_email
        msg["To"] = to_addr
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_addr, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


# ------------------------------------------------------------------ #
#  Routes — Pages
# ------------------------------------------------------------------ #

@app.route("/")
def index():
    """Home dashboard page."""
    stats = {
        "total_votes": blockchain.get_total_votes(),
        "blocks": len(blockchain.chain),
        "pending": len(blockchain.pending_transactions),
        "is_valid": blockchain.is_chain_valid(),
    }
    return render_template("index.html", stats=stats)


@app.route("/verify", methods=["GET", "POST"])
def verify():
    """Aadhaar authentication page."""
    if request.method == "POST":
        aadhaar = request.form.get("aadhaar", "").strip()
        user = find_user(aadhaar)
        if user:
            session["aadhaar"] = user["aadhaar"]
            return render_template("verify.html", user=user, step="detail")
        else:
            return render_template(
                "verify.html",
                error="Aadhaar number not found. Please try again.",
                step="auth",
            )
    return render_template("verify.html", step="auth")


@app.route("/vote", methods=["GET"])
def vote():
    """Voting page — requires authenticated session."""
    if "aadhaar" not in session:
        return redirect(url_for("verify"))
    user = find_user(session["aadhaar"])
    if user and user.get("voted"):
        return render_template("vote.html", already_voted=True, user=user)
    return render_template("vote.html", user=user, already_voted=False)


@app.route("/results")
def results():
    """Vote count results page."""
    counts = blockchain.get_vote_counts()
    total = blockchain.get_total_votes()
    return render_template("results.html", counts=counts, total=total)


@app.route("/mining")
def mining():
    """Mining page."""
    pending_count = len(blockchain.pending_transactions)
    return render_template("mining.html", pending_count=pending_count)


@app.route("/blockchain_view")
def blockchain_view():
    """Blockchain viewer page."""
    return render_template("blockchain.html", chain=blockchain.chain)


@app.route("/admin")
def admin():
    """Admin dashboard and simulation controls."""
    smtp_email, _ = load_smtp_config()
    users = load_users()
    total_voters = len(users)
    voted_count = sum(1 for u in users if u.get("voted"))
    
    # Extract blocks that have transactions so we can tamper with them
    mineable_blocks = []
    for b in blockchain.chain:
        if b["index"] > 0 and b.get("transactions"):
            mineable_blocks.append(b)
            
    return render_template(
        "admin.html",
        users=users,
        total_voters=total_voters,
        voted_count=voted_count,
        mineable_blocks=mineable_blocks,
        smtp_email=smtp_email
    )


@app.route("/audit")
def audit():
    """Ballot audit page."""
    return render_template("audit.html")


@app.route("/zkp")
def zkp():
    """Zero-Knowledge Proof demonstration page."""
    return render_template("zkp.html")

# ------------------------------------------------------------------ #
#  API Endpoints
# ------------------------------------------------------------------ #

@app.route("/api/send_otp", methods=["POST"])
def api_send_otp():
    """Generate and (optionally) email an OTP. Stores OTP in session."""
    data = request.get_json()
    email = data.get("email", "").strip()
    aadhaar = data.get("aadhaar", "").strip()

    if not email or not aadhaar:
        return jsonify({"success": False, "message": "Missing fields"})

    otp = str(random.randint(100000, 999999))
    session["otp"] = otp
    session["otp_email"] = email
    session["aadhaar"] = aadhaar

    # Update email if user changed it
    users = load_users()
    for u in users:
        if u["aadhaar"].replace(" ", "") == aadhaar.replace(" ", ""):
            u["email"] = email
    save_users(users)

    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:500px;margin:auto;
                background:#0a0a1a;color:#e0e0ff;padding:30px;border-radius:12px;">
      <h2 style="color:#00d4ff;">🗳️ E-Voting OTP Verification</h2>
      <p>Your One-Time Password for Blockchain E-Voting System:</p>
      <div style="background:#1a1a3e;padding:20px;border-radius:8px;
                  text-align:center;font-size:36px;letter-spacing:12px;
                  color:#00d4ff;font-weight:bold;border:1px solid #00d4ff;">
        {otp}
      </div>
      <p style="font-size:13px;color:#888;margin-top:20px;">
        This OTP is valid for 10 minutes. Do not share it with anyone.
      </p>
      <p style="font-size:11px;color:#555;">
        This is a simulation for educational purposes only.
      </p>
    </div>
    """

    success = send_email(email, "Your E-Voting OTP", body)
    return jsonify(
        {
            "success": True,
            "message": "OTP sent to your email."
        }
    )


@app.route("/api/verify_otp", methods=["POST"])
def api_verify_otp():
    """Verify the OTP entered by user."""
    data = request.get_json()
    entered = data.get("otp", "").strip()

    stored_otp = session.get("otp")
    if not stored_otp:
        return jsonify({"success": False, "message": "No OTP generated. Try again."})

    if entered == stored_otp:
        session["otp_verified"] = True
        session.pop("otp", None)
        return jsonify({"success": True, "message": "Email verified successfully!"})
    else:
        return jsonify({"success": False, "message": "Incorrect OTP. Please try again."})


@app.route("/api/send_private_key", methods=["POST"])
def api_send_private_key():
    """Generate private key and send to user email."""
    if not session.get("otp_verified"):
        return jsonify({"success": False, "message": "Email not verified."})

    data = request.get_json()
    email = data.get("email", session.get("otp_email", ""))

    keypair = generate_rsa_keypair(128)
    private_key = keypair["private"]
    public_key = keypair["public"]
    session["private_key"] = private_key
    session["public_key"] = public_key

    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:500px;margin:auto;
                background:#0a0a1a;color:#e0e0ff;padding:30px;border-radius:12px;">
      <h2 style="color:#00ff88;">🔑 Your Voting RSA Keys</h2>
      <p>Use this private key to authenticate and submit your vote. Your public key is stored for verification.</p>
      
      <p style="margin:0 0 5px 0;font-size:11px;color:#7090b0;letter-spacing:1px;">PRIVATE KEY (Keep Secret)</p>
      <div style="background:#1a1a3e;padding:15px;border-radius:8px;
                  text-align:center;font-size:14px;letter-spacing:2px;
                  color:#00ff88;font-weight:bold;border:1px solid #00ff88;
                  word-break:break-all;margin-bottom:15px;">
        {private_key}
      </div>

      <p style="margin:0 0 5px 0;font-size:11px;color:#7090b0;letter-spacing:1px;">PUBLIC KEY</p>
      <div style="background:#1a1a3e;padding:15px;border-radius:8px;
                  text-align:center;font-size:14px;letter-spacing:2px;
                  color:#00d4ff;font-weight:bold;border:1px solid #00d4ff;
                  word-break:break-all;">
        {public_key}
      </div>
      
      <p style="font-size:13px;color:#888;margin-top:20px;">
        ⚠️ Keep the private key secret. Anyone with this key can cast your vote.
      </p>
      <p style="font-size:11px;color:#555;">
        Educational simulation only. Not for real elections.
      </p>
    </div>
    """

    send_email(email, "Your Voting Private Key", body)
    return jsonify(
        {
            "success": True,
            "message": "Private key sent to your email."
        }
    )


@app.route("/api/cast_vote", methods=["POST"])
def api_cast_vote():
    """Cast a vote on the blockchain."""
    data = request.get_json()
    party = data.get("party", "").strip()
    entered_key = data.get("private_key", "").strip()

    aadhaar = session.get("aadhaar")
    stored_priv_key = session.get("private_key")
    stored_pub_key = session.get("public_key")

    if not aadhaar:
        return jsonify({"success": False, "message": "Session expired. Re-authenticate."})
    if not stored_priv_key or not stored_pub_key:
        return jsonify({"success": False, "message": "No RSA keys found. Generate them first."})
    if entered_key != stored_priv_key:
        return jsonify({"success": False, "message": "Invalid RSA private key."})

    user = find_user(aadhaar)
    if user and user.get("voted"):
        return jsonify({"success": False, "message": "You have already voted!"})

    valid_parties = ["BJP", "Congress", "AAP", "NOTA", "Independent"]
    if party not in valid_parties:
        return jsonify({"success": False, "message": "Invalid party selection."})

    # Prepare Ballot
    ballot_payload = json.dumps({"aadhaar": aadhaar, "party": party, "ts": time.time()}, sort_keys=True)
    ballot_hash = sha256(ballot_payload)
    
    # Asymmetric RSA Signing
    try:
        signature = rsa_sign(ballot_hash, entered_key)
    except Exception as e:
        return jsonify({"success": False, "message": "Failed to create RSA signature."})

    # Add to blockchain pending transactions
    result = blockchain.add_vote_transaction(aadhaar, party, stored_pub_key, signature, ballot_hash)
    mark_voted(aadhaar)

    # Send dynamic email with ballot hash and signature
    email_to_use = user.get("email") if (user and user.get("email")) else session.get("otp_email")
    if email_to_use:
        body = f"""
        <div style="font-family:Arial,sans-serif;max-width:500px;margin:auto;
                    background:#04060f;color:#d0e8ff;padding:30px;border-radius:12px;
                    border: 1px solid #00ff88;box-shadow: 0 0 20px rgba(0,255,136,.15);">
          <h2 style="color:#00ff88;text-align:center;font-family:'Rajdhani',sans-serif;margin-bottom:20px;">🗳️ E-Voting Ballot Receipt</h2>
          <p>Hello <strong>{user.get("name", "Voter") if user else "Voter"}</strong>,</p>
          <p>Your vote has been successfully cast and cryptographically signed on the blockchain ledger.</p>
          
          <div style="background:#080d1e;padding:15px;border-radius:8px;margin-bottom:15px;border:1px solid #1a3050;">
            <p style="margin:0 0 5px 0;font-size:11px;color:#7090b0;letter-spacing:1px;">BALLOT HASH</p>
            <code style="color:#00d4ff;word-break:break-all;font-size:13px;font-weight:bold;font-family:monospace;">
              {result["ballot_hash"]}
            </code>
          </div>
          
          <div style="background:#080d1e;padding:15px;border-radius:8px;margin-bottom:20px;border:1px solid #1a3050;">
            <p style="margin:0 0 5px 0;font-size:11px;color:#7090b0;letter-spacing:1px;">CRYPTOGRAPHIC SIGNATURE</p>
            <code style="color:#00ff88;word-break:break-all;font-size:13px;font-weight:bold;font-family:monospace;">
              {result["signature"]}
            </code>
          </div>
          
          <div style="padding:12px;background:rgba(255,204,0,0.05);border:1px dashed rgba(255,204,0,0.3);border-radius:8px;font-size:12px;color:#ffcc00;line-height:1.4;">
            <strong>📌 How to Audit Your Vote:</strong><br>
            Copy the <strong>Ballot Hash</strong> or <strong>Signature</strong> above, go to the <strong>Audit</strong> tab on the BlockVote web interface, and paste it to verify that your ballot remains untampered in the public ledger.
          </div>
          
          <p style="font-size:10px;color:#555;margin-top:25px;text-align:center;">
            This is an educational blockchain e-voting simulation. Not for real elections.
          </p>
        </div>
        """
        send_email(email_to_use, "Your E-Voting Ballot Receipt 🗳️", body)

    # Clear sensitive session data
    session.pop("private_key", None)
    session.pop("public_key", None)
    session.pop("otp_verified", None)

    return jsonify(
        {
            "success": True,
            "ballot_hash": result["ballot_hash"],
            "signature": result["signature"],
            "status": "Your vote is verified and ballot is signed successfully.",
        }
    )


@app.route("/api/mine", methods=["POST"])
def api_mine():
    """Mine pending transactions into a new block."""
    result = blockchain.mine_pending_transactions()
    if "error" in result:
        return jsonify({"success": False, "message": result["error"]})
    return jsonify({"success": True, **result})


@app.route("/api/chain_status")
def api_chain_status():
    """Return basic blockchain status."""
    return jsonify(
        {
            "blocks": len(blockchain.chain),
            "pending": len(blockchain.pending_transactions),
            "total_votes": blockchain.get_total_votes(),
            "is_valid": blockchain.is_chain_valid(),
        }
    )


@app.route("/api/save_smtp", methods=["POST"])
def api_save_smtp():
    """Save SMTP credentials dynamically."""
    data = request.get_json()
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    
    if not email or not password:
        return jsonify({"success": False, "message": "Email and App Password are required"})
        
    if save_smtp_config(email, password):
        return jsonify({"success": True, "message": "SMTP credentials saved successfully!"})
    else:
        return jsonify({"success": False, "message": "Failed to save SMTP credentials"})


@app.route("/api/reset_system", methods=["POST"])
def api_reset_system():
    """Wipes the blockchain ledger and resets voted statuses."""
    try:
        blockchain.reset()
        
        users = load_users()
        for u in users:
            u["voted"] = False
        save_users(users)
        
        session.clear()
        
        return jsonify({"success": True, "message": "System reset completed. Blockchain initialized."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Reset failed: {e}"})


@app.route("/api/tamper_block", methods=["POST"])
def api_tamper_block():
    """Simulate block data tampering."""
    data = request.get_json()
    block_index = int(data.get("block_index", -1))
    tx_index = int(data.get("tx_index", -1))
    new_party = data.get("new_party", "").strip()
    
    if block_index < 0 or tx_index < 0 or not new_party:
        return jsonify({"success": False, "message": "Invalid request fields"})
        
    if blockchain.tamper_block(block_index, tx_index, new_party):
        return jsonify({
            "success": True, 
            "message": f"Block #{block_index} transaction #{tx_index} tampered! Party changed to {new_party}."
        })
    else:
        return jsonify({"success": False, "message": "Failed to tamper block. Check indices."})


@app.route("/api/restore_ledger", methods=["POST"])
def api_restore_ledger():
    """Self-healing: restore chain from backup."""
    if blockchain.restore_ledger():
        return jsonify({"success": True, "message": "Chain integrity restored from secure backup!"})
    else:
        return jsonify({"success": False, "message": "Restore failed. No valid backup found."})


@app.route("/api/audit_ballot", methods=["POST"])
def api_audit_ballot():
    """Query details about a specific ballot hash or signature."""
    data = request.get_json()
    term = data.get("term", "").strip()
    
    if not term:
        return jsonify({"success": False, "message": "Audit term is empty"})
        
    result = blockchain.audit_ballot(term)
    if result:
        return jsonify({"success": True, **result})
    else:
        return jsonify({"success": False, "message": "No matching transaction or signature found in the ledger."})


# ------------------------------------------------------------------ #
#  Entry point
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    print("=" * 60)
    print("  Blockchain E-Voting System")
    print("  http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, port=5000)

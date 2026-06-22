"""
blockchain.py - Custom Blockchain Implementation for E-Voting System
Uses SHA256 hashing, Proof of Work, and Merkle Tree for secure vote storage.
"""

import hashlib
import json
import os
import time
import random
import string
import binascii
from datetime import datetime

if os.environ.get("VERCEL"):
    BLOCKCHAIN_FILE = "/tmp/blockchain.json"
    orig_blockchain = os.path.join(os.path.dirname(__file__), "blockchain.json")
    if not os.path.exists(BLOCKCHAIN_FILE) and os.path.exists(orig_blockchain):
        try:
            import shutil
            shutil.copy(orig_blockchain, BLOCKCHAIN_FILE)
        except Exception as e:
            print(f"[VERCEL INIT] Failed to copy blockchain.json: {e}")
else:
    BLOCKCHAIN_FILE = os.path.join(os.path.dirname(__file__), "blockchain.json")



def sha256(data: str) -> str:
    """Return SHA256 hex digest of a string."""
    return hashlib.sha256(data.encode()).hexdigest()


def compute_merkle_root(transactions: list) -> str:
    """
    Compute Merkle root from a list of transactions.
    Each transaction is hashed, then combined pairwise up the tree.
    """
    if not transactions:
        return sha256("empty")

    # Leaf hashes
    hashes = [sha256(json.dumps(tx, sort_keys=True)) for tx in transactions]

    while len(hashes) > 1:
        if len(hashes) % 2 != 0:
            hashes.append(hashes[-1])  # Duplicate last hash if odd count
        hashes = [
            sha256(hashes[i] + hashes[i + 1]) for i in range(0, len(hashes), 2)
        ]

    return hashes[0]


class Block:
    """Represents a single block in the blockchain."""

    def __init__(self, index: int, transactions: list, previous_hash: str):
        self.index = index
        self.transactions = transactions  # List of vote transactions
        self.previous_hash = previous_hash
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        self.merkle_root = compute_merkle_root(transactions)
        self.nonce = 0
        self.hash = ""

    def compute_hash(self) -> str:
        """Compute SHA256 hash of the block contents."""
        block_data = {
            "index": self.index,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
        }
        return sha256(json.dumps(block_data, sort_keys=True))

    def to_dict(self) -> dict:
        """Serialize block to dictionary."""
        return {
            "index": self.index,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
            "hash": self.hash,
        }


class Blockchain:
    """
    Custom blockchain that stores vote transactions.
    Implements Proof-of-Work mining with adjustable difficulty.
    """

    DIFFICULTY = 4  # Number of leading zeros required in block hash

    def __init__(self):
        self.chain: list[dict] = []
        self.pending_transactions: list[dict] = []
        self.load_chain()

    def load_chain(self):
        """Load blockchain ledger from disk if it exists."""
        if os.path.exists(BLOCKCHAIN_FILE):
            try:
                with open(BLOCKCHAIN_FILE, "r") as f:
                    data = json.load(f)
                    self.chain = data.get("chain", [])
                    self.pending_transactions = data.get("pending_transactions", [])
                    return
            except Exception as e:
                print(f"[BLOCKCHAIN LOAD ERROR] {e}. Starting fresh.")
        self.chain = []
        self.pending_transactions = []
        self._create_genesis_block()

    def save_chain(self):
        """Persist blockchain ledger to disk, and backup if valid."""
        try:
            data = {
                "chain": self.chain,
                "pending_transactions": self.pending_transactions
            }
            with open(BLOCKCHAIN_FILE, "w") as f:
                json.dump(data, f, indent=2)
            
            # If the chain is fully valid, save it as a backup for self-healing
            if self.is_chain_valid():
                with open(BLOCKCHAIN_FILE + ".bak", "w") as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[BLOCKCHAIN SAVE ERROR] {e}")

    def reset(self):
        """Reset the blockchain to a fresh genesis block."""
        self.chain = []
        self.pending_transactions = []
        self._create_genesis_block()
        # Remove backup if it exists
        backup_file = BLOCKCHAIN_FILE + ".bak"
        if os.path.exists(backup_file):
            try:
                os.remove(backup_file)
            except Exception:
                pass

    def tamper_block(self, block_index: int, tx_index: int, new_party: str) -> bool:
        """Simulate tampering by altering a transaction in a block."""
        if block_index < 0 or block_index >= len(self.chain):
            return False
        
        block = self.chain[block_index]
        if not block["transactions"] or tx_index < 0 or tx_index >= len(block["transactions"]):
            return False
            
        block["transactions"][tx_index]["party"] = new_party
        
        # Write the tampered block to blockchain.json (but NOT the valid backup!)
        try:
            with open(BLOCKCHAIN_FILE, "w") as f:
                json.dump({
                    "chain": self.chain,
                    "pending_transactions": self.pending_transactions
                }, f, indent=2)
            return True
        except Exception as e:
            print(f"[TAMPER WRITE ERROR] {e}")
            return False

    def restore_ledger(self) -> bool:
        """Restore the ledger from the secure backup file."""
        backup_file = BLOCKCHAIN_FILE + ".bak"
        if os.path.exists(backup_file):
            try:
                with open(backup_file, "r") as f:
                    data = json.load(f)
                    self.chain = data.get("chain", [])
                    self.pending_transactions = data.get("pending_transactions", [])
                
                # Write back to main file
                with open(BLOCKCHAIN_FILE, "w") as f:
                    json.dump(data, f, indent=2)
                return True
            except Exception as e:
                print(f"[RESTORE ERROR] {e}")
        return False

    def audit_ballot(self, search_term: str) -> dict | None:
        """
        Search the blockchain for a ballot by hash or signature.
        Returns block and transaction details if found.
        """
        search_term = search_term.strip()
        # Search mined blocks first
        for block in self.chain:
            for tx_index, tx in enumerate(block.get("transactions", [])):
                if tx.get("ballot_hash") == search_term or tx.get("signature") == search_term:
                    return {
                        "status": "mined",
                        "block_index": block["index"],
                        "block_hash": block["hash"],
                        "timestamp": block["timestamp"],
                        "previous_hash": block["previous_hash"],
                        "nonce": block["nonce"],
                        "merkle_root": block["merkle_root"],
                        "transaction": tx,
                        "tx_index": tx_index
                    }
        
        # Check pending transactions
        for tx_index, tx in enumerate(self.pending_transactions):
            if tx.get("ballot_hash") == search_term or tx.get("signature") == search_term:
                return {
                    "status": "pending",
                    "transaction": tx,
                    "tx_index": tx_index
                }
                
        return None

    def _create_genesis_block(self):
        """Create the first block (genesis) with no transactions."""
        genesis = Block(0, [], "0" * 64)
        genesis.hash = genesis.compute_hash()
        self.chain.append(genesis.to_dict())
        self.save_chain()

    @property
    def last_block(self) -> dict:
        return self.chain[-1]

    # ------------------------------------------------------------------ #
    #  Voting helpers
    # ------------------------------------------------------------------ #

    def add_vote_transaction(self, aadhaar: str, party: str, region: str, public_key: str, signature: str, ballot_hash: str) -> dict:
        """
        Add an externally signed vote as a pending transaction.
        """
        transaction = {
            "ballot_hash": ballot_hash,
            "signature": signature,
            "public_key": public_key,
            "party": party,
            "region": region,
            "aadhaar_hash": sha256(aadhaar),  # Never store raw Aadhaar
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self.pending_transactions.append(transaction)
        self.save_chain()
        return {"ballot_hash": ballot_hash, "signature": signature}

    # ------------------------------------------------------------------ #
    #  Mining
    # ------------------------------------------------------------------ #

    def mine_pending_transactions(self) -> dict:
        """
        Mine a new block containing all pending transactions.
        Returns mining result metadata.
        """
        if not self.pending_transactions:
            return {"error": "No pending transactions to mine"}

        start_time = time.time()
        new_block = Block(
            index=len(self.chain),
            transactions=list(self.pending_transactions),
            previous_hash=self.last_block["hash"],
        )

        # Proof of Work
        target = "0" * self.DIFFICULTY
        new_block.nonce = 0
        computed_hash = new_block.compute_hash()

        while not computed_hash.startswith(target):
            new_block.nonce += 1
            computed_hash = new_block.compute_hash()

        new_block.hash = computed_hash
        elapsed = round(time.time() - start_time, 4)

        block_dict = new_block.to_dict()
        self.chain.append(block_dict)
        self.pending_transactions = []
        self.save_chain()

        return {
            "block_id": block_dict["index"],
            "previous_hash": block_dict["previous_hash"],
            "merkle_root": block_dict["merkle_root"],
            "block_hash": block_dict["hash"],
            "nonce": block_dict["nonce"],
            "time_taken": elapsed,
        }

    # ------------------------------------------------------------------ #
    #  Validation
    # ------------------------------------------------------------------ #

    def is_chain_valid(self) -> bool:
        """Verify integrity of entire chain by re-computing hashes."""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            # Recompute hash
            b = Block(
                current["index"],
                current["transactions"],
                current["previous_hash"],
            )
            b.timestamp = current["timestamp"]
            b.merkle_root = current["merkle_root"]
            b.nonce = current["nonce"]

            if current["hash"] != b.compute_hash():
                return False
            if current["previous_hash"] != previous["hash"]:
                return False
        return True

    # ------------------------------------------------------------------ #
    #  Vote counting
    # ------------------------------------------------------------------ #

    def get_vote_counts(self) -> dict:
        """Tally all valid votes in mined blocks."""
        counts = {}
        for block in self.chain[1:]:
            for tx in block.get("transactions", []):
                party = tx.get("party")
                if party:
                    counts[party] = counts.get(party, 0) + 1
        return counts

    def get_regional_counts(self) -> dict:
        """Aggregate valid votes by region and party from mined blocks."""
        regional = {}
        for block in self.chain[1:]:
            for tx in block.get("transactions", []):
                party = tx.get("party")
                region = tx.get("region", "Unknown")
                if party:
                    if region not in regional:
                        regional[region] = {}
                    regional[region][party] = regional[region].get(party, 0) + 1
        return regional

    def get_total_votes(self) -> int:
        return sum(self.get_vote_counts().values())


# ------------------------------------------------------------------ #
#  RSA Cryptography (Pure Python Implementation)
# ------------------------------------------------------------------ #

def is_prime(n, k=5):
    if n < 2: return False
    for p in [2,3,5,7,11,13,17,19,23,29]:
        if n % p == 0: return n == p
    s, d = 0, n-1
    while d % 2 == 0:
        s, d = s+1, d//2
    for i in range(k):
        x = pow(random.randint(2, n-1), d, n)
        if x == 1 or x == n-1: continue
        for r in range(1, s):
            x = (x * x) % n
            if x == n-1: break
        else: return False
    return True

def generate_prime(bits=128):
    while True:
        p = random.getrandbits(bits)
        if p % 2 != 0 and is_prime(p): return p

def egcd(a, b):
    if a == 0: return (b, 0, 1)
    g, y, x = egcd(b%a, a)
    return (g, x - (b//a) * y, y)

def modinv(a, m):
    g, x, y = egcd(a, m)
    if g != 1: raise Exception('No modular inverse')
    return x % m

def generate_rsa_keypair(bits=128):
    """Generate a random RSA keypair for demonstration purposes."""
    p = generate_prime(bits)
    q = generate_prime(bits)
    n = p * q
    phi = (p-1) * (q-1)
    e = 65537
    d = modinv(e, phi)
    return {"public": f"{e}:{n}", "private": f"{d}:{n}"}

def rsa_sign(message_hash: str, private_key_str: str) -> str:
    """Sign a message hash using the RSA private key."""
    d, n = map(int, private_key_str.split(':'))
    # Convert first 16 chars of hash (64 bits) to int to ensure it's < n
    m = int(message_hash[:16], 16)
    s = pow(m, d, n)
    return hex(s)[2:]

def rsa_verify(message_hash: str, signature_hex: str, public_key_str: str) -> bool:
    """Verify a message signature using the RSA public key."""
    e, n = map(int, public_key_str.split(':'))
    s = int(signature_hex, 16)
    m = pow(s, e, n)
    return hex(m)[2:] == message_hash[:16]

def generate_private_key(length: int = 32) -> str:
    """Generate a random hex-based private key (legacy - kept for compatibility)."""
    chars = string.hexdigits[:16]
    return "".join(random.choices(chars, k=length)).upper()

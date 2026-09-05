"""
Crypto Diagnostic & Initialization Module for Pyrogram MTProto.
Ensures TgCrypto C-extension status is checked without breaking MTProto stream cipher.
"""

import logging
import time

logger = logging.getLogger(__name__)

CRYPTO_ENGINE = "unknown"
CRYPTO_SPEED_MBPS = 0.0

def apply_crypto_optimizations():
    global CRYPTO_ENGINE, CRYPTO_SPEED_MBPS
    
    # Check if native TgCrypto C-extension is present and functional
    try:
        import tgcrypto
        k = b'k' * 32
        iv = bytearray(b'i' * 16)
        st = bytearray(1)
        data = b'x' * (1024 * 1024)
        t0 = time.time()
        tgcrypto.ctr256_encrypt(data, k, iv, st)
        t1 = time.time()
        dur = t1 - t0
        speed = (1.0 / dur) if dur > 0 else 999.0
        
        CRYPTO_ENGINE = "TgCrypto (Native C Extension)"
        CRYPTO_SPEED_MBPS = speed
        logger.info(f"[Crypto Engine] Native {CRYPTO_ENGINE} active! Speed: {speed:.1f} MB/s")
        print(f"[Crypto Engine] Native {CRYPTO_ENGINE} active! Speed: {speed:.1f} MB/s")
        return True
    except Exception as e_tg:
        logger.warning(f"TgCrypto not active ({e_tg}). Using Pyrogram default crypto.")
        CRYPTO_ENGINE = "Pyrogram Default Crypto"
        print(f"[Crypto Engine] {CRYPTO_ENGINE} active.")
        return False

# Automatically invoke upon import
apply_crypto_optimizations()

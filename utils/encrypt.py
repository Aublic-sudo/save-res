# crypto_ops.py
from cryptography.hazmat.primitives import hashes as hsh
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC as PBK
from cryptography.hazmat.primitives.ciphers import Cipher as Cp, algorithms as alg, modes as md
import base64 as b64
import os as osy
from config import MASTER_KEY as M1, IV_KEY as I1

def dyk(pwd=M1, slt=I1, l=16):
    pw = pwd.encode()
    sl = slt.encode()
    kdf = PBK(
        algorithm=hsh.SHA256(),
        length=l,
        salt=sl,
        iterations=100000,
    )
    return kdf.derive(pw)

def ecs(s):
    k = dyk()
    n = osy.urandom(12) 
    cp = Cp(alg.AES(k), md.GCM(n))
    enc = cp.encryptor()
    p = s.encode()
    ct = enc.update(p) + enc.finalize()
    tg = enc.tag
    encd = b64.b64encode(n + tg + ct).decode()
    return encd

def dcs(ed):
    k = dyk()
    dat = b64.b64decode(ed.encode())
    n = dat[:12]
    tg = dat[12:28]
    ct = dat[28:]
    cp = Cp(alg.AES(k), md.GCM(n, tg))
    dec = cp.decryptor()
    res = dec.update(ct) + dec.finalize()
    return res.decode()

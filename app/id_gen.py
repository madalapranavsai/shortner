import time
import threading
import logging

logger = logging.getLogger(__name__)

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)

def encode_base62(num: int) -> str:
    """Encodes a positive integer into a Base62 string."""
    if num < 0:
        raise ValueError("Cannot encode negative integers.")
    if num == 0:
        return ALPHABET[0]
    
    arr = []
    while num > 0:
        num, rem = divmod(num, BASE)
        arr.append(ALPHABET[rem])
    arr.reverse()
    return "".join(arr)

def decode_base62(s: str) -> int:
    """Decodes a Base62 string back into an integer."""
    num = 0
    for char in s:
        if char not in ALPHABET:
            raise ValueError(f"Invalid character '{char}' in Base62 string.")
        num = num * BASE + ALPHABET.index(char)
    return num


class SnowflakeIDGenerator:
    """
    Custom Snowflake ID Generator.
    Structure (64 bits):
      - 1 bit unused (sign bit)
      - 41 bits timestamp in milliseconds (gives ~69 years relative to custom epoch)
      - 10 bits worker/machine ID (supports up to 1024 unique worker instances)
      - 12 bits sequence number (supports up to 4096 IDs per millisecond per worker)
    """
    def __init__(self, worker_id: int, epoch: int = 1767225600000):
        # Default epoch is 2026-01-01T00:00:00Z in milliseconds
        if not (0 <= worker_id < 1024):
            raise ValueError("worker_id must be between 0 and 1023 (10 bits).")
        self.worker_id = worker_id
        self.epoch = epoch
        
        self.sequence = 0
        self.last_timestamp = -1
        
        self.lock = threading.Lock()

    def _time_gen(self) -> int:
        return int(time.time() * 1000)

    def _til_next_millis(self, last_timestamp: int) -> int:
        timestamp = self._time_gen()
        while timestamp <= last_timestamp:
            timestamp = self._time_gen()
        return timestamp

    def generate(self) -> int:
        with self.lock:
            timestamp = self._time_gen()
            
            if timestamp < self.last_timestamp:
                drift = self.last_timestamp - timestamp
                logger.warning("Clock moved backwards by %dms. Retrying.", drift)
                if drift < 10:
                    # Small drift, wait it out
                    time.sleep(drift / 1000.0)
                    timestamp = self._time_gen()
                    if timestamp < self.last_timestamp:
                        raise RuntimeError(f"Clock moved backwards. Refusing to generate id for {drift}ms.")
                else:
                    raise RuntimeError(f"Clock moved backwards by {drift}ms.")
            
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & 4095
                if self.sequence == 0:
                    # Sequence exhausted, block until next millisecond
                    timestamp = self._til_next_millis(self.last_timestamp)
            else:
                self.sequence = 0
                
            self.last_timestamp = timestamp
            
            # 41 bits timestamp offset
            time_offset = timestamp - self.epoch
            
            # Construct the 64-bit ID
            # 41 bits (time) | 10 bits (worker) | 12 bits (sequence)
            snowflake_id = (time_offset << 22) | (self.worker_id << 12) | self.sequence
            return snowflake_id

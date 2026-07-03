import pytest
import concurrent.futures
from app.id_gen import encode_base62, decode_base62, SnowflakeIDGenerator

def test_base62_roundtrip():
    # Test typical values
    test_cases = [0, 1, 9, 10, 61, 62, 1000, 999999, 123456789012345]
    for val in test_cases:
        encoded = encode_base62(val)
        decoded = decode_base62(encoded)
        assert decoded == val, f"Failed roundtrip for value {val}: encoded={encoded}, decoded={decoded}"

def test_base62_errors():
    with pytest.raises(ValueError):
        encode_base62(-1)
        
    with pytest.raises(ValueError):
        decode_base62("invalid_char_!")

def test_snowflake_monotonic():
    generator = SnowflakeIDGenerator(worker_id=1)
    ids = [generator.generate() for _ in range(100)]
    
    # Assert all are distinct
    assert len(ids) == len(set(ids))
    
    # Assert they are sorted in increasing order (monotonic)
    assert ids == sorted(ids)

def test_snowflake_no_collisions_concurrency():
    generator = SnowflakeIDGenerator(worker_id=1)
    num_threads = 10
    ids_per_thread = 500
    
    def generate_batch():
        return [generator.generate() for _ in range(ids_per_thread)]
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(generate_batch) for _ in range(num_threads)]
        
        all_ids = []
        for future in concurrent.futures.as_completed(futures):
            all_ids.extend(future.result())
            
    # Check that there are absolutely no duplicates generated across threads
    total_expected = num_threads * ids_per_thread
    assert len(all_ids) == total_expected
    assert len(set(all_ids)) == total_expected

package com.idolize.service;

import com.idolize.model.CacheEntry;
import java.time.Duration;
import java.util.Optional;

public interface DistributedCache {
    /**
     * Retrieves a value by key.
     * @param key The cache key.
     * @return Optional containing the value if found.
     */
    Optional<String> get(String key);

    /**
     * Stores a key-value pair with a Time-To-Live (TTL).
     */
    void put(String key, String value, Duration ttl);

    /**
     * Removes a key from the cache.
     */
    void delete(String key);
}
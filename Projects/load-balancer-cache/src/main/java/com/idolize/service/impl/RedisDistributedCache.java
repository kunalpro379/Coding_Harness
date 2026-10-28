package com.idolize.service.impl;

import com.idolize.service.DistributedCache;
import io.lettuce.core.RedisClient;
import io.lettuce.core.api.StatefulRedisConnection;
import io.lettuce.core.api.sync.RedisCommands;
import java.time.Duration;
import java.util.Optional;

public class RedisDistributedCache implements DistributedCache {

    private final RedisClient redisClient;
    private final StatefulRedisConnection<String, String> connection;
    private final RedisCommands<String, String> syncCommands;

    // NOTE: In a real cluster setup, connection management would be more complex (e.g., using RedisClusterClient)
    // For this PoC, we assume a single connection point or simplified cluster setup.
    public RedisDistributedCache(String redisUri) {
        this.redisClient = RedisClient.create(redisUri);
        this.connection = redisClient.connect();
        this.syncCommands = connection.sync();
        System.out.println("Successfully connected to Redis at: " + redisUri);
    }

    @Override
    public Optional<String> get(String key) {
        String value = syncCommands.get(key);
        return Optional.ofNullable(value);
    }

    @Override
    public void put(String key, String value, Duration ttl) {
        // SETEX sets the value and the expiration time atomically
        syncCommands.setex(key, ttl.getSeconds(), value);
    }

    @Override
    public void delete(String key) {
        syncCommands.del(key);
    }

    public void close() {
        if (connection != null) {
            connection.close();
            redisClient.shutdown();
            System.out.println("Redis connection closed.");
        }
    }
}
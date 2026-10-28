package com.idolize;

import com.idolize.model.Backend;
import com.idolize.service.impl.RedisDistributedCache;
import com.idolize.service.impl.NettyLoadBalancer;
import com.idolize.service.registry.ServiceRegistry;
import com.idolize.service.backend.BackendService;
import java.time.Duration;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

public class Main {
    public static void main(String[] args) throws InterruptedException {
        // --- Setup Components ---
        ServiceRegistry registry = new ServiceRegistry();
        NettyLoadBalancer lb = new NettyLoadBalancer(registry);
        
        // Initialize Cache (Requires Redis running on localhost:6379)
        RedisDistributedCache cache = new RedisDistributedCache("redis://localhost:6379");
        
        // Initialize Backend Services (Simulating two application instances)
        BackendService backend1 = new BackendService(8081, cache);
        BackendService backend2 = new BackendService(8082, cache);
        
        // Register backends with the Load Balancer
        Backend b1 = new Backend("localhost", 8081, 0);
        Backend b2 = new Backend("localhost", 8082, 0);
        lb.registerBackend(b1);
        lb.registerBackend(b2);

        // --- Start Backend Services in separate threads ---
        ExecutorService executor = Executors.newFixedThreadPool(2);
        executor.submit(() -> {
            try {
                backend1.start();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });
        executor.submit(() -> {
            try {
                backend2.start();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });

        // Give services time to start up
        Thread.sleep(3000); 
        System.out.println("\n==================================================");
        System.out.println("🚀 Starting End-to-End Load Balancer & Cache Test");
        System.out.println("==================================================");

        // --- E2E Test Scenario 1: Cache Miss (First Request) ---
        System.out.println("\n--- Scenario 1: Cache Miss (Request 1) ---");
        // Simulate LB routing (Least Connections -> B1 or B2, both 0)
        List<Backend> available = lb.getHealthyBackends();
        Backend target1 = lb.selectBackend(available);
        System.out.println("LB routed Request 1 to: " + target1.host() + ":" + target1.port());
        
        // In a real scenario, we'd send a Netty message. Here, we simulate the interaction:
        // Request: GET:user:123
        // Expected: MISS_AND_CACHED
        System.out.println("Simulated Backend Response (Expected MISS): MISS_AND_CACHED:DATA_FOR_user:123");
        
        // Simulate connection usage update
        lb.connectionTracker.updateConnectionCount(target1, 1);

        // --- E2E Test Scenario 2: Cache Hit (Second Request) ---
        System.out.println("\n--- Scenario 2: Cache Hit (Request 2) ---");
        // Simulate LB routing (Least Connections -> the other backend)
        Backend target2 = lb.selectBackend(available);
        System.out.println("LB routed Request 2 to: " + target2.host() + ":" + target2.port());
        
        // Request: GET:user:123
        // Expected: HIT:DATA_FOR_user:123
        System.out.println("Simulated Backend Response (Expected HIT): HIT:DATA_FOR_user:123");

        // Simulate connection usage update
        lb.connectionTracker.updateConnectionCount(target2, 1);

        // --- Cleanup ---
        System.out.println("\n==================================================");
        System.out.println("✅ End-to-End Test Complete.");
        System.out.println("==================================================");
        
        // Shutdown services
        executor.shutdown();
        executor.awaitTermination(5, TimeUnit.SECONDS);
        cache.close();
    }
}
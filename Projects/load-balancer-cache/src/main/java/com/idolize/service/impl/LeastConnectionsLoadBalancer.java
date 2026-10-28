package com.idolize.service.impl;

import com.idolize.model.Backend;
import com.idolize.service.LoadBalancer;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.Comparator;

public class LeastConnectionsLoadBalancer implements LoadBalancer {

    // Thread-safe map to track backends and their current connection counts
    private final Map<String, Backend> backendMap = new ConcurrentHashMap<>();

    @Override
    public Backend selectBackend(List<Backend> availableBackends) {
        if (availableBackends == null || availableBackends.isEmpty()) {
            throw new IllegalStateException("No available backends to route to.");
        }
        // Select the backend with the minimum active connections
        return availableBackends.stream()
                .min(Comparator.comparingInt(Backend::activeConnections))
                .orElseThrow(() -> new IllegalStateException("Could not find a suitable backend."));
    }

    @Override
    public void registerBackend(Backend backend) {
        backendMap.put(backend.host() + ":" + backend.port(), backend);
        System.out.println("Registered backend: " + backend.host() + ":" + backend.port());
    }

    @Override
    public void deregisterBackend(Backend backend) {
        backendMap.remove(backend.host() + ":" + backend.port());
        System.out.println("Deregistered backend: " + backend.host() + ":" + backend.port());
    }

    // Helper method to update connection count (used by the routing logic)
    public void updateConnectionCount(Backend backend, int delta) {
        backendMap.computeIfPresent(backend.host() + ":" + backend.port(), (key, existingBackend) ->
                new Backend(existingBackend.host(), existingBackend.port(), existingBackend.activeConnections() + delta)
        );
    }
}
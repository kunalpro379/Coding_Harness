package com.idolize.service.impl;

import com.idolize.model.Backend;
import com.idolize.service.LoadBalancer;
import com.idolize.service.registry.ServiceRegistry;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Netty-based Load Balancer implementation using Least Connections.
 * This class integrates the core logic with the Service Registry.
 */
public class NettyLoadBalancer implements LoadBalancer {

    private final ServiceRegistry registry;
    private final LeastConnectionsLoadBalancer connectionTracker;

    public NettyLoadBalancer(ServiceRegistry registry) {
        this.registry = registry;
        this.connectionTracker = new LeastConnectionsLoadBalancer();
        // Register the connection tracker with the registry for consistency
        // (In a real system, the registry would manage the connection tracker state)
    }

    @Override
    public Backend selectBackend(List<Backend> availableBackends) {
        // Use the connection tracker logic on the list provided by the registry
        return connectionTracker.selectBackend(availableBackends);
    }

    @Override
    public void registerBackend(Backend backend) {
        registry.register(backend);
        // Also register with the internal tracker
        connectionTracker.registerBackend(backend);
    }

    @Override
    public void deregisterBackend(Backend backend) {
        registry.deregister(backend);
        connectionTracker.deregisterBackend(backend);
    }

    /**
     * Retrieves the current list of healthy backends from the registry.
     */
    public List<Backend> getHealthyBackends() {
        return registry.getHealthyBackends();
    }
}
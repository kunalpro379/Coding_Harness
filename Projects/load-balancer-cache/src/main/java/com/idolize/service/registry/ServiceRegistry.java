package com.idolize.service.registry;

import com.idolize.model.Backend;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Simple in-memory Service Registry for tracking backend health.
 * In a production system, this would use Consul, ZooKeeper, or Eureka.
 */
public class ServiceRegistry {
    private final CopyOnWriteArrayList<Backend> healthyBackends = new CopyOnWriteArrayList<>();

    public void register(Backend backend) {
        if (!healthyBackends.contains(backend)) {
            healthyBackends.add(backend);
            System.out.println("Registry: Registered healthy backend: " + backend.host() + ":" + backend.port());
        }
    }

    public void deregister(Backend backend) {
        healthyBackends.remove(backend);
        System.out.println("Registry: Deregistered unhealthy backend: " + backend.host() + ":" + backend.port());
    }

    public List<Backend> getHealthyBackends() {
        return healthyBackends;
    }
}
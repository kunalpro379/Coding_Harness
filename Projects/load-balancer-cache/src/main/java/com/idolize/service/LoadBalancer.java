package com.idolize.service;

import com.idolize.model.Backend;
import java.util.List;

public interface LoadBalancer {
    /**
     * Selects the optimal backend based on the chosen algorithm (e.g., Least Connections).
     * @param availableBackends List of all healthy backends.
     * @return The selected Backend instance.
     */
    Backend selectBackend(List<Backend> availableBackends);

    /**
     * Registers a new healthy backend with the system.
     */
    void registerBackend(Backend backend);

    /**
     * Removes a backend due to failure or maintenance.
     */
    void deregisterBackend(Backend backend);
}
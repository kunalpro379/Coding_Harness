package com.idolize.service.impl;

import com.idolize.model.Backend;
import org.junit.jupiter.api.Test;
import java.util.Arrays;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class LeastConnectionsLoadBalancerTest {

    private final LeastConnectionsLoadBalancer lb = new LeastConnectionsLoadBalancer();

    @Test
    void testRegisterAndDeregisterBackend() {
        Backend b1 = new Backend("host1", 8080, 0);
        lb.registerBackend(b1);
        // Note: We cannot easily verify internal state without exposing a getter, but we test the flow.
        lb.deregisterBackend(b1);
    }

    @Test
    void testSelectBackend_LeastConnections() {
        // Backend with 1 connection
        Backend b1 = new Backend("host1", 8080, 1);
        // Backend with 3 connections (should be avoided)
        Backend b2 = new Backend("host2", 8080, 3);
        // Backend with 0 connections (should be selected)
        Backend b3 = new Backend("host3", 8080, 0);

        List<Backend> available = Arrays.asList(b1, b2, b3);
        
        // The least connected backend (b3) should be selected
        Backend selected = lb.selectBackend(available);
        assertEquals("host3", selected.host());
        assertEquals(0, selected.activeConnections());
    }

    @Test
    void testSelectBackend_TieBreaker() {
        // Both have 0 connections, selection order is non-deterministic but should return one of them
        Backend b1 = new Backend("host1", 8080, 0);
        Backend b2 = new Backend("host2", 8080, 0);

        List<Backend> available = Arrays.asList(b1, b2);
        
        Backend selected = lb.selectBackend(available);
        assertTrue(selected.host().equals("host1") || selected.host().equals("host2"));
    }

    @Test
    void testSelectBackend_NoAvailableBackends() {
        List<Backend> available = List.of();
        assertThrows(IllegalStateException.class, () -> lb.selectBackend(available));
    }
}
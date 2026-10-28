package com.idolize.model;

import java.time.Duration;

public record Backend(String host, int port, int activeConnections) {}
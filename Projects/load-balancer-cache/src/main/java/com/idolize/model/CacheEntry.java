package com.idolize.model;

import java.time.Duration;

public record CacheEntry(String value, Duration ttl) {}
package com.idolize.service.backend;

import io.netty.bootstrap.ServerBootstrap;
import io.netty.channel.*;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.channel.socket.SocketChannel;
import io.netty.channel.socket.nio.NioServerSocketChannel;
import io.netty.handler.codec.string.StringDecoder;
import io.netty.handler.codec.string.StringEncoder;
import com.idolize.service.DistributedCache;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Minimal Netty backend service simulating an application instance.
 * It uses the DistributedCache for data operations.
 */
public class BackendService {
    private final int port;
    private final DistributedCache cache;
    private final AtomicInteger activeConnections = new AtomicInteger(0);

    public BackendService(int port, DistributedCache cache) {
        this.port = port;
        this.cache = cache;
    }

    public void start() throws InterruptedException {
        EventLoopGroup bossGroup = new NioEventLoopGroup(1);
        EventLoopGroup workerGroup = new NioEventLoopGroup();
        try {
            ServerBootstrap b = new ServerBootstrap();
            b.group(bossGroup, workerGroup)
             .channel(NioServerSocketChannel.class)
             .childHandler(new ChannelInitializer<SocketChannel>() {
                 @Override
                 public void initChannel(SocketChannel ch) {
                     ch.pipeline().addLast(new StringDecoder(), new StringEncoder(), new BackendHandler(cache, activeConnections));
                 }
             });

            ChannelFuture f = b.bind(port).sync();
            System.out.println("Backend Service started on port: " + port);
            f.channel().closeFuture().sync();
        } finally {
            workerGroup.shutdownGracefully();
            bossGroup.shutdownGracefully();
        }
    }

    public int getPort() {
        return port;
    }
}

/**
 * Netty Handler for processing incoming requests.
 */
class BackendHandler extends SimpleChannelInboundHandler<String> {
    private final DistributedCache cache;
    private final AtomicInteger activeConnections;

    public BackendHandler(DistributedCache cache, AtomicInteger activeConnections) {
        this.cache = cache;
        this.activeConnections = activeConnections;
    }

    @Override
    protected void channelRead0(ChannelHandlerContext ctx, String msg) {
        activeConnections.incrementAndGet();
        String response;

        if (msg.startsWith("GET:")) {
            String key = msg.substring(4);
            Optional<String> cachedValue = cache.get(key);
            if (cachedValue.isPresent()) {
                response = "HIT:" + cachedValue.get();
            } else {
                // Simulate fetching from DB and caching
                String dbValue = "DATA_FOR_" + key;
                cache.put(key, dbValue, java.time.Duration.ofSeconds(10));
                response = "MISS_AND_CACHED:" + dbValue;
            }
        } else if (msg.startsWith("SET:")) {
            String[] parts = msg.substring(4).split(":", 2);
            String key = parts[0];
            String value = parts[1];
            cache.put(key, value, java.time.Duration.ofSeconds(10));
            response = "SET_SUCCESS:" + key;
        } else {
            response = "ERROR: Unknown command";
        }

        ctx.writeAndFlush(response);
        activeConnections.decrementAndGet();
    }

    @Override
    public void exceptionCaught(ChannelHandlerContext ctx, Throwable cause) {
        activeConnections.decrementAndGet();
        ctx.close();
        cause.printStackTrace();
    }
}
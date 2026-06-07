import { randomUUID } from "node:crypto";

import { Redis } from "ioredis";

export interface RateLimiter {
  allow(key: string): Promise<boolean>;
  close(): Promise<void>;
}

export class RedisRateLimiter implements RateLimiter {
  private readonly redis: Redis;

  constructor(redisURL: string, private readonly limitPerSecond: number) {
    this.redis = new Redis(redisURL, { lazyConnect: true, maxRetriesPerRequest: 1 });
  }

  async allow(key: string): Promise<boolean> {
    if (this.redis.status === "wait") {
      await this.redis.connect();
    }
    const now = Date.now();
    const bucket = `whatsapp:ratelimit:${key}`;
    const member = `${now}:${randomUUID()}`;
    const windowStart = now - 1000;
    const pipeline = this.redis.pipeline();
    pipeline.zremrangebyscore(bucket, 0, windowStart);
    pipeline.zadd(bucket, now, member);
    pipeline.pexpire(bucket, 1000);
    pipeline.zcard(bucket);
    const results = await pipeline.exec();
    const count = results?.[3]?.[1];
    return typeof count === "number" && count <= this.limitPerSecond;
  }

  async close(): Promise<void> {
    this.redis.disconnect();
  }
}

export class MemoryRateLimiter implements RateLimiter {
  private readonly hits = new Map<string, number[]>();

  constructor(private readonly limitPerSecond: number) {}

  async allow(key: string): Promise<boolean> {
    const now = Date.now();
    const recent = (this.hits.get(key) ?? []).filter((seenAt) => seenAt >= now - 1000);
    recent.push(now);
    this.hits.set(key, recent);
    return recent.length <= this.limitPerSecond;
  }

  async close(): Promise<void> {}
}

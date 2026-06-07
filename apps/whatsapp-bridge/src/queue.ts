export class PerChatQueue {
  private readonly tails = new Map<string, Promise<void>>();
  private active = 0;
  private readonly waiters: Array<() => void> = [];

  constructor(private readonly concurrency: number) {}

  async run<T>(chatID: string, task: () => Promise<T>): Promise<T> {
    const previous = this.tails.get(chatID) ?? Promise.resolve();
    let releaseChat!: () => void;
    const current = new Promise<void>((resolve) => {
      releaseChat = resolve;
    });
    this.tails.set(chatID, previous.then(() => current));
    await previous;
    await this.acquire();
    try {
      return await task();
    } finally {
      this.release();
      releaseChat();
      if (this.tails.get(chatID) === current) {
        this.tails.delete(chatID);
      }
    }
  }

  private async acquire(): Promise<void> {
    if (this.active < this.concurrency) {
      this.active += 1;
      return;
    }
    await new Promise<void>((resolve) => this.waiters.push(resolve));
    this.active += 1;
  }

  private release(): void {
    this.active -= 1;
    this.waiters.shift()?.();
  }
}

import dgram from 'node:dgram';

export interface RoundScores {
  room: string;
  round: number;
  scores: Record<string, number>;
}

/** Fire-and-forget score updates to the scorekeeper, one datagram per round. */
export class ScoreReporter {
  private readonly socket = dgram.createSocket('udp4');

  constructor(
    private readonly host: string,
    private readonly port: number,
  ) {
    this.socket.unref();
  }

  report(update: RoundScores): void {
    const datagram = Buffer.from(JSON.stringify(update));
    this.socket.send(datagram, this.port, this.host, (err) => {
      if (err) console.error(`score report failed: ${err.message}`);
    });
  }

  close(): void {
    this.socket.close();
  }
}

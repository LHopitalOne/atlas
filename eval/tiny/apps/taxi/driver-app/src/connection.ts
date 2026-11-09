import { EventEmitter } from "node:events";
import WebSocket from "ws";
import type { ServerMessage } from "./types.js";

export class DriverConnection extends EventEmitter {
  private socket?: WebSocket;

  constructor(private readonly url: string) {
    super();
  }

  open(): Promise<void> {
    return new Promise((resolve, reject) => {
      const socket = new WebSocket(this.url);
      this.socket = socket;
      socket.once("open", () => resolve());
      socket.once("error", reject);
      socket.on("message", (data) => this.handle(data.toString()));
      socket.on("close", () => this.emit("close"));
    });
  }

  private handle(raw: string): void {
    const msg = JSON.parse(raw) as ServerMessage;
    console.log("RECV websocket SEND /drivers/stream");
    this.emit(msg.type, msg);
  }

  setStatus(status: "available" | "busy" | "offline"): void {
    this.socket?.send(JSON.stringify({ type: "status", status }));
  }

  close(): void {
    this.socket?.close();
  }
}

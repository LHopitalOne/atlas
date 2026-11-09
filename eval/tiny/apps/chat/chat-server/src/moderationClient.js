const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const config = require('./config');

class ModerationClient {
  constructor(address = config.moderationAddr) {
    const definition = protoLoader.loadSync(config.protoPath, {
      keepCase: false,
      longs: String,
      defaults: true,
    });
    const { moderation } = grpc.loadPackageDefinition(definition);
    this.stub = new moderation.Moderation(address, grpc.credentials.createInsecure());
  }

  deadline() {
    return new Date(Date.now() + config.moderationTimeoutMs);
  }

  checkMessage({ roomId, author, text }) {
    return new Promise((resolve, reject) => {
      this.stub.CheckMessage({ roomId, author, text }, { deadline: this.deadline() }, (err, res) =>
        err ? reject(err) : resolve(res),
      );
    });
  }

  reportUser({ reporter, reported, roomId, reason }) {
    return new Promise((resolve, reject) => {
      this.stub.ReportUser({ reporter, reported, roomId, reason }, { deadline: this.deadline() }, (err, res) =>
        err ? reject(err) : resolve(res),
      );
    });
  }

  close() {
    this.stub.close();
  }
}

module.exports = new ModerationClient();

FROM rust:1.87 AS build
WORKDIR /src
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
COPY --from=build /src/target/release/agent /usr/local/bin/agent
CMD ["agent"]

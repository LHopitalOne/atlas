// protoc is not required: protox parses the .proto in pure Rust and hands the
// file descriptor set to tonic-prost-build.
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let fds = protox::compile(["proto/indexer.proto"], ["proto"])?;
    tonic_prost_build::configure()
        .build_client(false)
        .compile_fds(fds)?;
    println!("cargo:rerun-if-changed=proto/indexer.proto");
    Ok(())
}

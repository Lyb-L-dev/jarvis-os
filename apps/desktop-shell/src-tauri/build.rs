fn stage_update_public_key() {
    let manifest_dir = std::path::PathBuf::from(
        std::env::var_os("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR is set"),
    );
    let source = std::env::var_os("JARVIS_UPDATE_PUBLIC_KEY_FILE")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| manifest_dir.join("update-public-key.json"));
    let contents = std::fs::read_to_string(&source)
        .unwrap_or_else(|error| panic!("failed to read update public key {}: {error}", source.display()));
    for required in ["key_id", "rsa-pkcs1-sha256", "modulus_base64", "exponent_base64"] {
        assert!(
            contents.to_ascii_lowercase().contains(required),
            "update public key is missing {required}"
        );
    }
    let output = std::path::PathBuf::from(std::env::var_os("OUT_DIR").expect("OUT_DIR is set"))
        .join("jarvis-update-public-key.json");
    std::fs::write(&output, contents)
        .unwrap_or_else(|error| panic!("failed to stage update public key: {error}"));
    println!("cargo:rerun-if-env-changed=JARVIS_UPDATE_PUBLIC_KEY_FILE");
    println!("cargo:rerun-if-changed={}", source.display());
    println!("cargo:rustc-env=JARVIS_UPDATE_PUBLIC_KEY_PATH={}", output.display());
}

fn main() {
    stage_update_public_key();
    if std::env::var_os("JARVIS_SKIP_TAURI_BUILD").as_deref() == Some(std::ffi::OsStr::new("1")) {
        println!("cargo:rustc-env=TAURI_ENV_TARGET_TRIPLE={}", std::env::var("TARGET").unwrap());
        println!("cargo:rerun-if-env-changed=JARVIS_SKIP_TAURI_BUILD");
        return;
    }
    tauri_build::try_build(
        tauri_build::Attributes::new().capabilities_path_pattern("capabilities/*.json"),
    )
    .expect("failed to build Jarvis OS desktop shell");
}

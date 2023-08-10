variable "TAG" { default = "" }
variable "BUILD_DATE" { default = "" }
variable "REGISTRY" { default = "rakwireless/lorawan-bacnet-bridge" }

group "default" {
    targets = ["aarch64", "amd64"]
}

target "aarch64" {
    tags = ["${REGISTRY}:aarch64-latest"]
    args = {
        "ARCH" = "aarch64",
        "TAG" = "${TAG}",
        "BUILD_DATE" = "${BUILD_DATE}"
    }
    platforms = ["linux/arm64"]
}

target "amd64" {
    tags = ["${REGISTRY}:amd64-latest"]
    args = {
        "ARCH" = "amd64",
        "TAG" = "${TAG}",
        "BUILD_DATE" = "${BUILD_DATE}"
    }
    platforms = ["linux/amd64"]
}
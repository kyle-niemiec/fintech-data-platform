ui = true
disable_mlock = true
api_addr = "http://vault:8200"
cluster_addr = "http://vault:8201"

storage "file" {
  path = "/vault/data/storage"
}

listener "tcp" {
  address = "0.0.0.0:8200"
  tls_disable = 1
}

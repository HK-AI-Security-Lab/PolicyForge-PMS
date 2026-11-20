# Illustrative custom language; no parser or execution engine is bundled.
policy "research-access" version 1 {
  subject agent == "research-agent"
  default deny

  allow action == "read" and resource.classification == "public"
  deny resource.type == "credential"
  require_approval action == "send" and destination.type == "external"
}

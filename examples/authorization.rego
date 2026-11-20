package policyforge.example

import rego.v1

default allow := false

allow if {
    input.agent == "research-agent"
    input.action == "read"
}

// Cedar policies for the OpenClaw task-authorization four-gate model.
// See docs/DESIGN.md §10. Entities are auto-generated from policy/*.json by
// pdp/taskauth/cedar_backend.py:build_entities; these rules are the gate logic.
//
// The Python orchestration enumerates candidate skills/tools and asks Cedar one
// permit question per gate, then converges to the minimal granted skills + tools.

// Gate 1 — user/channel -> agent:
//   the user holds a grant for {this channel, this agent}.
permit (
  principal,
  action == Action::"runAgent",
  resource
)
when {
  principal.grants.contains({channel: context.channel, agent: resource})
};

// Gates 2 + 3 — agent -> skill (allowlist) AND intent -> skill:
//   the skill is in the agent's allowlist (gate 2) AND at least one of the
//   task's intents maps to this skill (gate 3, via the skill's `intents` attr).
permit (
  principal,
  action == Action::"useSkill",
  resource
)
when {
  resource in principal.allowedSkills &&
  context.intents.containsAny(resource.intents)
};

// Gate 4 — skill -> tool:
//   the tool is one the skill declares (auto-derived from SKILL.md).
permit (
  principal,
  action == Action::"callTool",
  resource
)
when {
  resource in principal.tools
};

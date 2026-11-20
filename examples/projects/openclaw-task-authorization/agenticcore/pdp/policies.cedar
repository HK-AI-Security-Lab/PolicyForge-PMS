// AgenticCore execution-time authorization for one concrete tool call.
// The PDP receives the selected intent, skill and actual tool from the PEP.
// Cedar defaults to deny when either relationship does not match.
permit (
  principal,
  action == Action::"executeTool",
  resource
)
when {
  context.intent in context.skill.intents &&
  resource in context.skill.tools
};

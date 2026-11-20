// 自动生成的显式 Cedar 策略；运行时 entities=[]，无需关系 JSON。
// scenario: openclaw
// template-sha256: 7282bd87bc4d95d26d79dec06dda0a2a1e45cb381541082fcd1392e1abc83b70
// __catalog 声明恒为 false，仅供分类与候选枚举，不授予任何权限。

@kind("intent_catalog")
@intent("answer_faq")
@keywords_000000("faq")
@keywords_000001("how do i")
@keywords_000002("how to")
@keywords_000003("question")
@keywords_000004("what is")
permit (principal, action == Action::"__catalog", resource)
when { false };

@kind("intent_catalog")
@intent("open_ticket")
@keywords_000000("broken")
@keywords_000001("bug")
@keywords_000002("not working")
@keywords_000003("report")
@keywords_000004("ticket")
@regex_000000("issue\\s+#?\\d+")
permit (principal, action == Action::"__catalog", resource)
when { false };

@kind("intent_catalog")
@intent("research_topic")
@keywords_000000("compare")
@keywords_000001("find out")
@keywords_000002("investigate")
@keywords_000003("look up")
@keywords_000004("research")
permit (principal, action == Action::"__catalog", resource)
when { false };

@kind("run_agent")
@user("u_alice")
@channel("telegram")
@agent("support")
permit (principal == User::"u_alice", action == Action::"runAgent", resource == Agent::"support")
when { context.channel == "telegram" };

@kind("run_agent")
@user("u_bob")
@channel("slack")
@agent("support")
permit (principal == User::"u_bob", action == Action::"runAgent", resource == Agent::"support")
when { context.channel == "slack" };

@kind("run_agent")
@user("u_carol")
@channel("telegram")
@agent("researcher")
permit (principal == User::"u_carol", action == Action::"runAgent", resource == Agent::"researcher")
when { context.channel == "telegram" };

@kind("run_agent")
@user("u_local")
@channel("cli")
@agent("support")
permit (principal == User::"u_local", action == Action::"runAgent", resource == Agent::"support")
when { context.channel == "cli" };

@kind("agent_catalog")
@agent("researcher")
@skill_000000("faq")
@skill_000001("web-research")
permit (principal, action == Action::"__catalog", resource)
when { false };

@kind("use_skill")
@agent("researcher")
@intent("answer_faq")
@skill("faq")
permit (principal == Agent::"researcher", action == Action::"useSkill", resource == Skill::"faq")
when { context.intents.contains(Intent::"answer_faq") };

@kind("use_skill")
@agent("researcher")
@intent("research_topic")
@skill("web-research")
permit (principal == Agent::"researcher", action == Action::"useSkill", resource == Skill::"web-research")
when { context.intents.contains(Intent::"research_topic") };

@kind("agent_catalog")
@agent("support")
@skill_000000("faq")
@skill_000001("ticketing")
@skill_000002("web-research")
permit (principal, action == Action::"__catalog", resource)
when { false };

@kind("use_skill")
@agent("support")
@intent("answer_faq")
@skill("faq")
permit (principal == Agent::"support", action == Action::"useSkill", resource == Skill::"faq")
when { context.intents.contains(Intent::"answer_faq") };

@kind("use_skill")
@agent("support")
@intent("open_ticket")
@skill("ticketing")
permit (principal == Agent::"support", action == Action::"useSkill", resource == Skill::"ticketing")
when { context.intents.contains(Intent::"open_ticket") };

@kind("use_skill")
@agent("support")
@intent("research_topic")
@skill("web-research")
permit (principal == Agent::"support", action == Action::"useSkill", resource == Skill::"web-research")
when { context.intents.contains(Intent::"research_topic") };

@kind("call_tool")
@skill("faq")
@tool("read")
permit (principal == Skill::"faq", action == Action::"callTool", resource == Tool::"read")
when { true };

@kind("call_tool")
@skill("faq")
@tool("web_search")
permit (principal == Skill::"faq", action == Action::"callTool", resource == Tool::"web_search")
when { true };

@kind("call_tool")
@skill("ticketing")
@tool("exec")
permit (principal == Skill::"ticketing", action == Action::"callTool", resource == Tool::"exec")
when { true };

@kind("call_tool")
@skill("ticketing")
@tool("read")
permit (principal == Skill::"ticketing", action == Action::"callTool", resource == Tool::"read")
when { true };

@kind("call_tool")
@skill("ticketing")
@tool("write")
permit (principal == Skill::"ticketing", action == Action::"callTool", resource == Tool::"write")
when { true };

@kind("call_tool")
@skill("web-research")
@tool("read")
permit (principal == Skill::"web-research", action == Action::"callTool", resource == Tool::"read")
when { true };

@kind("call_tool")
@skill("web-research")
@tool("web_fetch")
permit (principal == Skill::"web-research", action == Action::"callTool", resource == Tool::"web_fetch")
when { true };

@kind("call_tool")
@skill("web-research")
@tool("web_search")
permit (principal == Skill::"web-research", action == Action::"callTool", resource == Tool::"web_search")
when { true };

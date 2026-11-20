// 自动生成的显式 Cedar 策略；运行时 entities=[]，无需关系 JSON。
// scenario: agenticcore
// template-sha256: a2904614782996d780f432cd2c530fd9a6e918a60d8f1f8bbdaf28271adbc05e
// __catalog 声明恒为 false，仅供分类与候选枚举，不授予任何权限。

@kind("intent_catalog")
@intent("create_ticket")
@description("为故障创建支持工单 / create a support ticket")
@keywords_000000("broken")
@keywords_000001("ticket")
@keywords_000002("坏了")
@keywords_000003("工单")
@keywords_000004("故障")
permit (principal, action == Action::"__catalog", resource)
when { false };

@kind("intent_catalog")
@intent("weather_forecast")
@description("查询城市天气预报 / query a city weather forecast")
@keywords_000000("forecast")
@keywords_000001("weather")
@keywords_000002("天气")
@keywords_000003("预报")
permit (principal, action == Action::"__catalog", resource)
when { false };

@kind("skill_catalog")
@skill("tickets")
@tool_000000("create_ticket_tool.sh")
permit (principal, action == Action::"__catalog", resource)
when { false };

@kind("skill_catalog")
@skill("weather")
@tool_000000("get_forecast_by_city_tool.sh")
permit (principal, action == Action::"__catalog", resource)
when { false };

@kind("execute_tool")
@intent("create_ticket")
@skill("tickets")
@tool("create_ticket_tool.sh")
permit (principal, action == Action::"executeTool", resource == Tool::"tickets/create_ticket_tool.sh")
when { context.intent == Intent::"create_ticket" && context.skill == Skill::"tickets" };

@kind("execute_tool")
@intent("weather_forecast")
@skill("weather")
@tool("get_forecast_by_city_tool.sh")
permit (principal, action == Action::"executeTool", resource == Tool::"weather/get_forecast_by_city_tool.sh")
when { context.intent == Intent::"weather_forecast" && context.skill == Skill::"weather" };
